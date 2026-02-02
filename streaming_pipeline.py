import os
import sys
import uuid
import time
from datetime import datetime
from urllib.parse import urlparse
from typing import Any, List, Dict, Optional
from pathlib import Path
from dotenv import load_dotenv
from firecrawl import Firecrawl
import concurrent.futures
import queue
import threading


current_dir = Path(__file__).parent
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))


from database.models import SessionLocal, Partner, Product
from ai_agent.tools.classify_product import classify_product
from ai_agent.tools.calculate_pricing import calculate_pricing
from database.crud import create_insurance_package


load_dotenv()


API_KEY = os.getenv("FIRECRAWL_API_KEY")
if not API_KEY:
    raise RuntimeError("FIRECRAWL_API_KEY missing from environment")


MAX_PAGES = 100
MAX_WORKERS = 5  


PRODUCT_SCHEMA = {
    "type": "object",
    "properties": {
        "products": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "product_name": {"type": "string"},
                    "brand": {"type": ["string", "null"]},
                    "price": {"type": ["number", "string", "null"]},
                    "currency": {"type": ["string", "null"]},
                    "description": {"type": ["string", "null"]},
                    "image_url": {"type": ["string", "null"]},
                    "product_url": {"type": ["string", "null"]},
                    "category": {"type": ["string", "null"]},
                    "sku": {"type": ["string", "null"]}
                },
                "required": ["product_name"]
            }
        }
    }
}




AVAILABLE_CATEGORIES = {
    "ELECTRONIC_PRODUCTS": {
        "display_name": "Electronics",
        "keywords": ["electronic", "smartphone", "laptop", "tablet", "tv", "television", 
                     "smartwatch", "gaming", "console", "camera", "audio", "headphone", 
                     "speaker", "earphone", "mobile", "computer", "monitor", "ipad", "macbook"]
    },
    "HOME_APPLIANCES": {
        "display_name": "Home Appliances",
        "keywords": ["appliance", "refrigerator", "washing machine", "dishwasher", 
                     "oven", "microwave", "air conditioner", "vacuum", "dryer"]
    },
    "BABY_EQUIPMENT_ESSENTIAL": {
        "display_name": "Baby Products",
        "keywords": ["baby", "stroller", "car seat", "crib", "monitor", "carrier", 
                     "high chair", "bassinet"]
    },
    "BAGS_LUGGAGE_ESSENTIAL": {
        "display_name": "Bags & Luggage",
        "keywords": ["bag", "luggage", "backpack", "suitcase", "briefcase", "handbag", 
                     "wallet", "purse"]
    },
    "GARDEN_DIY_ESSENTIAL": {
        "display_name": "Garden & DIY",
        "keywords": ["garden", "lawn", "mower", "chainsaw", "drill", "tool", "grill", 
                     "outdoor furniture"]
    },
    "HEALTH_WELLNESS_ESSENTIAL": {
        "display_name": "Health & Wellness",
        "keywords": ["health", "wellness", "blood pressure", "thermometer", "scale", 
                     "fitness tracker", "massage"]
    },
    "LIVING_FURNITURE_ESSENTIAL": {
        "display_name": "Living & Furniture",
        "keywords": ["furniture", "couch", "sofa", "table", "chair", "bed", "desk", 
                     "wardrobe", "cabinet"]
    },
    "MICRO_MOBILITY_ESSENTIAL": {
        "display_name": "Micromobility",
        "keywords": ["bike", "bicycle", "scooter", "electric bike", "e-bike", "skateboard", 
                     "hoverboard"]
    },
    "OPTICAL_HEARING_ESSENTIAL": {
        "display_name": "Optical & Hearing",
        "keywords": ["glasses", "sunglasses", "hearing aid", "contact lens", "optical"]
    },
    "PERSONAL_CARE_DEVICES": {
        "display_name": "Personal Care",
        "keywords": ["hair dryer", "shaver", "electric toothbrush", "straightener", 
                     "curling iron", "epilator"]
    },
    "OPULENCIA_PREMIUM": {
        "display_name": "Premium & Luxury",
        "keywords": ["luxury", "designer", "premium", "rolex", "gucci", "louis vuitton", 
                     "hermès", "chanel", "jewelry", "watch"]
    },
    "SOUND_MUSIC_ESSENTIAL": {
        "display_name": "Sound & Music",
        "keywords": ["guitar", "piano", "keyboard", "amplifier", "music", "instrument", 
                     "drum", "violin"]
    },
    "SPORT_OUTDOOR_ESSENTIAL": {
        "display_name": "Sport & Outdoor",
        "keywords": ["sport", "outdoor", "camping", "tent", "fishing", "golf", "yoga", 
                     "exercise", "gym", "fitness equipment", "treadmill"]
    },
    "TEXTILE_FOOTWEAR_ZARA": {
        "display_name": "Textile & Footwear",
        "keywords": ["clothes", "shoes", "boots", "sneakers", "jacket", "coat", "dress", 
                     "shirt", "pants", "footwear"]
    }
}


def match_product_to_selected_categories(product_name: str, category: str, selected_categories: List[str]) -> bool:
    """
    Check if product matches any of the selected categories based on keywords
    
    Args:
        product_name: Product name
        category: Product category from scraper
        selected_categories: List of category keys (e.g., ["ELECTRONIC_PRODUCTS", "MICRO_MOBILITY_ESSENTIAL"])
    
    Returns:
        True if product matches any selected category, False otherwise
    """
    if not selected_categories:
        return True  
    
    
    search_text = f"{product_name} {category}".lower()
    
    
    for cat_key in selected_categories:
        if cat_key not in AVAILABLE_CATEGORIES:
            continue
        
        keywords = AVAILABLE_CATEGORIES[cat_key]["keywords"]
        
        
        if any(keyword.lower() in search_text for keyword in keywords):
            return True
    
    return False


DOMAIN_COUNTRY_MAP = {
    "jumbo.ae": "AE",
    "noon.com": "AE",
    "sharafdg.com": "AE",
    "amazon.ae": "AE",
    "virginmegastore.ae": "AE",
    "emaxme.com": "AE",
    "jumia.com.tn": "TN",
    "tunisianet.com.tn": "TN",
    "mytek.tn": "TN",
}


ALLOWED_CURRENCIES = {"AED", "TND"}


CURRENCY_NORMALIZATION = {
    "AED": "AED", "D": "AED", "د.إ": "AED", "د.إ.‏": "AED", 
    "د": "AED", "DH": "AED", "DHM": "AED",
    "TND": "TND", "DT": "TND", "د.ت": "TND", "ت": "TND", "DIN": "TND",
}


def get_country_from_domain(domain: str) -> str:
    domain = domain.lower().replace("www.", "")
    if domain in DOMAIN_COUNTRY_MAP:
        return DOMAIN_COUNTRY_MAP[domain]
    if domain.endswith(".tn"):
        return "TN"
    if domain.endswith(".ae"):
        return "AE"
    return "AE"


def normalize_currency(raw: str) -> Optional[str]:
    if not raw:
        return None
    cleaned = raw.strip().upper()
    return CURRENCY_NORMALIZATION.get(cleaned)


def parse_price(value) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value) if value > 0 else None
    if isinstance(value, str):
        cleaned = "".join(c for c in value if c.isdigit() or c == '.')
        if not cleaned:
            return None
        try:
            price = float(cleaned)
            return price if price > 0 else None
        except ValueError:
            return None
    return None


def normalize_url(url: str) -> Optional[str]:
    if not url or url in ["Unknown URL", "unknown", ""]:
        return None
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        return None
    return url


def canonical_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")


def format_time(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.2f}s"
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"{minutes}m {secs:.0f}s"




def scrape_and_process_url(
    url: str, 
    partner_id: uuid.UUID, 
    domain: str, 
    seen_urls: set, 
    stats: dict, 
    stats_lock: threading.Lock, 
    url_index: int, 
    total_urls: int,
    selected_categories: List[str] 
):
    """
    Scrape a single URL, extract products, FILTER by category, process immediately with AI
    """
    client = Firecrawl(api_key=API_KEY)
    db = SessionLocal()
    
    try:
        # Scrape this single URL
        result = client.scrape(
            url=url,
            formats=[{
                "type": "json",
                "schema": PRODUCT_SCHEMA,
            }],
            only_main_content=True,
        )
        
        # Extract products
        data = getattr(result, "json", None)
        if not isinstance(data, dict):
            return
        
        products = data.get("products", [])
        
        # Process each product IMMEDIATELY
        for product_raw in products:
            with stats_lock:
                stats["scraped"] += 1
            
            
            if not product_raw.get("product_name"):
                with stats_lock:
                    stats["invalid"] += 1
                continue
            
            product_name = product_raw.get("product_name", "")
            product_category = product_raw.get("category", "")
            
           
            if not match_product_to_selected_categories(product_name, product_category, selected_categories):
                with stats_lock:
                    stats["filtered_out"] += 1
                continue
            
            product_url_raw = product_raw.get("product_url") or url
            product_url = normalize_url(product_url_raw)
            if not product_url:
                with stats_lock:
                    stats["invalid"] += 1
                continue
            
            product_url = canonical_url(product_url)
            
            # Check duplicate
            with stats_lock:
                if product_url in seen_urls:
                    stats["duplicates"] += 1
                    continue
                seen_urls.add(product_url)
            
            # Validate price and currency
            price = parse_price(product_raw.get("price"))
            if price is None or price <= 0:
                with stats_lock:
                    stats["invalid"] += 1
                continue
            
            currency = normalize_currency(product_raw.get("currency"))
            if currency not in ALLOWED_CURRENCIES:
                with stats_lock:
                    stats["invalid"] += 1
                continue
            
            # Save to database
            product = Product(
                product_id=uuid.uuid4(),
                partner_id=partner_id,
                product_name=product_raw["product_name"].strip(),
                description=product_raw.get("description", "").strip() if product_raw.get("description") else "",
                category=product_raw.get("category") or "N/A",
                brand=product_raw.get("brand") or "Unknown",
                price=price,
                currency=currency,
                product_url=product_url,
                image_url=product_raw.get("image_url"),
                source_website=domain,
                in_stock=True,
                scraped_at=datetime.utcnow(),
                processing_status='processing',
                processing_started_at=datetime.utcnow()
            )
            db.add(product)
            db.commit()
            db.refresh(product)
            
            # AI Classification
            classification_result = classify_product.invoke({
                "product_name": product.product_name,
                "category": product.category,
                "brand": product.brand,
                "price": float(product.price),
                "currency": product.currency,
                "description": product.description
            })
            
            classification = classification_result.get("classification", {})
            market = classification_result.get("market", "UAE")
            
            # Build response
            response = {
                "product": {
                    "name": product.product_name,
                    "brand": product.brand,
                    "category": classification_result.get("category", "N/A"),
                    "price": float(product.price),
                    "currency": product.currency,
                },
                "eligible": classification.get("eligible", False),
                "market": market,
                "risk_profile": classification.get("risk_profile"),
                "coverage_modules": classification.get("coverage_modules", []),
                "exclusions": classification.get("exclusions", [])
            }
            
            # If not eligible
            if not response["eligible"]:
                response["reason"] = classification.get("reason", "Not eligible")
                
                create_insurance_package(
                    db=db,
                    partner_id=str(product.partner_id),
                    product_id=str(product.product_id),
                    package_data=response,
                    is_eligible=False
                )
                
                product.processing_status = 'completed'
                product.processing_completed_at = datetime.utcnow()
                db.commit()
                
                with stats_lock:
                    stats["processed"] += 1
                    stats["not_eligible"] += 1
                
                print(f"\n[{url_index}/{total_urls}] NOT ELIGIBLE: {product.product_name[:50]}")
                print(f"  Reason: {response['reason'][:60]}")
                continue
            
            # Calculate pricing for eligible
            risk_profile = classification.get("risk_profile")
            product_value = float(product.price)
            
            try:
                # Standard pricing
                standard_pricing = calculate_pricing.invoke({
                    "risk_profile": risk_profile,
                    "product_value": product_value,
                    "market": market,
                    "plan": "STANDARD"
                })
                
                if standard_pricing.get("error"):
                    response["eligible"] = False
                    response["reason"] = standard_pricing["error"]
                else:
                    # Get monthly premium or calculate it as fallback
                    monthly_prem = standard_pricing.get("monthly", {}).get("monthly_premium")
                    if not monthly_prem:
                        annual = standard_pricing["12_months"]["annual_premium"]
                        monthly_prem = round((annual * 1.05) / 12, 2)
                    
                    response["monthly_premium"] = {
                        "amount": monthly_prem,
                        "currency": standard_pricing["12_months"]["currency"]
                    }
                    response["standard_premium_12_months"] = {
                        "amount": standard_pricing["12_months"]["annual_premium"],
                        "currency": standard_pricing["12_months"]["currency"]
                    }
                    response["standard_premium_24_months"] = {
                        "amount": standard_pricing["24_months"]["total_premium"],
                        "currency": standard_pricing["24_months"]["currency"]
                    }
                
                # ASSURMAX if applicable
                if market.upper() == "UAE" and product_value <= 5000:
                    electronics_keywords = [
                        "ELECTRONIC", "SMARTPHONE", "LAPTOP", "TABLET", 
                        "TV", "TELEVISION", "SMARTWATCH", "GAMING", "CONSOLE"
                    ]
                    
                    risk_profile_upper = str(risk_profile).upper() if risk_profile else ""
                    category_upper = str(classification_result.get("category", "")).upper()
                    
                    is_electronics = any(
                        keyword in risk_profile_upper or keyword in category_upper
                        for keyword in electronics_keywords
                    )
                    
                    if is_electronics:
                        assurmax_pricing = calculate_pricing.invoke({
                            "product_value": product_value,
                            "market": market,
                            "plan": "ASSURMAX"
                        })
                        
                        if not assurmax_pricing.get("error"):
                            response["assurmax_premium"] = {
                                "monthly_amount": assurmax_pricing["monthly"]["monthly_premium"],
                                "amount": assurmax_pricing["12_months"]["annual_premium"],
                                "currency": assurmax_pricing["12_months"]["currency"],
                                "pack_cap": assurmax_pricing["assurmax_pack_cap"]["pack_cap"],
                                "max_products": assurmax_pricing["assurmax_pack_cap"]["max_products_covered"],
                                "eligible": True
                            }
                
            except Exception as e:
                response["eligible"] = False
                response["reason"] = f"Pricing failed: {str(e)}"
            
            # Save insurance package
            create_insurance_package(
                db=db,
                partner_id=str(product.partner_id),
                product_id=str(product.product_id),
                package_data=response,
                is_eligible=response.get("eligible", False)
            )
            
            product.processing_status = 'completed'
            product.processing_completed_at = datetime.utcnow()
            db.commit()
            
            with stats_lock:
                stats["processed"] += 1
                if response.get("eligible"):
                    stats["eligible"] += 1
                else:
                    stats["not_eligible"] += 1
            
            # Print result IMMEDIATELY
            if response.get("eligible"):
                monthly = response.get("monthly_premium", {})
                std_12 = response.get("standard_premium_12_months", {})
                
                print(f"\n[{url_index}/{total_urls}] ✅ ELIGIBLE: {product.product_name[:50]}")
                print(f"  Price: {product.price} {product.currency}")
                print(f"  Monthly: {monthly.get('amount')} {monthly.get('currency')}")
                print(f"  Standard 12m: {std_12.get('amount')} {std_12.get('currency')}")
                
                assurmax = response.get("assurmax_premium")
                if assurmax and assurmax.get("eligible"):
                    print(f"  ASSURMAX: {assurmax.get('amount')} {assurmax.get('currency')}")
    
    except Exception as e:
        print(f"\n[{url_index}/{total_urls}] ERROR scraping {url}: {e}")
    
    finally:
        db.close()






def true_streaming_pipeline(start_url: str, selected_categories: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    TRUE STREAMING: Scrapes URLs in parallel, processes each product immediately
    
    Args:
        start_url: Starting URL to scrape
        selected_categories: List of category keys to filter (e.g., ["ELECTRONIC_PRODUCTS", "MICRO_MOBILITY_ESSENTIAL"])
                            If None or empty, all categories are processed
    """
    total_start = time.time()
    
    client = Firecrawl(api_key=API_KEY)
    
    parsed_start = urlparse(start_url)
    start_domain = parsed_start.netloc.replace("www.", "")
    start_tld = start_domain.split('.')[-1]


    print(f"\n{'='*70}")
    print(f"TRUE STREAMING PIPELINE WITH CATEGORY FILTERING")
    print(f"{'='*70}")
    print(f"Domain: {start_domain}")
    print(f"URL: {start_url}")
    print(f"Workers: {MAX_WORKERS} parallel scrapers")
    
    # Display selected categories
    if selected_categories:
        print(f"\n✅ SELECTED CATEGORIES ({len(selected_categories)}):")
        for cat_key in selected_categories:
            if cat_key in AVAILABLE_CATEGORIES:
                display_name = AVAILABLE_CATEGORIES[cat_key]["display_name"]
                print(f"  - {display_name}")
    else:
        print(f"\n✅ ALL CATEGORIES (no filter)\n")


    # Get partner
    partner_name = start_domain.split(".")[0].title()
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
    
    country_code = get_country_from_domain(start_domain)


    db = SessionLocal()
    try:
        partner = db.query(Partner).filter_by(company_name=partner_name).first()
        if not partner:
            partner = Partner(
                company_name=partner_name,
                website_url=start_url,
                country=country_code,
                status="scraped",
            )
            db.add(partner)
            db.commit()
            db.refresh(partner)
        partner_id = partner.partner_id
    finally:
        db.close()


    # Step 1: Discover URLs
    print("\nStep 1: Discovering URLs...")
    map_start = time.time()
    
    try:
        map_result = client.map(url=start_url, limit=MAX_PAGES)
        
        all_urls = []
        if hasattr(map_result, 'links'):
            for link in map_result.links:
                if hasattr(link, 'url'):
                    all_urls.append(link.url)
        
        filtered_urls = [
            url for url in all_urls 
            if urlparse(url).netloc.replace("www.", "").split('.')[-1] == start_tld
        ]
        
        map_time = time.time() - map_start
        print(f"Discovered {len(filtered_urls)} URLs in {format_time(map_time)}\n")
        
    except Exception as e:
        print(f"Map failed: {e}")
        return {"success": False, "error": str(e)}


    # Step 2: Scrape and process each URL in parallel (TRUE STREAMING)
    print(f"Step 2: Scraping and processing {len(filtered_urls)} URLs in real-time...")
    print(f"Results will appear IMMEDIATELY as products are found and processed\n")
    print(f"{'='*70}\n")
    
  
    seen_urls = set()
    stats = {
        "scraped": 0,
        "processed": 0,
        "eligible": 0,
        "not_eligible": 0,
        "duplicates": 0,
        "invalid": 0,
        "filtered_out": 0  
    }
    stats_lock = threading.Lock()
    
    scrape_start = time.time()
    
    # Process URLs in parallel with ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = []
        for idx, url in enumerate(filtered_urls, 1):
            future = executor.submit(
                scrape_and_process_url,
                url, partner_id, start_domain, seen_urls, stats, stats_lock, idx, len(filtered_urls),
                selected_categories or []  
            )
            futures.append(future)
        
        # Wait for all to complete
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"\nWorker error: {e}")
    
    scrape_time = time.time() - scrape_start
    total_time = time.time() - total_start


    print(f"\n{'='*70}")
    print("PIPELINE COMPLETE")
    print(f"{'='*70}")
    print(f"Partner: {partner_name} ({country_code})")
    print(f"Scraped: {stats['scraped']}")
    print(f"Filtered Out: {stats['filtered_out']} (not in selected categories)")  # ← NEW
    print(f"Processed: {stats['processed']}")
    print(f"Eligible: {stats['eligible']}")
    print(f"Not Eligible: {stats['not_eligible']}")
    print(f"Duplicates: {stats['duplicates']}")
    print(f"Invalid: {stats['invalid']}")
    print(f"{'='*70}")
    print(f"Total Time: {format_time(total_time)}")
    print(f"{'='*70}\n")


    return {
        "success": True,
        "partner_id": str(partner_id),
        "partner_name": partner_name,
        "stats": stats,
        "total_time": total_time
    }



if __name__ == "__main__":
   
    
    start_url = sys.argv[1] if len(sys.argv) > 1 else "https://www.virginmegastore.ae/en"
    
    selected_categories = None
    if len(sys.argv) > 2:
        categories_str = sys.argv[2]
        selected_categories = [cat.strip() for cat in categories_str.split(",")]
    
    result = true_streaming_pipeline(start_url, selected_categories)
    
    if result.get("success"):
        print("TRUE STREAMING PIPELINE COMPLETED")
    else:
        print(f"FAILED: {result.get('error')}")