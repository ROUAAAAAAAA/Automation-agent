import os
import sys
import uuid
from datetime import datetime
from urllib.parse import urlparse
from typing import Any, List, Dict, Optional
from pathlib import Path
from dotenv import load_dotenv
from firecrawl import Firecrawl
import traceback
import time
import concurrent.futures
import threading
import queue


current_dir = Path(__file__).parent
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))

from database.models import SessionLocal, Partner, Product

load_dotenv()

API_KEY = os.getenv("FIRECRAWL_API_KEY")
if not API_KEY:
    raise RuntimeError("FIRECRAWL_API_KEY missing from environment")

MAX_PAGES = 100
POLL_INTERVAL = 1
MAX_WORKERS = 10  

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

# ============================================================
# CONFIGURATION
# ============================================================

DOMAIN_COUNTRY_MAP = {
    "jumbo.ae": "AE",
    "noon.com": "AE",
    "sharafdg.com": "AE",
    "amazon.ae": "AE",
    "virginmegastore.ae": "AE",
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

# ============================================================
# HELPERS
# ============================================================

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
    if cleaned in CURRENCY_NORMALIZATION:
        return CURRENCY_NORMALIZATION[cleaned]
    if raw.strip() in CURRENCY_NORMALIZATION:
        return CURRENCY_NORMALIZATION[raw.strip()]
    return None

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
    if url.startswith("httpswww.") or url.startswith("httpwww."):
        url = url.replace("httpswww.", "https://www.").replace("httpwww.", "http://www.")
    elif url.startswith("https") and "://" not in url:
        url = url.replace("https", "https://", 1)
    elif url.startswith("http") and "://" not in url:
        url = url.replace("http", "http://", 1)
    if not url.startswith(("http://", "https://")):
        return None
    return url

def canonical_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")

def format_time(seconds: float) -> str:
    """Format seconds into human-readable time"""
    if seconds < 60:
        return f"{seconds:.2f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.0f}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours}h {minutes}m {secs:.0f}s"



class AsyncDatabaseInserter:
    """
    Optimized async batch inserter - validates and inserts products
    with background database writes for non-blocking performance
    """
    
    def __init__(self, partner_id: uuid.UUID, domain: str, batch_size: int = 100):
        self.partner_id = partner_id
        self.domain = domain
        self.batch_size = batch_size
        self.product_queue = queue.Queue(maxsize=1000)
        self.stop_event = threading.Event()
        
        db = SessionLocal()
        try:
         
            self.seen_urls = set(
                url for (url,) in db.query(Product.product_url)
                .filter_by(partner_id=partner_id)
                .order_by(Product.scraped_at.desc())
                .limit(10_000)  
            )
        finally:
            db.close()
        
        self.stats = {
            "added": 0,
            "duplicates": 0,
            "invalid": 0,
            "total": 0
        }
        self.stats_lock = threading.Lock()
        
        
        self.writer_thread = threading.Thread(target=self._writer_loop, daemon=True)
        self.writer_thread.start()
    
    def validate_product(self, raw: dict) -> Optional[dict]:
        """Validate and clean product"""
        if not raw.get("product_name"):
            return None
        
        product_url_raw = raw.get("product_url")
        if not product_url_raw:
            return None
            
        product_url = normalize_url(product_url_raw)
        if not product_url:
            return None
            
        product_url = canonical_url(product_url)
        
        price = parse_price(raw.get("price"))
        if price is None or price <= 0:
            return None
        
        currency = normalize_currency(raw.get("currency"))
        if currency not in ALLOWED_CURRENCIES:
            return None
        
        return {
            "product_name": raw["product_name"].strip(),
            "description": raw.get("description", "").strip() if raw.get("description") else "",
            "brand": raw.get("brand") or "Unknown",
            "category": raw.get("category") or "N/A",
            "price": price,
            "currency": currency,
            "product_url": product_url,
            "image_url": raw.get("image_url"),
            "sku": raw.get("sku"),
            "in_stock": bool(raw.get("in_stock", True)),
        }
    
    def add_product(self, raw: dict):
        """Add product to processing queue (non-blocking)"""
        with self.stats_lock:
            self.stats["total"] += 1
        
        clean = self.validate_product(raw)
        if not clean:
            with self.stats_lock:
                self.stats["invalid"] += 1
            return
        
        if clean["product_url"] in self.seen_urls:
            with self.stats_lock:
                self.stats["duplicates"] += 1
            return
        
        self.seen_urls.add(clean["product_url"])
        
        product_obj = Product(
            product_id=uuid.uuid4(),
            partner_id=self.partner_id,
            product_name=clean["product_name"],
            description=clean["description"],
            category=clean["category"],
            brand=clean["brand"],
            price=clean["price"],
            currency=clean["currency"],
            product_url=clean["product_url"],
            image_url=clean["image_url"],
            source_website=self.domain,
            in_stock=clean["in_stock"],
            scraped_at=datetime.utcnow(),
            processing_status='pending',
        )
        
        self.product_queue.put(product_obj)
    
    def _writer_loop(self):
        """Background thread that writes batches to database"""
        db = SessionLocal()
        batch = []
        
        while not self.stop_event.is_set() or not self.product_queue.empty():
            try:
                product = self.product_queue.get(timeout=0.5)
                batch.append(product)
                
                if len(batch) >= self.batch_size:
                    self._flush_batch(db, batch)
                    batch = []
                    
            except queue.Empty:
                if batch:
                    self._flush_batch(db, batch)
                    batch = []
        
        # Final flush
        if batch:
            self._flush_batch(db, batch)
        
        db.close()
    
    def _flush_batch(self, db, batch):
        """Flush batch to database"""
        try:
            db.bulk_save_objects(batch)
            db.commit()
            with self.stats_lock:
                self.stats["added"] += len(batch)
            print(f"   Inserted {len(batch)} products (Total: {self.stats['added']})")
        except Exception as e:
            db.rollback()
            print(f"   Batch insert failed: {e}")
            # Fallback: try individual inserts
            for product in batch:
                try:
                    db.add(product)
                    db.commit()
                    with self.stats_lock:
                        self.stats["added"] += 1
                except:
                    db.rollback()
                    with self.stats_lock:
                        self.stats["invalid"] += 1
    
    def close(self):
        """Wait for queue to drain and stop writer"""
        self.stop_event.set()
        self.writer_thread.join(timeout=30)
    
    def get_stats(self) -> dict:
        """Get current stats"""
        with self.stats_lock:
            return self.stats.copy()



def process_page(page_data):
    """Process a single page's products (runs in parallel)"""
    page, idx = page_data
    page_products = []
    
    try:
        page_url = getattr(page, "url", None) or "Unknown URL"
        data = getattr(page, "json", None)
        
        if not isinstance(data, dict):
            return []
        
        for product in data.get("products", []):
            if not product.get("product_url"):
                product["product_url"] = page_url
            page_products.append(product)
            
    except Exception as e:
        print(f"    Page {idx} error: {e}")
    
    return page_products



def crawl_entire_site(start_url: str) -> Dict[str, Any]:
    total_start = time.time()
    
    client = Firecrawl(api_key=API_KEY)
    
    parsed_start = urlparse(start_url)
    start_domain = parsed_start.netloc.replace("www.", "")
    start_tld = start_domain.split('.')[-1]

    print(f"\n Starting  crawl: {start_domain}")
    print(f" Start URL: {start_url}\n")

    partner_name = start_domain.split(".")[0].title()
    if "noon" in partner_name.lower():
        partner_name = "Noon"
    elif "virginmegastore" in partner_name.lower():
        partner_name = "Virginmegastore.Ae"
    elif "jumbo" in partner_name.lower():
        partner_name = "Jumbo"
    elif "mytek" in partner_name.lower():
        partner_name = "Mytek"
    
    country_code = get_country_from_domain(start_domain)

    db_setup_start = time.time()
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
            print(f" Created partner: {partner_name} ({country_code})")
        else:
            print(f" Found partner: {partner_name} ({country_code})")
        
        partner_id = partner.partner_id
    finally:
        db.close()
    db_setup_time = time.time() - db_setup_start

    inserter = AsyncDatabaseInserter(partner_id, start_domain, batch_size=100)

    map_start = time.time()
    print(" Step 1: Discovering URLs...")
    try:
        map_result = client.map(
            url=start_url, 
            limit=MAX_PAGES
        )
        
        all_urls = []
        if hasattr(map_result, 'links'):
            for link in map_result.links:
                if hasattr(link, 'url'):
                    all_urls.append(link.url)
        
        discovered_urls = [
            url for url in all_urls 
            if urlparse(url).netloc.replace("www.", "").split('.')[-1] == start_tld
        ]
        
        print(f" Discovered {len(discovered_urls)} URLs")
        
        # ============================================================
        # PRE-FILTER: Skip already scraped URLs
        # ============================================================
        print(f" Checking for already scraped URLs...")
        
        db = SessionLocal()
        try:
            existing_urls = set(
                canonical_url(url) for (url,) in db.query(Product.product_url)
                .filter_by(partner_id=partner_id)
                .distinct()
            )
        finally:
            db.close()
        
        canonical_discovered = {canonical_url(url): url for url in discovered_urls}
        filtered_urls = [
            original_url 
            for canon_url, original_url in canonical_discovered.items()
            if canon_url not in existing_urls
        ]
        
        skipped = len(discovered_urls) - len(filtered_urls)
        
        map_time = time.time() - map_start
        print(f" Found {len(filtered_urls)} NEW URLs (skipped {skipped} already scraped)")
        print(f"  URL filtering completed in {format_time(map_time)}\n")
        
        if not filtered_urls:
            inserter.close()
            print("  No new URLs to scrape ")
            return {
                "success": True,
                "partner_id": str(partner_id),
                "partner_name": partner_name,
                "stats": {"added": 0, "duplicates": 0, "invalid": 0, "total": 0, "skipped": skipped},
                "timing": {"total": time.time() - total_start, "map": map_time}
            }
            
    except Exception as e:
        print(f"Map failed: {e}")
        inserter.close()
        return {
            "success": False, 
            "error": str(e),
            "timing": {"total": time.time() - total_start}
        }

    scrape_start = time.time()
    print(f" Batch scraping {len(filtered_urls)} NEW URLs...")
    try:
        batch_job = client.batch_scrape(
            urls=filtered_urls,
            formats=[{"type": "json", "schema": PRODUCT_SCHEMA}],
            only_main_content=True,
            poll_interval=POLL_INTERVAL,
            max_age=3600000,  # Cache for repeated scrapes
        )
        
        pages = batch_job.data if hasattr(batch_job, 'data') else []
        scrape_time = time.time() - scrape_start
        print(f" Scraped {len(pages)} pages in {format_time(scrape_time)}\n")
        
    except Exception as e:
        print(f" Batch scrape failed: {e}")
        inserter.close()
        return {
            "success": False, 
            "error": str(e),
            "timing": {
                "map": map_time,
                "total": time.time() - total_start
            }
        }

    processing_start = time.time()
    print(f"  Processing {len(pages)} pages with {MAX_WORKERS} parallel workers...\n")
    
    # OPTIMIZED: Parallel page processing with ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        page_data = [(page, idx) for idx, page in enumerate(pages, 1)]
        results = executor.map(process_page, page_data)
        
        # Add all products to async inserter
        for products in results:
            for product in products:
                inserter.add_product(product)
    
    # Wait for background writer to finish
    print(f"\n Waiting for database writes to complete...")
    inserter.close()
    
    stats = inserter.get_stats()
    stats["skipped"] = skipped
    processing_time = time.time() - processing_start
    total_time = time.time() - total_start

    print("\n" + "="*70)
    print(" SCRAPING COMPLETE")
    print("="*70)
    print(f"Partner       : {partner_name} ({country_code})")
    print(f" Added      : {stats['added']}")
    print(f" Duplicates : {stats['duplicates']}")
    print(f"  Skipped    : {stats['skipped']} (already scraped)")
    print(f" Invalid    : {stats['invalid']}")
    print(f" Total      : {stats['total']}")
    print("="*70)
    print("  TIMING BREAKDOWN")
    print("="*70)
    print(f"Database Setup : {format_time(db_setup_time)}")
    print(f"URL Discovery  : {format_time(map_time)}")
    print(f"Batch Scraping : {format_time(scrape_time)}")
    print(f"DB Processing  : {format_time(processing_time)}")
    print(f"{'─'*70}")
    print(f"TOTAL TIME     : {format_time(total_time)}")
    print("="*70)
    
    if total_time > 0 and len(pages) > 0:
        pages_per_sec = len(pages) / total_time
        products_per_sec = stats['added'] / total_time if stats['added'] > 0 else 0
        print(f" Speed       : {pages_per_sec:.1f} pages/sec")
        print(f" Speed       : {products_per_sec:.1f} products/sec")
        print("="*70)

    return {
        "success": True,
        "partner_id": str(partner_id),
        "partner_name": partner_name,
        "stats": stats,
        "timing": {
            "total": total_time,
            "db_setup": db_setup_time,
            "map": map_time,
            "scrape": scrape_time,
            "processing": processing_time
        },
        "speeds": {
            "pages_per_sec": len(pages) / total_time if total_time > 0 else 0,
            "products_per_sec": stats['added'] / total_time if total_time > 0 and stats['added'] > 0 else 0
        }
    }



if __name__ == "__main__":
    start_url = sys.argv[1] if len(sys.argv) > 1 else "https://www.virginmegastore.ae/en"
    
  
    
    result = crawl_entire_site(start_url)
    
    if result.get("success"):
        print(f"\n Products ready for  processing!")
    else:
        print(f"\n Failed: {result.get('error')}")
