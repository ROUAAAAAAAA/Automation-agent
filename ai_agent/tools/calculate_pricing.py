from langchain_core.tools import tool
from typing import Union

ASSURMAX_CONFIG = {
    "UAE": {
        "pack_cap": 5000,
        "currency": "AED",
        "premium": 550.0,
        "max_products": 3,
    }
}

CATEGORY_RATE_MATRIX = {
    "BABY_EQUIPMENT_ESSENTIAL": (0.055, 1.25),
    "BAGS_LUGGAGE_ESSENTIAL": (0.065, 1.25),
    "APPLE_PRODUCTS": (0.11, 1.35),
    "ELECTRONIC_PRODUCTS": (0.05, 1.25),
    "HOME_APPLIANCES": (0.04, 1.2),
    "LIVING_FURNITURE_ESSENTIAL": (0.05, 1.2),
    "MICRO_MOBILITY_ESSENTIAL": (0.08, 1.25),
    "OPTICAL_HEARING_ESSENTIAL": (0.05, 1.2),
    "PERSONAL_CARE_DEVICES": (0.05, 1.24),
    "OPULENCIA_PREMIUM": (0.065, 1.25),
    "SOUND_MUSIC_ESSENTIAL": (0.05, 1.2),
    "SPORT_OUTDOOR_ESSENTIAL": (0.04, 1.2),
    "TEXTILE_FOOTWEAR_ZARA": (0.03, 1.2),
    "ELECTRONIC_PRODUCTS_TN": (0.05, 1.25),
    "BABY_EQUIPMENT_TN": (0.055, 1.25),
    "HOME_APPLIANCES_TN": (0.04, 1.2),
    "GARDEN_DIY_TN": (0.05, 1.25),
    "HEALTH_WELLNESS_TN": (0.06, 1.25),
    "FURNITURE_TN": (0.05, 1.2),
    "SPORT_OUTDOOR_TN": (0.04, 1.2),
}

@tool
def calculate_pricing(
    risk_profile: str = "",
    product_value: Union[float, int, str] = 0,
    market: str = "UAE",
    plan: str = "STANDARD",
) -> dict:
    """
    Calculate insurance pricing 
   
    
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
                "market": market_upper,
            }

        config = ASSURMAX_CONFIG["UAE"]
        pack_cap = config["pack_cap"]
        currency = config["currency"]
        flat_premium = config["premium"]
        max_products = config["max_products"]

        if product_value_float > pack_cap:
            return {
                "error": f"Product value ({product_value_float} {currency}) exceeds ASSURMAX pack cap ({pack_cap} {currency})",
                "plan": "ASSURMAX",
                "pack_cap": pack_cap,
                "currency": currency,
                "eligible": False,
                "reason": f"Product price must be ≤ {pack_cap} {currency} for ASSURMAX",
            }

        monthly_premium = round((flat_premium * 1.05) / 12, 2)

        return {
            "plan": "ASSURMAX",
            "market": market_upper,
            "monthly": {
                "monthly_premium": monthly_premium,
                "currency": currency,
            },
            "12_months": {
                "annual_premium": flat_premium,
                "currency": currency,
            },
            "24_months": {
                "total_premium": flat_premium * 2,
                "currency": currency,
            },
            "assurmax_pack_cap": {
                "pack_cap": pack_cap,
                "currency": currency,
                "max_products_covered": max_products,
            },
            "product_value": product_value_float,
            "flat_premium": True,
        }

    elif plan_upper == "STANDARD":
        if not risk_profile:
            return {"error": "risk_profile is required for STANDARD pricing"}

        if risk_profile not in CATEGORY_RATE_MATRIX:
            return {
                "error": f"Risk profile '{risk_profile}' not found in rate matrix",
                "valid_profiles": list(CATEGORY_RATE_MATRIX.keys()),
                "risk_profile": risk_profile,
            }

        rate_12m, duration_factor_24m = CATEGORY_RATE_MATRIX[risk_profile]

        currency = "TND" if "tunisia" in market.lower() or "tn" in market.lower() else "AED"

        premium_12_months = round(product_value_float * rate_12m, 2)
        premium_24_months = round(premium_12_months * duration_factor_24m, 2)
        monthly_premium = round((premium_12_months * 1.05) / 12, 2)

        return {
            "plan": "STANDARD",
            "market": market_upper,
            "monthly": {
                "monthly_premium": monthly_premium,
                "currency": currency,
            },
            "12_months": {
                "annual_premium": premium_12_months,
                "currency": currency,
            },
            "24_months": {
                "total_premium": premium_24_months,
                "currency": currency,
            },
            "product_value": product_value_float,
            "risk_profile": risk_profile,
            "rate_12m_percent": round(rate_12m * 100, 2),
            "duration_factor_24m": duration_factor_24m,
        }

    else:
        return {
            "error": f"Invalid plan: {plan}. Valid options: ASSURMAX, STANDARD",
            "valid_plans": {
                "UAE": ["ASSURMAX", "STANDARD"],
                "Tunisia": ["STANDARD"],
            },
        }
