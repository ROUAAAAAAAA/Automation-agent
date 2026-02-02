import time
import traceback
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Dict, List
from uuid import UUID

# Database imports
from database.models import SessionLocal, Product, Partner
from database.crud import (
    get_partner_by_name,
    get_unprocessed_products,
    mark_product_processing,
    mark_product_completed,
    mark_product_failed,
    create_insurance_package,
    get_processing_stats
)


from ai_agent.tools.classify_product import classify_product
from ai_agent.tools.calculate_pricing import calculate_pricing



def process_single_product_db(product_id: UUID) -> Dict:
    db = SessionLocal()
    try:
        product = db.query(Product).filter(Product.product_id == product_id).first()
        if not product:
            return {"error": "Product not found", "product_id": str(product_id)}

        print(f"    Processing: {product.product_name[:50]}...")

        # Mark as processing
        product.processing_status = 'processing'
        product.processing_started_at = datetime.utcnow()  
        db.commit()

        # AI classification
        classification_result = classify_product.invoke({
            "product_name": product.product_name or "",
            "category": product.category or "",
            "brand": product.brand or "",
            "price": float(product.price) if product.price else 0,
            "currency": product.currency or "AED",
            "description": product.description or ""
        })

        classification = classification_result.get("classification", {})
        market = classification_result.get("market", "UAE")

        # Not eligible
        if not classification.get("eligible"):
            response = {
                "product": {
                    "name": product.product_name,
                    "brand": product.brand or "N/A",
                    "category": classification_result.get("category", "N/A"),
                    "price": float(product.price),
                    "currency": product.currency,
                    "description": product.description or ""
                },
                "eligible": False,
                "reason": classification.get("reason", "Not eligible"),
                "market": market,
                "risk_profile": classification.get("risk_profile"),  
                "coverage_modules": classification.get("coverage_modules", []),  
                "exclusions": classification.get("exclusions", [])  
            }

            create_insurance_package(
                db=db,
                partner_id=str(product.partner_id),
                product_id=str(product.product_id),
                package_data=response,
                is_eligible=False
            )
            mark_product_completed(db, str(product.product_id))
            
            reason_short = response["reason"][:50]
            print(f"  Not eligible: {product.product_name[:40]}")
            print(f"      Reason: {reason_short}")
            
            return response

        # Eligible
        risk_profile = classification.get("risk_profile")
        product_value = float(product.price)

        response = {
            "product": {
                "name": product.product_name,
                "brand": product.brand or "N/A",
                "category": classification_result.get("category", "N/A"),
                "price": product_value,
                "currency": product.currency,
                "description": product.description or ""
            },
            "eligible": True,
            "risk_profile": risk_profile,
            "market": market,
            "coverage_modules": classification.get("coverage_modules", []),  
            "exclusions": classification.get("exclusions", [])  
        }

        # STANDARD pricing 
        try:
            standard_pricing = calculate_pricing.invoke({
                "risk_profile": risk_profile,
                "product_value": product_value,
                "market": market,
                "plan": "STANDARD"
            })

            if standard_pricing.get("error"):
                # If STANDARD fails, mark as not eligible
                response["eligible"] = False
                response["reason"] = standard_pricing["error"]
                
                create_insurance_package(
                    db=db,
                    partner_id=str(product.partner_id),
                    product_id=str(product.product_id),
                    package_data=response,
                    is_eligible=False
                )
                mark_product_completed(db, str(product.product_id))
                
                print(f"    Pricing failed: {product.product_name[:40]}")
                print(f"      Reason: {standard_pricing['error']}")
                
                return response

            response["standard_premium_12_months"] = {
                "amount": standard_pricing["12_months"]["annual_premium"],
                "currency": standard_pricing["12_months"]["currency"]
            }
            response["standard_premium_24_months"] = {
                "amount": standard_pricing["24_months"]["total_premium"],
                "currency": standard_pricing["24_months"]["currency"]
            }

        except Exception as e:
            print(f"    Standard pricing error: {e}")
            response["eligible"] = False
            response["reason"] = f"Pricing calculation failed: {str(e)}"
            
            create_insurance_package(
                db=db,
                partner_id=str(product.partner_id),
                product_id=str(product.product_id),
                package_data=response,
                is_eligible=False
            )
            mark_product_completed(db, str(product.product_id))
            return response

        
        if market.upper() == "UAE" and product_value <= 5000:
            #  Check if product is electronics
            electronics_keywords = [
                "ELECTRONIC", "SMARTPHONE", "LAPTOP", "TABLET", 
                "TV", "TELEVISION", "SMARTWATCH", "GAMING", "CONSOLE",
                "AUDIO", "SPEAKER", "HEADPHONE"
            ]
            
            risk_profile_upper = str(risk_profile).upper() if risk_profile else ""
            category_upper = str(classification_result.get("category", "")).upper()
            
            is_electronics = any(
                keyword in risk_profile_upper or keyword in category_upper
                for keyword in electronics_keywords
            )
            
            if is_electronics:
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
                            "max_products": assurmax_pricing["assurmax_pack_cap"]["max_products_covered"],
                            "eligible": True
                        }
                    else:
                        response["assurmax_premium"] = {
                            "eligible": False,
                            "reason": assurmax_pricing["error"]
                        }
                        
                except Exception as e:
                    print(f"   ⚠️ ASSURMAX pricing error: {e}")
                    response["assurmax_premium"] = {
                        "eligible": False,
                        "reason": f"ASSURMAX calculation failed: {str(e)}"
                    }

        # Save result
        create_insurance_package(
            db=db,
            partner_id=str(product.partner_id),
            product_id=str(product.product_id),
            package_data=response,
            is_eligible=True
        )
        mark_product_completed(db, str(product.product_id))

        # Print success
        std_12 = response.get("standard_premium_12_months", {})
        std_24 = response.get("standard_premium_24_months", {})
        
        print(f"    {market}: {product.product_name[:40]}")
        print(f"      Standard 12m: {std_12.get('amount')} {std_12.get('currency')}")
        print(f"      Standard 24m: {std_24.get('amount')} {std_24.get('currency')}")
        
        assurmax = response.get("assurmax_premium")
        if assurmax and assurmax.get("eligible"):
            print(f"      ASSURMAX Premium: {assurmax.get('amount')} {assurmax.get('currency')}")
            print(f"      ASSURMAX Pack Cap: {assurmax.get('pack_cap')} {assurmax.get('currency')} (covers up to {assurmax.get('max_products')} products)")

        return response

    except Exception as e:
        print(f"   Error processing: {e}")
        traceback.print_exc()
        if product:
            mark_product_failed(db, str(product.product_id), str(e))
        return {
            "product": {"name": product.product_name if product else "Unknown"}, 
            "eligible": False, 
            "reason": str(e)
        }
    finally:
        db.close()


# ============================================================
# WORKFLOW ENTRY POINT
# ============================================================

def run_workflow(max_products: int = 8, domain_hint: Optional[str] = None) -> Optional[Dict]:
    """
    Runs the insurance workflow using products already in the DB.
    
    Args:
        max_products: Maximum number of products to process
        domain_hint: Partner name or domain to find the partner
        
    Returns:
        dict with results or None if failed
    """
    db = SessionLocal()
    try:
        # STEP 1: Find partner
        if not domain_hint:
            print(" Must provide domain_hint (partner name or domain)")
            return None

        partner = get_partner_by_name(db, domain_hint)
        if not partner:
            print(f" Partner not found: {domain_hint}")
            return None

        print("\n" + "="*70)
        print(" INSURANCE WORKFLOW ")
        print("="*70)
        print(f"Partner: {partner.company_name}")
        print(f"Country: {partner.country}")
        print("="*70)

        # STEP 2: Get unprocessed products
        products = get_unprocessed_products(db, str(partner.partner_id), limit=max_products)
        
        if not products:
            print("\n No unprocessed products found")
            stats = get_processing_stats(db, str(partner.partner_id))
            print(f"Stats: {stats['processed']}/{stats['total_products']} already processed")
            return None

        product_ids = [p.product_id for p in products]
        product_count = len(products)

        print(f"\n Found {product_count} products to process")
        print(f"   Partner: {partner.company_name}")
        print(f"   Currency: {products[0].currency if products else 'N/A'}")
        
        if products:
            prices = [float(p.price) for p in products]
            print(f"   Price range: {min(prices):.0f} - {max(prices):.0f}")

        # STEP 3: Process in parallel
        WORKER_COUNT = min(24, max(4, product_count // 5))
        
        print(f"\n Processing {product_count} products")
        print(f"   Parallel workers: {WORKER_COUNT}")
        print(f"   NEW: Simplified ASSURMAX pricing (550 AED flat)")
        print("="*70 + "\n")
        
        start_time = time.time()
        eligible_count = 0
        not_eligible_count = 0

        with ThreadPoolExecutor(max_workers=WORKER_COUNT) as executor:
            future_to_id = {executor.submit(process_single_product_db, pid): pid for pid in product_ids}
            completed = 0
            
            for future in as_completed(future_to_id):
                completed += 1
                try:
                    result = future.result()
                    
                    if result.get("eligible"):
                        eligible_count += 1
                        status = "✅"
                    else:
                        not_eligible_count += 1
                        status = "❌"
                    
                    progress = (completed / product_count) * 100
                    print(f"\n{status} [{completed}/{product_count}] ({progress:.0f}%)\n")
                    
                except Exception as e:
                    not_eligible_count += 1
                    print(f" Worker failed: {e}\n")

        elapsed = time.time() - start_time

        # STEP 4: Final stats
        stats = get_processing_stats(db, str(partner.partner_id))

        print("\n" + "="*70)
        print("  PROCESSING COMPLETE")
        print("="*70)
        print(f" Processed: {product_count} products")
        print(f" Time: {elapsed:.1f} seconds ({elapsed/product_count:.1f} sec/product)")
        print(f" Eligible: {eligible_count}")
        print(f" Not Eligible: {not_eligible_count}")
        
        print(f"\n Overall Stats:")
        print(f"   Total products in DB: {stats['total_products']}")
        print(f"   Total processed: {stats['processed']}")
        print(f"   Total eligible: {stats['eligible']} ({stats['eligible_rate']:.2f}%)")
        print("="*70 + "\n")

        return {
            "success": True,
            "partner_id": str(partner.partner_id),
            "partner_name": partner.company_name,
            "processed": product_count,
            "eligible": eligible_count,
            "not_eligible": not_eligible_count,
            "processing_time": round(elapsed, 2),
            "overall_stats": stats
        }

    finally:
        db.close()


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("\n" + "="*70)
        print("USAGE:")
        print("="*70)
        print("\n  python main_workflow_optimised.py <partner_name> [max_products]")
        print("\nExamples:")
        print("  python main_workflow_optimised.py 'Noon' 10")
        print("  python main_workflow_optimised.py 'Virginmegastore.Ae' 20")
        print("  python main_workflow_optimised.py 'Jumbo' 50")
        print("="*70 + "\n")
        sys.exit(1)
    
    domain_hint = sys.argv[1]
    max_prod = int(sys.argv[2]) if len(sys.argv) > 2 else 8

    result = run_workflow(max_products=max_prod, domain_hint=domain_hint)

    if result and result.get("success"):
        print("\n WORKFLOW COMPLETED SUCCESSFULLY")
        print(f"Processed: {result['processed']} products")
        print(f"Eligible: {result['eligible']}")
        print(f"Time: {result['processing_time']} seconds")
        print(f"Average: {result['processing_time']/result['processed']:.1f} sec/product")
    else:
        print("\nWORKFLOW FAILED")
        sys.exit(1)
