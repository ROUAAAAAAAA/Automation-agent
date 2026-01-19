import json
import os
import sys
from datetime import datetime
from urllib.parse import urlparse
from typing import Any, cast, List, Dict
from dotenv import load_dotenv
from firecrawl import Firecrawl
import traceback


load_dotenv()

API_KEY = os.getenv("FIRECRAWL_API_KEY")
if not API_KEY:
    raise RuntimeError("FIRECRAWL_API_KEY missing from environment")

OUTPUT_DIR = "scraped_products"
MAX_PAGES = 20
POLL_INTERVAL = 5


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


PRODUCT_EXTRACTION_PROMPT = """
You are an expert e-commerce product extractor.

ALWAYS return valid JSON in this format:
{"products": []}

RULES:
- If the page contains products, extract ALL visible products
- Works for category pages AND single product pages
- Extract product_name for each product
- Extract any available price, currency, brand, image, description, SKU
- If individual product URLs are visible, include them
- Otherwise use the current page URL
- If no products exist, return an empty array
- Do NOT hallucinate products
"""


def canonical_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")


def crawl_entire_site(start_url: str) -> List[Dict[str, Any]]:
    client = Firecrawl(api_key=API_KEY)

    parsed_start = urlparse(start_url)
    start_domain = parsed_start.netloc.replace("www.", "")
    start_tld = start_domain.split('.')[-1]  # e.g. "ae", "com"

    print(f"\n Starting crawl: {start_domain}")
    print(f" Start URL: {start_url}\n")

    try:
        result = client.crawl(
            url=start_url,
            limit=MAX_PAGES,
            crawl_entire_domain=True,
            max_discovery_depth=3,
            
            scrape_options=cast(Any, {
                "formats": [{
                    "type": "json",
                    "schema": PRODUCT_SCHEMA,
                    "prompt": PRODUCT_EXTRACTION_PROMPT
                }],
                "onlyMainContent": True,
                "proxy": 'auto',
                "location": {"country": "AE", "languages": ["en"]}  # Enforce UAE proxy
                
            }),
            poll_interval=POLL_INTERVAL
        )

        pages = getattr(result, "data", None)
        if not pages:
            print(" Crawl finished but no pages returned")
            return []

    except Exception as e:
        print(f" Crawl failed: {e}")
        traceback.print_exc()
        return []

    print(f" Processing {len(pages)} pages...\n")

    products: List[Dict[str, Any]] = []
    seen = set()

    for idx, page in enumerate(pages, start=1):
        try:
            page_url = getattr(page, "url", None)

            # Enforce country restriction ONLY if URL exists
            if page_url:
                page_netloc = urlparse(page_url).netloc.replace("www.", "")
                page_tld = page_netloc.split('.')[-1]

                if page_tld != start_tld:
                    print(f"  ⚠️ Skipping page from another country: {page_url}")
                    continue
            else:
                page_url = "Unknown URL"

            data = getattr(page, "json", None)
            if not isinstance(data, dict):
                print(f" Page {idx}: Invalid JSON data, skipping: {page_url}")
                continue

            for product in data.get("products", []):
                if not product.get("product_name"):
                    continue

                if not product.get("product_url"):
                    product["product_url"] = page_url

                key = canonical_url(product["product_url"])
                if key in seen:
                    continue

                seen.add(key)
                product["scraped_at"] = datetime.now().isoformat()
                products.append(product)

                print(f"  ✓ [{idx}] {product['product_name'][:70]}")

        except Exception as e:
            print(f" Page {idx}: Failed to process {page_url} - {e}")
            traceback.print_exc()
            continue

    print(f"\n Total unique products found: {len(products)}")
    return products



def save_products(products: List[Dict[str, Any]], start_url: str) -> str:
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
        print(f"\n Saved products to: {filename}")
    except Exception as e:
        print(f" Failed to save products: {e}")
        traceback.print_exc()
    return filename


if __name__ == "__main__":
    import sys
    
    # Default URL if none provided
    start_url = sys.argv[1] if len(sys.argv) > 1 else "https://www.virginmegastore.ae/en"
    
    products = crawl_entire_site(start_url)
    
    if products:
        save_products(products, start_url)
        print("\nSample product:\n")
        print(json.dumps(products[0], indent=2))
    else:
        print("\n No products found. Check your crawl settings, Firecrawl API key, or site structure.")