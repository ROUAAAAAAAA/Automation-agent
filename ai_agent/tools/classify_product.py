from langchain_core.tools import tool
from typing import Union, List, Dict
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI
import os
import json
import dotenv

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
dotenv.load_dotenv()

def _get_llm():
    return ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        openai_api_key=os.getenv("OPENAI_API_KEY"),
    )


# ---------------------------------------------------------------------------
# LUXURY BRAND LIST (deterministic routing)
# ---------------------------------------------------------------------------

LUXURY_BRANDS = {
    "gucci", "prada", "louis vuitton", "lv",
    "hermes", "hermès", "dior", "balenciaga",
    "versace", "chanel", "burberry",
    "rolex", "cartier", "tiffany",
    "fendi", "givenchy", "valentino",
    "saint laurent", "ysl", "bottega veneta",
}


# ---------------------------------------------------------------------------
# SPEC FAMILY ROUTING (deterministic, no LLM)
# ---------------------------------------------------------------------------

SPEC_FAMILY_MAP = {
    # Electronics
    "smartphone": "ELECTRONICS",
    "mobile": "ELECTRONICS",
    "phone": "ELECTRONICS",
    "laptop": "ELECTRONICS",
    "notebook": "ELECTRONICS",
    "tablet": "ELECTRONICS",
    "television": "ELECTRONICS",
    "tv": "ELECTRONICS",
    "smartwatch": "ELECTRONICS",
    "smart watch": "ELECTRONICS",
    "gaming console": "ELECTRONICS",
    "console": "ELECTRONICS",
    "camera": "ELECTRONICS",
    "headphones": "ELECTRONICS",
    "earbuds": "ELECTRONICS",
    "speaker": "ELECTRONICS",
    "electronic accessory": "ELECTRONICS",
    "keyboard": "ELECTRONICS",
    "mouse": "ELECTRONICS",
    
    # Bags & Luggage
    "backpack": "BAGS_LUGGAGE",
    "suitcase": "BAGS_LUGGAGE",
    "luggage": "BAGS_LUGGAGE",
    "bag": "BAGS_LUGGAGE",
    "handbag": "BAGS_LUGGAGE",
    "wallet": "BAGS_LUGGAGE",
    "briefcase": "BAGS_LUGGAGE",
    
    # Furniture & Living
    "sofa": "FURNITURE",
    "couch": "FURNITURE",
    "bed": "FURNITURE",
    "table": "FURNITURE",
    "chair": "FURNITURE",
    "desk": "FURNITURE",
    "wardrobe": "FURNITURE",
    "cabinet": "FURNITURE",
    
    # Home Appliances
    "refrigerator": "HOME_APPLIANCES",
    "fridge": "HOME_APPLIANCES",
    "washing machine": "HOME_APPLIANCES",
    "dryer": "HOME_APPLIANCES",
    "dishwasher": "HOME_APPLIANCES",
    "oven": "HOME_APPLIANCES",
    "microwave": "HOME_APPLIANCES",
    "vacuum cleaner": "HOME_APPLIANCES",
    
    # Micromobility
    "electric scooter": "MICROMOBILITY",
    "e-scooter": "MICROMOBILITY",
    "electric bike": "MICROMOBILITY",
    "e-bike": "MICROMOBILITY",
    "hoverboard": "MICROMOBILITY",
    
    # Luxury
    "watch (luxury)": "LUXURY",
    "handbag (luxury)": "LUXURY",
    "jewelry": "LUXURY",
    
    # Health & Wellness
    "treadmill": "HEALTH_WELLNESS",
    "elliptical": "HEALTH_WELLNESS",
    "exercise bike": "HEALTH_WELLNESS",
    
    # Baby
    "stroller": "BABY",
    "car seat": "BABY",
    "high chair": "BABY",
    "crib": "BABY",
    
    # Optical
    "glasses": "OPTICAL",
    "sunglasses": "OPTICAL",
    "contact lenses": "OPTICAL",
    
    # Textiles (ZARA only for normal clothes, LUXURY for luxury brands)
    "clothing": "TEXTILES",
    "shoes": "TEXTILES",
    "footwear": "TEXTILES",
    "apparel": "TEXTILES",
    "shirt": "TEXTILES",
    "dress": "TEXTILES",
    "pants": "TEXTILES",
    "jacket": "TEXTILES",
}


# ---------------------------------------------------------------------------
# SPEC INTERPRETATION MODE (deterministic, no LLM)
# ---------------------------------------------------------------------------

SPEC_INTERPRETATION_MODE = {
    "ELECTRONICS": "CLASS_BASED",
    "BAGS_LUGGAGE": "OBJECT_EXHAUSTIVE",
    "FURNITURE": "OBJECT_EXHAUSTIVE",
    "HOME_APPLIANCES": "OBJECT_EXHAUSTIVE",
    "MICROMOBILITY": "OBJECT_EXHAUSTIVE",
    "HEALTH_WELLNESS": "OBJECT_EXHAUSTIVE",
    "BABY": "OBJECT_EXHAUSTIVE",
    "OPTICAL": "OBJECT_EXHAUSTIVE",
    "TEXTILES": "BRAND_RESTRICTED",  # ZARA ONLY
    "LUXURY": "BRAND_RESTRICTED",     # Luxury brands only
}


def route_to_spec_family(insurance_object: str) -> str | None:
    """
    Deterministic routing from insurance object to spec family.
    Uses substring matching to handle variations like "Smart phone", "Cell Phone", etc.
    Returns None if no match → product is out of scope entirely.
    """
    obj_lower = insurance_object.strip().lower()
    
    # Try substring matching to handle variations
    for key, family in SPEC_FAMILY_MAP.items():
        if key in obj_lower:
            return family
    
    return None


def infer_insurance_object_with_llm(product_name: str, description: str, brand: str) -> str:
    """
    Normalize the product to its INSURANCE OBJECT — what it actually IS 
    for insurance purposes, not its retail category.
    
    This must be spec-agnostic. A keyboard case is an "Electronic accessory",
    not a "Bag" or "Case". A luxury watch is a "Watch (luxury)", not "Jewelry".
    """
    llm = _get_llm()

    prompt = (
        "What IS this product from an insurance classification perspective? "
        "Return ONLY the insurance object type (1-4 words), nothing else.\n\n"
        f"Product: {product_name}\n"
        f"Brand: {brand}\n"
        f"Description: {description}\n\n"
        "CRITICAL RULES:\n"
        "- Electronic accessories (cases, covers, keyboards for devices) → 'Electronic accessory'\n"
        "- Standalone bags/backpacks/luggage → 'Backpack' or 'Suitcase' or 'Luggage'\n"
        "- Luxury brands (Hermès, Rolex, Cartier, etc.) → add '(luxury)' suffix\n"
        "- Be specific about the OBJECT, not the use case\n\n"
        "Examples:\n"
        '- "Apple Smart Folio for iPad" → "Electronic accessory"\n'
        '- "Samsung Tab Keyboard Case" → "Electronic accessory"\n'
        '- "ROG Gaming Backpack" → "Backpack"\n'
        '- "Leather Wallet" → "Wallet"\n'
        '- "iPhone 15 Pro" → "Smartphone"\n'
        '- "MacBook Air" → "Laptop"\n'
        '- "Electric Scooter" → "Electric scooter"\n'
        '- "Rolex Submariner" → "Watch (luxury)"\n'
        '- "Samsung QLED TV" → "Television"\n'
        '- "Sofa" → "Sofa"\n\n'
        "Insurance object:"
    )

    try:
        response = llm.invoke(prompt)
        obj = response.content.strip().replace('"', '').replace("'", "")
        return obj if len(obj) < 50 else "General Product"
    except Exception as e:
        print(f"⚠️  Insurance object inference failed: {e}")
        return "General Product"


# ---------------------------------------------------------------------------
# CORE: LLM-BASED ELIGIBILITY
# ---------------------------------------------------------------------------

def analyze_eligibility_with_llm(
    product_name: str,
    insurance_object: str,
    spec_family: str,
    interpretation_mode: str,
    brand: str,
    price: float,
    currency: str,
    documents: List[Document],
) -> Dict:
    """
    Ask the LLM to determine eligibility based on the interpretation mode.
    
    CLASS_BASED: Product must belong to a listed product class (e.g., smartphones → mobile devices)
    OBJECT_EXHAUSTIVE: Product must be explicitly listed (but ignoring modifiers)
    BRAND_RESTRICTED: Product must match both object AND brand restrictions
    """
    llm = _get_llm()
    market = "UAE" if currency == "AED" else "Tunisia"

    # --------------- build the docs block ---------------
    real_filenames: List[str] = []
    docs_block = ""
    for i, doc in enumerate(documents[:6]):
        fname = doc.metadata.get("file_name", "unknown")
        real_filenames.append(fname)
        docs_block += (
            f"\n--- DOCUMENT {i+1} | {fname} ---\n"
            f"{doc.page_content}\n"
        )

    # --------------- enhanced prompt with interpretation modes ---------------
    prompt = f"""You are a product-insurance eligibility classifier.

Your job: Determine if this product is eligible for insurance coverage based on the specification documents.

INTERPRETATION MODE: {interpretation_mode}

===== INTERPRETATION RULES =====

🔹 IF MODE = "CLASS_BASED" (e.g., ELECTRONICS):
   - The product is eligible if it belongs to a PRODUCT CLASS mentioned in the spec
   - Product classes are CATEGORIES of products, not individual items
   - Examples of valid class matches:
     • "Smartphone" / "Mobile" / "Phone" → "Mobile devices" ✅
     • "Laptop" / "Notebook" → "Tablets & Computers" ✅
     • "Headphones" / "Earbuds" → "Audio devices" ✅
     • "TV" / "Television" → "Televisions" ✅
     • "Smartwatch" / "Smart watch" → "Wearables" or "Mobile devices" ✅
   - Check for SEMANTIC CLASS MEMBERSHIP, not exact string matching
   
   🚨 CRITICAL ACCESSORY RULE:
   - Accessories (cases, covers, keyboard cases, folios, etc.) are ONLY eligible if:
     a) The spec explicitly mentions "accessories" as a covered class, OR
     b) The spec explicitly lists the specific accessory type
   - If the product is an accessory and the spec only lists primary devices (phones, laptops, etc.) → NOT eligible
   - Do NOT assume accessories are covered just because the primary device is covered
   
   - ALWAYS check exclusions — if explicitly excluded, NOT eligible

🔹 IF MODE = "OBJECT_EXHAUSTIVE" (e.g., BAGS, FURNITURE):
   - The CORE insurance object MUST be explicitly listed in "Eligible Products" or "Included Products"
   - Ignore modifiers/adjectives when matching — focus on the BASE product type
   - Examples of valid matches:
     • "Gaming Backpack" / "Travel Backpack" / "Laptop Backpack" → matches "Backpack" ✅
     • "Leather Sofa" / "Corner Sofa" / "3-Seater Sofa" → matches "Sofa" ✅
     • "Large Suitcase" / "Wheeled Suitcase" / "Hard-Shell Suitcase" → matches "Suitcase" ✅
     • "Designer Handbag" / "Leather Handbag" → matches "Handbag" ✅
   - The modifier (Gaming, Leather, Large, etc.) does NOT change the core object type
   - If the CORE object type is not listed → NOT eligible

🔹 IF MODE = "BRAND_RESTRICTED" (e.g., LUXURY, TEXTILES):
   - Product must match BOTH:
     1. Eligible product category/object
     2. Brand restrictions stated in the spec (e.g., "ZARA only", "luxury brands")
   
   🚨 CRITICAL BRAND RULES:
   - If the spec says "ZARA only" and the brand is NOT ZARA → NOT eligible
   - If the spec restricts to specific luxury brands and this brand is not listed → NOT eligible
   - Do NOT infer brand eligibility from product type alone
   - Check brand match EXPLICITLY before declaring eligible

===== ABSOLUTE RULES =====
1. Use ONLY information from the provided specification documents
2. Exclusions ALWAYS override inclusions
3. Return the EXACT document number (1-6) that justified your decision
4. Do NOT make up filenames, categories, or document numbers
5. If uncertain → NOT eligible (better safe than sorry)
6. For accessories in CLASS_BASED mode: default to NOT eligible unless explicitly covered
7. For OBJECT_EXHAUSTIVE mode: strip modifiers to find the core object (Gaming Backpack → Backpack)

===== PRODUCT DETAILS =====
Product Name      : {product_name}
Insurance Object  : {insurance_object}
Spec Family       : {spec_family}
Interpretation    : {interpretation_mode}
Brand             : {brand}
Price             : {price} {currency}
Market            : {market}

===== SPECIFICATION DOCUMENTS =====
{docs_block}

===== REQUIRED OUTPUT =====
Return ONLY valid JSON with this exact structure (no extra text, no markdown):
{{
  "eligible": true or false,
  "reason": "<concise explanation of why eligible or not eligible>",
  "matched_document_index": <integer 1-6 of the document that justified the decision, or null>,
  "risk_profile": "<risk profile code from document if eligible, or null>",
  "coverage_modules": ["list", "of", "modules"],
  "exclusions": ["list", "of", "exclusions"],
  "synonyms_checked": ["list", "of", "terms", "you", "searched", "for"]
}}

EXAMPLES OF CORRECT REASONING:

Example 1 (CLASS_BASED - ELIGIBLE):
Product: "iPhone 15 Pro", Object: "Smartphone", Mode: CLASS_BASED
Doc mentions: "Mobile devices"
→ eligible: true, reason: "Smartphone belongs to Mobile devices class"

Example 2 (CLASS_BASED - NOT ELIGIBLE - ACCESSORY):
Product: "Apple Smart Folio", Object: "Electronic accessory", Mode: CLASS_BASED
Doc mentions: "Mobile devices, Tablets & Computers, Audio" (no mention of accessories)
→ eligible: false, reason: "Accessories not explicitly covered in specification"

Example 3 (CLASS_BASED - NOT ELIGIBLE - EXCLUDED):
Product: "Microwave", Object: "Microwave", Mode: CLASS_BASED  
Doc mentions: "Mobile devices, Computers, Audio" but excludes "Home appliances"
→ eligible: false, reason: "Home appliances explicitly excluded"

Example 4 (OBJECT_EXHAUSTIVE - NOT ELIGIBLE):
Product: "Gaming Chair", Object: "Gaming Chair", Mode: OBJECT_EXHAUSTIVE
Doc lists: "Sofa, Bed, Table, Desk"
→ eligible: false, reason: "Chair (core object) not explicitly listed in eligible products"

Example 5 (BRAND_RESTRICTED - NOT ELIGIBLE):
Product: "H&M Shirt", Object: "Clothing", Mode: BRAND_RESTRICTED
Doc says: "ZARA products only"
→ eligible: false, reason: "Brand H&M does not match ZARA-only restriction"

Example 6 (OBJECT_EXHAUSTIVE - ELIGIBLE - MODIFIER IGNORED):
Product: "Gaming Backpack with LED", Object: "Backpack", Mode: OBJECT_EXHAUSTIVE
Doc lists: "Backpack, Suitcase, Handbag"
→ eligible: true, reason: "Backpack (core object) is explicitly listed"

Now analyze the product above:"""

    try:
        response = llm.invoke(prompt)
        content = response.content.strip()

        # strip markdown fences if present
        if content.startswith("```json"):
            content = content.replace("```json", "").replace("```", "").strip()
        elif content.startswith("```"):
            content = content.replace("```", "").strip()

        result = json.loads(content)

        # --------------- ground document_used in REAL metadata ---------------
        doc_idx = result.get("matched_document_index")
        if doc_idx and 1 <= doc_idx <= len(real_filenames):
            result["document_used"] = real_filenames[doc_idx - 1]
        else:
            result["document_used"] = None
            # If LLM said eligible but gave no valid doc index, that's suspicious
            if result.get("eligible"):
                result["eligible"] = False
                result["reason"] = (
                    "LLM returned eligible but did not ground the match "
                    "in a specific retrieved document."
                )

        # --------------- market-mismatch guard ---------------
        doc_used_lower = (result.get("document_used") or "").lower()
        if market == "UAE" and ("_tn" in doc_used_lower or "tunisia" in doc_used_lower):
            result["eligible"] = False
            result["reason"] = f"Market mismatch: matched Tunisia doc '{result['document_used']}' for a UAE product."
            result["document_used"] = None
        elif market == "Tunisia" and any(
            tag in doc_used_lower for tag in ("uae", "essential", "final")
        ) and "_tn" not in doc_used_lower:
            result["eligible"] = False
            result["reason"] = f"Market mismatch: matched UAE doc '{result['document_used']}' for a Tunisia product."
            result["document_used"] = None

        # --------------- defaults ---------------
        result.setdefault("eligible", False)
        result.setdefault("reason", "Unknown reason")
        result.setdefault("risk_profile", None)
        result.setdefault("document_type", "STANDARD")
        result.setdefault("coverage_modules", [])
        result.setdefault("exclusions", [])
        result.setdefault("synonyms_checked", [])
        result["document_type"] = "STANDARD"

        # rename for downstream compatibility
        result["semantic_matches_checked"] = result.pop("synonyms_checked", [])

        return result

    except json.JSONDecodeError as e:
        print(f"⚠️  LLM returned invalid JSON: {e}")
        return _empty_result(f"Failed to parse LLM response: {e}")
    except Exception as e:
        print(f"⚠️  Classification error: {e}")
        return _empty_result(str(e))


def _empty_result(reason: str) -> Dict:
    return {
        "eligible": False,
        "reason": reason,
        "risk_profile": None,
        "document_used": None,
        "document_type": "STANDARD",
        "coverage_modules": [],
        "exclusions": [],
        "semantic_matches_checked": [],
    }


# ---------------------------------------------------------------------------
# MAIN TOOL
# ---------------------------------------------------------------------------

@tool
def classify_product(
    product_name: str,
    category: str = "",
    brand: str = "",
    price: Union[float, int, str] = 0.0,
    currency: str = "AED",
    description: str = "",
) -> dict:
    """
    Classify product and determine insurance eligibility using spec-family routing.

    Pipeline:
        1. Normalize to INSURANCE OBJECT (spec-agnostic: "Electronic accessory", not "Case")
        2. Route to SPEC FAMILY (deterministic: ELECTRONICS, BAGS_LUGGAGE, etc.)
        3. Split TEXTILES into TEXTILES (ZARA) or LUXURY (luxury brands) based on brand
        4. Determine INTERPRETATION MODE (CLASS_BASED vs OBJECT_EXHAUSTIVE vs BRAND_RESTRICTED)
        5. Retrieve FAMILY-SCOPED docs from RAG (no cross-contamination)
        6. LLM checks eligibility using the correct interpretation mode

    This prevents false positives and enables correct class-based matching for electronics.

    Args:
        product_name: Name of the product
        category: Insurance object (inferred if missing)
        brand: Brand name
        price: Product price
        currency: AED (UAE) or TND (Tunisia)
        description: Product description

    Returns:
        dict with:
        - product info (name, brand, category, price, currency, market)
        - classification (eligible, reason, risk_profile, document_type, coverage_modules, exclusions)
    """
    # --------------- price normalisation ---------------
    try:
        price_float = float(price) if price else 0.0
    except (ValueError, TypeError):
        price_float = 0.0

    market = "UAE" if currency == "AED" else "Tunisia" if currency == "TND" else "UAE"

    # --------------- insurance object normalization if missing ---------------
    original_category = category
    if not category or category.strip() in ["N/A", "", "Unknown", "General", "None"]:
        print(f"🔍 Inferring insurance object for: {product_name[:50]}...")
        category = infer_insurance_object_with_llm(product_name, description, brand)
        print(f"   '{original_category or 'N/A'}' → '{category}'")

    print(f"\n{'='*70}")
    print(f"📦 CLASSIFYING PRODUCT")
    print(f"{'='*70}")
    print(f"  Name             : {product_name[:60]}")
    print(f"  Insurance Object : {category}")
    print(f"  Brand            : {brand or 'N/A'}")
    print(f"  Price            : {price_float} {currency}")
    print(f"  Market           : {market}")
    print(f"{'='*70}\n")

    # --------------- RAG retrieval — FAMILY-SCOPED ---------------
    from ai_agent.rag.retriever import retrieve_specs_raw

    # Route to spec family
    spec_family = route_to_spec_family(category)
    
    if spec_family is None:
        print(f"\n   ⚠️  Insurance object '{category}' does not map to any known spec family")
        return {
            "product_name": product_name,
            "brand": brand,
            "category": category,
            "price": price_float,
            "currency": currency,
            "market": market,
            "classification": _empty_result(
                f"Insurance object '{category}' is not covered by any available specification family."
            ),
        }
    
    # 🔥 TEXTILES SPLIT LOGIC: Separate ZARA from LUXURY brands
    if spec_family == "TEXTILES":
        brand_lower = (brand or "").lower()
        
        if brand_lower in LUXURY_BRANDS:
            spec_family = "LUXURY"
            print(f"   🔀 Rerouting: TEXTILES → LUXURY (luxury brand detected)")
    
    # Get interpretation mode
    interpretation_mode = SPEC_INTERPRETATION_MODE.get(spec_family, "OBJECT_EXHAUSTIVE")
    
    print(f"   Spec Family       : {spec_family}")
    print(f"   Interpretation    : {interpretation_mode}")
    
    # Query targets the spec family, not the product
    query = f"{spec_family} {market} insurance specification eligible products"

    print(f"🔎 Retrieving {spec_family} specs for {market}...")
    print(f"   Query: {query}")

    try:
        docs = retrieve_specs_raw(query, k=3, market=market)
        print(f"   Retrieved {len(docs)} documents")
    except Exception as e:
        print(f"   ❌ Retrieval failed: {e}")
        docs = []

    # --------------- dedup + sort ---------------
    seen, unique_docs = set(), []
    for doc in docs:
        fname = doc.metadata.get("file_name", "")
        if fname and fname not in seen:
            seen.add(fname)
            unique_docs.append(doc)

    print(f"\n   Using {len(unique_docs)} unique docs:")
    for d in unique_docs:
        print(f"     • {d.metadata.get('file_name', 'unknown')}")

    # --------------- no docs → early return ---------------
    if not unique_docs:
        print(f"\n   ⚠️  No {market} spec docs found for '{category}'")
        return {
            "product_name": product_name,
            "brand": brand,
            "category": category,
            "price": price_float,
            "currency": currency,
            "market": market,
            "classification": _empty_result(
                f"No {market} insurance specification documents found for product category '{category}'."
            ),
        }

    # --------------- LLM classification with interpretation mode ---------------
    print(f"\n🤖 Analyzing eligibility (mode: {interpretation_mode})...")
    classification = analyze_eligibility_with_llm(
        product_name,
        category,
        spec_family,
        interpretation_mode,
        brand,
        price_float,
        currency,
        unique_docs
    )

    # --------------- log & return ---------------
    if classification.get("eligible"):
        print(f"\n✅ ELIGIBLE")
        print(f"   Risk Profile : {classification.get('risk_profile')}")
        print(f"   Doc Used     : {classification.get('document_used')}")
    else:
        print(f"\n❌ NOT ELIGIBLE")
        print(f"   Reason: {classification.get('reason', 'Unknown')}")

    print(f"{'='*70}\n")

    return {
        "product_name": product_name,
        "brand": brand,
        "category": category,
        "price": price_float,
        "currency": currency,
        "market": market,
        "classification": classification,
    }


# ---------------------------------------------------------------------------
# QUICK SMOKE TEST
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("TESTING PRODUCT CLASSIFIER")
    print("=" * 80)

    test_products = [
        # Smartphones — different ways to say it
        {"product_name": "iPhone 15 Pro Max",  "category": "Smartphone",      "brand": "Apple",    "price": 4500,  "currency": "AED"},
        {"product_name": "Samsung Galaxy S24", "category": "Mobile",          "brand": "Samsung",  "price": 3200,  "currency": "AED"},
        {"product_name": "Google Pixel 8",     "category": "Phone",           "brand": "Google",   "price": 2800,  "currency": "AED"},
        {"product_name": "OnePlus 12",         "category": "Cell Phone",      "brand": "OnePlus",  "price": 3000,  "currency": "AED"},

        # Laptops — different ways to say it
        {"product_name": "MacBook Pro 16",     "category": "Laptop",          "brand": "Apple",    "price": 12000, "currency": "AED"},
        {"product_name": "Dell XPS 15",        "category": "Notebook",        "brand": "Dell",     "price": 8000,  "currency": "AED"},
        {"product_name": "MacBook Air M2",     "category": "MacBook",         "brand": "Apple",    "price": 6000,  "currency": "AED"},

        # TVs — different ways to say it
        {"product_name": "Samsung QLED 65",    "category": "TV",              "brand": "Samsung",  "price": 5000,  "currency": "AED"},
        {"product_name": "LG OLED 55",         "category": "Television",      "brand": "LG",       "price": 4500,  "currency": "AED"},
        {"product_name": "Sony Bravia 75",     "category": "Smart TV",        "brand": "Sony",     "price": 7000,  "currency": "AED"},
    ]

    results_by_category_type = {}

    for product in test_products:
        result = classify_product.invoke(product)

        category_type = product["product_name"].split()[0]
        if category_type not in results_by_category_type:
            results_by_category_type[category_type] = []

        results_by_category_type[category_type].append({
            "name": result["product_name"],
            "category": result["category"],
            "eligible": result["classification"]["eligible"],
            "risk_profile": result["classification"].get("risk_profile"),
        })

    # Consistency check
    print(f"\n{'='*80}")
    print("CONSISTENCY CHECK")
    print(f"{'='*80}\n")

    print("📱 SMARTPHONES:")
    for key in ("iPhone", "Samsung", "Google", "OnePlus"):
        for r in results_by_category_type.get(key, []):
            if any(x in r["name"] for x in ("iPhone", "Galaxy S", "Pixel", "OnePlus")):
                print(f"   {r['name'][:25]:25} | Category: {r['category']:15} | Eligible: {r['eligible']}")

    print("\n💻 LAPTOPS:")
    for key in ("MacBook", "Dell"):
        for r in results_by_category_type.get(key, []):
            print(f"   {r['name'][:25]:25} | Category: {r['category']:15} | Eligible: {r['eligible']}")

    print("\n📺 TVs:")
    for key in ("Samsung", "LG", "Sony"):
        for r in results_by_category_type.get(key, []):
            if any(x in r["name"] for x in ("QLED", "OLED", "Bravia")):
                print(f"   {r['name'][:25]:25} | Category: {r['category']:15} | Eligible: {r['eligible']}")