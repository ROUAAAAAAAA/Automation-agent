import os
import sys
import uuid
import time
from datetime import datetime
from urllib.parse import urlparse
from typing import Any, List, Dict, Optional, Callable
from pathlib import Path
from dotenv import load_dotenv
from firecrawl import Firecrawl
import concurrent.futures
import threading
import traceback
from functools import wraps


current_dir = Path(__file__).parent
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))


from database.models import SessionLocal, Product, Partner
from ai_agent.tools.classify_product import classify_product
from ai_agent.tools.calculate_pricing import calculate_pricing
from database.crud import create_insurance_package


load_dotenv()


API_KEY = os.getenv("FIRECRAWL_API_KEY")
if not API_KEY:
    raise RuntimeError("FIRECRAWL_API_KEY missing from environment")


MAX_PAGES = 100
MAX_WORKERS = 5


# Add stop exception
class PipelineStopRequested(Exception):
    """Raised when pipeline stop is requested"""
    pass


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




def debug_log(message: str):
    """Log debug messages with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] 🔍 {message}")


def time_function(func_name: str):
    """Decorator to time function execution"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            debug_log(f"START {func_name}")
            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start_time
                debug_log(f"END {func_name} - {elapsed:.2f}s")
                return result
            except Exception as e:
                elapsed = time.time() - start_time
                debug_log(f"ERROR {func_name} after {elapsed:.2f}s: {e}")
                debug_log(f"Traceback: {traceback.format_exc()}")
                raise
        return wrapper
    return decorator




@time_function("scrape_and_process_url")
def scrape_and_process_url(
    url: str, 
    partner_id: uuid.UUID, 
    domain: str, 
    seen_urls: set, 
    stats: dict, 
    stats_lock: threading.Lock, 
    url_index: int, 
    total_urls: int,
    selected_categories: List[str],
    progress_cb: Optional[Callable[[Dict[str, Any]], None]] = None,
    stop_flag: Optional[threading.Event] = None
):
    """
    Scrape a single URL, extract products, FILTER by category, process immediately with AI
    """
    # Check stop flag at the start
    if stop_flag and stop_flag.is_set():
        debug_log(f" Stop requested - skipping URL {url_index}")
        raise PipelineStopRequested("Stop requested")
    
    debug_log(f"Starting URL {url_index}/{total_urls}: {url[:80]}...")
    
    client = Firecrawl(api_key=API_KEY)
    db = SessionLocal()
    
    try:
        # Check stop before scraping
        if stop_flag and stop_flag.is_set():
            raise PipelineStopRequested("Stop requested before scrape")
        
        # Scrape this single URL
        scrape_start = time.time()
        debug_log(f"  Calling Firecrawl.scrape()...")
        
        result = client.scrape(
            url=url,
            formats=[{
                "type": "json",
                "schema": PRODUCT_SCHEMA,
            }],
            only_main_content=True,
        )
        
        scrape_time = time.time() - scrape_start
        debug_log(f"  Firecrawl.scrape() completed in {scrape_time:.2f}s")
        
        # Extract products
        data = getattr(result, "json", None)
        if not isinstance(data, dict):
            debug_log(f"  No JSON data returned from scrape")
            return
        
        products = data.get("products", [])
        debug_log(f"  Found {len(products)} raw products")
        
        # Process each product IMMEDIATELY
        for product_idx, product_raw in enumerate(products):
            # Check stop flag before each product
            if stop_flag and stop_flag.is_set():
                debug_log(f" Stop requested during product processing")
                raise PipelineStopRequested("Stop requested during processing")
            
            with stats_lock:
                stats["scraped"] += 1
            
            
            if not product_raw.get("product_name"):
                debug_log(f"    Product {product_idx+1}: Missing product_name")
                with stats_lock:
                    stats["invalid"] += 1
                continue
            
            product_name = product_raw.get("product_name", "")
            product_category = product_raw.get("category", "")
            
            debug_log(f"    Product {product_idx+1}: '{product_name[:50]}...' | Category: {product_category}")
            
           
            if not match_product_to_selected_categories(product_name, product_category, selected_categories):
                debug_log(f"    Product filtered out (not in selected categories)")
                with stats_lock:
                    stats["filtered_out"] += 1
                continue
            
            product_url_raw = product_raw.get("product_url") or url
            product_url = normalize_url(product_url_raw)
            if not product_url:
                debug_log(f"    Invalid URL: {product_url_raw}")
                with stats_lock:
                    stats["invalid"] += 1
                continue
            
            product_url = canonical_url(product_url)
            
            # Check duplicate
            with stats_lock:
                if product_url in seen_urls:
                    debug_log(f"    Duplicate URL")
                    stats["duplicates"] += 1
                    continue
                seen_urls.add(product_url)
            
            # Validate price and currency
            price = parse_price(product_raw.get("price"))
            if price is None or price <= 0:
                debug_log(f"    Invalid price: {product_raw.get('price')}")
                with stats_lock:
                    stats["invalid"] += 1
                continue
            
            currency = normalize_currency(product_raw.get("currency"))
            if currency not in ALLOWED_CURRENCIES:
                debug_log(f"    Invalid currency: {product_raw.get('currency')}")
                with stats_lock:
                    stats["invalid"] += 1
                continue
            
            debug_log(f"    Valid product: {product_name[:40]}... | Price: {price} {currency}")
            
            # Check stop before database save
            if stop_flag and stop_flag.is_set():
                raise PipelineStopRequested("Stop requested before database save")
            
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
            
            # Check stop before AI classification
            if stop_flag and stop_flag.is_set():
                raise PipelineStopRequested("Stop requested before AI classification")
            
            debug_log(f"    Saved to database, starting AI classification...")
            
            # AI Classification
            classify_start = time.time()
            classification_result = classify_product.invoke({
                "product_name": product.product_name,
                "category": product.category,
                "brand": product.brand,
                "price": float(product.price),
                "currency": product.currency,
                "description": product.description
            })
            classify_time = time.time() - classify_start
            debug_log(f"    AI classification completed in {classify_time:.2f}s")
            
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
                
                debug_log(f"    NOT ELIGIBLE: {response['reason'][:60]}")
                
                # Send progress update
                if progress_cb:
                    progress_cb({
                        "processed": stats["processed"],
                        "eligible": stats["eligible"],
                        "not_eligible": stats["not_eligible"],
                        "scraped": stats["scraped"],
                        "current_url": url,
                        "url_index": url_index,
                        "total_urls": total_urls,
                        "product_name": product_name[:50],
                        "eligible_status": False,
                        "reason": response["reason"][:100]
                    })
                
                continue
            
            # Check stop before pricing calculation
            if stop_flag and stop_flag.is_set():
                raise PipelineStopRequested("Stop requested before pricing")
            
            # Calculate pricing for eligible
            risk_profile = classification.get("risk_profile")
            product_value = float(product.price)
            
            debug_log(f"    Eligible! Starting pricing calculation...")
            
            try:
                # Standard pricing
                pricing_start = time.time()
                standard_pricing = calculate_pricing.invoke({
                    "risk_profile": risk_profile,
                    "product_value": product_value,
                    "market": market,
                    "plan": "STANDARD"
                })
                pricing_time = time.time() - pricing_start
                debug_log(f"    Pricing calculation completed in {pricing_time:.2f}s")
                
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
                    debug_log(f"    Checking ASSURMAX eligibility...")
                    
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
                        # Check stop before ASSURMAX pricing
                        if stop_flag and stop_flag.is_set():
                            raise PipelineStopRequested("Stop requested before ASSURMAX")
                        
                        assurmax_start = time.time()
                        assurmax_pricing = calculate_pricing.invoke({
                            "product_value": product_value,
                            "market": market,
                            "plan": "ASSURMAX"
                        })
                        assurmax_time = time.time() - assurmax_start
                        debug_log(f"    ASSURMAX pricing completed in {assurmax_time:.2f}s")
                        
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
                debug_log(f"    Pricing calculation ERROR: {e}")
                response["eligible"] = False
                response["reason"] = f"Pricing failed: {str(e)}"
            
            # Save insurance package
            debug_log(f"    Saving insurance package...")
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
                
                debug_log(f"     ELIGIBLE | Monthly: {monthly.get('amount')} {monthly.get('currency')}")
                
                assurmax = response.get("assurmax_premium")
                if assurmax and assurmax.get("eligible"):
                    debug_log(f"     ASSURMAX eligible: {assurmax.get('amount')} {assurmax.get('currency')}")
            
            # Send progress update after EACH product
            if progress_cb:
                progress_cb({
                    "processed": stats["processed"],
                    "eligible": stats["eligible"],
                    "not_eligible": stats["not_eligible"],
                    "scraped": stats["scraped"],
                    "current_url": url,
                    "url_index": url_index,
                    "total_urls": total_urls,
                    "product_name": product_name[:50],
                    "eligible_status": response.get("eligible", False),
                    "price": price,
                    "currency": currency,
                    "product_index": product_idx + 1,
                    "total_products_in_url": len(products)
                })
    
    except PipelineStopRequested:
        debug_log(f" URL {url_index} stopped cleanly")
        raise  # Re-raise to propagate to executor
    except Exception as e:
        debug_log(f"ERROR scraping {url}: {e}")
        debug_log(f"Traceback: {traceback.format_exc()}")
        
        # Send error progress
        if progress_cb:
            progress_cb({
                "error": str(e),
                "url": url,
                "url_index": url_index,
                "error_type": type(e).__name__
            })
    
    finally:
        db.close()
        debug_log(f"Finished processing URL {url_index}/{total_urls}")




@time_function("true_streaming_pipeline")
def true_streaming_pipeline(
    start_url: str, 
    selected_categories: Optional[List[str]] = None,
    progress_cb: Optional[Callable[[Dict[str, Any]], None]] = None
) -> Dict[str, Any]:
    """
    TRUE STREAMING: Scrapes URLs in parallel, processes each product immediately
    
    Args:
        start_url: Starting URL to scrape
        selected_categories: List of category keys to filter (e.g., ["ELECTRONIC_PRODUCTS", "MICRO_MOBILITY_ESSENTIAL"])
                            If None or empty, all categories are processed
        progress_cb: Optional callback function to report progress to backend
    """
    
    # CREATE STOP FLAG - THIS IS THE KEY FIX
    stop_flag = threading.Event()
    
    # Wrap progress callback to check for stop
    def report_progress(data: Dict[str, Any]):
        if progress_cb:
            try:
                progress_cb(data)
            except Exception as e:
                # If progress callback raises exception (like JobStopRequested), set stop flag
                debug_log(f" Stop requested via progress callback: {e}")
                stop_flag.set()
                raise
    
    try:
        report_progress({
            "phase": "starting",
            "message": "Pipeline starting",
            "start_url": start_url,
            "selected_categories": selected_categories,
            "timestamp": datetime.utcnow().isoformat()
        })
    except:
        return {"success": False, "error": "Stopped before start", "stopped": True}
    
    total_start = time.time()
    
    client = Firecrawl(api_key=API_KEY)
    
    parsed_start = urlparse(start_url)
    start_domain = parsed_start.netloc.replace("www.", "")
    start_tld = start_domain.split('.')[-1]

    try:
        report_progress({
            "phase": "setup",
            "message": f"Setting up for domain: {start_domain}",
            "domain": start_domain,
            "max_workers": MAX_WORKERS,
            "max_pages": MAX_PAGES
        })
    except:
        return {"success": False, "error": "Stopped during setup", "stopped": True}

    # Display selected categories
    if selected_categories:
        category_names = []
        for cat_key in selected_categories:
            if cat_key in AVAILABLE_CATEGORIES:
                category_names.append(AVAILABLE_CATEGORIES[cat_key]["display_name"])
        
        try:
            report_progress({
                "phase": "categories",
                "message": f"Filtering {len(selected_categories)} categories",
                "selected_categories": selected_categories,
                "category_names": category_names
            })
        except:
            return {"success": False, "error": "Stopped during category setup", "stopped": True}
    else:
        try:
            report_progress({
                "phase": "categories",
                "message": "Processing all categories (no filter)"
            })
        except:
            return {"success": False, "error": "Stopped during category setup", "stopped": True}

    # Get partner
    try:
        report_progress({
            "phase": "partner",
            "message": "Getting or creating partner..."
        })
    except:
        return {"success": False, "error": "Stopped during partner setup", "stopped": True}
    
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
            try:
                report_progress({
                    "phase": "partner",
                    "message": f"Creating new partner: {partner_name}",
                    "action": "created"
                })
            except:
                db.close()
                return {"success": False, "error": "Stopped during partner creation", "stopped": True}
            
            partner = Partner(
                company_name=partner_name,
                website_url=start_url,
                country=country_code,
                status="scraped",
            )
            db.add(partner)
            db.commit()
            db.refresh(partner)
        else:
            try:
                report_progress({
                    "phase": "partner",
                    "message": f"Found existing partner: {partner_name}",
                    "action": "found"
                })
            except:
                db.close()
                return {"success": False, "error": "Stopped during partner lookup", "stopped": True}
        
        partner_id = partner.partner_id
        
        try:
            report_progress({
                "phase": "partner",
                "message": f"Partner ready: {partner_name}",
                "partner_id": str(partner_id),
                "partner_name": partner_name,
                "country": country_code
            })
        except:
            db.close()
            return {"success": False, "error": "Stopped after partner setup", "stopped": True}
    finally:
        db.close()

    # Step 1: Discover URLs
    try:
        report_progress({
            "phase": "discovery",
            "message": "Discovering URLs...",
            "max_pages": MAX_PAGES
        })
    except:
        return {"success": False, "error": "Stopped before URL discovery", "stopped": True}
    
    map_start = time.time()
    
    try:
        debug_log(f"Starting URL discovery at {datetime.now().strftime('%H:%M:%S')}")
        map_result = client.map(url=start_url, limit=MAX_PAGES)
        map_time = time.time() - map_start
        
        try:
            report_progress({
                "phase": "discovery_complete",
                "message": f"URL discovery completed in {map_time:.2f}s",
                "discovery_time": map_time,
                "timestamp": datetime.utcnow().isoformat()
            })
        except:
            return {"success": False, "error": "Stopped after URL discovery", "stopped": True}
        
        all_urls = []
        if hasattr(map_result, 'links'):
            debug_log(f"Found {len(map_result.links)} total links")
            for link in map_result.links:
                if hasattr(link, 'url'):
                    all_urls.append(link.url)
        
        filtered_urls = [
            url for url in all_urls 
            if urlparse(url).netloc.replace("www.", "").split('.')[-1] == start_tld
        ]
        
        try:
            report_progress({
                "phase": "urls_filtered",
                "message": f"Filtered to {len(filtered_urls)} URLs from same domain",
                "total_urls": len(filtered_urls),
                "filtered_urls_sample": filtered_urls[:3] if filtered_urls else []
            })
        except:
            return {"success": False, "error": "Stopped after URL filtering", "stopped": True}
        
    except Exception as e:
        error_msg = f"URL discovery failed: {e}"
        debug_log(f" Map FAILED: {e}")
        debug_log(f"Traceback: {traceback.format_exc()}")
        
        try:
            report_progress({
                "phase": "error",
                "error": error_msg,
                "error_type": type(e).__name__,
                "timestamp": datetime.utcnow().isoformat()
            })
        except:
            pass
        
        return {"success": False, "error": error_msg}

    # Step 2: Scrape and process each URL in parallel
    try:
        report_progress({
            "phase": "scraping",
            "message": f"Starting to scrape {len(filtered_urls)} URLs",
            "total_urls": len(filtered_urls),
            "workers": MAX_WORKERS,
            "timestamp": datetime.utcnow().isoformat()
        })
    except:
        return {"success": False, "error": "Stopped before scraping", "stopped": True}
    
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
    
    # CRITICAL FIX: Use executor properly with shutdown
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS)
    futures = []
    
    try:
        try:
            report_progress({
                "phase": "workers_starting",
                "message": f"Starting {MAX_WORKERS} parallel workers",
                "timestamp": datetime.utcnow().isoformat()
            })
        except:
            executor.shutdown(wait=False)
            return {"success": False, "error": "Stopped before worker start", "stopped": True}
        
        # Submit all URLs
        for idx, url in enumerate(filtered_urls, 1):
            # Check if stop was requested before submitting more work
            if stop_flag.is_set():
                debug_log(f" Stop flag set")
                break
            
            debug_log(f"Submitting URL {idx}/{len(filtered_urls)}: {url[:80]}...")
            
            try:
                report_progress({
                    "phase": "url_submitted",
                    "url_index": idx,
                    "total_urls": len(filtered_urls),
                    "url": url[:100]
                })
            except:
                debug_log(f" Stop requested during URL submission")
                stop_flag.set()
                break
            
            future = executor.submit(
                scrape_and_process_url,
                url, partner_id, start_domain, seen_urls, stats, stats_lock, 
                idx, len(filtered_urls),
                selected_categories or [],
                report_progress,
                stop_flag  # PASS STOP FLAG TO WORKERS
            )
            futures.append(future)
        
        debug_log(f" Submitted {len(futures)} URLs for processing")
        
        try:
            report_progress({
                "phase": "all_urls_submitted",
                "message": f"All {len(futures)} URLs submitted for processing",
                "timestamp": datetime.utcnow().isoformat()
            })
        except:
            stop_flag.set()
        
        # Wait for completion or cancellation
        completed_count = 0
        for future in concurrent.futures.as_completed(futures):
            # Check stop flag
            if stop_flag.is_set():
                debug_log(f" Stop flag set - cancelling remaining futures")
                break
            
            completed_count += 1
            try:
                future.result(timeout=120)  # 2 minute timeout per URL
                
                # Send batch progress every 5 URLs
                if completed_count % 5 == 0:
                    try:
                        report_progress({
                            "phase": "batch_progress",
                            "completed_urls": completed_count,
                            "total_urls": len(filtered_urls),
                            "stats": stats.copy(),
                            "elapsed_time": time.time() - scrape_start,
                            "timestamp": datetime.utcnow().isoformat()
                        })
                    except:
                        debug_log(f" Stop requested during progress update")
                        stop_flag.set()
                        break
                
                debug_log(f" Completed {completed_count}/{len(futures)} URLs")
                
            except PipelineStopRequested:
                debug_log(f" URL stopped by request")
                stop_flag.set()
                break
            except concurrent.futures.TimeoutError:
                debug_log(f" Timeout on URL {completed_count}")
                try:
                    report_progress({
                        "phase": "timeout",
                        "url_index": completed_count,
                        "message": f"Timeout processing URL {completed_count}"
                    })
                except:
                    pass
            except Exception as e:
                debug_log(f"Worker error: {e}")
                try:
                    report_progress({
                        "phase": "worker_error",
                        "url_index": completed_count,
                        "error": str(e),
                        "error_type": type(e).__name__
                    })
                except:
                    pass
    
    finally:
        # CRITICAL: Shutdown executor and cancel pending futures
        debug_log(" Shutting down executor...")
        
        # Cancel all pending futures
        for future in futures:
            if not future.done():
                future.cancel()
        
        # Shutdown executor - wait=False means don't wait for running tasks
        executor.shutdown(wait=False)
        
        debug_log(" Executor shutdown complete")
    
    scrape_time = time.time() - scrape_start
    total_time = time.time() - total_start
    
    # Check if stopped
    if stop_flag.is_set():
        debug_log(" Pipeline was stopped")
        
        try:
            report_progress({
                "phase": "stopped",
                "message": "Pipeline stopped by user",
                "stats": stats.copy(),
                "partial_time": total_time,
                "timestamp": datetime.utcnow().isoformat()
            })
        except:
            pass
        
        debug_log("\n" + "=" * 70)
        debug_log("PIPELINE STOPPED")
        debug_log("=" * 70)
        debug_log(f"Partial Time: {format_time(total_time)}")
        debug_log(f"Partner: {partner_name} ({country_code})")
        debug_log(f"Scraped: {stats['scraped']}")
        debug_log(f"Processed: {stats['processed']}")
        debug_log(f"Eligible: {stats['eligible']}")
        debug_log("=" * 70)
        
        return {
            "success": False,
            "stopped": True,
            "partner_id": str(partner_id),
            "partner_name": partner_name,
            "stats": stats,
            "partial_time": total_time,
        }

    # Final progress update
    try:
        report_progress({
            "phase": "completed",
            "message": "Pipeline completed successfully",
            "stats": stats.copy(),
            "total_time": total_time,
            "map_time": map_time,
            "scrape_time": scrape_time,
            "partner_name": partner_name,
            "partner_id": str(partner_id),
            "timestamp": datetime.utcnow().isoformat()
        })
    except:
        pass

    debug_log("\n" + "=" * 70)
    debug_log("PIPELINE COMPLETE")
    debug_log("=" * 70)
    debug_log(f"Total Time: {format_time(total_time)}")
    debug_log(f"URL Discovery: {format_time(map_time)}")
    debug_log(f"Scraping & Processing: {format_time(scrape_time)}")
    debug_log(f"Partner: {partner_name} ({country_code})")
    debug_log(f"Scraped: {stats['scraped']}")
    debug_log(f"Filtered Out: {stats['filtered_out']}")
    debug_log(f"Processed: {stats['processed']}")
    debug_log(f"Eligible: {stats['eligible']}")
    debug_log(f"Not Eligible: {stats['not_eligible']}")
    debug_log(f"Duplicates: {stats['duplicates']}")
    debug_log(f"Invalid: {stats['invalid']}")
    debug_log("=" * 70)

    return {
        "success": True,
        "partner_id": str(partner_id),
        "partner_name": partner_name,
        "stats": stats,
        "total_time": total_time,
        "map_time": map_time,
        "scrape_time": scrape_time,
        "urls_processed": len(filtered_urls)
    }



if __name__ == "__main__":
    debug_log("=" * 70)
    debug_log("PIPELINE STARTING IN STANDALONE MODE")
    debug_log("=" * 70)
    debug_log(f"Python: {sys.executable}")
    debug_log(f"Working dir: {os.getcwd()}")
    debug_log(f"Script dir: {current_dir}")
    
    # Simple progress callback for CLI mode
    def cli_progress_cb(data: Dict[str, Any]):
        if "stats" in data:
            stats = data["stats"]
            print(f"\rProcessed: {stats.get('processed', 0)} | Eligible: {stats.get('eligible', 0)} | Scraped: {stats.get('scraped', 0)}", end="")
        elif "phase" in data and data["phase"] == "completed":
            print(f"\ Pipeline completed!")
            stats = data.get("stats", {})
            print(f"   Total Scraped: {stats.get('scraped', 0)}")
            print(f"   Total Eligible: {stats.get('eligible', 0)}")
            print(f"   Total Time: {data.get('total_time', 0):.2f}s")
        elif "phase" in data and data["phase"] == "stopped":
            print(f"\n Pipeline stopped!")
            stats = data.get("stats", {})
            print(f"   Scraped: {stats.get('scraped', 0)}")
            print(f"   Processed: {stats.get('processed', 0)}")
    
    # Parse command line arguments
    import argparse
    
    parser = argparse.ArgumentParser(description="Run the streaming pipeline")
    parser.add_argument("url", help="Start URL to scrape")
    parser.add_argument("--categories", "-c", help="Comma-separated list of categories")
    
    args = parser.parse_args()
    
    start_url = args.url
    selected_categories = args.categories.split(",") if args.categories else None
    
    debug_log(f"URL: {start_url}")
    debug_log(f"Categories: {selected_categories}")
    
    # Run pipeline
    try:
        result = true_streaming_pipeline(
            start_url=start_url,
            selected_categories=selected_categories,
            progress_cb=cli_progress_cb
        )
        
        debug_log("=" * 70)
        debug_log("PIPELINE COMPLETED")
        debug_log("=" * 70)
        
        if result.get("success"):
            stats = result.get("stats", {})
            print(f"\n SUCCESS!")
            print(f"Partner: {result.get('partner_name')}")
            print(f"Scraped: {stats.get('scraped', 0)}")
            print(f"Processed: {stats.get('processed', 0)}")
            print(f"Eligible: {stats.get('eligible', 0)}")
            print(f"Time: {result.get('total_time', 0):.2f}s")
        elif result.get("stopped"):
            print(f"\n STOPPED by user")
            stats = result.get("stats", {})
            print(f"Partial results: {stats.get('processed', 0)} processed")
        else:
            print(f"\n FAILED: {result.get('error')}")
            
    except KeyboardInterrupt:
        debug_log("\n Pipeline interrupted by user (Ctrl+C)")
        print("\n\n Pipeline interrupted - shutting down...")
    except Exception as e:
        debug_log(f"\n UNEXPECTED ERROR: {e}")
        traceback.print_exc()