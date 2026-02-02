from langchain_core.tools import tool
from typing import Union

# ============================================================
# NEW RATE MATRIX FROM CSV FILE
# ============================================================

# Based on products_pricing1-Products-Pricing.csv
RATE_MATRIX_CSV = {
    # Category: (12_month_rate, 24_month_duration_factor)
    
    # UAE Categories
    "ELECTRONIC_PRODUCTS": (0.095, 1.35),  # Electronics: 9.5%, factor 1.35
    "MOBILE_PERSONAL": (0.095, 1.35),       # Part of Electronics
    "COMPUTING_GAMING": (0.095, 1.35),      # Part of Electronics
    "HOME_AV": (0.095, 1.35),               # Part of Electronics
    
    "APPLE_PRODUCTS": (0.15, 1.4),          # Apple: 15%, factor 1.4 (special)
    
    "HOME_APPLIANCES": (0.095, 1.35),       # Home Appliances: 9.5%, factor 1.35
    
    "BABY_EQUIPMENT_ESSENTIAL": (0.115, 1.35),   # Baby: 11.5%, factor 1.35
    
    "BAGS_LUGGAGE_ESSENTIAL": (0.125, 1.4),      # Bags: 12.5%, factor 1.4
    
    "GARDEN_DIY_ESSENTIAL": (0.11, 1.4),         # Garden: 11%, factor 1.4
    
    "HEALTH_WELLNESS_ESSENTIAL": (0.115, 1.35),  # Health: 11.5%, factor 1.35
    
    "LIVING_FURNITURE_ESSENTIAL": (0.10, 1.35),  # Furniture: 10%, factor 1.35
    
    "MICRO_MOBILITY_ESSENTIAL": (0.12, 1.4),     # Bikes: 12%, factor 1.4
    
    "OPTICAL_HEARING_ESSENTIAL": (0.08, 1.4),    # Optical: 8%, factor 1.4
    
    "PERSONAL_CARE_DEVICES": (0.11, 1.4),        # Personal Care: 11%, factor 1.4
    
    "OPULENCIA_PREMIUM": (0.11, 1.4),            # Luxury: 11%, factor 1.4
    
    "SOUND_MUSIC_ESSENTIAL": (0.08, 1.4),        # Music: 8%, factor 1.4
    
    "SPORT_OUTDOOR_ESSENTIAL": (0.08, 1.4),      # Sport: 8%, factor 1.4
    
    "TEXTILE_FOOTWEAR_ZARA": (0.07, 1.35),       # Textiles: 7%, factor 1.35
    
    # Tunisia Categories (same rates, add _TN suffix)
    "ELECTRONIC_PRODUCTS_TN": (0.095, 1.35),
    "BABY_EQUIPMENT_TN": (0.115, 1.35),
    "HOME_APPLIANCES_TN": (0.095, 1.35),
    "GARDEN_DIY_TN": (0.11, 1.4),
    "HEALTH_WELLNESS_TN": (0.115, 1.35),
    "FURNITURE_TN": (0.10, 1.35),
    "SPORT_OUTDOOR_TN": (0.08, 1.4),
}


# ASSURMAX remains unchanged
ASSURMAX_CONFIG = {
    "UAE": {
        "pack_cap": 5000,
        "currency": "AED",
        "premium": 550.0,  # Flat premium
        "max_products": 3
    }
}


@tool
def calculate_pricing(
    risk_profile: str = "",
    product_value: Union[float, int, str] = 0,
    market: str = "UAE",
    plan: str = "STANDARD"
) -> dict:
    """
    Calculate insurance pricing using SIMPLIFIED FLAT RATES from CSV.
    
    NO BUCKETS (L/M/H) - Just apply flat percentage rate to product value.
    
    UAE: Returns STANDARD premiums (12m & 24m) + MONTHLY + ASSURMAX premium if eligible
    Tunisia: Returns STANDARD premiums (12m & 24m) + MONTHLY only
    
    Monthly Premium = (Yearly Premium × 1.05) / 12
    
    Args:
        risk_profile: Product risk category (required for STANDARD plans)
        product_value: Product price in AED or TND
        market: Market region (UAE or Tunisia)
        plan: "ASSURMAX" or "STANDARD"
    
    Returns:
        Dictionary with pricing details including monthly premium
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
    
    # ==========================================
    # ASSURMAX PRICING (UAE ONLY)
    # ==========================================
    if plan_upper == "ASSURMAX":
        if market_upper != "UAE":
            return {
                "error": "ASSURMAX is only available for UAE market",
                "market": market_upper
            }
        
        config = ASSURMAX_CONFIG["UAE"]
        pack_cap = config["pack_cap"]
        currency = config["currency"]
        flat_premium = config["premium"]
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
        
        # Calculate monthly premium: (yearly × 1.05) / 12
        monthly_premium = round((flat_premium * 1.05) / 12, 2)
        
        # Flat premium: 550 AED regardless of product value
        return {
            "plan": "ASSURMAX",
            "market": market_upper,
            
            "monthly": {
                "monthly_premium": monthly_premium,
                "currency": currency
            },
            
            "12_months": {
                "annual_premium": flat_premium,
                "currency": currency
            },
            
            "24_months": {
                "total_premium": flat_premium * 2,  # 1100 AED for 2 years
                "currency": currency
            },
            
            "assurmax_pack_cap": {
                "pack_cap": pack_cap,
                "currency": currency,
                "max_products_covered": max_products
            },
            
            "product_value": product_value_float,
            "flat_premium": True
        }
    
    # ==========================================
    # STANDARD PRICING (FLAT RATE - NO BUCKETS)
    # ==========================================
    elif plan_upper == "STANDARD":
        if not risk_profile:
            return {"error": "risk_profile is required for STANDARD pricing"}
        
        # Get rate from CSV mapping
        if risk_profile not in RATE_MATRIX_CSV:
            return {
                "error": f"Risk profile '{risk_profile}' not found in rate matrix",
                "valid_profiles": list(RATE_MATRIX_CSV.keys()),
                "risk_profile": risk_profile
            }
        
        rate_12m, duration_factor_24m = RATE_MATRIX_CSV[risk_profile]
        
        # Determine currency
        currency = "TND" if "tunisia" in market.lower() or "tn" in market.lower() else "AED"
        
        # Calculate premiums (NO BUCKETS - simple multiplication)
        premium_12_months = round(product_value_float * rate_12m, 2)
        premium_24_months = round(premium_12_months * duration_factor_24m, 2)
        
        # Calculate monthly premium: (yearly × 1.05) / 12
        monthly_premium = round((premium_12_months * 1.05) / 12, 2)
        
        return {
            "plan": "STANDARD",
            "market": market_upper,
            
            "monthly": {
                "monthly_premium": monthly_premium,
                "currency": currency
            },
            
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
            "rate_12m_percent": round(rate_12m * 100, 2),
            "duration_factor_24m": duration_factor_24m
        }
    
    else:
        return {
            "error": f"Invalid plan: {plan}. Valid options: ASSURMAX , STANDARD",
            "valid_plans": {
                "UAE": ["ASSURMAX", "STANDARD"],
                "Tunisia": ["STANDARD"]
            }
        }
