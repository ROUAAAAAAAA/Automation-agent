from langchain_core.tools import tool
from typing import Union, List, Dict
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI
import os
import json
import dotenv

import sys
import os
from pathlib import Path


project_root = Path(__file__).parent.parent.parent 
sys.path.insert(0, str(project_root))
dotenv.load_dotenv()

def infer_category_with_llm(product_name: str, description: str, brand: str) -> str:
    """Use LLM to infer product category if missing."""
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        openai_api_key=os.getenv("OPENAI_API_KEY")
    )
    
    prompt = f"""What category does this product belong to? Return ONLY the category name (1-3 words).

Product: {product_name}
Brand: {brand}
Description: {description}

Examples:
- "iPhone 15" → "Smartphone"
- "Lip care set" → "Beauty & Cosmetics"
- "Kitchen knives" → "Kitchenware"
- "MacBook Air" → "Laptop"
- "Bluetooth speaker" → "Audio Equipment"
- "Samsung TV" → "Television"
- "PlayStation 5" → "Gaming Console"
- "Tripod" → "Camera Accessories"

Category:"""
    
    try:
        response = llm.invoke(prompt)
        category = response.content.strip().replace('"', '').replace("'", "")
        return category if len(category) < 50 else "General Product"
    except Exception as e:
        print(f"⚠️ Category inference failed: {e}")
        return "General Product"


def analyze_eligibility_with_llm(
    product_name: str, 
    category: str, 
    brand: str,
    price: float,
    currency: str,
    documents: List[Document]
) -> Dict:
    """
    Use LLM to analyze retrieved documents and determine eligibility.
    Uses SMART SEMANTIC MATCHING instead of exhaustive category lists.
    """
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        openai_api_key=os.getenv("OPENAI_API_KEY")
    )
    
    # Format documents for LLM
    docs_text = ""
    doc_filenames = []
    
    for i, doc in enumerate(documents[:6]):  
        filename = doc.metadata.get('file_name', 'Unknown')
        doc_filenames.append(filename)
        docs_text += f"\n\n{'='*70}\n[DOCUMENT {i+1}]: {filename}\n{'='*70}\n{doc.page_content}\n"
    
    # Determine market
    market = "UAE" if currency == "AED" else "Tunisia"
    
    # SMART PROMPT - No exhaustive lists, uses principles
    prompt = f"""You are an insurance eligibility classifier. Your job: Find if the product category "{category}" is covered in the specification documents.

⚠️ CRITICAL RULES:
1. Use ONLY the provided documents
2. Do NOT use external knowledge
3. **Same category = same answer ALWAYS** (consistency is critical)
4. Use SEMANTIC MATCHING (meaning-based, not just exact text)

==========================================
PRODUCT TO CLASSIFY
==========================================
Product Name: {product_name}
Category: {category}
Brand: {brand}
Price: {price} {currency}
Market: {market}
==========================================

SPECIFICATION DOCUMENTS ({market} ONLY)
==========================================
{docs_text}
==========================================

🎯 CLASSIFICATION PROCESS
==========================================

STEP 1: VALIDATE MARKET DOCUMENTS
-------------------------------------------
Check: Are these {market} specification documents?
- UAE documents: Filenames with "UAE", "ESSENTIAL", "FINAL" (NOT "_TN")
- Tunisia documents: Filenames with "TUNISIA" or "_TN"

❌ If wrong market → NOT ELIGIBLE
   Reason: "No {market} specification documents available"

STEP 2: CHECK LUXURY PRODUCTS (SPECIAL CASE)
-------------------------------------------
Is this a luxury/designer product?
- Luxury brands: Hermès, Louis Vuitton, Gucci, Chanel, Prada, Rolex, Cartier, Tiffany, Dior, Versace, Balenciaga, Fendi, Burberry, etc.
- Price indicator: > 10,000 AED or > 5,000 TND
- Keywords: "luxury", "designer", "haute couture", "premium collection"

If YES → Look for OPULENCIA_PREMIUM specification FIRST
If NO → Continue to Step 3

STEP 3: SEMANTIC CATEGORY MATCHING (SMART!)
-------------------------------------------
Your task: Find if "{category}" (or its semantic equivalents) appears in the specification documents.

🧠 SEMANTIC MATCHING RULES:

1️⃣ **PLURAL/SINGULAR EQUIVALENCE**
   "Smartphone" = "Smartphones"
   "Laptop" = "Laptops"
   "Washing Machine" = "Washing Machines"
   → Always treat singular and plural as IDENTICAL

2️⃣ **COMMON SYNONYMS** (Use your knowledge of English)
   "Mobile" = "Smartphone" = "Phone" = "Cell Phone"
   "Notebook" = "Laptop" = "Portable Computer"
   "Fridge" = "Refrigerator"
   "TV" = "Television"
   "E-Bike" = "Electric Bike"
   "Headset" = "Headphone" = "Earphone" = "Earbud"
   → Check for ALL common synonyms

3️⃣ **BRAND-SPECIFIC TERMS**
   "MacBook" → Look for "Laptops"
   "iPad" → Look for "Tablets"
   "AirPods" → Look for "Headphones" or "Earbuds"
   "PlayStation" → Look for "Gaming Consoles"
   → Strip brand names, match generic category

4️⃣ **HYPHENATION/SPACING**
   "Washing Machine" = "Washing-Machine" = "WashingMachine"
   "Smart Watch" = "Smartwatch" = "Smart-Watch"
   → Ignore spacing and hyphenation differences

5️⃣ **DESCRIPTIVE PREFIXES** (Usually ignorable)
   "Wireless Headphones" → Look for "Headphones"
   "Smart TV" → Look for "TV" or "Television"
   "Electric Scooter" → Look for "Scooter" or "Electric Scooter"
   → Try both with and without prefixes

WHERE TO SEARCH:
✓ "Eligible Products" section
✓ "Included Products" section
✓ "Covered Products" section
✓ "Product Categories" section
✓ "Included Categories" section
✓ Risk profile lists (e.g., "ELECTRONIC_PRODUCTS: Smartphones, Laptops...")

HOW TO SEARCH:
1. First: Look for EXACT match of "{category}"
2. Then: Check singular/plural variant
3. Then: Check common synonyms (from rules above)
4. Then: Check generic category if it's a brand-specific term

EXAMPLE MATCHING LOGIC:
- Input category: "Mobile"
  → Search for: "Mobile", "Mobiles", "Smartphone", "Smartphones", "Phone", "Phones", "Cell Phone"
  
- Input category: "MacBook"
  → Strip brand → Generic: "Laptop"
  → Search for: "Laptop", "Laptops", "Notebook", "Notebooks", "Portable Computer"

- Input category: "Wireless Headphone"
  → Remove prefix → Core: "Headphone"
  → Search for: "Headphone", "Headphones", "Earphone", "Earphones", "Earbud", "Earbuds", "Headset"

✅ If you find a match (exact OR semantic) → Category is COVERED → Continue to Step 4
❌ If NO match found → Category is NOT COVERED → NOT ELIGIBLE
   Reason: "Category '{category}' and its semantic equivalents not found in {market} specification documents"

STEP 4: CHECK EXCLUSIONS
-------------------------------------------
Search exclusions sections:
✓ "Excluded Products"
✓ "Not Covered"
✓ "Exclusions"
IMPORTANT: be aware the categories Textiles, Footwear, Clothing are only eligible if the brand is "ZARA".

Is the product category or type in exclusions?
✅ YES → NOT ELIGIBLE (Reason: "Product category is explicitly excluded")
❌ NO → Continue to Step 5

STEP 5: EXTRACT DETAILS (ELIGIBLE)
-------------------------------------------
Product is ELIGIBLE! Extract:
1. **risk_profile**: Exact risk profile code (e.g., "ELECTRONIC_PRODUCTS")
2. **document_used**: Filename of specification used
3. **coverage_modules**: List of coverage modules/benefits
4. **exclusions**: General exclusions that apply

==========================================
🔍 CONSISTENCY CHECK (CRITICAL!)
==========================================
Before responding, ask yourself:

❓ If I see another product with category "{category}" tomorrow:
   - Would I give it the SAME result?
   - Am I being consistent with my semantic matching rules?
   - Did I check ALL common synonyms?

❓ Verification:
   □ Used correct {market} documents?
   □ Applied semantic matching rules correctly?
   □ Checked singular AND plural forms?
   □ Checked common synonyms?
   □ Stripped brand names to generic categories?
   □ Same category would ALWAYS get same result?

==========================================
📤 RESPONSE FORMAT (JSON ONLY)
==========================================
Return ONLY valid JSON:

{{
  "eligible": true or false,
  "reason": "If NOT eligible: explain which step failed and what you searched for. If eligible: 'Product category is covered under {market} specifications'",
  "risk_profile": "EXACT_RISK_PROFILE_CODE" or null,
  "document_used": "filename.pdf" or null,
  "document_type": "STANDARD",
  "coverage_modules": ["Module 1", "Module 2", ...] or [],
  "exclusions": ["Exclusion 1", "Exclusion 2", ...] or [],
  "semantic_matches_checked": ["term1", "term2", "term3"] (list of synonyms you searched for)
}}

Think step-by-step, apply semantic matching rules, then respond with JSON:"""
    
    try:
        response = llm.invoke(prompt)
        content = response.content.strip()
        
        # Clean JSON formatting
        if content.startswith("```json"):
            content = content.replace("```json", "").replace("```", "").strip()
        elif content.startswith("```"):
            content = content.replace("```", "").strip()
        
        # Parse JSON
        result = json.loads(content)
        
        # Validate and set defaults
        result.setdefault("eligible", False)
        result.setdefault("reason", "Unknown reason")
        result.setdefault("risk_profile", None)
        result.setdefault("document_used", None)
        result.setdefault("document_type", "STANDARD")
        result.setdefault("coverage_modules", [])
        result.setdefault("exclusions", [])
        result.setdefault("semantic_matches_checked", [])
        
        # Force document_type to STANDARD
        result["document_type"] = "STANDARD"
        
        # ==========================================
        # POST-PROCESSING: VALIDATE MARKET MATCH
        # ==========================================
        if result.get("eligible"):
            risk_profile = result.get("risk_profile", "").lower()
            doc_used = result.get("document_used", "").lower()
            
            # Check for market mismatch
            if market == "UAE":
                # UAE product should NOT have Tunisia spec
                if "_tn" in risk_profile or "tunisia" in doc_used:
                    print(f"⚠️  VALIDATION FAILED: UAE product with Tunisia spec!")
                    result = {
                        "eligible": False,
                        "reason": f"Market mismatch: UAE product incorrectly classified with Tunisia specification ({doc_used}). This product is not eligible.",
                        "risk_profile": None,
                        "document_used": None,
                        "document_type": "STANDARD",
                        "coverage_modules": [],
                        "exclusions": [],
                        "semantic_matches_checked": []
                    }
            elif market == "Tunisia":
                # Tunisia product SHOULD have Tunisia spec
                if "_tn" not in risk_profile and "tunisia" not in doc_used and \
                   not any(x in doc_used for x in ["essential", "uae"]):
                    print(f"⚠️  VALIDATION FAILED: Tunisia product with UAE spec!")
                    result = {
                        "eligible": False,
                        "reason": f"Market mismatch: Tunisia product incorrectly classified with UAE specification ({doc_used}). This product is not eligible.",
                        "risk_profile": None,
                        "document_used": None,
                        "document_type": "STANDARD",
                        "coverage_modules": [],
                        "exclusions": [],
                        "semantic_matches_checked": []
                    }
        
        # Log what synonyms were checked (for debugging)
        if result.get("semantic_matches_checked"):
            print(f"   🔍 Checked synonyms: {', '.join(result['semantic_matches_checked'][:5])}")
        
        return result
        
    except json.JSONDecodeError as e:
        print(f"❌ LLM returned invalid JSON: {e}")
        print(f"Response was: {content[:200]}...")
        return {
            "eligible": False,
            "reason": f"Failed to parse classification response: {str(e)}",
            "risk_profile": None,
            "document_used": None,
            "document_type": "STANDARD",
            "coverage_modules": [],
            "exclusions": [],
            "semantic_matches_checked": []
        }
    except Exception as e:
        print(f"❌ Classification error: {e}")
        return {
            "eligible": False,
            "reason": f"Classification error: {str(e)}",
            "risk_profile": None,
            "document_used": None,
            "document_type": "STANDARD",
            "coverage_modules": [],
            "exclusions": [],
            "semantic_matches_checked": []
        }


@tool
def classify_product(
    product_name: str,
    category: str = "",
    brand: str = "",
    price: Union[float, int, str] = 0.0,
    currency: str = "AED",
    description: str = ""
) -> dict:
    """
    Classify product and determine insurance eligibility.
    
    Now with SMART SEMANTIC MATCHING - no exhaustive category lists needed!
    
    This tool:
    1. Infers category if missing (using LLM)
    2. Retrieves MARKET-SPECIFIC specification documents from RAG
    3. Analyzes eligibility using SEMANTIC MATCHING (meaning-based)
    4. Returns structured classification
    
    Args:
        product_name: Name of the product
        category: Product category (inferred if missing)
        brand: Brand name
        price: Product price
        currency: AED (UAE) or TND (Tunisia)
        description: Product description
    
    Returns:
        dict with:
        - product info (name, brand, category, price, currency, market)
        - classification (eligible, reason, risk_profile, document_type, coverage_modules, exclusions)
    """
    # Convert price
    try:
        price_float = float(price) if price else 0.0
    except (ValueError, TypeError):
        price_float = 0.0
    
    # Determine market
    market = "UAE" if currency == "AED" else "Tunisia" if currency == "TND" else "UAE"
    
    # Infer category if missing
    original_category = category
    if not category or category.strip() in ["N/A", "", "Unknown", "General", "None"]:
        print(f"🔍 Inferring category for: {product_name[:50]}...")
        category = infer_category_with_llm(product_name, description, brand)
        print(f"   Category: '{original_category or 'N/A'}' → '{category}'")
    
    print(f"\n{'='*70}")
    print(f"📋 CLASSIFYING PRODUCT")
    print(f"{'='*70}")
    print(f"Name: {product_name[:60]}")
    print(f"Category: {category}")
    print(f"Brand: {brand or 'N/A'}")
    print(f"Price: {price_float} {currency}")
    print(f"Market: {market}")
    print(f"{'='*70}\n")
    
    # ==========================================
    # STEP 2: RETRIEVE MARKET-SPECIFIC DOCUMENTS
    # ==========================================
    from ai_agent.rag.retriever import retrieve_specs_raw
    
    # Build market-specific query
    market_hint = "UAE ESSENTIAL" if market == "UAE" else "TUNISIA TN"
    query = f"{product_name} {category} {brand} {market_hint} insurance specification eligible coverage"
    
    print(f"🔍 Retrieving {market}-specific specifications...")
    print(f"   Query: {query[:80]}...")
    
    try:
        # CRITICAL: Pass market parameter to filter docs
        docs = retrieve_specs_raw(query, k=6, market=market)
        print(f"✓  Retrieved {len(docs)} {market}-specific documents")
    except Exception as e:
        print(f"❌  Retrieval failed: {e}")
        docs = []
    
    # Remove duplicates
    seen_files = set()
    unique_docs = []
    for doc in docs:
        filename = doc.metadata.get('file_name', '')
        if filename and filename not in seen_files:
            seen_files.add(filename)
            unique_docs.append(doc)
    
    # Sort: STANDARD specs first
    def sort_key(doc):
        filename = doc.metadata.get('file_name', '').lower()
        if 'garantyaffinity' in filename or 'dev_spec' in filename:
            return 0
        elif 'opulencia' in filename:
            return 1
        elif 'assurmax' in filename:
            return 2
        else:
            return 3
    
    unique_docs.sort(key=sort_key)
    
    print(f"\n📄 Using {len(unique_docs)} unique {market} documents:")
    for doc in unique_docs:
        filename = doc.metadata.get('file_name', 'Unknown')
        doc_type = "📋" if any(x in filename.lower() for x in ['garantyaffinity', 'dev_spec', 'opulencia']) else "⚡"
        print(f"   {doc_type} {filename}")
    
    if not unique_docs:
        print(f"\n❌ No {market} specification documents found for category '{category}'\n")
        return {
            "product_name": product_name,
            "brand": brand,
            "category": category,
            "price": price_float,
            "currency": currency,
            "market": market,
            "classification": {
                "eligible": False,
                "reason": f"No {market} insurance specification documents found for product category '{category}'",
                "risk_profile": None,
                "document_used": None,
                "document_type": "STANDARD",
                "coverage_modules": [],
                "exclusions": []
            }
        }
    
    # ==========================================
    # STEP 3: ANALYZE ELIGIBILITY WITH SEMANTIC MATCHING
    # ==========================================
    print(f"\n🤖 Analyzing eligibility with SEMANTIC MATCHING...")
    classification = analyze_eligibility_with_llm(
        product_name, 
        category, 
        brand,
        price_float,
        currency,
        unique_docs
    )
    
    # Print result
    if classification['eligible']:
        print(f"✅  ELIGIBLE for insurance")
        print(f"   Risk Profile: {classification.get('risk_profile', 'N/A')}")
        print(f"   Document Used: {classification.get('document_used', 'N/A')}")
        print(f"✓  Market validation: PASSED")
    else:
        print(f"❌  NOT ELIGIBLE")
        print(f"   Reason: {classification.get('reason', 'Unknown')[:120]}")
    
    print(f"{'='*70}\n")
    
    # ==========================================
    # STEP 4: RETURN STRUCTURED RESULT
    # ==========================================
    return {
        "product_name": product_name,
        "brand": brand,
        "category": category,
        "price": price_float,
        "currency": currency,
        "market": market,
        "classification": classification
    }


# ==========================================
# TEST FUNCTION
# ==========================================

if __name__ == "__main__":
    """Test the semantic matching classifier"""
    
    print("\n" + "="*80)
    print("TESTING SEMANTIC MATCHING PRODUCT CLASSIFIER")
    print("="*80)
    
    # Test with various category formats to prove consistency
    test_products = [
        # Smartphones - different ways to say it
        {"product_name": "iPhone 15 Pro Max", "category": "Smartphone", "brand": "Apple", "price": 4500, "currency": "AED"},
        {"product_name": "Samsung Galaxy S24", "category": "Mobile", "brand": "Samsung", "price": 3200, "currency": "AED"},
        {"product_name": "Google Pixel 8", "category": "Phone", "brand": "Google", "price": 2800, "currency": "AED"},
        {"product_name": "OnePlus 12", "category": "Cell Phone", "brand": "OnePlus", "price": 3000, "currency": "AED"},
        
        # Laptops - different ways to say it
        {"product_name": "MacBook Pro 16", "category": "Laptop", "brand": "Apple", "price": 12000, "currency": "AED"},
        {"product_name": "Dell XPS 15", "category": "Notebook", "brand": "Dell", "price": 8000, "currency": "AED"},
        {"product_name": "MacBook Air M2", "category": "MacBook", "brand": "Apple", "price": 6000, "currency": "AED"},
        
        # TVs - different ways to say it
        {"product_name": "Samsung QLED 65", "category": "TV", "brand": "Samsung", "price": 5000, "currency": "AED"},
        {"product_name": "LG OLED 55", "category": "Television", "brand": "LG", "price": 4500, "currency": "AED"},
        {"product_name": "Sony Bravia 75", "category": "Smart TV", "brand": "Sony", "price": 7000, "currency": "AED"},
    ]
    
    results_by_category_type = {}
    
    for product in test_products:
        result = classify_product.invoke(product)
        
        # Group by category type
        category_type = product["product_name"].split()[0]  # iPhone, Samsung, Google, etc.
        if category_type not in results_by_category_type:
            results_by_category_type[category_type] = []
        
        results_by_category_type[category_type].append({
            "name": result['product_name'],
            "category": result['category'],
            "eligible": result['classification']['eligible'],
            "risk_profile": result['classification'].get('risk_profile')
        })
    
    # Check consistency
    print(f"\n{'='*80}")
    print("CONSISTENCY CHECK")
    print(f"{'='*80}\n")
    
    print("📱 SMARTPHONES (should all have same eligibility):")
    for result in results_by_category_type.get("iPhone", []) + results_by_category_type.get("Samsung", []) + \
                  results_by_category_type.get("Google", []) + results_by_category_type.get("OnePlus", []):
        status = "✅" if result["eligible"] else "❌"
        print(f"  {status} {result['name'][:25]:25} | Category: {result['category']:15} | Eligible: {result['eligible']}")
    
    print("\n💻 LAPTOPS (should all have same eligibility):")
    for result in results_by_category_type.get("MacBook", []) + results_by_category_type.get("Dell", []):
        status = "✅" if result["eligible"] else "❌"
        print(f"  {status} {result['name'][:25]:25} | Category: {result['category']:15} | Eligible: {result['eligible']}")
    
    print("\n📺 TVs (should all have same eligibility):")
    for result in results_by_category_type.get("Samsung", []) + results_by_category_type.get("LG", []) + \
                  results_by_category_type.get("Sony", []):
        if "TV" in result["name"] or "OLED" in result["name"] or "Bravia" in result["name"]:
            status = "✅" if result["eligible"] else "❌"
            print(f"  {status} {result['name'][:25]:25} | Category: {result['category']:15} | Eligible: {result['eligible']}")