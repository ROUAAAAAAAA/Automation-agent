import streamlit as st
import sys
from pathlib import Path
from datetime import datetime
import time
import json
import subprocess
import threading


st.set_page_config(
    page_title="Garanty Affinity Insurance - Real-time",
    page_icon="🛡️",
    layout="wide"
)


# ============================================================
# IMPORTS
# ============================================================
current_dir = Path(__file__).parent


if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))
if str(current_dir.parent) not in sys.path:
    sys.path.insert(0, str(current_dir.parent))


try:
    from database.models import SessionLocal, Product, InsurancePackage, Partner
    from urllib.parse import urlparse
    import uuid
except ImportError as e:
    st.error(f"Cannot import database modules: {e}")
    st.stop()


# ============================================================
# AVAILABLE CATEGORIES
# ============================================================

AVAILABLE_CATEGORIES = {
    "ELECTRONIC_PRODUCTS": "Electronics",
    "HOME_APPLIANCES": "Home Appliances",
    "BABY_EQUIPMENT_ESSENTIAL": "Baby Products",
    "BAGS_LUGGAGE_ESSENTIAL": "Bags & Luggage",
    "GARDEN_DIY_ESSENTIAL": "Garden & DIY",
    "HEALTH_WELLNESS_ESSENTIAL": "Health & Wellness",
    "LIVING_FURNITURE_ESSENTIAL": "Living & Furniture",
    "MICRO_MOBILITY_ESSENTIAL": "Micromobility",
    "OPTICAL_HEARING_ESSENTIAL": "Optical & Hearing",
    "PERSONAL_CARE_DEVICES": "Personal Care",
    "OPULENCIA_PREMIUM": "Premium & Luxury",
    "SOUND_MUSIC_ESSENTIAL": "Sound & Music",
    "SPORT_OUTDOOR_ESSENTIAL": "Sport & Outdoor",
    "TEXTILE_FOOTWEAR_ZARA": "Textile & Footwear"
}


# ============================================================
# HELPER FUNCTIONS
# ============================================================


def get_partner_from_url(url: str):
    """Extract partner info from URL"""
    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "")
    partner_name = domain.split(".")[0].title()
    
    if "noon" in partner_name.lower():
        partner_name = "Noon"
    elif "virginmegastore" in partner_name.lower():
        partner_name = "Virginmegastore.Ae"
    elif "jumbo" in partner_name.lower():
        partner_name = "Jumbo"
    elif "mytek" in partner_name.lower():
        partner_name = "Mytek"
    elif "emax" in partner_name.lower():
        partner_name = "Emax"
    elif "sharaf" in partner_name.lower() or "uae" in partner_name.lower():
        partner_name = "Uae"
    
    db = SessionLocal()
    try:
        partner = db.query(Partner).filter_by(company_name=partner_name).first()
        if partner:
            return str(partner.partner_id), partner_name
    finally:
        db.close()
    
    return None, partner_name


def render_coverage_modules(modules: list):
    if not modules:
        return
    st.markdown("### What's Covered")
    for m in modules:
        st.markdown(f"- {m}")


def render_exclusions(exclusions: list):
    if not exclusions or not any(exclusions):
        return
    with st.expander("What's NOT Covered"):
        for e in exclusions:
            if e:
                st.markdown(f"- {e}")


def render_pricing_cards(insurance_data: dict):
    market = insurance_data.get("market", "UAE")
    monthly = insurance_data.get("monthly_premium", {})
    std_12 = insurance_data.get("standard_premium_12_months", {})
    std_24 = insurance_data.get("standard_premium_24_months", {})
    assurmax = insurance_data.get("assurmax_premium", {})
    
    st.markdown("### Insurance Pricing Options")
    
    if market == "UAE" and assurmax and assurmax.get("amount"):
        cols = st.columns(4)
        with cols[0]:
            st.markdown("#### Monthly")
            st.markdown(f"### {monthly.get('amount', 'N/A')} {monthly.get('currency', 'AED')}")
            st.caption("Per month")
        with cols[1]:
            st.markdown("#### Standard (12 Months)")
            st.markdown(f"### {std_12.get('amount', 'N/A')} {std_12.get('currency', 'AED')}")
            st.caption("Annual coverage")
        with cols[2]:
            st.markdown("#### Standard (24 Months)")
            st.markdown(f"### {std_24.get('amount', 'N/A')} {std_24.get('currency', 'AED')}")
            st.caption("2-year coverage")
        with cols[3]:
            st.markdown("#### ASSURMAX")
            if assurmax.get("eligible") == False:
                st.warning("Not Eligible")
            else:
                st.markdown(f"### {assurmax.get('amount', 'N/A')} {assurmax.get('currency', 'AED')}")
                st.caption(f"Cap: {assurmax.get('pack_cap', 'N/A')} {assurmax.get('currency', 'AED')}")
    else:
        cols = st.columns(3)
        with cols[0]:
            st.markdown("#### Monthly")
            st.markdown(f"### {monthly.get('amount', 'N/A')} {monthly.get('currency', 'TND' if market == 'Tunisia' else 'AED')}")
            st.caption("Per month")
        with cols[1]:
            st.markdown("#### Standard (12 Months)")
            st.markdown(f"### {std_12.get('amount', 'N/A')} {std_12.get('currency', 'TND' if market == 'Tunisia' else 'AED')}")
        with cols[2]:
            st.markdown("#### Standard (24 Months)")
            st.markdown(f"### {std_24.get('amount', 'N/A')} {std_24.get('currency', 'TND' if market == 'Tunisia' else 'AED')}")


def render_product_card(insurance: dict, idx: int, is_eligible: bool):
    product = insurance.get("product", {})
    product_name = product.get("name", "Unknown")
    icon = "ELIGIBLE" if is_eligible else "NOT ELIGIBLE"
    
    with st.expander(f"{icon} #{idx} - {product_name[:70]}", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            st.write(f"**Name:** {product.get('name', 'N/A')}")
            st.write(f"**Brand:** {product.get('brand', 'N/A')}")
            st.write(f"**Category:** {product.get('category', 'N/A')}")
        with c2:
            st.write(f"**Price:** {product.get('price', 'N/A')} {product.get('currency', 'AED')}")
            st.write(f"**Market:** {insurance.get('market', 'N/A')}")
            if is_eligible:
                st.write(f"**Risk:** {insurance.get('risk_profile', 'N/A')}")
        
        description = product.get('description')
        if description and description not in ['N/A', '', None]:
            st.markdown("---")
            st.markdown("#### Description")
            st.write(description)
        
        if is_eligible:
            st.markdown("---")
            render_pricing_cards(insurance)
            st.markdown("---")
            render_coverage_modules(insurance.get("coverage_modules", []))
            render_exclusions(insurance.get("exclusions", []))
        else:
            st.markdown("---")
            st.error(f"**Reason:** {insurance.get('reason', 'Not eligible')}")


# ============================================================
# MAIN APP
# ============================================================


st.title("Garanty Affinity Insurance ")



# Initialize session state
if 'pipeline_running' not in st.session_state:
    st.session_state.pipeline_running = False
    st.session_state.partner_id = None
    st.session_state.partner_name = None
    st.session_state.start_time = None
    st.session_state.session_start_time = None
    st.session_state.url = None
    st.session_state.expected_partner_name = None
    st.session_state.selected_categories = []  # ← NEW


# ============================================================
# INPUT SECTION
# ============================================================

website_url = st.text_input(
    "E-commerce Website URL:",
    placeholder="https://www.virginmegastore.ae/en",
    value=st.session_state.get('url', ''),
    disabled=st.session_state.pipeline_running
)

# NEW: Category Selection
st.markdown("---")
st.markdown("### Select Product Categories to Insure")
st.caption("Choose which product categories you want to process. Leave empty to process all categories.")

# Create columns for category checkboxes (3 per row)
num_cols = 3
categories_list = list(AVAILABLE_CATEGORIES.items())
rows = [categories_list[i:i+num_cols] for i in range(0, len(categories_list), num_cols)]

selected_categories = []

for row in rows:
    cols = st.columns(num_cols)
    for idx, (cat_key, cat_display) in enumerate(row):
        with cols[idx]:
            if st.checkbox(
                cat_display, 
                key=cat_key,
                disabled=st.session_state.pipeline_running
            ):
                selected_categories.append(cat_key)

# Store in session state
if not st.session_state.pipeline_running:
    st.session_state.selected_categories = selected_categories

# Show selected categories
if selected_categories:
    st.info(f"Selected: {len(selected_categories)} categories")
else:
    st.warning("No categories selected - will process ALL categories")

st.markdown("---")


# ============================================================
# START BUTTON
# ============================================================

if st.button("Start Real-time Processing", type="primary", disabled=st.session_state.pipeline_running):
    
    if not website_url:
        st.warning("Please enter a URL")
        st.stop()
    
    if not website_url.startswith(("http://", "https://")):
        st.error("URL must start with http:// or https://")
        st.stop()
    
    # Get expected partner name
    _, expected_name = get_partner_from_url(website_url)
    
    # Set session start timestamp BEFORE starting pipeline
    st.session_state.session_start_time = datetime.utcnow()
    st.session_state.pipeline_running = True
    st.session_state.url = website_url
    st.session_state.start_time = time.time()
    st.session_state.expected_partner_name = expected_name
    st.session_state.partner_id = None
    st.session_state.partner_name = expected_name
    
    # Start pipeline in background with selected categories
    try:
        # Build command with categories
        cmd = [sys.executable, str(current_dir / "streaming_pipeline.py"), website_url]
        
        # Add categories as comma-separated string
        if st.session_state.selected_categories:
            categories_str = ",".join(st.session_state.selected_categories)
            cmd.append(categories_str)
        
        subprocess.Popen(cmd)
        
        st.success(f"Pipeline started! Check your terminal for live updates.")
        st.info(f"Session started at: {st.session_state.session_start_time.strftime('%H:%M:%S')}")
        
        if st.session_state.selected_categories:
            selected_names = [AVAILABLE_CATEGORIES[cat] for cat in st.session_state.selected_categories]
            st.info(f"Processing categories: {', '.join(selected_names)}")
        else:
            st.info("Processing ALL categories")
        
        time.sleep(2)
        st.rerun()
        
    except Exception as e:
        st.error(f"Failed to start pipeline: {e}")
        st.session_state.pipeline_running = False


# Stop button
if st.session_state.pipeline_running:
    if st.button("Stop & Show Final Results", type="secondary"):
        st.session_state.pipeline_running = False
        st.rerun()


# ============================================================
# REAL-TIME DISPLAY
# ============================================================


if st.session_state.pipeline_running or st.session_state.partner_id:
    
    st.markdown("---")
    
    # Try to find partner if not found yet
    if not st.session_state.partner_id and st.session_state.expected_partner_name:
        db = SessionLocal()
        try:
            partner = db.query(Partner).filter_by(
                company_name=st.session_state.expected_partner_name
            ).first()
            
            if partner:
                st.session_state.partner_id = str(partner.partner_id)
                st.session_state.partner_name = partner.company_name
        finally:
            db.close()
    
    partner_id = st.session_state.partner_id
    partner_name = st.session_state.partner_name
    session_start = st.session_state.session_start_time
    
    if not partner_id:
        st.warning(f"Waiting for partner '{st.session_state.expected_partner_name}' to be created...")
        st.caption("The pipeline is discovering URLs and creating the partner...")
        time.sleep(3)
        st.rerun()
    
    # Query database
    db = SessionLocal()
    
    try:
        # Base query with session filter
        base_query = db.query(Product).filter(
            Product.partner_id == partner_id
        )
        
        # Apply session filter if available
        if session_start:
            base_query = base_query.filter(Product.scraped_at >= session_start)
        
        # Get counts (ONLY from this session)
        completed = base_query.filter(
            Product.processing_status == 'completed'
        ).count()
        
        pending = base_query.filter(
            Product.processing_status == 'processing'
        ).count()
        
        scraped = base_query.count()
        
        # Get products with insurance data (ONLY from this session)
        processed_query = db.query(
            Product.product_name,
            Product.brand,
            Product.price,
            Product.currency,
            Product.category,
            Product.description,
            InsurancePackage.package_data,
            InsurancePackage.status
        ).join(
            InsurancePackage,
            Product.product_id == InsurancePackage.product_id
        ).filter(
            Product.partner_id == partner_id,
            Product.processing_status == 'completed'
        )
        
        # Apply session filter
        if session_start:
            processed_query = processed_query.filter(Product.scraped_at >= session_start)
        
        processed_products = processed_query.order_by(
            Product.processing_completed_at.desc()
        ).all()
        
        # Separate eligible/not eligible
        eligible = []
        not_eligible = []
        
        for row in processed_products:
            pkg = row.package_data
            pkg["product"] = {
                "name": row.product_name,
                "brand": row.brand,
                "price": float(row.price) if row.price else 0.0,
                "currency": row.currency,
                "category": row.category,
                "description": row.description
            }
            
            is_eligible = (
                pkg.get("eligible") is True or
                row.status == "eligible" or
                (pkg.get("standard_premium_12_months") and 
                 pkg.get("standard_premium_12_months", {}).get("amount"))
            )
            
            if is_eligible:
                eligible.append(pkg)
            else:
                not_eligible.append(pkg)
        
        # Display metrics
        elapsed = time.time() - st.session_state.start_time if st.session_state.start_time else 0
        
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Scraped", scraped)
        col2.metric("Eligible", len(eligible))
        col3.metric("Not Eligible", len(not_eligible))
        col4.metric("Processing", pending)
        col5.metric("Time", f"{int(elapsed)}s")
        
        # Show selected categories if any
        if st.session_state.selected_categories:
            selected_display = [AVAILABLE_CATEGORIES[cat] for cat in st.session_state.selected_categories]
            st.info(f"Filtering by: {', '.join(selected_display)}")
        
        # Progress indicator
        if scraped > 0:
            progress = completed / scraped if scraped > 0 else 0
            st.progress(progress, text=f"Processed {completed}/{scraped} products ({progress*100:.0f}%)")
        else:
            st.info("Discovering and scraping products...")
        
        # Status message
        if st.session_state.pipeline_running:
            if scraped == 0:
                st.info("Pipeline starting... discovering URLs and scraping products")
            elif completed == 0:
                st.info(f"Scraped {scraped} products, starting AI classification...")
            elif pending > 0:
                st.info(f"Pipeline running... processing products in real-time")
            else:
                st.success(f"Pipeline active - processed {completed} products so far!")
        else:
            st.success(f"Pipeline completed! Total: {completed} products")
        
        st.markdown("---")
        
        # Display products
        if eligible:
            st.subheader(f"Eligible Products ({len(eligible)})")
            for idx, product in enumerate(eligible, 1):
                render_product_card(product, idx, True)
        
        if not_eligible:
            st.markdown("---")
            st.subheader(f"Not Eligible Products ({len(not_eligible)})")
            for idx, product in enumerate(not_eligible, 1):
                render_product_card(product, idx, False)
        
        # Show message if no products yet
        if not eligible and not not_eligible and completed == 0:
            st.info("Waiting for first products to be processed... Check terminal for live updates!")
        
        # Download button
        if completed > 0:
            st.markdown("---")
            
            # Build category info for download
            category_info = None
            if st.session_state.selected_categories:
                category_info = [AVAILABLE_CATEGORIES[cat] for cat in st.session_state.selected_categories]
            
            download_data = {
                "metadata": {
                    "partner": partner_name,
                    "session_start": session_start.isoformat() if session_start else None,
                    "timestamp": datetime.utcnow().isoformat(),
                    "selected_categories": category_info,
                    "total_scraped": scraped,
                    "total_processed": completed,
                    "eligible": len(eligible),
                    "not_eligible": len(not_eligible),
                    "processing_time": f"{int(elapsed)}s"
                },
                "eligible_products": eligible,
                "not_eligible_products": not_eligible
            }
            
            st.download_button(
                label="Download JSON Report",
                data=json.dumps(download_data, indent=2, ensure_ascii=False),
                file_name=f"{partner_name}_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
    
    finally:
        db.close()
    
    # Auto-refresh every 3 seconds if pipeline is running
    if st.session_state.pipeline_running:
        time.sleep(3)
        st.rerun()