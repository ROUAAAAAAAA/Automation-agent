# app_ui_mock.py

import streamlit as st
import json

# ------------------------------------------------------------------
# Streamlit config
# ------------------------------------------------------------------
st.set_page_config(
    page_title="Garanty Affinity Insurance (UI Mock)",
    page_icon="🛡️",
    layout="wide"
)

# ------------------------------------------------------------------
# UI helper renderers (IDENTICAL TO REAL APP)
# ------------------------------------------------------------------
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
    st.markdown("### 🛡️ Insurance Plans (ASSURMAX)")

    if not plans:
        return

    plan_cols = st.columns(len(plans))

    for col, (plan_name, durations) in zip(plan_cols, plans.items()):
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
    st.markdown("### 🛡️ Insurance Premium (STANDARD)")

    cols = st.columns(len(premium))
    for col, (period, values) in zip(cols, premium.items()):
        with col:
            st.markdown(f"**{period.replace('_', ' ').title()}**")
            st.write(
                f"Total Premium: **{values['total_premium']} {values['currency']}**"
            )

# ------------------------------------------------------------------
# MOCK DATA (STRICT CONTRACT)
# ------------------------------------------------------------------
packages = [
    {
        "eligible": True,
        "product": {
            "product_name": "Apple iPhone 15 Pro Max 256GB",
            "brand": "Apple",
            "category": "Smartphones",
            "price": 5299,
            "currency": "AED"
        },
        "insurance_package": {
            "document_type": "ASSURMAX",
            "market": "UAE",
            "risk_profile": "HIGH",
            "coverage_modules": [
                "Accidental Damage",
                "Liquid Damage",
                "Theft"
            ],
            "exclusions": [
                "Cosmetic damage",
                "Intentional damage"
            ],
            "plans": {
                "ASSURMAX": {
                    "12_months": {
                        "annual_premium": 349,
                        "currency": "AED",
                        "per_item_cap": 4000,
                        "pack_cap": 8000
                    }
                },
                "ASSURMAX+": {
                    "24_months": {
                        "total_premium": 599,
                        "currency": "AED",
                        "per_item_cap": 6000,
                        "pack_cap": 12000
                    }
                }
            }
        }
    },
    {
        "eligible": True,
        "product": {
            "product_name": "Samsung 55 Inch QLED TV",
            "brand": "Samsung",
            "category": "Televisions",
            "price": 2899,
            "currency": "AED"
        },
        "insurance_package": {
            "document_type": "STANDARD",
            "market": "UAE",
            "risk_profile": "MEDIUM",
            "coverage_modules": [
                "Electrical failure",
                "Mechanical breakdown"
            ],
            "exclusions": [
                "Physical damage"
            ],
            "premium": {
                "12_months": {
                    "total_premium": 199,
                    "currency": "AED"
                },
                "24_months": {
                    "total_premium": 329,
                    "currency": "AED"
                }
            }
        }
    },
    {
        "eligible": False,
        "product": {
            "product_name": "Used Laptop – 2014 Model",
            "price": 800,
            "currency": "AED"
        },
        "insurance_package": {
            "reason": "Refurbished products are not eligible for coverage"
        }
    }
]

# ------------------------------------------------------------------
# App UI
# ------------------------------------------------------------------
st.title("Garanty Affinity Insurance (UI Mock Mode)")

eligible = [p for p in packages if p.get("eligible") is True]
not_eligible = [p for p in packages if p.get("eligible") is False]

col1, col2, col3 = st.columns(3)
col1.metric("Products Processed", len(packages))
col2.metric("Eligible", len(eligible))
col3.metric("Not Eligible", len(not_eligible))

st.markdown("---")

# ------------------------------------------------------------------
# Eligible products
# ------------------------------------------------------------------
if eligible:
    st.subheader("Products with Insurance Coverage")

    for idx, pkg in enumerate(eligible, 1):
        product = pkg["product"]
        insurance = pkg["insurance_package"]

        with st.expander(f"#{idx} - {product['product_name'][:70]}"):
            st.markdown("### Product Information")

            c1, c2 = st.columns(2)
            with c1:
                st.write(f"**Name:** {product['product_name']}")
                st.write(f"**Brand:** {product.get('brand')}")
                st.write(f"**Category:** {product.get('category')}")
            with c2:
                st.write(f"**Price:** {product['price']} {product['currency']}")
                st.write(f"**Market:** {insurance.get('market')}")
                st.write(f"**Risk Profile:** {insurance.get('risk_profile')}")

            st.markdown("---")

            if insurance.get("document_type") == "ASSURMAX":
                render_assurmax_plans(insurance.get("plans", {}))
            elif insurance.get("document_type") == "STANDARD":
                render_standard_premium(insurance.get("premium", {}))

            st.markdown("---")
            render_coverage_modules(insurance.get("coverage_modules", []))
            render_exclusions(insurance.get("exclusions", []))

# ------------------------------------------------------------------
# Not eligible products
# ------------------------------------------------------------------
if not_eligible:
    st.markdown("---")
    st.subheader("Products Not Eligible for Insurance")

    for idx, pkg in enumerate(not_eligible, 1):
        product = pkg["product"]
        insurance = pkg["insurance_package"]

        with st.expander(f"#{idx} - {product['product_name'][:60]}"):
            st.write(f"**Price:** {product['price']} {product['currency']}")
            st.error(insurance.get("reason"))
