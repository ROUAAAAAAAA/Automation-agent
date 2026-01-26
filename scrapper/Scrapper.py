import json
import os
import sys
from datetime import datetime
from urllib.parse import urlparse
from typing import Any, List, Dict
from dotenv import load_dotenv
from firecrawl import Firecrawl
import traceback
import time


load_dotenv()

API_KEY = os.getenv("FIRECRAWL_API_KEY")
if not API_KEY:
    raise RuntimeError("FIRECRAWL_API_KEY missing from environment")

OUTPUT_DIR = "scraped_products"
MAX_PAGES = 100
POLL_INTERVAL = 2


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
                    "sku": {"type": ["string", "null"]}
                },
                "required": ["product_name"]
            }
        }
    }
}


def canonical_url(url: str) -> str:
    """Normalize URLs for deduplication"""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")


def crawl_entire_site(start_url: str) -> List[Dict[str, Any]]:
    """
    Fast scraping using Map + Batch Scrape strategy:
    1. Use Map endpoint to discover all URLs (very fast)
    2. Use Batch Scrape to scrape all URLs in parallel
    """
    client = Firecrawl(api_key=API_KEY)
    
    parsed_start = urlparse(start_url)
    start_domain = parsed_start.netloc.replace("www.", "")
    start_tld = start_domain.split('.')[-1]

    print(f"\n🚀 Starting FAST crawl: {start_domain}")
    print(f"📍 Start URL: {start_url}\n")

    # STEP 1: Use Map endpoint to discover all URLs (EXTREMELY FAST)
    print("🗺️  Step 1: Discovering URLs with Map endpoint...")
    try:
        map_result = client.map(
            url=start_url,
            limit=MAX_PAGES
        )
        
        # Extract URLs from map result - LinkResult objects have .url attribute
        all_urls = []
        
        # The map result should have a 'links' attribute
        if hasattr(map_result, 'links'):
            links = map_result.links
            # Each link is a LinkResult object with .url attribute
            for link in links:
                if hasattr(link, 'url'):
                    all_urls.append(link.url)
        else:
            print(f"❌ Unexpected map result format: {type(map_result)}")
            print(f"Available attributes: {dir(map_result)}")
            return []
        
        # Filter URLs by TLD to stay in same country
        filtered_urls = []
        for url in all_urls:
            try:
                url_netloc = urlparse(url).netloc.replace("www.", "")
                url_tld = url_netloc.split('.')[-1]
                if url_tld == start_tld:
                    filtered_urls.append(url)
            except Exception as e:
                print(f"  ⚠️  Skipping invalid URL: {url}")
                continue
        
        print(f"✅ Discovered {len(filtered_urls)} URLs (filtered from {len(all_urls)} total)\n")
        
        if not filtered_urls:
            print("❌ No URLs discovered. Exiting.")
            return []
            
    except Exception as e:
        print(f"❌ Map failed: {e}")
        traceback.print_exc()
        return []

    # STEP 2: Use Batch Scrape to scrape all URLs in parallel
    print(f"🔥 Step 2: Batch scraping {len(filtered_urls)} URLs in parallel...")
    try:
        # Start batch scrape job with correct parameter names
        batch_job = client.batch_scrape(
            urls=filtered_urls,
            formats=[{
                "type": "json",
                "schema": PRODUCT_SCHEMA,
            }],
            only_main_content=True,
            poll_interval=POLL_INTERVAL
        )
        
        print(f"✅ Batch scrape completed!")
        
        # Check what attributes the batch_job has
        if hasattr(batch_job, 'status'):
            print(f"📊 Status: {batch_job.status}")
        if hasattr(batch_job, 'total'):
            print(f"📄 Total pages: {batch_job.total}")
        if hasattr(batch_job, 'completed'):
            print(f"✓ Completed: {batch_job.completed}\n")
        
        # Get pages from batch result
        if hasattr(batch_job, 'data'):
            pages = batch_job.data
        else:
            print(f"❌ Unexpected batch result format")
            print(f"Available attributes: {dir(batch_job)}")
            return []
        
    except Exception as e:
        print(f"❌ Batch scrape failed: {e}")
        traceback.print_exc()
        return []

    # STEP 3: Process results
    print(f"⚙️  Step 3: Processing {len(pages)} pages...\n")
    
    products: List[Dict[str, Any]] = []
    seen = set()
    
    for idx, page in enumerate(pages, start=1):
        try:
            page_url = getattr(page, "url", None) or "Unknown URL"
            
            # Get JSON data
            data = getattr(page, "json", None)
            if not isinstance(data, dict):
                continue
            
            # Extract products
            for product in data.get("products", []):
                if not product.get("product_name"):
                    continue
                
                # Set product URL
                if not product.get("product_url"):
                    product["product_url"] = page_url
                
                # Deduplicate
                key = canonical_url(product["product_url"])
                if key in seen:
                    continue
                
                seen.add(key)
                product["scraped_at"] = datetime.now().isoformat()
                products.append(product)
                
                print(f"  ✓ [{idx}] {product['product_name'][:70]}")
                
        except Exception as e:
            print(f"  ⚠️  Page {idx}: Error - {e}")
            continue

    print(f"\n✨ Total unique products found: {len(products)}")
    return products


def save_products(products: List[Dict[str, Any]], start_url: str) -> str:
    """Save products to JSON file"""
    domain = urlparse(start_url).netloc.replace("www.", "")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    filename = f"{OUTPUT_DIR}/{domain}_products_{datetime.now():%Y%m%d_%H%M%S}.json"
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump({
                "metadata": {
                    "domain": domain,
                    "start_url": start_url,
                    "scraped_at": datetime.now().isoformat(),
                    "product_count": len(products)
                },
                "products": products
            }, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Saved products to: {filename}")
    except Exception as e:
        print(f"❌ Failed to save products: {e}")
        traceback.print_exc()
    return filename


if __name__ == "__main__":
    # Default URL if none provided
    start_url = sys.argv[1] if len(sys.argv) > 1 else "https://www.virginmegastore.ae/en"
    
    print("=" * 70)
    print("🔥 FIRECRAWL FAST PRODUCT SCRAPER")
    print("=" * 70)
    
    start_time = time.time()
    
    products = crawl_entire_site_fast(start_url)
    
    elapsed = time.time() - start_time
    
    if products:
        save_products(products, start_url)
        print("\n📦 Sample product:\n")
        print(json.dumps(products[0], indent=2))
        print(f"\n⏱️  Total time: {elapsed:.2f} seconds")
        print(f"⚡ Speed: {len(products)/elapsed:.2f} products/second")
    else:
        print("\n❌ No products found. Check your crawl settings or site structure.")
        print(f"⏱️  Total time: {elapsed:.2f} seconds")