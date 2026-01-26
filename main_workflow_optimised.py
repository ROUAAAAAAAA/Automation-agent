

import json
import time
import traceback
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Dict, List
from uuid import UUID

# Database imports
from database.load_to_db import load_products_from_json
from database.models import SessionLocal, Product, InsurancePackage, Partner
from database.crud import (
    get_partner_by_name,
    get_unprocessed_products,
    mark_product_processing,
    mark_product_completed,
    mark_product_failed,
    create_insurance_package,
    get_processing_stats
)

# AI tool imports
from ai_agent.tools.classify_product import classify_product
from ai_agent.tools.calculate_pricing import calculate_pricing


# ============================================================
# CORE PROCESSING FUNCTION
# ============================================================

def process_single_product_db(product_id: UUID) -> Dict:
    """
    Process ONE product through the AI workflow.
    
    UAE Products: Show 3 premiums (Standard 12m, Standard 24m, ASSURMAX)
    Tunisia Products: Show 2 premiums (Standard 12m, Standard 24m)
    
    Args:
        product_id: Product UUID from database
    
    Returns:
        Dictionary with processing result
    """
    
    db = SessionLocal()
    
    try:
        # ==========================================
        # STEP 1: GET PRODUCT FROM DATABASE
        # ==========================================
        product = db.query(Product).filter(Product.product_id == product_id).first()
        
        if not product:
            return {"error": "Product not found", "product_id": str(product_id)}
        
        product_name = product.product_name
        print(f"   🔄 Processing: {product_name[:50]}...")
        
        # ==========================================
        # STEP 2: MARK AS PROCESSING
        # ==========================================
        product.processing_status = 'processing'
        product.processing_started_at = datetime.utcnow()
        db.commit()
        
        # ==========================================
        # STEP 3: AI CLASSIFICATION (1 call)
        # ==========================================
        classification_result = classify_product.invoke({
            "product_name": product.product_name or "",
            "category": product.category or "",
            "brand": product.brand or "",
            "price": float(product.price) if product.price else 0,
            "currency": product.currency or "AED",
            "description": product.description or ""
        })
        
        classification = classification_result.get("classification", {})
        
        # ==========================================
        # STEP 4: CHECK ELIGIBILITY
        # ==========================================
        if not classification.get("eligible"):
            response = {
                "product": {
                    "name": product.product_name,
                    "brand": product.brand or "N/A",
                    "category": classification_result.get("category", "N/A"),
                    "price": float(product.price),
                    "currency": product.currency
                },
                "eligible": False,
                "reason": classification.get("reason", "Product not eligible for insurance")
            }
            
            create_insurance_package(
                db=db,
                partner_id=str(product.partner_id),
                product_id=str(product.product_id),
                package_data=response,
                is_eligible=False
            )
            
            mark_product_completed(db, str(product.product_id))
            
            print(f"   ❌ Not eligible: {product_name[:40]}")
            print(f"      Reason: {response['reason'][:60]}\n")
            return response
        
        # ==========================================
        # STEP 5: Build base response
        # ==========================================
        risk_profile = classification.get("risk_profile")
        product_value = float(product.price)
        market = classification_result.get("market", "UAE")
        currency = product.currency
        
        response = {
            "product": {
                "name": product.product_name,
                "brand": product.brand or "N/A",
                "category": classification_result.get("category", "N/A"),
                "price": product_value,
                "currency": currency
            },
            "eligible": True,
            "risk_profile": risk_profile,
            "market": market
        }
        
        # ==========================================
        # STEP 6: Calculate STANDARD pricing (ALWAYS)
        # ==========================================
        try:
            standard_pricing = calculate_pricing.invoke({
                "risk_profile": risk_profile,
                "product_value": product_value,
                "market": market,
                "plan": "STANDARD"
            })
            
            response["standard_premium_12_months"] = {
                "amount": standard_pricing["12_months"]["annual_premium"],
                "currency": standard_pricing["12_months"]["currency"]
            }
            
            response["standard_premium_24_months"] = {
                "amount": standard_pricing["24_months"]["total_premium"],
                "currency": standard_pricing["24_months"]["currency"]
            }
            
        except Exception as e:
            print(f"   ⚠️ Standard pricing error: {e}")
            response["standard_premium_12_months"] = None
            response["standard_premium_24_months"] = None
        
        # ==========================================
        # STEP 7: Calculate ASSURMAX (UAE ONLY)
        # ==========================================
        if market.upper() == "UAE":
            try:
                assurmax_pricing = calculate_pricing.invoke({
                    "product_value": product_value,
                    "market": market,
                    "plan": "ASSURMAX"
                })
                
                if not assurmax_pricing.get("error"):
                    response["assurmax_premium"] = {
                        "amount": assurmax_pricing["12_months"]["annual_premium"],
                        "currency": assurmax_pricing["12_months"]["currency"],
                        "pack_cap": assurmax_pricing["assurmax_pack_cap"]["pack_cap"],
                        "max_products": assurmax_pricing["assurmax_pack_cap"]["max_products_covered"]
                    }
                else:
                    response["assurmax_premium"] = {
                        "eligible": False,
                        "reason": assurmax_pricing["error"]
                    }
                    
            except Exception as e:
                print(f"   ⚠️ ASSURMAX pricing error: {e}")
                response["assurmax_premium"] = None
        
        # ==========================================
        # STEP 8: Save to database
        # ==========================================
        create_insurance_package(
            db=db,
            partner_id=str(product.partner_id),
            product_id=str(product.product_id),
            package_data=response,
            is_eligible=True
        )
        
        mark_product_completed(db, str(product.product_id))
        
        # ==========================================
        # STEP 9: PRINT CLEAN SUMMARY
        # ==========================================
        if response.get("standard_premium_12_months"):
            std_12 = response["standard_premium_12_months"]["amount"]
            std_24 = response["standard_premium_24_months"]["amount"]
            currency = response["standard_premium_12_months"]["currency"]
            
            print(f"   ✅ {market.upper()}: {product_name[:40]}")
            print(f"      Standard 12m: {std_12:.2f} {currency}")
            print(f"      Standard 24m: {std_24:.2f} {currency}")
            
            # Show ASSURMAX details for UAE
            if market.upper() == "UAE" and response.get("assurmax_premium"):
                assurmax = response["assurmax_premium"]
                
                if assurmax.get("amount"):
                    print(f"      ASSURMAX Premium: {assurmax['amount']:.2f} {assurmax['currency']}")
                    print(f"      ASSURMAX Pack Cap: {assurmax['pack_cap']} {assurmax['currency']} (covers up to {assurmax['max_products']} products)")
                else:
                    print(f"      ASSURMAX: Not eligible - {assurmax.get('reason', 'Unknown reason')}")
            
            print()  # Empty line for readability
        else:
            print(f"   ✅ Eligible: {product_name[:40]}\n")
        
        return response
        
    except Exception as e:
        print(f"   ❌ Error processing: {str(e)}")
        traceback.print_exc()
        
        if product:
            mark_product_failed(db, str(product.product_id), str(e))
        
        return {
            "product": {
                "name": product.product_name if product else "Unknown",
                "error": str(e)
            },
            "eligible": False,
            "reason": f"Processing error: {str(e)}"
        }
        
    finally:
        db.close()


# ============================================================
# MAIN WORKFLOW FUNCTION
# ============================================================

def run_workflow_from_json(json_path: str, max_products: int = 8) -> Optional[Dict]:
    """
    OPTIMIZED WORKFLOW WITH NEW ASSURMAX LOGIC
    
    Args:
        json_path: Path to scraped products JSON file
        max_products: Maximum number of products to process (None = all)
    
    Returns:
        Dictionary with processing summary
    """
    json_path = Path(json_path)
    if not json_path.exists():
        print("❌ JSON file not found.")
        return None

    print(f"\n{'='*70}")
    print(f"⚡ INSURANCE WORKFLOW - NEW ASSURMAX LOGIC")
    print(f"{'='*70}\n")

    # STEP 1: LOAD PRODUCTS TO DATABASE
    print(f"{'='*70}")
    print(f"STEP 1: Loading products from JSON into database...")
    print(f"{'='*70}\n")
    
    try:
        added_count = load_products_from_json(str(json_path))
        print(f"✅ Loaded {added_count} new products to database\n")
    except Exception as e:
        print(f"❌ Failed to load products: {e}")
        traceback.print_exc()
        return None

    # STEP 2: FIND PARTNER
    db = SessionLocal()
    
    try:
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
        
        if isinstance(data, dict):
            domain = data.get("metadata", {}).get("domain", "unknown")
        else:
            domain = json_path.stem.split("_")[0]
        
        partner_name = domain.replace("www.", "").replace(".com", "").title()
        if "noon" in partner_name.lower():
            partner_name = "Noon"
        
        partner = get_partner_by_name(db, partner_name)
        
        if not partner:
            print(f"❌ No partner found: {partner_name}")
            return None
        
        print(f"{'='*70}")
        print(f"STEP 2: Found partner: {partner.company_name}")
        print(f"{'='*70}\n")
        
        # STEP 3: GET UNPROCESSED PRODUCTS
        print(f"{'='*70}")
        print(f"STEP 3: Querying unprocessed products...")
        print(f"{'='*70}\n")
        
        products = get_unprocessed_products(db, str(partner.partner_id), limit=max_products)
        
        if not products:
            print(f"❌ No unprocessed products found for {partner.company_name}")
            
            stats = get_processing_stats(db, str(partner.partner_id))
            print(f"\n📊 Current Statistics:")
            print(f"   Total products: {stats['total_products']}")
            print(f"   Processed: {stats['processed']}")
            print(f"   Pending: {stats['pending']}")
            print(f"   Eligible: {stats['eligible']} ({stats['eligible_rate']}%)")
            
            return None
        
        product_ids = [product.product_id for product in products]
        product_count = len(products)
        
        print(f"✅ Found {product_count} products to process")
        print(f"   Partner: {partner.company_name}")
        print(f"   Currency: {products[0].currency}")
        print(f"   Price range: {min(p.price for p in products):.0f} - {max(p.price for p in products):.0f}\n")
        
        # STEP 4: PROCESS IN PARALLEL
        if product_count <= 10:
            WORKER_COUNT = 4
        elif product_count <= 50:
            WORKER_COUNT = 8
        elif product_count <= 150:
            WORKER_COUNT = 16
        else:
            WORKER_COUNT = 24
        
        print(f"{'='*70}")
        print(f"STEP 4: Processing {product_count} products")
        print(f"        Parallel workers: {WORKER_COUNT}")
        print(f"        NEW: Simplified ASSURMAX pricing (550 AED flat)")
        print(f"{'='*70}\n")
        
        start_time = time.time()
        
        # Process in parallel
        with ThreadPoolExecutor(max_workers=WORKER_COUNT) as executor:
            future_to_id = {
                executor.submit(process_single_product_db, pid): pid
                for pid in product_ids
            }
            
            completed = 0
            for future in as_completed(future_to_id):
                completed += 1
                try:
                    result = future.result()
                    
                    progress = (completed / product_count) * 100
                    status = "✅" if result.get("eligible") else "❌"
                    print(f"{status} [{completed}/{product_count}] ({progress:.0f}%)")
                    
                except Exception as e:
                    print(f"❌ [{completed}/{product_count}] Worker failed: {e}")
        
        elapsed = time.time() - start_time
        
        # STEP 5: GET FINAL STATISTICS
        print(f"\n{'='*70}")
        print(f"STEP 5: Retrieving results from database...")
        print(f"{'='*70}\n")
        
        stats = get_processing_stats(db, str(partner.partner_id))
        
        print(f"{'='*70}")
        print(f"⏱️  PROCESSING COMPLETE")
        print(f"{'='*70}")
        print(f"✅ Processed: {product_count} products")
        print(f"⚡ Time: {elapsed:.1f} seconds ({elapsed/product_count:.1f} sec/product)")
        print(f"✅ Eligible: {stats['eligible']}")
        print(f"❌ Not Eligible: {product_count - stats['eligible']}")
        print(f"📊 Overall Stats:")
        print(f"   Total products in DB: {stats['total_products']}")
        print(f"   Total processed: {stats['processed']}")
        print(f"   Total eligible: {stats['eligible']} ({stats['eligible_rate']}%)")
        print(f"{'='*70}\n")
        
        return {
            "success": True,
            "partner_id": str(partner.partner_id),
            "partner_name": partner.company_name,
            "total_processed": product_count,
            "eligible_count": stats['eligible'],
            "processing_time": round(elapsed, 2),
            "stats": stats,
            "message": f"✅ Successfully processed {product_count} products from {partner.company_name}"
        }
        
    finally:
        db.close()


# ============================================================
# CLI INTERFACE
# ============================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        json_file = sys.argv[1]
        max_prod = int(sys.argv[2]) if len(sys.argv) > 2 else None
    else:
        json_file = "C:\\Users\\rouam\\OneDrive\\Bureau\\Automation\\scraped_products\\noon.com_products_20260112_160523.json"
        max_prod = 8
    
    print("\n" + "="*70)
    print("INSURANCE WORKFLOW - NEW ASSURMAX LOGIC")
    print("="*70)
    print(f"Input file: {json_file}")
    if max_prod:
        print(f"Max products: {max_prod}")
    print()
    
    result = run_workflow_from_json(json_file, max_products=max_prod)
    
    if result and result.get("success"):
        print("\n" + "="*70)
        print("✅ WORKFLOW COMPLETED SUCCESSFULLY")
        print("="*70)
        print(f"\nProcessed: {result['total_processed']} products")
        print(f"Eligible: {result['eligible_count']}")
        print(f"Time: {result['processing_time']} seconds")
        print(f"Average: {result['processing_time'] / result['total_processed']:.1f} sec/product")
    else:
        print("\n" + "="*70)
        print("❌ WORKFLOW FAILED")
        print("="*70)
