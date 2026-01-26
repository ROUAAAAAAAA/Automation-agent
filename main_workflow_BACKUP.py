
from database.load_to_db import load_products_from_json
from database.models import SessionLocal, Product, InsurancePackage, Partner
from ai_agent.agent import generate_packages
from datetime import datetime
from pathlib import Path
import json
import traceback
from sqlalchemy import func 

def run_workflow_from_json(json_path: str, max_products: int = 8) -> str:
    """
    Load products from JSON, process with AI agent, return results file.
    """
    json_path = Path(json_path)
    if not json_path.exists():
        print("❌ JSON file not found.")
        return None

    # Step 1: Load products into database
    print("\\n" + "="*70)
    print("STEP 1: Loading products from JSON into database...")
    print("="*70)
    
    try:
        added_count = load_products_from_json(str(json_path))
        if added_count == 0:
            print("⚠️  No products were added. Check your JSON data quality.")
            # Continue anyway to process existing products
    except Exception as e:
        print(f"❌ Failed to load products: {e}")
        traceback.print_exc()
        return None

    db = SessionLocal()
    results = {
        "metadata": {
            "processed_at": datetime.utcnow().isoformat(),
            "source_file": json_path.name
        },
        "packages": []
    }

    try:
        # Step 2: Identify the partner from the JSON file
        print("\\n" + "="*70)
        print("STEP 2: Identifying partner from JSON...")
        print("="*70)
        
        # Extract domain from JSON metadata to find the correct partner
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
        
        if isinstance(data, dict):
            domain = data.get("metadata", {}).get("domain", "unknown")
        else:
            domain = json_path.stem.split("_")[0]
        
        # Find partner by domain/name
        partner_name = domain.replace("www.", "").replace(".com", "").title()
        if "noon" in partner_name.lower():
            partner_name = "Noon"
        
        partner = db.query(Partner).filter_by(company_name=partner_name).first()
        
        if not partner:
            print(f"❌ No partner found with name: {partner_name}")
            return None
        
        print(f"✅ Found partner: {partner.company_name} (ID: {partner.partner_id})")

        # Step 3: Query products for THIS PARTNER ONLY
        print("\\n" + "="*70)
        print(f"STEP 3: Querying products for partner: {partner.company_name}")
        print("="*70)
        
        products = (
            db.query(Product)
            .filter(
                Product.partner_id == partner.partner_id,
                Product.price > 0,
                Product.currency.isnot(None),
                Product.product_url.isnot(None)
            )
            .order_by(func.random())  
            .limit(max_products)
            .all()
        )

        if not products:
            print(f"❌ No valid products found for partner: {partner.company_name}")
            print("   Check if products were loaded successfully in Step 1.")
            return None
        
        print(f"✅ Found {len(products)} valid products for {partner.company_name}")
        print(f"   Currency: {products[0].currency}")
        print(f"   Price range: {min(p.price for p in products):.0f} - {max(p.price for p in products):.0f}")

        # Step 4: Process with AI agent
        print("\\n" + "="*70)
        print(f"STEP 4: Processing {len(products)} products with AI agent...")
        print("="*70)

        for idx, product in enumerate(products, 1):
            product_dict = {
                "product_name": product.product_name,
                "brand": product.brand or "N/A",
                "category": product.category or "N/A",
                "price": float(product.price),
                "currency": product.currency,
                "description": product.description or "N/A",
            }

            try:
                print(f"\\n  [{idx}/{len(products)}] {product.product_name[:50]}...")
                print(f"               Price: {product.price} {product.currency}")
                
                agent_output = generate_packages(product_dict)

                # Handle string response
                if isinstance(agent_output, str):
                    agent_output = json.loads(agent_output)

                eligible = bool(agent_output.get("eligible", False))
                print(f"               Result: {'✅ ELIGIBLE' if eligible else '❌ NOT ELIGIBLE'}")

            except Exception as exc:
                print(f"    ⚠️  AI agent error: {exc}")
                agent_output = {
                    "eligible": False,
                    "error": str(exc),
                    "reason": "AI processing failed"
                }
                eligible = False

            # Save to results
            results["packages"].append({
                "product": product_dict,
                "insurance_package": agent_output,
                "eligible": eligible,
                "processed_at": datetime.utcnow().isoformat()
            })

            # Save to database
            db.add(
                InsurancePackage(
                    partner_id=partner.partner_id,
                    product_id=product.product_id,
                    package_data=agent_output,
                    status="eligible" if eligible else "not_eligible",
                    ai_confidence=0.95 if eligible else 0.0
                )
            )

        db.commit()

        # Step 5: Save results
        print("\\n" + "="*70)
        print("STEP 5: Saving results...")
        print("="*70)
        
        out_file = json_path.with_name(f"{json_path.stem}_insurance_results.json")
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        eligible_count = sum(1 for pkg in results["packages"] if pkg["eligible"])
        print(f"\\n✅ SUCCESS!")
        print(f"   Partner: {partner.company_name}")
        print(f"   Processed: {len(products)} products")
        print(f"   Eligible: {eligible_count}")
        print(f"   Results saved to: {out_file}")
        
        return str(out_file)

    except Exception as e:
        print(f"\\n❌ Workflow error: {e}")
        traceback.print_exc()
        db.rollback()
        return None

    finally:
        db.close()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        json_file = sys.argv[1]
    else:
        json_file = "C:\\Users\\rouam\\OneDrive\\Bureau\\Automation\\scraped_products\\ounass.ae_products_20260115_114956.json"
    
    print("\\n" + "="*70)
    print("INSURANCE PACKAGE WORKFLOW")
    print("="*70)
    print(f"Input file: {json_file}\\n")
    
    result = run_workflow_from_json(json_file)
    
    if result:
        print("\\n" + "="*70)
        print("WORKFLOW COMPLETED SUCCESSFULLY")
        print("="*70)
    else:
        print("\\n" + "="*70)
        print("WORKFLOW FAILED")
        print("="*70)