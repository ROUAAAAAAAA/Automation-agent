"""
Streamlit App for Garanty Affinity Insurance
Reads processed products directly from DATABASE (not JSON files)
UPDATED: NEW ASSURMAX Logic (5000 AED cap, 550 AED premium)
"""

import streamlit as st
import sys
from pathlib import Path
from datetime import datetime

st.set_page_config(
    page_title="Garanty Affinity Insurance",
    page_icon="🛡️",
    layout="wide"
)


# ============================================================
# UI HELPER FUNCTIONS
# ============================================================

def render_coverage_modules(modules: list):
    """Display coverage modules"""
    if not modules:
        return
    st.markdown("### ✅ What's Covered")
    for m in modules:
        st.markdown(f"- ✅ {m}")


def render_exclusions(exclusions: list):
    """Display exclusions"""
    if not exclusions:
        return
    with st.expander("❌ What's NOT Covered"):
        for e in exclusions:
            st.markdown(f"- ❌ {e}")


def render_pricing_cards(insurance_data: dict):
    """
    Render pricing cards for UAE products (3 options) or Tunisia (2 options)
    
    NEW LOGIC:
    - UAE: Standard 12m, Standard 24m, ASSURMAX
    - Tunisia: Standard 12m, Standard 24m only
    """
    market = insurance_data.get("market", "UAE")
    
    # Standard premiums (always present)
    std_12 = insurance_data.get("standard_premium_12_months", {})
    std_24 = insurance_data.get("standard_premium_24_months", {})
    
    # ASSURMAX premium (UAE only)
    assurmax = insurance_data.get("assurmax_premium", {})
    
    st.markdown("### 💰 Insurance Pricing Options")
    
    if market == "UAE" and assurmax and assurmax.get("amount"):
        # UAE: Show 3 options
        cols = st.columns(3)
        
        # Card 1: Standard 12-month
        with cols[0]:
            st.markdown("#### 📅 Standard (12 Months)")
            st.markdown(f"### {std_12.get('amount', 'N/A')} {std_12.get('currency', 'AED')}")
            st.caption("Annual coverage with standard benefits")
        
        # Card 2: Standard 24-month
        with cols[1]:
            st.markdown("#### 📅 Standard (24 Months)")
            st.markdown(f"### {std_24.get('amount', 'N/A')} {std_24.get('currency', 'AED')}")
            st.caption("2-year coverage with standard benefits")
        
        # Card 3: ASSURMAX
        with cols[2]:
            st.markdown("#### ⚡ ASSURMAX")
            
            if assurmax.get("eligible") == False:
                # Product exceeds ASSURMAX cap
                st.warning("Not Eligible")
                st.caption(assurmax.get("reason", "Product exceeds ASSURMAX cap"))
            else:
                st.markdown(f"### {assurmax.get('amount', 'N/A')} {assurmax.get('currency', 'AED')}")
                st.markdown(f"📦 **Pack Cap:** {assurmax.get('pack_cap', 'N/A')} {assurmax.get('currency', 'AED')}")
                st.markdown(f"🎯 **Max Products:** {assurmax.get('max_products', 'N/A')}")
    
    else:
        # Tunisia or UAE without ASSURMAX: Show 2 options
        cols = st.columns(2)
        
        # Card 1: Standard 12-month
        with cols[0]:
            st.markdown("#### 📅 Standard (12 Months)")
            st.markdown(f"### {std_12.get('amount', 'N/A')} {std_12.get('currency', 'TND' if market == 'Tunisia' else 'AED')}")
            st.caption("Annual coverage with standard benefits")
        
        # Card 2: Standard 24-month
        with cols[1]:
            st.markdown("#### 📅 Standard (24 Months)")
            st.markdown(f"### {std_24.get('amount', 'N/A')} {std_24.get('currency', 'TND' if market == 'Tunisia' else 'AED')}")
            st.caption("2-year coverage with standard benefits")


# ============================================================
# MAIN APP UI
# ============================================================

st.title("🛡️ Garanty Affinity Insurance")


website_url = st.text_input(
    "E-commerce Website URL:",
    placeholder="https://www.noon.com",
    help="Enter the URL of the e-commerce website to scrape"
)

max_products = st.slider(
    "Maximum products to process:",
    min_value=5,
    max_value=50,
    value=10,
    step=5,
    help="Limit processing for faster results"
)

if st.button("🚀 Generate Insurance Quotes", type="primary"):

    if not website_url:
        st.warning("⚠️ Please enter a URL")
        st.stop()

    if not website_url.startswith(("http://", "https://")):
        st.error("❌ URL must start with http:// or https://")
        st.stop()

    try:
        # ==========================================
        # STEP 1: Import Modules
        # ==========================================
        current_dir = Path(__file__).parent
        
        if str(current_dir) not in sys.path:
            sys.path.insert(0, str(current_dir))
        if str(current_dir.parent) not in sys.path:
            sys.path.insert(0, str(current_dir.parent))
        
        try:
            from scrapper.Scrapper import crawl_entire_site, save_products
        except ImportError as e:
            st.error(f"❌ Cannot import scrapper module: {e}")
            st.stop()
        
        try:
            from main_workflow_optimised import run_workflow_from_json
        except ImportError as e:
            st.error(f"❌ Cannot import workflow module: {e}")
            st.stop()
        
        try:
            from database.models import SessionLocal, Product, InsurancePackage
            from database.crud import get_partner_by_name, get_processing_stats
        except ImportError as e:
            st.error(f"❌ Cannot import database modules: {e}")
            st.stop()
        
        # ==========================================
        # STEP 2: Scrape Website
        # ==========================================
        with st.spinner("🔍 Scraping website..."):
            products = crawl_entire_site(website_url)

        if not products:
            st.error("❌ No valid product pages detected.")
            st.stop()

        st.success(f"✅ Found {len(products)} products")

        # ==========================================
        # STEP 3: Save Products to JSON
        # ==========================================
        filename = save_products(products, website_url)
        if not filename:
            st.error("❌ Failed to save products.")
            st.stop()

        # ==========================================
        # STEP 4: Process with AI Workflow
        # ==========================================
        with st.spinner(f"🤖 Processing {max_products} products with AI..."):
            result = run_workflow_from_json(filename, max_products=max_products)

        if not result or not result.get("success"):
            st.error("❌ Insurance generation failed.")
            st.stop()

        # ==========================================
        # STEP 5: Read Results from DATABASE
        # ==========================================
        st.success("✅ Processing complete! Loading results from database...")
        
        db = SessionLocal()
        
        try:
            # Get partner info
            partner_id = result["partner_id"]
            partner_name = result["partner_name"]
            
            # Query processed products from database
            processed_products = db.query(
                Product.product_name,
                Product.brand,
                Product.price,
                Product.currency,
                Product.category,
                Product.description,
                InsurancePackage.package_data,
                InsurancePackage.status  # ✅ Correct column name
            ).join(
                InsurancePackage,
                Product.product_id == InsurancePackage.product_id
            ).filter(
                Product.partner_id == partner_id,
                Product.processing_status == 'completed'
            ).order_by(
                Product.processing_completed_at.desc()
            ).limit(max_products).all()
            
            # Separate eligible and not eligible
            eligible = []
            not_eligible = []
            
            for row in processed_products:
                pkg_data = row.package_data
                
                # Add product info to package data
                pkg_data["product"] = {
                    "name": row.product_name,
                    "brand": row.brand,
                    "price": float(row.price) if row.price else 0.0,
                    "currency": row.currency,
                    "category": row.category,
                    "description": row.description
                }
                
                # ✅ Check eligibility from package_data (where it's actually stored)
                is_eligible = False
                
                # Method 1: Check classification.eligible (most common)
                if pkg_data.get("classification", {}).get("eligible") is True:
                    is_eligible = True
                
                # Method 2: Check root level eligible
                elif pkg_data.get("eligible") is True:
                    is_eligible = True
                
                # Method 3: Check if premium data exists (means eligible)
                elif (pkg_data.get("standard_premium_12_months") and 
                      pkg_data.get("standard_premium_12_months", {}).get("amount")):
                    is_eligible = True
                
                # Method 4: Check status column (as fallback)
                elif row.status == "eligible":
                    is_eligible = True
                
                if is_eligible:
                    eligible.append(pkg_data)
                else:
                    not_eligible.append(pkg_data)
            
            # ==========================================
            # STEP 6: Display Metrics
            # ==========================================
            st.markdown("---")
            st.subheader(f"📊 Results for {partner_name}")
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Products Processed", len(processed_products))
            c2.metric("✅ Eligible", len(eligible))
            c3.metric("❌ Not Eligible", len(not_eligible))
            c4.metric("⏱️ Time", f"{result.get('processing_time', 'N/A')}s")

            st.markdown("---")

            # ==========================================
            # STEP 7: Display Eligible Products
            # ==========================================
            if eligible:
                st.subheader("✅ Products with Insurance Coverage")

                for idx, insurance in enumerate(eligible, 1):
                    product = insurance.get("product", {})
                    product_name = product.get("name", "Unknown")
                    
                    with st.expander(f"#{idx} - {product_name[:70]}"):
                        st.markdown("### 📦 Product Information")

                        c1, c2 = st.columns(2)
                        with c1:
                            st.write(f"**Name:** {product.get('name', 'N/A')}")
                            st.write(f"**Brand:** {product.get('brand', 'N/A')}")
                            st.write(f"**Category:** {product.get('category', 'N/A')}")
                        with c2:
                            st.write(f"**Price:** {product.get('price', 'N/A')} {product.get('currency', 'AED')}")
                            st.write(f"**Market:** {insurance.get('market', 'N/A')}")
                            st.write(f"**Risk Profile:** {insurance.get('risk_profile', 'N/A')}")

                        # Description
                        description = product.get('description')
                        if description and description not in ['N/A', '', None]:
                            st.markdown("---")
                            st.markdown("#### 📝 Product Description")
                            st.write(description)

                        st.markdown("---")

                        # Pricing Cards (NEW)
                        render_pricing_cards(insurance)
                        
                        st.markdown("---")
                        
                        # Coverage Details
                        render_coverage_modules(insurance.get("coverage_modules", []))
                        render_exclusions(insurance.get("exclusions", []))

            else:
                st.info("ℹ️ No products were eligible for insurance.")

            # ==========================================
            # STEP 8: Display Not Eligible Products
            # ==========================================
            if not_eligible:
                st.markdown("---")
                st.subheader("❌ Products Not Eligible for Insurance")

                for idx, insurance in enumerate(not_eligible, 1):
                    product = insurance.get("product", {})
                    product_name = product.get("name", "Unknown")
                    
                    with st.expander(f"#{idx} - {product_name[:60]}"):
                        st.write(f"**Name:** {product.get('name', 'N/A')}")
                        st.write(f"**Brand:** {product.get('brand', 'N/A')}")
                        st.write(f"**Category:** {product.get('category', 'N/A')}")
                        st.write(f"**Price:** {product.get('price', 'N/A')} {product.get('currency', 'AED')}")
                        
                        description = product.get('description')
                        if description and description not in ['N/A', '', None]:
                            st.markdown("---")
                            st.markdown("#### 📝 Product Description")
                            st.write(description)
                            st.markdown("---")
                        
                        # Get reason from classification or root level
                        reason = (
                            insurance.get("classification", {}).get("reason") or
                            insurance.get("reason") or
                            "Not eligible for insurance"
                        )
                        st.error(f"**Reason:** {reason}")
                        
                        if insurance.get('risk_profile'):
                            st.info(f"**Risk Profile:** {insurance['risk_profile']}")
                        if insurance.get('market'):
                            st.info(f"**Market:** {insurance['market']}")
            
            # ==========================================
            # STEP 9: Download Results
            # ==========================================
            st.markdown("---")
            st.subheader("📥 Download Results")
            
            import json
            
            download_data = {
                "metadata": {
                    "partner": partner_name,
                    "processed_at": datetime.utcnow().isoformat(),
                    "total_products": len(processed_products),
                    "eligible": len(eligible),
                    "not_eligible": len(not_eligible),
                    "assurmax_version": "Simplified (5000 AED cap, 550 AED premium)"
                },
                "eligible_products": eligible,
                "not_eligible_products": not_eligible
            }
            
            st.download_button(
                label="📄 Download JSON Report",
                data=json.dumps(download_data, indent=2, ensure_ascii=False),
                file_name=f"{partner_name}_insurance_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
        
        finally:
            db.close()

    except Exception as e:
        import traceback
        st.error(f"❌ Unexpected error occurred: {str(e)}")
        with st.expander("🔍 Show Error Details"):
            st.code(traceback.format_exc())

