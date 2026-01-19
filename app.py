

import streamlit as st
import json
import sys
from pathlib import Path


st.set_page_config(
    page_title="Garanty Affinity Insurance",
    page_icon="🛡️",
    layout="wide"
)


# UI helper renderers

def render_coverage_modules(modules: list):
    if not modules:
        return
    st.markdown("### What's Covered")
    for m in modules:
        st.markdown(f"✅ {m}")


def render_exclusions(exclusions: list):
    if not exclusions:
        return
    with st.expander("What's NOT Covered"):
        for e in exclusions:
            st.markdown(f"❌ {e}")


def render_assurmax_plans(plans: dict):
    if not plans:
        return

    st.markdown("### ASSURMAX Insurance Plans")
    cols = st.columns(len(plans))

    for col, (plan_name, durations) in zip(cols, plans.items()):
        with col:
            st.markdown(f"#### {plan_name}")

            for period, values in durations.items():
                st.markdown(f"**{period.replace('_', ' ').title()}**")

                if "annual_premium" in values:
                    st.write(
                        f"Annual Premium: **{values['annual_premium']} {values['currency']}**"
                    )
                else:
                    st.write(
                        f"Total Premium: **{values['total_premium']} {values['currency']}**"
                    )

                if values.get("per_item_cap"):
                    st.write(
                        f"Per Item Cap: {values['per_item_cap']} {values['currency']}"
                    )

                if values.get("pack_cap"):
                    st.write(
                        f"Pack Cap: {values['pack_cap']} {values['currency']}"
                    )

                st.markdown("---")


def render_standard_premium(premium: dict):
    if not premium:
        return

    st.markdown("### Standard Insurance Premium")
    cols = st.columns(len(premium))

    for col, (period, values) in zip(cols, premium.items()):
        with col:
            st.markdown(f"**{period.replace('_', ' ').title()}**")

            if "annual_premium" in values:
                st.write(
                    f"Annual Premium: **{values['annual_premium']} {values['currency']}**"
                )
            else:
                st.write(
                    f"Total Premium: **{values['total_premium']} {values['currency']}**"
                )

# ------------------------------------------------------------------
# App UI
# ------------------------------------------------------------------
st.title("Garanty Affinity Insurance")

website_url = st.text_input(
    "E-commerce Website URL:",
    placeholder="https://www.noon.com"
)

if st.button("Generate Insurance Quotes", type="primary"):

    if not website_url:
        st.warning("Please enter a URL")
        st.stop()

    if not website_url.startswith(("http://", "https://")):
        st.error("URL must start with http:// or https://")
        st.stop()

    try:
       
        current_dir = Path(__file__).parent
        
        # Add paths to sys.path dynamically
        if str(current_dir) not in sys.path:
            sys.path.insert(0, str(current_dir))
        if str(current_dir.parent) not in sys.path:
            sys.path.insert(0, str(current_dir.parent))
        
        
        try:
            from scrapper.Scrapper import crawl_entire_site, save_products
        except ImportError as e:
            st.error(f"Cannot import scrapper module: {e}")
            st.stop()
        
        try:
            from main_workflow import run_workflow_from_json
        except ImportError as e:
            st.error(f"Cannot import workflow module: {e}")
            st.stop()
        
        
        with st.spinner("Scraping website..."):
            products = crawl_entire_site(website_url)

        if not products:
            st.error("No valid product pages detected.")
            st.stop()

        st.success(f"Found {len(products)} products")

        
        filename = save_products(products, website_url)
        if not filename:
            st.error("Failed to save products.")
            st.stop()

       
        with st.spinner("Generating insurance packages..."):
            results_file = run_workflow_from_json(filename, max_products=8)

        if not results_file:
            st.error("Insurance generation failed.")
            st.stop()

        
        with open(results_file, "r", encoding="utf-8") as f:
            results = json.load(f)

        packages = results.get("packages", [])
        eligible = [p for p in packages if p.get("eligible")]
        not_eligible = [p for p in packages if not p.get("eligible")]

        
        c1, c2, c3 = st.columns(3)
        c1.metric("Products Processed", len(packages))
        c2.metric("Eligible", len(eligible))
        c3.metric("Not Eligible", len(not_eligible))

        st.markdown("---")

        # ----------------------------------------------------------
        # Eligible products
        # ----------------------------------------------------------
        if eligible:
            st.subheader("Products with Insurance Coverage")

            for idx, pkg in enumerate(eligible[:10], 1):
               
                
                insurance = pkg.get("insurance_package", {})
                
                
                agent_product = insurance.get("product", {})
                
               
                if not agent_product:
                    agent_product = pkg.get("product", {})
                
                # Get product name from either source
                product_name = agent_product.get("name") or agent_product.get("product_name") or "Unknown"
                
                with st.expander(f"#{idx} - {product_name[:70]}"):
                    st.markdown("### Product Information")

                    c1, c2 = st.columns(2)
                    with c1:
                        st.write(f"**Name:** {agent_product.get('name', agent_product.get('product_name', 'N/A'))}")
                        st.write(f"**Brand:** {agent_product.get('brand', 'N/A')}")
                        # This shows the INFERRED category from the agent, not 'N/A'
                        st.write(f"**Category:** {agent_product.get('category', 'N/A')}")
                    with c2:
                        st.write(f"**Price:** {agent_product.get('price', 'N/A')} {agent_product.get('currency', 'AED')}")
                        st.write(f"**Market:** {insurance.get('market', 'N/A')}")
                        st.write(f"**Risk Profile:** {insurance.get('risk_profile', 'N/A')}")
                        
                        # Show value bucket if available
                        if insurance.get("value_bucket"):
                            st.write(f"**Value Bucket:** {insurance['value_bucket']}")

                    # Show description if available
                    description = agent_product.get('description')
                    if description and description != 'N/A':
                        st.markdown("---")
                        st.markdown("#### Product Description")
                        st.write(description)

                    st.markdown("---")

                    # Insurance rendering
                    doc_type = insurance.get("document_type")

                    if doc_type == "ASSURMAX":
                        render_assurmax_plans(insurance.get("plans", {}))
                        st.markdown("---")
                        render_coverage_modules(insurance.get("coverage_modules", []))
                        render_exclusions(insurance.get("exclusions", []))
                    elif doc_type == "STANDARD":
                        render_standard_premium(insurance.get("premium", {}))
                        st.markdown("---")
                        render_coverage_modules(insurance.get("coverage_modules", []))
                        render_exclusions(insurance.get("exclusions", []))
                    else:
                        st.warning(f"Unknown insurance document type: {doc_type}")

        else:
            st.info("No products were eligible for insurance.")

        # ----------------------------------------------------------
        # Not eligible products
        # ----------------------------------------------------------
        if not_eligible:
            st.markdown("---")
            st.subheader("Products Not Eligible for Insurance")

            for idx, pkg in enumerate(not_eligible[:10], 1):
                insurance = pkg.get("insurance_package", {})
                agent_product = insurance.get("product", {})
                
                if not agent_product:
                    agent_product = pkg.get("product", {})
                
                product_name = agent_product.get("name") or agent_product.get("product_name") or "Unknown"
                
                with st.expander(f"#{idx} - {product_name[:60]}"):
                    # Show product info
                    st.write(f"**Name:** {agent_product.get('name', agent_product.get('product_name', 'N/A'))}")
                    st.write(f"**Brand:** {agent_product.get('brand', 'N/A')}")
                    st.write(f"**Category:** {agent_product.get('category', 'N/A')}")
                    st.write(f"**Price:** {agent_product.get('price', 'N/A')} {agent_product.get('currency', 'AED')}")
                    
                    # Show description if available
                    description = agent_product.get('description')
                    if description and description != 'N/A':
                        st.markdown("---")
                        st.markdown("#### Product Description")
                        st.write(description)
                        st.markdown("---")
                    
                    reason = insurance.get("reason", "Not eligible")
                    st.error(f"**Reason for ineligibility:** {reason}")
                    
                    # Show any available insurance info
                    if insurance.get('risk_profile'):
                        st.info(f"**Risk Profile:** {insurance['risk_profile']}")
                    if insurance.get('market'):
                        st.info(f"**Market:** {insurance['market']}")

    except Exception as e:
        import traceback
        st.error(f"Unexpected error occurred: {str(e)}")
        st.code(traceback.format_exc())