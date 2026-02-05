import streamlit as st
import sys
import os
from pathlib import Path
from datetime import datetime
import time
import json
import requests




BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


def _api_start_job(url: str, categories: list[str] | None = None) -> str:
    """POST /jobs  →  returns the new job_id."""
    resp = requests.post(
        f"{BACKEND_URL}/jobs",
        json={"start_url": url, "selected_categories": categories or []},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["job_id"]


def _api_stop_job(job_id: str) -> bool:
    """POST /jobs/{id}/stop  →  True if the backend accepted it."""
    try:
        resp = requests.post(f"{BACKEND_URL}/jobs/{job_id}/stop", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


def _api_job_status(job_id: str) -> dict | None:
    """GET /jobs/{id}/status  →  the status payload, or None on failure."""
    try:
        resp = requests.get(f"{BACKEND_URL}/jobs/{job_id}/status", timeout=5)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None




st.set_page_config(
    page_title="Garanty Affinity Insurance",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# INJECTED STYLESHEET


CSS = """
<style>
/* ── global reset / base ──────────────────────────────── */
.reportview-container, .stApp {
    background: #0f1623;
    color: #e2e6ea;
    font-family: 'Segoe UI', system-ui, sans-serif;
}
.css-1aumxhk { display: none !important; }

/* ── header strip ──────────────────────────────────────── */
.ga-header {
    background: linear-gradient(135deg, #0f1623 0%, #162236 100%);
    border-bottom: 1px solid #1e2d45;
    padding: 28px 0 18px;
    margin-bottom: 8px;
}
.ga-header h1 {
    color: #fff;
    font-size: 1.75rem;
    font-weight: 600;
    margin: 0 0 4px;
    letter-spacing: -0.02em;
}
.ga-header p {
    color: #6b7d99;
    font-size: 0.82rem;
    margin: 0;
}

/* ── badges ────────────────────────────────────────────── */
.badge {
    display: inline-block;
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    padding: 3px 9px;
    border-radius: 3px;
    margin-right: 5px;
}
.badge-eligible   { background: #14532d; color: #86efac; }
.badge-assurmax   { background: #3d2f0e; color: #c9a84c; border: 1px solid #c9a84c55; }
.badge-ineligible { background: #3b1515; color: #f87171; }
.badge-selected   { background: #1e3a5f; color: #60a5fa; }

/* ── product card ──────────────────────────────────────── */
.ga-card {
    background: #162236;
    border: 1px solid #1e2d45;
    border-radius: 10px;
    padding: 20px 22px 16px;
    margin-bottom: 14px;
    transition: border-color 0.2s;
}
.ga-card:hover { border-color: #2a4a7a; }
.ga-card.selected {
    border-color: #3b7dd8;
    background: #162a3e;
}
.ga-card.in-assurmax {
    border-color: #c9a84c;
    background: #1a1810;
}

/* ── card title ────────────────────────────────────────── */
.ga-card-title {
    font-size: 1.05rem;
    font-weight: 600;
    color: #fff;
    margin: 8px 0 10px;
    line-height: 1.3;
}

/* ── info strip ────────────────────────────────────────── */
.ga-info-strip {
    font-size: 0.8rem;
    color: #7a8fa8;
    margin-bottom: 4px;
    line-height: 1.6;
}
.ga-info-strip .label {
    color: #5a6f8a;
    text-transform: uppercase;
    font-size: 0.7rem;
    letter-spacing: 0.04em;
    margin-right: 3px;
}
.ga-info-strip .value {
    color: #b0bec8;
    font-weight: 500;
}

/* ── section divider inside card ───────────────────────── */
.ga-card-divider {
    border: none;
    border-top: 1px solid #1e2d45;
    margin: 13px 0;
}

/* ── pricing row ───────────────────────────────────────── */
.ga-pricing-row {
    display: flex;
    gap: 10px;
    margin: 12px 0 4px;
}
.ga-pricing-box {
    flex: 1;
    background: #0f1e2e;
    border: 1px solid #1e2d45;
    border-radius: 7px;
    padding: 10px 12px;
    text-align: center;
}
.ga-pricing-box .p-label {
    font-size: 0.68rem;
    color: #5a6f8a;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 4px;
}
.ga-pricing-box .p-amount {
    font-size: 1.05rem;
    font-weight: 700;
    color: #fff;
}
.ga-pricing-box .p-detail {
    font-size: 0.68rem;
    color: #5a6f8a;
    margin-top: 3px;
    line-height: 1.4;
}

/* ── ASSURMAX pack summary bar ─────────────────────────── */
.ga-pack-bar {
    background: linear-gradient(135deg, #2a1f06, #1f2510);
    border: 1px solid #c9a84c44;
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 18px;
}
.ga-pack-bar .pack-title {
    color: #c9a84c;
    font-weight: 700;
    font-size: 0.82rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 8px;
}
.ga-pack-bar .pack-meta {
    color: #a89060;
    font-size: 0.77rem;
    line-height: 1.5;
}
.ga-pack-bar .pack-items {
    margin-top: 10px;
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
}
.ga-pack-item {
    background: #3d2f0e;
    border: 1px solid #c9a84c44;
    border-radius: 5px;
    padding: 5px 10px;
    font-size: 0.74rem;
    color: #c9a84c;
    max-width: 200px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.ga-pack-cap-bar {
    margin-top: 14px;
    background: #1a1408;
    border-radius: 4px;
    height: 6px;
    overflow: hidden;
}
.ga-pack-cap-fill {
    height: 100%;
    background: #c9a84c;
    border-radius: 4px;
    transition: width 0.3s;
}
.ga-pack-cap-fill.over { background: #ef4444; }

/* ── summary metric row ────────────────────────────────── */
.ga-summary-row {
    display: flex;
    gap: 12px;
    margin-bottom: 18px;
}
.ga-summary-box {
    flex: 1;
    background: #162236;
    border: 1px solid #1e2d45;
    border-radius: 8px;
    padding: 14px 16px;
    text-align: center;
}
.ga-summary-box .s-value {
    font-size: 1.6rem;
    font-weight: 700;
    color: #fff;
}
.ga-summary-box .s-label {
    font-size: 0.72rem;
    color: #6b7d99;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-top: 2px;
}

/* ── order totals box ──────────────────────────────────── */
.ga-totals-box {
    background: linear-gradient(135deg, #1a2332, #0f1a28);
    border: 2px solid #3b7dd8;
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 24px;
}
.ga-totals-title {
    color: #60a5fa;
    font-size: 1.1rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 16px;
    padding-bottom: 10px;
    border-bottom: 1px solid #3b7dd844;
}
.ga-totals-section {
    margin-bottom: 16px;
    padding: 12px 16px;
    background: #0f1e2e55;
    border-radius: 8px;
}
.ga-totals-section-title {
    color: #8ab4d6;
    font-size: 0.8rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 10px;
}
.ga-totals-row {
    display: flex;
    justify-content: space-between;
    padding: 6px 0;
    font-size: 0.85rem;
    color: #b0bec8;
}
.ga-totals-row.main {
    font-size: 1rem;
    font-weight: 700;
    color: #fff;
    border-top: 1px solid #3b7dd844;
    padding-top: 12px;
    margin-top: 8px;
}

/* ── product item card in totals ───────────────────────── */
.ga-product-item {
    margin-bottom: 10px;
    padding: 12px;
    background: #0f1e2e;
    border: 1px solid #1e2d45;
    border-radius: 6px;
}
.ga-product-item-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
}
.ga-product-item-name {
    color: #fff;
    font-weight: 600;
    font-size: 0.9rem;
}
.ga-product-item-meta {
    color: #6b7d99;
    font-size: 0.75rem;
    margin-left: 8px;
}
.ga-product-item-pricing {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 8px;
    margin-top: 8px;
}
.ga-product-item-plan {
    padding: 8px;
    background: #0a1420;
    border-radius: 4px;
    border-left: 2px solid;
}
.ga-product-item-plan.monthly { border-color: #3b7dd8; }
.ga-product-item-plan.twelve { border-color: #34d399; }
.ga-product-item-plan.twentyfour { border-color: #fbbf24; }
.ga-product-item-plan-label {
    font-size: 0.65rem;
    color: #6b7d99;
    text-transform: uppercase;
    margin-bottom: 4px;
}
.ga-product-item-plan-amount {
    font-size: 0.9rem;
    font-weight: 700;
    color: #fff;
}
.ga-product-item-plan-comm {
    font-size: 0.65rem;
    color: #86efac;
    margin-top: 2px;
}

/* ── section titles ────────────────────────────────────── */
.ga-section-title {
    color: #fff;
    font-size: 0.82rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 12px;
    padding-bottom: 6px;
    border-bottom: 1px solid #1e2d45;
}

/* ── widget overrides ──────────────────────────────────── */
.stCheckbox label    { color: #b0bec8 !important; font-size: 0.82rem !important; }
.stNumberInput label { color: #6b7d99 !important; font-size: 0.72rem !important; text-transform: uppercase; letter-spacing: 0.04em; }
.stSelectbox label   { color: #6b7d99 !important; font-size: 0.72rem !important; text-transform: uppercase; letter-spacing: 0.04em; }

.streamlit-expander         { border-color: #1e2d45 !important; background: #0f1e2e !important; border-radius: 6px !important; margin: 6px 0 !important; }
.streamlit-expander summary { color: #8a9db8 !important; font-size: 0.78rem !important; }

[data-testid="stMetric"]      { background: #0f1e2e; border-radius: 8px; padding: 10px !important; border: 1px solid #1e2d45; }
[data-testid="stMetricValue"] { color: #fff !important; }
[data-testid="stMetricLabel"] { color: #6b7d99 !important; font-size: 0.72rem !important; text-transform: uppercase; letter-spacing: 0.04em; }

.stButton button            { border-radius: 6px !important; font-weight: 600 !important; font-size: 0.82rem !important; }
.stButton button[kind="primary"]   { background: #c9a84c !important; color: #0f1623 !important; border: none !important; }
.stButton button[kind="primary"]:hover { background: #dbb85a !important; }
.stButton button[kind="secondary"] { background: #1e2d45 !important; color: #b0bec8 !important; border: 1px solid #2a4a7a !important; }

.stTextInput input, .stNumberInput input, .stSelectbox select {
    background: #0f1e2e !important; color: #e2e6ea !important;
    border-color: #2a3f5a !important; border-radius: 6px !important;
}
.stTextInput input:focus, .stNumberInput input:focus {
    border-color: #3b7dd8 !important; box-shadow: 0 0 0 2px #3b7dd822 !important;
}

.stProgress div     { background: #1e2d45 !important; border-radius: 4px !important; }
.stProgress div div { background: #3b7dd8 !important; border-radius: 4px !important; }

.stInfo    { background: #0e1f30 !important; border-left-color: #3b7dd8 !important; color: #8ab4d6 !important; border-radius: 6px !important; }
.stSuccess { background: #0d1f18 !important; border-left-color: #34d399 !important; color: #6ee7b7 !important; border-radius: 6px !important; }
.stWarning { background: #1f1a0d !important; border-left-color: #fbbf24 !important; color: #d4a828 !important; border-radius: 6px !important; }
.stError   { background: #1f0e0e !important; border-left-color: #ef4444 !important; color: #f87171 !important; border-radius: 6px !important; }

/* ── not-eligible list ─────────────────────────────────── */
.ga-ineligible-row {
    padding: 8px 0;
    border-bottom: 1px solid #1e2d451a;
    font-size: 0.8rem;
    color: #7a8fa8;
}
.ga-ineligible-row .inel-name   { color: #c0cad5; font-weight: 500; }
.ga-ineligible-row .inel-reason { color: #f87171; margin-left: 12px; font-size: 0.74rem; }

/* ── warning box ───────────────────────────────────────── */
.ga-warning-box {
    background: #2a1f06;
    border: 1px solid #c9a84c;
    border-radius: 6px;
    padding: 10px 12px;
    margin: 8px 0;
    font-size: 0.75rem;
    color: #a89060;
}
</style>
"""


def _inject_css():
    st.markdown(CSS, unsafe_allow_html=True)




AVAILABLE_CATEGORIES = {
    "ELECTRONIC_PRODUCTS":          "Electronics",
    "HOME_APPLIANCES":              "Home Appliances",
    "BABY_EQUIPMENT_ESSENTIAL":     "Baby Products",
    "BAGS_LUGGAGE_ESSENTIAL":       "Bags & Luggage",
    "GARDEN_DIY_ESSENTIAL":         "Garden & DIY",
    "HEALTH_WELLNESS_ESSENTIAL":    "Health & Wellness",
    "LIVING_FURNITURE_ESSENTIAL":   "Living & Furniture",
    "MICRO_MOBILITY_ESSENTIAL":     "Micromobility",
    "OPTICAL_HEARING_ESSENTIAL":    "Optical & Hearing",
    "PERSONAL_CARE_DEVICES":        "Personal Care",
    "OPULENCIA_PREMIUM":            "Premium & Luxury",
    "SOUND_MUSIC_ESSENTIAL":        "Sound & Music",
    "SPORT_OUTDOOR_ESSENTIAL":      "Sport & Outdoor",
    "TEXTILE_FOOTWEAR_ZARA":        "Textile & Footwear",
}

COMMISSION_RATES = {"10%": 0.10, "15%": 0.15, "20%": 0.20}

ASSURMAX_FIXED_PREMIUM = 550.00  
ASSURMAX_MAX_ITEMS = 3          
ASSURMAX_TOTAL_CAP = 5000.0     

# Job statuses
_TERMINAL_STATUSES = {"completed", "failed", "stopped"}




current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))
if str(current_dir.parent) not in sys.path:
    sys.path.insert(0, str(current_dir.parent))

try:
    from database.models import SessionLocal, Product, InsurancePackage, Partner
    from urllib.parse import urlparse
except ImportError as e:
    st.error(f"Cannot import database modules: {e}")
    st.stop()




def get_partner_from_url(url: str):
    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "")
    partner_name = domain.split(".")[0].title()
    name_map = {
        "noon": "Noon", "virginmegastore": "Virginmegastore.Ae",
        "jumbo": "Jumbo", "mytek": "Mytek", "emax": "Emax",
        "sharaf": "Uae", "uae": "Uae",
    }
    for key, val in name_map.items():
        if key in partner_name.lower():
            partner_name = val
            break
    db = SessionLocal()
    try:
        partner = db.query(Partner).filter_by(company_name=partner_name).first()
        if partner:
            return str(partner.partner_id), partner_name
    finally:
        db.close()
    return None, partner_name


def calc_breakdown(gross: float, rate: float):
    """Calculate commission breakdown for a premium"""
    comm = round(gross * rate, 2)
    return {"gross": gross, "comm": comm, "net": round(gross - comm, 2)}


def _init_session():
    defaults = {
        "pipeline_running":      False,
        "configuration_mode":    False,
        "job_id":                None,
        "partner_id":            None,
        "partner_name":          None,
        "start_time":            None,
        "session_start_time":    None,
        "url":                   None,
        "expected_partner_name": None,
        "selected_categories":   [],
        "product_selections":    {},
        "assurmax_selections":   {},
        "eligible_products":     [],
        "not_eligible_products": [],
        "frozen_eligible_order": [],
        "assurmax_commission_rate": 0.10,  
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v




def calculate_assurmax_bundle(pack_items: list, commission_rate: float = 0.10) -> dict:
    """
    Calculate ASSURMAX bundle - ALWAYS 550 AED premium (5,000 × 11%)
    
    Args:
        pack_items: List of items with 'price' and 'qty'
        commission_rate: 0.10, 0.15, or 0.20
        
    Returns:
        Dictionary with bundle details
    """
    if not pack_items:
        return None
    
    # Calculate total insured value
    total_value = sum(item['price'] * item['qty'] for item in pack_items)
    
    # Premium is ALWAYS 550 AED (fixed)
    premium = ASSURMAX_FIXED_PREMIUM
    
    # Calculate commission
    commission = round(premium * commission_rate, 2)
    net = round(premium - commission, 2)
    
    return {
        "total_insured_value": total_value,
        "coverage_cap": ASSURMAX_TOTAL_CAP,
        "premium": premium,  
        "premium_rate": 0.11,  
        "commission_rate": commission_rate,
        "commission": commission,
        "net": net,
        "items_count": len(pack_items),
        "max_items": ASSURMAX_MAX_ITEMS,
        "warning": f"Maximum payout limited to {ASSURMAX_TOTAL_CAP:,.0f} AED total" if total_value > ASSURMAX_TOTAL_CAP else None
    }



def calculate_order_totals(selections: dict, assurmax_selections: dict, assurmax_commission_rate: float = 0.10) -> dict:
    """
    Calculate complete order totals with correct ASSURMAX logic
    
    Args:
        selections: All selected products
        assurmax_selections: Products in ASSURMAX pack
        assurmax_commission_rate: Commission rate for ASSURMAX bundle
        
    Returns:
        Dictionary with complete order breakdown
    """
    # Separate ASSURMAX vs standalone
    assurmax_items = []
    standalone_items = []
    
    for pid, data in selections.items():
        if assurmax_selections.get(pid):
            assurmax_items.append({
                'price': float(data['product']['price']),
                'qty': data['quantity'],
                'name': data['product']['name']
            })
        else:
            standalone_items.append(data)
    
    # Calculate ASSURMAX bundle (if any products in pack)
    assurmax_bundle = None
    if assurmax_items:
        assurmax_bundle = calculate_assurmax_bundle(assurmax_items, assurmax_commission_rate)
    
    # Calculate standalone totals (normal insurance) - PER PRODUCT
    standalone_products = []
    total_monthly_premium = 0
    total_monthly_commission = 0
    total_12month_premium = 0
    total_12month_commission = 0
    total_24month_premium = 0
    total_24month_commission = 0
    
    for item in standalone_items:
        ins = item['insurance']
        qty = item['quantity']
        cr = item['commission_rate']
        product = item['product']
        
        # Monthly
        monthly_prem = float(ins.get("monthly_premium", {}).get("amount", 0)) * qty
        monthly_bd = calc_breakdown(monthly_prem, cr)
        
        # 12 Month
        std12_prem = float(ins.get("standard_premium_12_months", {}).get("amount", 0)) * qty
        std12_bd = calc_breakdown(std12_prem, cr)
        
        # 24 Month
        std24_prem = float(ins.get("standard_premium_24_months", {}).get("amount", 0)) * qty
        std24_bd = calc_breakdown(std24_prem, cr)
        
        standalone_products.append({
            "name": product.get("name", "Unknown"),
            "quantity": qty,
            "commission_rate": cr,
            "monthly": monthly_bd,
            "12_month": std12_bd,
            "24_month": std24_bd
        })
        
        # Add to totals
        total_monthly_premium += monthly_bd["gross"]
        total_monthly_commission += monthly_bd["comm"]
        total_12month_premium += std12_bd["gross"]
        total_12month_commission += std12_bd["comm"]
        total_24month_premium += std24_bd["gross"]
        total_24month_commission += std24_bd["comm"]
    
    return {
        "assurmax_bundle": assurmax_bundle,
        "standalone_products": standalone_products,
        "standalone_totals": {
            "monthly": {
                "premium": round(total_monthly_premium, 2),
                "commission": round(total_monthly_commission, 2),
                "net": round(total_monthly_premium - total_monthly_commission, 2)
            },
            "12_month": {
                "premium": round(total_12month_premium, 2),
                "commission": round(total_12month_commission, 2),
                "net": round(total_12month_premium - total_12month_commission, 2)
            },
            "24_month": {
                "premium": round(total_24month_premium, 2),
                "commission": round(total_24month_commission, 2),
                "net": round(total_24month_premium - total_24month_commission, 2)
            }
        },
        "assurmax_item_count": len(assurmax_items),
        "standalone_item_count": len(standalone_items),
        "total_items": len(assurmax_items) + len(standalone_items)
    }





def _render_order_totals(totals: dict):
    """Render comprehensive order totals box - B2B PARTNER VIEW"""
    
    assurmax = totals.get("assurmax_bundle")
    standalone_products = totals.get("standalone_products", [])
    standalone_totals = totals.get("standalone_totals")
    selections = st.session_state.product_selections
    assurmax_selections = st.session_state.assurmax_selections
    
    st.markdown('<div class="ga-totals-box">', unsafe_allow_html=True)
    st.markdown('<div class="ga-totals-title">📊 Partner Commission Summary</div>', unsafe_allow_html=True)
    
    # ===== ASSURMAX Bundle Section =====
    if assurmax and not assurmax.get("error"):
        # Get products in ASSURMAX pack
        assurmax_items = []
        for pid, in_pack in assurmax_selections.items():
            if in_pack:
                sel = selections.get(pid, {})
                if sel:
                    assurmax_items.append(sel)
        
        st.markdown(
            f'<div class="ga-totals-section">'
            f'<div class="ga-totals-section-title">🎁 ASSURMAX BUNDLE ({assurmax["items_count"]} product{"s" if assurmax["items_count"] != 1 else ""})</div>',
            unsafe_allow_html=True
        )
        
        # Show each product in ASSURMAX pack
        for idx, item in enumerate(assurmax_items, 1):
            product = item['product']
            qty = item['quantity']
            total_value = product['price'] * qty
            
            st.markdown(
                f'<div style="margin-bottom:8px;padding:8px 12px;background:#1a181055;border-radius:6px;border-left:3px solid #c9a84c">'
                f'<div style="display:flex;justify-content:space-between;align-items:center">'
                f'  <div>'
                f'    <span style="color:#fff;font-weight:600">{product["name"][:50]}</span>'
                f'    <span style="color:#a89060;font-size:0.75rem;margin-left:8px">Qty: {qty}</span>'
                f'  </div>'
                f'  <div style="color:#c9a84c;font-weight:700">{total_value:,.2f} AED</div>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True
            )
        
        # ASSURMAX totals
        st.markdown(
            f'<div style="margin-top:16px;padding-top:12px;border-top:1px solid #c9a84c44">'
            f'<div class="ga-totals-row">'
            f'  <span>Total Insured Value:</span>'
            f'  <span style="color:#c9a84c;font-weight:700">{assurmax["total_insured_value"]:,.2f} AED</span>'
            f'</div>'
            f'<div class="ga-totals-row">'
            f'  <span>Coverage Cap:</span>'
            f'  <span>{assurmax["coverage_cap"]:,.0f} AED</span>'
            f'</div>'
            f'<div class="ga-totals-row" style="background:#2a1f0633;padding:10px;border-radius:6px;margin:8px 0">'
            f'  <span>Bundle Premium (Fixed):</span>'
            f'  <span style="font-weight:800;color:#fff;font-size:1.1rem">{assurmax["premium"]:,.2f} AED</span>'
            f'</div>'
            f'<div class="ga-totals-row" style="background:#14532d44;padding:10px;border-radius:6px">'
            f'  <span style="font-weight:700">Partner Commission ({int(assurmax["commission_rate"]*100)}%):</span>'
            f'  <span style="color:#86efac;font-weight:800;font-size:1.15rem">+{assurmax["commission"]:,.2f} AED</span>'
            f'</div>'
            f'<div class="ga-totals-row" style="margin-top:4px">'
            f'  <span>Net Revenue:</span>'
            f'  <span>{assurmax["net"]:,.2f} AED</span>'
            f'</div>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True
        )
        
        # Show warning if total value exceeds cap
        if assurmax.get("warning"):
            st.markdown(
                f'<div class="ga-warning-box">'
                f'⚠️ {assurmax["warning"]}'
                f'</div>',
                unsafe_allow_html=True
            )
    
    # ===== Standalone Products Section =====
    if totals["standalone_item_count"] > 0:
        st.markdown(
            f'<div class="ga-totals-section">'
            f'<div class="ga-totals-section-title">📦 INDIVIDUAL PRODUCTS ({totals["standalone_item_count"]} product{"s" if totals["standalone_item_count"] != 1 else ""})</div>',
            unsafe_allow_html=True
        )
        
        # Show each individual product with its own pricing
        for product_data in standalone_products:
            name = product_data["name"]
            qty = product_data["quantity"]
            comm_rate = int(product_data["commission_rate"] * 100)
            
            monthly = product_data["monthly"]
            m12 = product_data["12_month"]
            m24 = product_data["24_month"]
            
            st.markdown(
                f'<div class="ga-product-item">'
                f'  <div class="ga-product-item-header">'
                f'    <span class="ga-product-item-name">{name[:60]}</span>'
                f'    <span class="ga-product-item-meta">Qty: {qty} | Commission: {comm_rate}%</span>'
                f'  </div>'
                f'  <div class="ga-product-item-pricing">'
                f'    <div class="ga-product-item-plan monthly">'
                f'      <div class="ga-product-item-plan-label">Monthly</div>'
                f'      <div class="ga-product-item-plan-amount">{monthly["gross"]:,.2f} AED</div>'
                f'      <div class="ga-product-item-plan-comm">Comm: +{monthly["comm"]:,.2f}</div>'
                f'    </div>'
                f'    <div class="ga-product-item-plan twelve">'
                f'      <div class="ga-product-item-plan-label">12 Months</div>'
                f'      <div class="ga-product-item-plan-amount">{m12["gross"]:,.2f} AED</div>'
                f'      <div class="ga-product-item-plan-comm">Comm: +{m12["comm"]:,.2f}</div>'
                f'    </div>'
                f'    <div class="ga-product-item-plan twentyfour">'
                f'      <div class="ga-product-item-plan-label">24 Months</div>'
                f'      <div class="ga-product-item-plan-amount">{m24["gross"]:,.2f} AED</div>'
                f'      <div class="ga-product-item-plan-comm">Comm: +{m24["comm"]:,.2f}</div>'
                f'    </div>'
                f'  </div>'
                f'</div>',
                unsafe_allow_html=True
            )
        
        # Standalone TOTALS summary
        st.markdown(
            f'<div style="margin-top:16px;padding:16px;background:#0e1f3055;border-radius:8px;border-top:1px solid #2a4a7a55">'
            f'<div style="color:#8ab4d6;font-size:0.75rem;font-weight:700;text-transform:uppercase;margin-bottom:12px">INDIVIDUAL PRODUCTS TOTALS</div>'
            f'<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px">',
            unsafe_allow_html=True
        )
        
        # Monthly Total
        if standalone_totals["monthly"]["premium"] > 0:
            st.markdown(
                f'<div style="padding:10px;background:#0a1420;border-radius:6px;border-left:3px solid #3b7dd8">'
                f'<div style="color:#60a5fa;font-size:0.7rem;font-weight:600;margin-bottom:4px">MONTHLY TOTAL</div>'
                f'<div style="color:#fff;font-weight:800;font-size:1.2rem">{standalone_totals["monthly"]["premium"]:,.2f} AED</div>'
                f'<div style="color:#86efac;font-size:0.75rem;margin-top:4px">Commission: +{standalone_totals["monthly"]["commission"]:,.2f}</div>'
                f'</div>',
                unsafe_allow_html=True
            )
        
        # 12 Month Total
        if standalone_totals["12_month"]["premium"] > 0:
            st.markdown(
                f'<div style="padding:10px;background:#0a1420;border-radius:6px;border-left:3px solid #34d399">'
                f'<div style="color:#34d399;font-size:0.7rem;font-weight:600;margin-bottom:4px">12 MONTHS TOTAL</div>'
                f'<div style="color:#fff;font-weight:800;font-size:1.2rem">{standalone_totals["12_month"]["premium"]:,.2f} AED</div>'
                f'<div style="color:#86efac;font-size:0.75rem;margin-top:4px">Commission: +{standalone_totals["12_month"]["commission"]:,.2f}</div>'
                f'</div>',
                unsafe_allow_html=True
            )
        
        # 24 Month Total
        if standalone_totals["24_month"]["premium"] > 0:
            st.markdown(
                f'<div style="padding:10px;background:#0a1420;border-radius:6px;border-left:3px solid #fbbf24">'
                f'<div style="color:#fbbf24;font-size:0.7rem;font-weight:600;margin-bottom:4px">24 MONTHS TOTAL</div>'
                f'<div style="color:#fff;font-weight:800;font-size:1.2rem">{standalone_totals["24_month"]["premium"]:,.2f} AED</div>'
                f'<div style="color:#86efac;font-size:0.75rem;margin-top:4px">Commission: +{standalone_totals["24_month"]["commission"]:,.2f}</div>'
                f'</div>',
                unsafe_allow_html=True
            )
        
        st.markdown('</div></div></div>', unsafe_allow_html=True)
    
    # ===== TOTAL PARTNER COMMISSION Section =====
    if totals["standalone_item_count"] > 0 or (assurmax and not assurmax.get("error")):
        st.markdown(
            f'<div style="margin-top:24px;padding-top:20px;border-top:2px solid #3b7dd8">'
            f'<div style="color:#60a5fa;font-size:0.85rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:16px">💰 TOTAL PARTNER EARNINGS</div>',
            unsafe_allow_html=True
        )
        
        # Calculate total commission (ASSURMAX + Monthly standalone as example)
        commission_total = 0
        
        if assurmax and not assurmax.get("error"):
            commission_total += assurmax["commission"]
        
        if totals["standalone_item_count"] > 0:
            commission_total += standalone_totals["monthly"]["commission"]
        
        st.markdown(
            f'<div style="padding:20px;background:linear-gradient(135deg,#14532d,#0d1f18);border-radius:10px;border:2px solid #86efac">'
            f'<div style="display:flex;justify-content:space-between;align-items:center">'
            f'  <div style="color:#d4ffd9;font-size:0.85rem">Total Partner Commission</div>'
            f'  <div style="color:#86efac;font-weight:800;font-size:2rem">+{commission_total:,.2f} AED</div>'
            f'</div>'
            f'<div style="color:#a3e6b0;font-size:0.75rem;margin-top:8px">Based on selected plan (Monthly shown as example)</div>'
            f'</div>',
            unsafe_allow_html=True
        )
    
    st.markdown('</div>', unsafe_allow_html=True)



def _load_products_from_db():
    partner_id = st.session_state.partner_id
    session_start = st.session_state.session_start_time
    db = SessionLocal()
    try:
        base = db.query(Product).filter(Product.partner_id == partner_id)
        if session_start:
            base = base.filter(Product.scraped_at >= session_start)

        scraped = base.count()
        completed = base.filter(Product.processing_status == "completed").count()
        pending = base.filter(Product.processing_status == "processing").count()

        q = (
            db.query(
                Product.product_id, Product.product_name, Product.brand,
                Product.price, Product.currency, Product.category,
                Product.description, InsurancePackage.package_data, InsurancePackage.status,
            )
            .join(InsurancePackage, Product.product_id == InsurancePackage.product_id)
            .filter(Product.partner_id == partner_id, Product.processing_status == "completed")
        )
        if session_start:
            q = q.filter(Product.scraped_at >= session_start)

        rows = q.order_by(Product.processing_completed_at.desc()).all()

        eligible, not_eligible = [], []
        for row in rows:
            pkg = row.package_data
            pkg["product"] = {
                "name": row.product_name,
                "brand": row.brand,
                "price": float(row.price) if row.price else 0.0,
                "currency": row.currency,
                "category": row.category,
                "description": row.description,
            }
            pkg["product_id"] = str(row.product_id)
            is_elig = (
                pkg.get("eligible") is True
                or row.status == "eligible"
                or bool(pkg.get("standard_premium_12_months", {}).get("amount"))
            )
            (eligible if is_elig else not_eligible).append(pkg)

        return scraped, completed, pending, eligible, not_eligible
    finally:
        db.close()




def _assurmax_eligible(pkg: dict) -> bool:
    """Check if a product is eligible for ASSURMAX pack - CHECK BACKEND DATA"""
    # Check if backend already marked it as ASSURMAX eligible
    assurmax_data = pkg.get("assurmax_premium", {})
    
    # Return True if 'eligible' is True OR if the field exists (backward compatibility)
    return assurmax_data.get("eligible") is True or bool(assurmax_data)


def _assurmax_pack_total() -> float:
    """Sum of product prices × qty for every item in the pack"""
    total = 0.0
    for pid, in_pack in st.session_state.assurmax_selections.items():
        if not in_pack:
            continue
        sel = st.session_state.product_selections.get(pid, {})
        price = float(sel.get("product", {}).get("price", 0))
        total += price * sel.get("quantity", 1)
    return round(total, 2)


def _assurmax_pack_count() -> int:
    """Count of PRODUCTS (not items) in ASSURMAX pack"""
    return sum(1 for v in st.session_state.assurmax_selections.values() if v)


def _can_add_to_assurmax(product_id: str, qty: int = 1) -> tuple[bool, str]:
    """
    Check if a product can be added to ASSURMAX pack with STRICT cap enforcement
    
    Args:
        product_id: Product ID to check
        qty: Quantity being added
    
    Returns:
        (can_add: bool, reason: str)
    """
    # Check if product is selected
    if product_id not in st.session_state.product_selections:
        return False, "Product not selected"
    
    # Check if pack is full (3 products max)
    current_count = _assurmax_pack_count()
    is_already_in_pack = st.session_state.assurmax_selections.get(product_id, False)
    
    if current_count >= ASSURMAX_MAX_ITEMS and not is_already_in_pack:
        return False, f"Pack is full ({ASSURMAX_MAX_ITEMS} products maximum)"
    
    # STRICT: Check if adding this product would exceed the 5000 AED cap
    sel = st.session_state.product_selections.get(product_id, {})
    product_price = float(sel.get("product", {}).get("price", 0))
    product_total = product_price * qty
    
    # Get current pack total (excluding this product if already in pack)
    current_pack_total = 0.0
    for pid, in_pack in st.session_state.assurmax_selections.items():
        if not in_pack or pid == product_id:  # Skip current product
            continue
        other_sel = st.session_state.product_selections.get(pid, {})
        other_price = float(other_sel.get("product", {}).get("price", 0))
        current_pack_total += other_price * other_sel.get("quantity", 1)
    
    # Check if new total would exceed cap
    new_total = current_pack_total + product_total
    if new_total > ASSURMAX_TOTAL_CAP:
        excess = new_total - ASSURMAX_TOTAL_CAP
        return False, f"Would exceed 5,000 AED cap by {excess:,.2f} AED (Current: {current_pack_total:,.2f} + This product: {product_total:,.2f})"
    
    return True, ""




def _render_input_section():
    st.markdown('<div class="ga-section-title">Website</div>', unsafe_allow_html=True)
    website_url = st.text_input(
        "URL",
        placeholder="https://www.virginmegastore.ae/en",
        value=st.session_state.get("url", ""),
        label_visibility="collapsed",
    )

    st.markdown('<div class="ga-section-title" style="margin-top:24px">Product Categories</div>', unsafe_allow_html=True)
    st.caption("Select categories to filter. Leave all unchecked to process everything.")

    cats = list(AVAILABLE_CATEGORIES.items())
    num_cols = 4
    selected_categories = []
    for row in [cats[i:i+num_cols] for i in range(0, len(cats), num_cols)]:
        cols = st.columns(num_cols)
        for idx, (key, display) in enumerate(row):
            with cols[idx]:
                if st.checkbox(display, key=key):
                    selected_categories.append(key)

    st.session_state.selected_categories = selected_categories

    if selected_categories:
        st.success(f"✓ {len(selected_categories)} categories selected")
    else:
        st.info("ℹ️ No filter applied — all categories will be processed")

    st.markdown("<br>", unsafe_allow_html=True)

    if st.button("🚀 Start Real-time Processing", type="primary"):
        if not website_url:
            st.warning("Please enter a URL")
            st.stop()
        if not website_url.startswith(("http://", "https://")):
            st.error("URL must start with http:// or https://")
            st.stop()

        _, expected_name = get_partner_from_url(website_url)

        # Start backend job
        try:
            job_id = _api_start_job(website_url, selected_categories or None)
        except Exception as e:
            st.error(f"Backend unreachable or returned an error: {e}")
            st.stop()

        # Update session state
        st.session_state.job_id = job_id
        st.session_state.session_start_time = datetime.utcnow()
        st.session_state.pipeline_running = True
        st.session_state.configuration_mode = False
        st.session_state.url = website_url
        st.session_state.start_time = time.time()
        st.session_state.expected_partner_name = expected_name
        st.session_state.partner_id = None
        st.session_state.partner_name = expected_name
        st.session_state.product_selections = {}
        st.session_state.assurmax_selections = {}
        st.session_state.frozen_eligible_order = []
        st.session_state.assurmax_commission_rate = 0.10  # Default commission

        st.success("✓ Pipeline started successfully.")
        time.sleep(1)
        st.rerun()


# ============================================================
# RENDER: LIVE PIPELINE VIEW
# ============================================================

def _render_pipeline_view(scraped, completed, pending, eligible, not_eligible):
    elapsed = int(time.time() - (st.session_state.start_time or time.time()))

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Scraped", scraped)
    c2.metric("Eligible", len(eligible))
    c3.metric("Not Eligible", len(not_eligible))
    c4.metric("Processing", pending)
    c5.metric("Elapsed", f"{elapsed}s")

    if scraped > 0:
        st.progress(completed / scraped, text=f"{completed} / {scraped} processed")
    else:
        st.info("🔍 Discovering and scraping products…")

    if st.session_state.selected_categories:
        names = [AVAILABLE_CATEGORIES[c] for c in st.session_state.selected_categories]
        st.info(f"🔎 Filtering: {', '.join(names)}")

    if scraped == 0:
        st.info("⏳ Pipeline starting… discovering URLs")
    elif completed == 0:
        st.info(f"📦 Scraped {scraped} products, starting classification…")
    elif pending > 0:
        st.info("⚙️ Processing products in real-time…")
    else:
        st.success(f"✅ {completed} products processed so far")

    st.markdown("<br>", unsafe_allow_html=True)

    if st.button("⏸️ Stop & Configure Insurance", type="primary"):
        if st.session_state.job_id:
            _api_stop_job(st.session_state.job_id)
        st.session_state.pipeline_running = False
        st.session_state.configuration_mode = True
        st.session_state.frozen_eligible_order = [p["product_id"] for p in eligible]
        st.rerun()

    st.markdown("<hr style='border-color:#1e2d45'>", unsafe_allow_html=True)

    if eligible:
        st.markdown('<div class="ga-section-title">✅ Eligible Products</div>', unsafe_allow_html=True)
        for idx, pkg in enumerate(eligible, 1):
            name = pkg.get("product", {}).get("name", "Unknown")
            am_badge = ' · ASSURMAX' if _assurmax_eligible(pkg) else ''
            with st.expander(f"#{idx}  {name[:70]}{am_badge}", expanded=False):
                _render_product_info(pkg)
                _render_base_premiums(pkg)

    if not_eligible:
        st.markdown('<div class="ga-section-title" style="margin-top:20px">❌ Not Eligible</div>', unsafe_allow_html=True)
        for idx, pkg in enumerate(not_eligible, 1):
            name = pkg.get("product", {}).get("name", "Unknown")
            with st.expander(f"#{idx}  {name[:70]}", expanded=False):
                _render_product_info(pkg)
                st.error(f"Reason: {pkg.get('reason', 'Not eligible')}")

    if not eligible and not not_eligible and completed == 0:
        st.info("⏳ Waiting for first products…")




def _render_configuration_view(eligible, not_eligible):
    if not st.session_state.frozen_eligible_order:
        st.session_state.frozen_eligible_order = [p["product_id"] for p in eligible]

    frozen_ids = st.session_state.frozen_eligible_order
    pkg_map = {p["product_id"]: p for p in eligible}
    selections = st.session_state.product_selections

    # Calculate stats
    total_selected = len(selections)
    total_items = sum(s["quantity"] for s in selections.values())
    pack_count = _assurmax_pack_count()
    pack_total = _assurmax_pack_total()

    # Summary section - only show if products are selected
    if total_selected > 0:
        # Simple summary row
        st.markdown(f"""
        <div class="ga-summary-row">
            <div class="ga-summary-box">
                <div class="s-value">{total_selected}</div>
                <div class="s-label">Products Selected</div>
            </div>
            <div class="ga-summary-box">
                <div class="s-value">{total_items}</div>
                <div class="s-label">Total Items</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ASSURMAX pack bar - only if items in pack
        if pack_count > 0:
            cap_pct = min(pack_total / ASSURMAX_TOTAL_CAP * 100, 100)
            over_class = "over" if pack_total > ASSURMAX_TOTAL_CAP else ""

            item_pills = ""
            for pid, in_pack in st.session_state.assurmax_selections.items():
                if not in_pack:
                    continue
                raw_name = selections.get(pid, {}).get("product", {}).get("name", "—")
                display_name = (raw_name[:35] + "…") if len(raw_name) > 35 else raw_name
                item_pills += f'<span class="ga-pack-item">{display_name}</span>'

            warning = ""
            if pack_count >= ASSURMAX_MAX_ITEMS:
                warning = '<div style="color:#f87171;font-size:0.74rem;margin-top:8px">⚠️ Pack is full — maximum 3 products reached.</div>'
            
            # STRICT: Check if cap is exceeded
            cap_warning = ""
            if pack_total > ASSURMAX_TOTAL_CAP:
                excess = pack_total - ASSURMAX_TOTAL_CAP
                cap_warning = f'<div style="color:#ef4444;font-size:0.74rem;margin-top:8px;font-weight:700">🚫 EXCEEDS CAP by {excess:,.2f} AED — Remove items to continue</div>'

            remaining = max(0, ASSURMAX_TOTAL_CAP - pack_total)

            st.markdown(f"""
            <div class="ga-pack-bar">
                <div class="pack-title">🎁 ASSURMAX BUNDLE ({pack_count}/{ASSURMAX_MAX_ITEMS} products)</div>
                <div class="pack-meta">Fixed 550 AED premium · Up to 5,000 AED total coverage</div>
                <div class="pack-items">{item_pills}</div>
                <div class="ga-pack-cap-bar">
                    <div class="ga-pack-cap-fill {over_class}" style="width:{cap_pct}%"></div>
                </div>
                <div style="display:flex; justify-content:space-between; margin-top:8px; gap:16px;">
                    <span style="font-size:0.72rem; color:#a89060;">Value: <strong style="color:#c9a84c">{pack_total:,.2f} AED</strong></span>
                    <span style="font-size:0.72rem; color:#a89060;">Coverage remaining: <strong style="color:#a89060">{remaining:,.2f} AED</strong></span>
                </div>
                {warning}
                {cap_warning}
            </div>
            """, unsafe_allow_html=True)
            
            # ASSURMAX Commission Selection
            st.markdown('<div class="ga-section-title">Commission Rate for ASSURMAX Bundle</div>', unsafe_allow_html=True)
            assurmax_commission = st.selectbox(
                "Select commission rate:",
                options=["10%", "15%", "20%"],
                index=["10%", "15%", "20%"].index(f"{int(st.session_state.assurmax_commission_rate*100)}%"),
                key="assurmax_commission_select",
                label_visibility="collapsed"
            )
            st.session_state.assurmax_commission_rate = COMMISSION_RATES[assurmax_commission]

        # Calculate and display order totals
        totals = calculate_order_totals(
            st.session_state.product_selections,
            st.session_state.assurmax_selections,
            st.session_state.assurmax_commission_rate
        )
        _render_order_totals(totals)
        
        # Download button
        _render_download_button(selections, st.session_state.partner_name, totals)
        st.markdown("<br>", unsafe_allow_html=True)

    # Product cards
    st.markdown('<div class="ga-section-title">📦 Available Products</div>', unsafe_allow_html=True)
    
    for display_idx, pid in enumerate(frozen_ids, 1):
        pkg = pkg_map.get(pid)
        if pkg is None:
            continue
        _render_config_card(pkg, display_idx, pid)

    # Not-eligible collapsed
    if not_eligible:
        with st.expander(f"❌ Not Eligible Products ({len(not_eligible)})", expanded=False):
            for idx, pkg in enumerate(not_eligible, 1):
                name = pkg.get("product", {}).get("name", "Unknown")
                reason = pkg.get("reason", "Not eligible")
                st.markdown(
                    f'<div class="ga-ineligible-row">'
                    f'<span class="inel-name">#{idx}  {name[:65]}</span>'
                    f'<span class="inel-reason">{reason}</span></div>',
                    unsafe_allow_html=True,
                )




def _render_product_info(pkg):
    p = pkg.get("product", {})
    st.markdown(
        f'<div class="ga-info-strip">'
        f'<span class="label">Brand</span><span class="value">{p.get("brand","—")}</span>  ·  '
        f'<span class="label">Category</span><span class="value">{p.get("category","—")}</span>  ·  '
        f'<span class="label">Value</span><span class="value">{p.get("price","—")} {p.get("currency","AED")}</span>  ·  '
        f'<span class="label">Market</span><span class="value">{pkg.get("market","—")}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )
    risk = pkg.get("risk_profile")
    if risk:
        st.markdown(
            f'<div class="ga-info-strip"><span class="label">Risk Profile</span><span class="value">{risk}</span></div>',
            unsafe_allow_html=True,
        )
    desc = p.get("description")
    if desc and desc not in ("N/A", "", None):
        with st.expander("📄 Description", expanded=False):
            st.write(desc)


def _render_base_premiums(pkg):
    monthly = pkg.get("monthly_premium", {})
    std12 = pkg.get("standard_premium_12_months", {})
    std24 = pkg.get("standard_premium_24_months", {})
    c1, c2, c3 = st.columns(3)
    c1.metric("Monthly", f"{monthly.get('amount','—')} AED")
    c2.metric("12 Months", f"{std12.get('amount','—')} AED")
    c3.metric("24 Months", f"{std24.get('amount','—')} AED")



def _render_config_card(pkg: dict, display_idx: int, product_id: str):
    product = pkg.get("product", {})
    name = product.get("name", "Unknown")
    am_elig = _assurmax_eligible(pkg)

    is_selected = product_id in st.session_state.product_selections
    sel = st.session_state.product_selections.get(product_id, {})
    cur_qty = sel.get("quantity", 1)
    cur_comm = sel.get("commission_label", "10%")
    in_pack = st.session_state.assurmax_selections.get(product_id, False)

    # badges
    badge_html = '<span class="badge badge-eligible">Eligible</span>'
    if am_elig:
        badge_html += '<span class="badge badge-assurmax">ASSURMAX</span>'
    if is_selected:
        badge_html += '<span class="badge badge-selected">Selected</span>'

    card_class = "ga-card"
    if is_selected:
        card_class += " selected"
    if in_pack:
        card_class += " in-assurmax"

    st.markdown(
        f'<div class="{card_class}">'
        f'  <div>{badge_html}</div>'
        f'  <div class="ga-card-title">#{display_idx}  {name}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    _render_product_info(pkg)
    
    # Show coverage BEFORE selection controls
    modules = pkg.get("coverage_modules", [])
    exclusions = pkg.get("exclusions", [])
    
    if modules or exclusions:
        with st.expander("🛡️ Coverage Details", expanded=False):
            if modules:
                st.markdown("**✓ What's Covered:**")
                for idx, m in enumerate(modules[:5], 1):
                    st.markdown(f"{idx}. {m}")
                if len(modules) > 5:
                    st.caption(f"*... and {len(modules)-5} more coverage items*")
            
            if exclusions:
                st.markdown("**✗ What's NOT Covered:**")
                for idx, e in enumerate(exclusions[:3], 1):
                    st.markdown(f"{idx}. {e}")
                if len(exclusions) > 3:
                    st.caption(f"*... and {len(exclusions)-3} more exclusions*")
    
    st.markdown('<hr class="ga-card-divider">', unsafe_allow_html=True)

    # Selection controls in a container to prevent jumping
    with st.container():
        ctrl1, ctrl2, ctrl3 = st.columns([2.5, 1.2, 1.8])
        with ctrl1:
            selected = st.checkbox(
                "✓ Include in insurance package",
                value=is_selected,
                key=f"sel_{product_id}",
            )
        with ctrl2:
            quantity = st.number_input(
                "Quantity", min_value=1, max_value=100,
                value=cur_qty, key=f"qty_{product_id}",
                disabled=not selected,
            )
        with ctrl3:
            commission_label = st.selectbox(
                "Commission",
                options=list(COMMISSION_RATES.keys()),
                index=list(COMMISSION_RATES.keys()).index(cur_comm) if cur_comm in COMMISSION_RATES else 0,
                key=f"comm_{product_id}",
                disabled=not selected,
            )

    # sync selections
    if selected:
        st.session_state.product_selections[product_id] = {
            "product": product,
            "insurance": pkg,
            "quantity": quantity,
            "commission_rate": COMMISSION_RATES[commission_label],
            "commission_label": commission_label,
            "product_id": product_id,
            "assurmax_eligible": am_elig,
        }
    else:
        st.session_state.product_selections.pop(product_id, None)
        st.session_state.assurmax_selections.pop(product_id, None)

    # Show pricing and ASSURMAX options ONLY if selected
    if selected:
        # Pricing
        comm_rate = COMMISSION_RATES[commission_label]
        monthly = pkg.get("monthly_premium", {})
        std12 = pkg.get("standard_premium_12_months", {})
        std24 = pkg.get("standard_premium_24_months", {})

        boxes_html = '<div class="ga-pricing-row">'
        for label, raw in [("Monthly", monthly), ("12 Months", std12), ("24 Months", std24)]:
            gross = float(raw.get("amount", 0)) * quantity
            bd = calc_breakdown(gross, comm_rate)
            boxes_html += (
                f'<div class="ga-pricing-box">'
                f'  <div class="p-label">{label}</div>'
                f'  <div class="p-amount">{bd["gross"]:,.2f} AED</div>'
                f'  <div class="p-detail">Comm {bd["comm"]:,.2f} · Net {bd["net"]:,.2f}</div>'
                f'</div>'
            )
        boxes_html += '</div>'
        st.markdown(boxes_html, unsafe_allow_html=True)

        # ASSURMAX option
        if am_elig:
            can_add, reason = _can_add_to_assurmax(product_id, quantity)
            disabled = not can_add and not in_pack
            
            with st.expander("🎁 Add to ASSURMAX Bundle", expanded=in_pack):
                item_value = float(product.get("price", 0)) * quantity
                
                st.markdown(
                    f'<div style="padding:10px;background:#0f1e2e;border-radius:6px;margin-bottom:10px">'
                    f'<div style="color:#86efac;font-size:0.75rem;margin-bottom:4px">Product Value</div>'
                    f'<div style="color:#c9a84c;font-weight:700;font-size:1.1rem">{item_value:,.2f} AED</div>'
                    f'<div style="color:#6b7d99;font-size:0.7rem;margin-top:2px">Counts toward 5,000 AED cap</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                
                # Show bundle calculation if in pack
                if in_pack:
                    pack_items = []
                    for pid, in_pack_bool in st.session_state.assurmax_selections.items():
                        if in_pack_bool:
                            sel_item = st.session_state.product_selections.get(pid, {})
                            pack_items.append({
                                'price': float(sel_item.get("product", {}).get("price", 0)),
                                'qty': sel_item.get("quantity", 1),
                                'name': sel_item.get("product", {}).get("name", "")
                            })
                    
                    bundle = calculate_assurmax_bundle(pack_items, st.session_state.assurmax_commission_rate)
                    if bundle:
                        st.markdown(
                            f'<div style="padding:10px;background:#2a1f0633;border-radius:6px;border:1px solid #c9a84c44">'
                            f'<div style="color:#c9a84c;font-size:0.75rem;margin-bottom:6px">Bundle Premium</div>'
                            f'<div style="color:#fff;font-weight:800;font-size:1.3rem">{bundle["premium"]:,.2f} AED</div>'
                            f'<div style="color:#a89060;font-size:0.7rem;margin-top:4px">Fixed price for up to 5,000 AED coverage</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                        
                        if bundle.get("warning"):
                            st.markdown(
                                f'<div class="ga-warning-box" style="margin-top:8px">'
                                f'⚠️ {bundle["warning"]}'
                                f'</div>',
                                unsafe_allow_html=True
                            )
                
                add_to_pack = st.checkbox(
                    "✓ Add to ASSURMAX pack",
                    value=in_pack,
                    key=f"assurmax_{product_id}",
                    disabled=disabled,
                )
                
                if disabled and not in_pack:
                    st.error(f"🚫 {reason}")
                
                st.session_state.assurmax_selections[product_id] = add_to_pack

    st.markdown("<br>", unsafe_allow_html=True)




def _render_download_button(selections: dict, partner_name: str, totals: dict = None):
    selected_data = []
    assurmax_names = []

    for pid, s in selections.items():
        ins = s["insurance"]
        qty = s["quantity"]
        cr = s["commission_rate"]
        in_pack = st.session_state.assurmax_selections.get(pid, False)

        monthly_bd = calc_breakdown(float(ins.get("monthly_premium", {}).get("amount", 0)) * qty, cr)
        std12_bd = calc_breakdown(float(ins.get("standard_premium_12_months", {}).get("amount", 0)) * qty, cr)
        std24_bd = calc_breakdown(float(ins.get("standard_premium_24_months", {}).get("amount", 0)) * qty, cr)

        selected_data.append({
            "product": s["product"],
            "quantity": qty,
            "commission_rate": s["commission_label"],
            "assurmax_eligible": s.get("assurmax_eligible", False),
            "added_to_assurmax_pack": in_pack,
            "premiums": {
                "monthly": monthly_bd,
                "standard_12_months": std12_bd,
                "standard_24_months": std24_bd,
            },
            "insurance_details": ins,
        })
        if in_pack:
            assurmax_names.append(s["product"].get("name", ""))

    pack_total = _assurmax_pack_total()

    download_payload = {
        "metadata": {
            "partner": partner_name,
            "timestamp": datetime.utcnow().isoformat(),
            "total_products_selected": len(selections),
            "total_items": sum(s["quantity"] for s in selections.values()),
        },
        "assurmax_pack": {
            "cap_aed": ASSURMAX_TOTAL_CAP,
            "max_items": ASSURMAX_MAX_ITEMS,
            "items_in_pack": len(assurmax_names),
            "total_insured_value_aed": pack_total,
            "fixed_premium_aed": ASSURMAX_FIXED_PREMIUM,
            "premium_calculation": f"{ASSURMAX_TOTAL_CAP:,.0f} AED × 11% = {ASSURMAX_FIXED_PREMIUM:,.0f} AED",
            "commission_rate": st.session_state.assurmax_commission_rate,
            "products": assurmax_names,
        },
        "selected_products": selected_data,
    }
    
    # Add order totals if provided
    if totals:
        download_payload["order_totals"] = totals

    st.download_button(
        label="💾 Download Configuration (JSON)",
        data=json.dumps(download_payload, indent=2, ensure_ascii=False),
        file_name=f"{partner_name}_insurance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json",
        type="primary",
    )




_inject_css()
_init_session()

st.markdown(
    '<div class="ga-header">'
    '  <h1>🛡️ Garanty Affinity Insurance</h1>'
    '  <p>Real-time quote generation and insurance configuration</p>'
    '</div>',
    unsafe_allow_html=True,
)

# Application flow
if not st.session_state.pipeline_running and not st.session_state.configuration_mode:
    _render_input_section()
else:
    # Resolve partner_id
    if not st.session_state.partner_id and st.session_state.expected_partner_name:
        db = SessionLocal()
        try:
            partner = db.query(Partner).filter_by(company_name=st.session_state.expected_partner_name).first()
            if partner:
                st.session_state.partner_id = str(partner.partner_id)
                st.session_state.partner_name = partner.company_name
        finally:
            db.close()

    if not st.session_state.partner_id:
        st.info(f"⏳ Waiting for partner '{st.session_state.expected_partner_name}' to be created…")
        time.sleep(3)
        st.rerun()
        st.stop()

    scraped, completed, pending, eligible, not_eligible = _load_products_from_db()
    st.session_state.eligible_products = eligible
    st.session_state.not_eligible_products = not_eligible

    # Live pipeline view
    if st.session_state.pipeline_running:
        job_status = _api_job_status(st.session_state.job_id) if st.session_state.job_id else None

        if job_status and job_status.get("status") in _TERMINAL_STATUSES:
            st.session_state.pipeline_running = False
            st.session_state.configuration_mode = True
            st.session_state.frozen_eligible_order = [p["product_id"] for p in eligible]
            if job_status["status"] == "failed":
                st.error(f"❌ Pipeline failed: {job_status.get('progress', {}).get('error', 'unknown')}")
            st.rerun()
        else:
            _render_pipeline_view(scraped, completed, pending, eligible, not_eligible)
            time.sleep(3)
            st.rerun()

    # Configuration view
    elif st.session_state.configuration_mode:
        elapsed = int(time.time() - (st.session_state.start_time or time.time()))

        st.markdown('<div class="ga-section-title">⏸️ Pipeline Paused — Configure Insurance</div>', unsafe_allow_html=True)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("📦 Scraped", scraped)
        m2.metric("✅ Eligible", len(eligible))
        m3.metric("❌ Not Eligible", len(not_eligible))
        m4.metric("⏱️ Elapsed", f"{elapsed}s")

        st.markdown("<hr style='border-color:#1e2d45;margin:18px 0'>", unsafe_allow_html=True)

        _render_configuration_view(eligible, not_eligible)

        # Reset button
        st.markdown("<br><br>", unsafe_allow_html=True)
        if st.button("🔄 Start New Session", type="secondary"):
            if st.session_state.job_id:
                _api_stop_job(st.session_state.job_id)

            keys = [
                "pipeline_running", "configuration_mode", "job_id",
                "partner_id", "partner_name", "start_time", "session_start_time",
                "url", "expected_partner_name", "selected_categories",
                "product_selections", "assurmax_selections",
                "eligible_products", "not_eligible_products", "frozen_eligible_order",
                "assurmax_commission_rate",
            ]
            for k in keys:
                st.session_state.pop(k, None)
            _init_session()
            st.rerun()