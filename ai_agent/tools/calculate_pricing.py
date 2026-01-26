from langchain_core.tools import tool
from typing import Union




ASSURMAX_CONFIG = {
    "UAE": {
        "pack_cap": 5000,
        "currency": "AED",
        "premium_rate": 0.11,  # 11%
        "max_products": 3
    }
}




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

# DURATION FACTOR 
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



@tool
def calculate_pricing(
    risk_profile: str = "",
    product_value: Union[float, int, str] = 0,
    market: str = "UAE",
    duration_months: int = 12,
    plan: str = "STANDARD"
) -> dict:
    """
    Calculate insurance pricing with NEW SIMPLIFIED ASSURMAX LOGIC.
    
    UAE: Returns STANDARD premiums (12m & 24m) + ASSURMAX premium if eligible
    Tunisia: Returns STANDARD premiums (12m & 24m) only
    
    Args:
        risk_profile: Product risk category (required for STANDARD plans)
        product_value: Product price in AED or TND
        market: Market region (UAE or Tunisia)
        duration_months: Coverage duration (12 or 24 months)
        plan: "ASSURMAX" or "STANDARD"
    
    Returns:
        Dictionary with pricing details
    """
    
    # Convert product value
    try:
        product_value_float = float(product_value) if product_value else 0.0
    except (ValueError, TypeError):
        product_value_float = 0.0
    
    if product_value_float <= 0:
        return {"error": "Invalid product value"}
    
    plan_upper = plan.upper()
    market_upper = market.upper()
    
  
    if plan_upper == "ASSURMAX":
        if market_upper != "UAE":
            return {
                "error": "ASSURMAX is only available for UAE market",
                "market": market_upper
            }
        
        config = ASSURMAX_CONFIG["UAE"]
        pack_cap = config["pack_cap"]
        currency = config["currency"]
        premium_rate = config["premium_rate"]
        max_products = config["max_products"]
        
        # Check if product exceeds pack cap
        if product_value_float > pack_cap:
            return {
                "error": f"Product value ({product_value_float} {currency}) exceeds ASSURMAX pack cap ({pack_cap} {currency})",
                "plan": "ASSURMAX",
                "pack_cap": pack_cap,
                "currency": currency,
                "eligible": False,
                "reason": f"Product price must be ≤ {pack_cap} {currency} for ASSURMAX"
            }
        
        # Calculate flat premium (11% of pack cap = 550 AED)
        annual_premium = pack_cap * premium_rate
        
        return {
            "plan": "ASSURMAX",
            "market": market_upper,
            
            "12_months": {
                "annual_premium": round(annual_premium, 2),
                "currency": currency
            },
            
            "24_months": {
                "total_premium": round(annual_premium * 2, 2),
                "currency": currency
            },
            
            "assurmax_pack_cap": {
                "pack_cap": pack_cap,
                "currency": currency,
                "max_products_covered": max_products
            },
            
            "product_value": product_value_float,
            "premium_rate_percent": round(premium_rate * 100, 1)
        }
    
    # ==========================================
    # STANDARD PRICING (UAE & TUNISIA)
    # ==========================================
    elif plan_upper == "STANDARD":
        if not risk_profile:
            return {"error": "risk_profile is required for STANDARD pricing"}
        
        # Determine bucket
        bucket = get_bucket(product_value_float, market, risk_profile)
        
        # Get base rate
        rate = RATE_MATRIX.get(risk_profile, {}).get(bucket)
        
        if not rate:
            return {
                "error": f"No rate found for risk_profile '{risk_profile}' in bucket '{bucket}'",
                "risk_profile": risk_profile,
                "bucket": bucket
            }
        
        # Determine currency
        currency = "TND" if "tunisia" in market.lower() or "tn" in market.lower() else "AED"
        
        # Calculate premiums
        premium_12_months = round(product_value_float * rate, 2)
        premium_24_months = round(premium_12_months * DURATION_FACTOR[24], 2)
        
        return {
            "plan": "STANDARD",
            "market": market_upper,
            
            "12_months": {
                "annual_premium": premium_12_months,
                "currency": currency
            },
            
            "24_months": {
                "total_premium": premium_24_months,
                "currency": currency
            },
            
            "product_value": product_value_float,
            "risk_profile": risk_profile,
            "bucket": bucket,
            "base_rate_percent": round(rate * 100, 1)
        }
    
    else:
        return {
            "error": f"Invalid plan: {plan}. Valid options: ASSURMAX (UAE only), STANDARD",
            "valid_plans": {
                "UAE": ["ASSURMAX", "STANDARD"],
                "Tunisia": ["STANDARD"]
            }
        }
