from langchain_core.tools import tool
from typing import Union


# RATE MATRIX - Base rates per risk profile and value bucket
RATE_MATRIX = {
    # UAE 
    "ELECTRONIC_PRODUCTS": {"L": 0.08, "M": 0.095, "H": 0.11},
    "MOBILE_PERSONAL": {"L": 0.08, "M": 0.095, "H": 0.11},
    "COMPUTING_GAMING": {"L": 0.07, "M": 0.085, "H": 0.10},
    "HOME_AV": {"L": 0.06, "M": 0.075, "H": 0.09},
    
    "GARDEN_DIY_ESSENTIAL": {"L": 0.07, "M": 0.085, "H": 0.10},
    "SPORT_OUTDOOR_ESSENTIAL": {"L": 0.08, "M": 0.095, "H": 0.11},
    "BABY_EQUIPMENT_ESSENTIAL": {"L": 0.07, "M": 0.085, "H": 0.10},
    "HOME_APPLIANCES": {"L": 0.05, "M": 0.06, "H": 0.07},
    "HEALTH_WELLNESS_ESSENTIAL": {"L": 0.07, "M": 0.085, "H": 0.10},
    "MICRO_MOBILITY_ESSENTIAL": {"L": 0.09, "M": 0.11, "H": 0.13},
    "BAGS_LUGGAGE_ESSENTIAL": {"L": 0.06, "M": 0.075, "H": 0.09},
    "LIVING_FURNITURE_ESSENTIAL": {"L": 0.06, "M": 0.075, "H": 0.09},
    "OPTICAL_HEARING_ESSENTIAL": {"L": 0.07, "M": 0.085, "H": 0.10},
    "PERSONAL_CARE_DEVICES": {"L": 0.07, "M": 0.085, "H": 0.10},
    "SOUND_MUSIC_ESSENTIAL": {"L": 0.08, "M": 0.095, "H": 0.11},
    "OPULENCIA_PREMIUM": {"L": 0.10, "M": 0.12, "H": 0.15},
    "TEXTILE_FOOTWEAR_ZARA": {"L": 0.05, "M": 0.06, "H": 0.07},
    "SPECIALTY": {"L": 0.09, "M": 0.11, "H": 0.13},
    
    # Tunisia
    "ELECTRONIC_PRODUCTS_TN": {"L": 0.08, "M": 0.095, "H": 0.11},
    "GARDEN_DIY_TN": {"L": 0.07, "M": 0.085, "H": 0.10},
    "SPORT_OUTDOOR_TN": {"L": 0.08, "M": 0.095, "H": 0.11},
    "BABY_EQUIPMENT_TN": {"L": 0.07, "M": 0.085, "H": 0.10},
    "HOME_APPLIANCES_TN": {"L": 0.05, "M": 0.06, "H": 0.07},
    "HEALTH_WELLNESS_TN": {"L": 0.07, "M": 0.085, "H": 0.10},
    "FURNITURE_TN": {"L": 0.06, "M": 0.075, "H": 0.09},
}


# DURATION FACTOR ONLY - NO PACK FACTOR!
DURATION_FACTOR = {
    12: 1.00,
    24: 1.35
}


# VALUE BUCKETS
BUCKETS_BY_PROFILE_TN = {
    "ELECTRONIC_PRODUCTS_TN": [(1500, "L"), (4000, "M"), (8000, "H")],
    "BABY_EQUIPMENT_TN": [(400, "L"), (1200, "M"), (3000, "H")],
    "FURNITURE_TN": [(800, "L"), (2000, "M"), (5000, "H")],
    "GARDEN_DIY_TN": [(500, "L"), (1500, "M"), (3500, "H")],
    "HEALTH_WELLNESS_TN": [(300, "L"), (900, "M"), (2000, "H")],
    "HOME_APPLIANCES_TN": [(2000, "L"), (4500, "M"), (7500, "H")],
    "SPORT_OUTDOOR_TN": [(400, "L"), (1200, "M"), (3000, "H")],
}

BUCKETS_UAE_DEFAULT = [(2000, "L"), (6000, "M"), (float('inf'), "H")]

BUCKETS_BY_PROFILE_UAE = {
    "HOME_APPLIANCES": [(2000, "L"), (6000, "M"), (11000, "H")],
    "OPULENCIA_PREMIUM": [(3000, "M"), (10000, "M"), (50000, "H"), (300000, "XH")],
}


def get_bucket(price: float, market: str = "UAE", risk_profile: str = "") -> str:
    """Determine the price bucket (L/M/H) based on market and risk profile."""
    market_lower = market.lower()
    
    if "tunisia" in market_lower or "tn" in market_lower:
        profile_buckets = BUCKETS_BY_PROFILE_TN.get(risk_profile, [])
        
        if profile_buckets:
            for limit, label in profile_buckets:
                if price <= limit:
                    return label
            return profile_buckets[-1][1]
        
        if price <= 400:
            return "L"
        elif price <= 1200:
            return "M"
        else:
            return "H"
    
    else:
        profile_buckets = BUCKETS_BY_PROFILE_UAE.get(risk_profile, BUCKETS_UAE_DEFAULT)
        
        for limit, label in profile_buckets:
            if price <= limit:
                return label
        
        return "H"


def get_coverage_caps(plan: str, market: str, risk_profile: str) -> dict:
    """
    Get coverage caps for ASSURMAX/ASSURMAX+ plans.
    Returns per_item_cap and pack_cap.
    """
    plan_upper = plan.upper()
    market_lower = market.lower()
    
    caps = {
        "per_item_cap": None,
        "pack_cap": None,
        "currency": "AED" if market_lower == "uae" else "TND"
    }
    
    # ELECTRONICS (from ASSURMAX_ELECTRONICS docs)
    electronics_profiles = [
        "ELECTRONIC_PRODUCTS", "ELECTRONIC_PRODUCTS_TN", 
        "MOBILE_PERSONAL", "COMPUTING_GAMING", "HOME_AV", "SPECIALTY"
    ]
    
    if risk_profile in electronics_profiles:
        if market_lower == "uae":
            if plan_upper == "ASSURMAX":
                caps["per_item_cap"] = 4000
                caps["pack_cap"] = 8000
            elif plan_upper == "ASSURMAX+":
                caps["per_item_cap"] = 6000
                caps["pack_cap"] = 12000
        elif market_lower == "tunisia":
            if plan_upper == "ASSURMAX":
                caps["per_item_cap"] = 2500
                caps["pack_cap"] = 2500
            elif plan_upper == "ASSURMAX+":
                caps["per_item_cap"] = 5000
                caps["pack_cap"] = 5000
    
    # LUXURY (from ASSURMAX_LUXURY doc)
    elif risk_profile == "OPULENCIA_PREMIUM" and market_lower == "uae":
        caps["per_item_cap"] = 60000
        caps["pack_cap"] = None
    
    # TEXTILE (from ASSURMAX_TEXTILE doc)
    elif risk_profile == "TEXTILE_FOOTWEAR_ZARA":
        # Textile: fixed price per item, retail value reimbursement
        caps["per_item_cap"] = None
        caps["pack_cap"] = None
        caps["note"] = "Fixed price per item, reimbursement based on retail value"
    
    return caps


@tool
def calculate_pricing(
    risk_profile: str,
    product_value: Union[float, int, str],  
    market: str = "UAE",
    duration_months: int = 12,
    plan: str = "standard"
) -> dict:
    """
    Calculate insurance pricing based on risk profile and product value.
    
    Args:
        risk_profile: Product risk category (e.g., ELECTRONIC_PRODUCTS, OPULENCIA_PREMIUM)
        product_value: Product price in AED or TND
        market: Market region (UAE or Tunisia)
        duration_months: Coverage duration (12 or 24 months)
        plan: Plan type (ASSURMAX, ASSURMAX+, or standard)
    
    Returns:
        Dictionary with pricing details including premiums, buckets, and coverage caps
    """
    
    try:
        product_value_float = float(product_value) if product_value else 0.0
    except (ValueError, TypeError):
        product_value_float = 0.0
    
    if product_value_float <= 0:
        return {"error": "Invalid product value"}
    
    plan_upper = plan.upper()
    
    # ✅ NEW: Get coverage caps FIRST
    coverage_caps = None
    insured_value = product_value_float  # Start with full value
    
    if plan_upper in ["ASSURMAX", "ASSURMAX+"]:
        coverage_caps = get_coverage_caps(plan, market, risk_profile)
        per_item_cap = coverage_caps.get("per_item_cap")
        
        # ✅ Apply cap to insured value
        if per_item_cap and product_value_float > per_item_cap:
            insured_value = per_item_cap
            print(f"   💡 Product value {product_value_float} exceeds {plan_upper} cap.")
            print(f"   💡 Premium calculated on capped value: {insured_value}")
    
    # Get duration factor
    duration_factor = DURATION_FACTOR.get(duration_months, 1.0)
    
    # Determine bucket (use insured_value, not full value)
    bucket = get_bucket(insured_value, market, risk_profile)
    
    # Get base rate
    rate = RATE_MATRIX.get(risk_profile, {}).get(bucket, 0.08)
    
    # ✅ Calculate premium using INSURED VALUE (not product value)
    gross_premium = (
        insured_value    # ← Use capped value
        * rate 
        * duration_factor
    )
    
    # Determine currency
    currency = "TND" if "tunisia" in market.lower() else "AED"
    
    # Calculate 12-month and 24-month premiums
    premium_12_months = round(gross_premium, 2)
    premium_24_months = round(gross_premium * DURATION_FACTOR.get(24, 1.35), 2)
    
    return {
        "plan": plan_upper,
        "12_months": {
            "annual_premium": premium_12_months,
            "currency": currency
        },
        "24_months": {
            "total_premium": premium_24_months,
            "currency": currency
        },
        "bucket": bucket,
        "base_rate_percent": round(rate * 100, 1),
        "duration_months": duration_months,
        "product_value": product_value_float,      # ← Original value
        "insured_value": insured_value,            # ← NEW: Capped value
        "risk_profile": risk_profile,
        "duration_factor": duration_factor,
        "coverage_caps": coverage_caps if coverage_caps else None
    }
