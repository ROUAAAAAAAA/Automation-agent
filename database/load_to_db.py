import json
import os
import sys
import uuid
import re
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

current_dir = Path(__file__).parent
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))

from database.models import Base, Partner, Product

# ------------------------------------------------------------------------------
# DB SETUP
# ------------------------------------------------------------------------------

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base.metadata.create_all(bind=engine)

# ------------------------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------------------------

# Map domains to country codes
DOMAIN_COUNTRY_MAP = {
    # UAE sites
    "jumbo.ae": "AE",
    "noon.com": "AE",
    "sharafdg.com": "AE",
    "amazon.ae": "AE",
    
    # Tunisia sites
    "jumia.com.tn": "TN",
    "tunisianet.com.tn": "TN",
    "mytek.tn": "TN",
}

# Only allow AED and TND
ALLOWED_CURRENCIES = {"AED", "TND"}

# Map scraped currency symbols to ISO codes
CURRENCY_NORMALIZATION = {
    # AED (UAE Dirham)
    "AED": "AED",
    "D": "AED",        # Common abbreviation on UAE sites
    "د.إ": "AED",     # Arabic AED symbol (full)
    "د.إ.‏": "AED",   # Arabic AED with extra characters
    "د": "AED",        # Short Arabic form
    "DH": "AED",       # Alternative abbreviation
    "DHM": "AED",      # Dirham abbreviation
    
    # TND (Tunisian Dinar)
    "TND": "TND",
    "DT": "TND",       # Common abbreviation (Dinar Tunisien)
    "د.ت": "TND",     # Arabic TND symbol
    "ت": "TND",        # Short Arabic form for Tunisian Dinar
    "DIN": "TND",      # Alternative abbreviation
}

def get_country_from_domain(domain: str) -> str:
    """
    Map domain to ISO 3166-1 alpha-2 country code.
    """
    domain = domain.lower().replace("www.", "")
    
    # Exact match
    if domain in DOMAIN_COUNTRY_MAP:
        return DOMAIN_COUNTRY_MAP[domain]
    
    # Check if domain ends with country TLD
    if domain.endswith(".tn"):
        return "TN"
    if domain.endswith(".ae"):
        return "AE"
    
    # Default to AE
    return "AE"

def normalize_currency(raw_currency: str) -> str | None:
    """
    Normalize currency symbols to ISO codes (AED/TND only).
    Returns None if currency is invalid or unsupported.
    """
    if not raw_currency:
        return None
    
    # Clean up the currency string
    cleaned = raw_currency.strip().upper()
    
    # Try direct mapping
    if cleaned in CURRENCY_NORMALIZATION:
        return CURRENCY_NORMALIZATION[cleaned]
    
    # Try with original casing for Arabic symbols
    cleaned_original = raw_currency.strip()
    if cleaned_original in CURRENCY_NORMALIZATION:
        return CURRENCY_NORMALIZATION[cleaned_original]
    
    return None

def parse_price(value) -> float | None:
    """
    Extract numeric price from ANY format.
    Examples:
      "1,299.00" -> 1299.0
      "839,000" -> 839000.0
      "1 199,000" -> 1199000.0
      "Free" -> None
    """
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value) if value > 0 else None

    if isinstance(value, str):
        # Remove ALL non-digit characters except decimal point
        # This handles commas, spaces, and any other separators
        cleaned = ""
        for char in value:
            if char.isdigit() or char == '.':
                cleaned += char
        
        # Handle empty string after cleaning
        if not cleaned:
            return None
            
        try:
            price = float(cleaned)
            return price if price > 0 else None
        except ValueError:
            return None

    return None

def normalize_url(url: str) -> str | None:
    """
    Fix malformed URLs from scraper.
    Returns None if URL is invalid.
    """
    if not url:
        return None
    
    url = url.strip()
    
    # Reject invalid URLs
    if url in ["Unknown URL", "unknown", ""]:
        return None
    
    # Fix missing protocol (httpswww.jumbo.ae -> https://www.jumbo.ae)
    if url.startswith("httpswww.") or url.startswith("httpwww."):
        url = url.replace("httpswww.", "https://www.")
        url = url.replace("httpwww.", "http://www.")
    elif url.startswith("https") and "://" not in url:
        url = url.replace("https", "https://", 1)
    elif url.startswith("http") and "://" not in url:
        url = url.replace("http", "http://", 1)
    
    # Must start with http:// or https://
    if not url.startswith(("http://", "https://")):
        return None
    
    return url

def validate_and_clean_product(raw: dict, domain: str) -> dict | None:
    """
    Returns CLEAN product dict or None.
    Loads ONLY products with:
      - valid URL (not "Unknown URL")
      - price > 0
      - currency in {AED, TND}
    """
    p = raw.copy()

    # Required fields
    if not p.get("product_name"):
        return None

    # Normalize URL (just fix formatting, don't validate if it's a product page)
    product_url = normalize_url(p.get("product_url"))
    if not product_url:
        return None

    # Price (must exist and be > 0)
    price = parse_price(p.get("price"))
    if price is None:
        return None

    # Normalize currency
    raw_currency = p.get("currency")
    currency = normalize_currency(raw_currency)
    
    # Only accept AED and TND
    if currency not in ALLOWED_CURRENCIES:
        return None

    return {
        "product_name": p["product_name"].strip(),
        "description": p.get("description", "").strip() if p.get("description") else "",
        "brand": p.get("brand") or "Unknown",
        "category": p.get("category"),
        "price": price,
        "currency": currency,
        "product_url": product_url,
        "image_url": p.get("image_url"),
        "in_stock": bool(p.get("in_stock", True)),
    }

# ------------------------------------------------------------------------------
# MAIN LOADER
# ------------------------------------------------------------------------------

def load_products_from_json(json_path: str):
    json_path = Path(json_path)
    if not json_path.exists():
        raise FileNotFoundError(json_path)

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
       products = data.get("products", [])
       print(f"\n🔍 DEBUG: Loaded {len(products)} products from JSON")
    
    # Check first 5 products with prices
       count = 0
       for p in products:
           if p.get("price") and count < 10:
              print(f"\n  Product: {p.get('product_name', 'NO NAME')[:50]}")
              print(f"  Price (raw): {p.get('price')} | Type: {type(p.get('price'))}")
              print(f"  Currency (raw): {p.get('currency')}")
            
            # Test parse_price
              parsed = parse_price(p.get("price"))
              print(f"  After parse_price(): {parsed}")
            
            # Test currency normalize
              normalized = normalize_currency(p.get("currency"))
              print(f"  After normalize_currency(): {normalized}")
              count += 1

    if isinstance(data, dict):
        products = data.get("products", [])
        domain = data.get("metadata", {}).get("domain", "unknown")
        start_url = data.get("metadata", {}).get("start_url")
    elif isinstance(data, list):
        products = data
        domain = json_path.stem.split("_")[0]
        start_url = None
    else:
        raise ValueError("Invalid JSON format")

    if not products:
        print("⚠️ No products found")
        return 0

    db = SessionLocal()

    try:
        # Get partner name
        partner_name = domain.replace("www.", "").replace(".com", "").title()
        if "noon" in partner_name.lower():
            partner_name = "Noon"
        
        # Get country code
        country_code = get_country_from_domain(domain)

        # Find or create partner
        partner = db.query(Partner).filter_by(company_name=partner_name).first()
        if not partner:
            partner = Partner(
                company_name=partner_name,
                website_url=start_url or f"https://{domain}",
                country=country_code,
                status="scraped",
            )
            db.add(partner)
            db.commit()

        added = skipped = duplicates = 0

        for raw in products:
            if not isinstance(raw, dict):
                skipped += 1
                continue

            clean = validate_and_clean_product(raw, domain)
            if not clean:
                skipped += 1
                continue

            # Check for duplicates
            exists = db.query(Product).filter_by(
                partner_id=partner.partner_id,
                product_url=clean["product_url"],
            ).first()

            if exists:
                duplicates += 1
                continue

            # Add product
            db.add(
                Product(
                    product_id=uuid.uuid4(),
                    partner_id=partner.partner_id,
                    product_name=clean["product_name"],
                    description=clean["description"],
                    category=clean["category"],
                    brand=clean["brand"],
                    price=clean["price"],
                    currency=clean["currency"],
                    product_url=clean["product_url"],
                    image_url=clean["image_url"],
                    source_website=domain,
                    in_stock=clean["in_stock"],
                    scraped_at=datetime.utcnow(),
                )
            )
            added += 1

        db.commit()

        print("\\n================ INGESTION SUMMARY ================")
        print(f"Partner     : {partner_name} ({country_code})")
        print(f"Added       : {added}")
        print(f"Duplicates  : {duplicates}")
        print(f"Skipped     : {skipped}")
        print(f"Total       : {len(products)}")
        print("===================================================")

        return added

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

# ------------------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------------------

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "C:\\Users\\rouam\\OneDrive\\Bureau\\Automation\\scraped_products\\mytek.tn_products_20260113_200700.json"
    print(f"🚀 Loading {path}")
    load_products_from_json(path)