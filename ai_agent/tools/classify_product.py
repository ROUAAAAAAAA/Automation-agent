
from langchain_core.tools import tool
from typing import Union, List, Dict
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI
import os
import json
import dotenv
dotenv.load_dotenv()



def infer_category_with_llm(product_name: str, description: str, brand: str) -> str:
    """Use LLM to infer product category."""
    llm = ChatOpenAI(
        model="gpt-5-mini-2025-08-07",
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

Category:"""
    
    try:
        response = llm.invoke(prompt)
        category = response.content.strip().replace('"', '').replace("'", "")
        return category if len(category) < 50 else "General Product"
    except Exception as e:
        print(f" Category inference failed: {e}")
        return "General Product"



def analyze_eligibility_with_llm(product_name: str, category: str, documents: List[Document]) -> Dict:
    """
    Use LLM to analyze retrieved documents and determine eligibility.
    Returns structured classification result.
    """
    llm = ChatOpenAI(
        model="gpt-5-mini-2025-08-07",
        temperature=0,
        openai_api_key=os.getenv("OPENAI_API_KEY")
    )
    
    # Format documents for LLM with document type labels
    docs_text = ""
    has_assurmax_doc = False
    
    for i, doc in enumerate(documents[:5]):
        filename = doc.metadata.get('file_name', 'Unknown')
        
        # Identify document type
        if 'assurmax' in filename.lower():
            doc_type = " ASSURMAX PRICING DOCUMENT"
            has_assurmax_doc = True
        elif 'garantyaffinity' in filename.lower():
            doc_type = " STANDARD SPECIFICATION DOCUMENT"
        else:
            doc_type = " DOCUMENT"
        
        docs_text += f"\n\n--- {doc_type} {i+1}: {filename} ---\n{doc.page_content}\n"
    
    prompt = f"""You are analyzing insurance specification documents to determine if a product is eligible for coverage.

PRODUCT TO ANALYZE:
- Name: {product_name}
- Category: {category}

SPECIFICATION DOCUMENTS:
{docs_text}

CRITICAL INSTRUCTIONS:
STEP 0: DETERMINE IF THIS IS A LUXURY PRODUCT
- Check brand: Is it a luxury brand? (Gucci, Prada, Louis Vuitton, Rolex, Cartier, etc.)
- Check price: Is price ≥ 3000 AED or equivalent? 
- Check category/description: Does it sound like luxury/premium item?
- If ANY of these are true → This is likely a LUXURY product that needs OPULENCIA_PREMIUM spec



STEP 1: Find the STANDARD SPECIFICATION document (GarantyAffinity_...)
- This document tells you IF the product is eligible
- Extract: risk_profile, coverage_modules, exclusions
- Use the document that matches the product category and market
- If product is LUXURY → Look for OPULENCIA_PREMIUM document (mentions "Opulencia", "Premium", "Luxury")

STEP 2: Look for ASSURMAX PRICING documents (ASSURMAX_...)
- These documents contain CAPS/LIMITS for maximum coverage
- Look for text like:
  * "Per Item Cap: X AED"
  * "Pack Cap: Y AED"
  * "ASSURMAX: X AED"
  * "ASSURMAX+: Y AED"
- If you find ANY ASSURMAX document, you MUST extract the caps

STEP 3: Build the response
- eligible: true/false (from STANDARD doc)
- risk_profile: CODE from STANDARD doc (e.g., ELECTRONIC_PRODUCTS)
- coverage_modules: from STANDARD doc
- exclusions: from STANDARD doc
- assurmax_caps: from ASSURMAX doc (if present)

ASSURMAX CAPS FORMAT:
If you find ASSURMAX caps, return:
{{
  "ASSURMAX": {{
    "per_item_cap_AED": <number>,
    "pack_cap_AED": <number>
  }},
  "ASSURMAX+": {{
    "per_item_cap_AED": <number>,
    "pack_cap_AED": <number>
  }}
}}

If no ASSURMAX document found or no caps mentioned, return:
"assurmax_caps": null

CRITICAL: You MUST return ONLY a valid JSON object, nothing else. No explanations, no markdown, just JSON.

JSON FORMAT:
{{
  "eligible": true or false,
  "reason": "Clear explanation if not eligible, or 'Product is covered' if eligible",
  "risk_profile": "Exact risk profile code from STANDARD document",
  "document_used": "Filename of the STANDARD document used for eligibility decision",
  "document_type": "STANDARD",
  "coverage_modules": ["Module 1", "Module 2"],
  "exclusions": ["Exclusion 1", "Exclusion 2"],
  "assurmax_caps": null or {{"ASSURMAX": {{...}}, "ASSURMAX+": {{...}}}}
}}

Return ONLY the JSON object above with actual values filled in. Do not include any other text.
"""
    
    try:
        response = llm.invoke(prompt)
        content = response.content.strip()
        
        # Remove markdown code blocks if present
        if content.startswith("```json"):
            content = content.replace("```json", "").replace("```", "").strip()
        elif content.startswith("```"):
            content = content.replace("```", "").strip()
        
        # Try to parse JSON
        result = json.loads(content)
        
        # Validate required fields
        if "eligible" not in result:
            result["eligible"] = False
        if "reason" not in result:
            result["reason"] = "Unknown reason"
        if "risk_profile" not in result:
            result["risk_profile"] = None
        if "document_type" not in result:
            result["document_type"] = "STANDARD"
        if "coverage_modules" not in result:
            result["coverage_modules"] = []
        if "exclusions" not in result:
            result["exclusions"] = []
        if "assurmax_caps" not in result:
            result["assurmax_caps"] = None
        
        #  ASSURMAX DETECTION LOGIC
        if result.get("assurmax_caps") and result.get("document_type") == "STANDARD":
            # If ASSURMAX caps found, update document type
            result["document_type"] = "ASSURMAX"
            print("    ASSURMAX caps detected - switching to ASSURMAX document type")
        elif not result.get("assurmax_caps") and has_assurmax_doc:
            #  ASSURMAX doc was retrieved but LLM didn't extract caps
            print("    WARNING: ASSURMAX document retrieved but no caps extracted!")
            print("    LLM may have missed the caps in the document")
        
        return result
        
    except json.JSONDecodeError as e:
        print(f" LLM returned invalid JSON. Raw response:")
        print(f"   {response.content[:500]}")
        return {
            "eligible": False,
            "reason": f"Failed to parse LLM response: {str(e)}",
            "risk_profile": None,
            "document_used": None,
            "document_type": "STANDARD",
            "coverage_modules": [],
            "exclusions": [],
            "assurmax_caps": None
        }
    except Exception as e:
        print(f" Eligibility analysis failed: {e}")
        return {
            "eligible": False,
            "reason": f"Analysis error: {str(e)}",
            "risk_profile": None,
            "document_used": None,
            "document_type": "STANDARD",
            "coverage_modules": [],
            "exclusions": [],
            "assurmax_caps": None
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
    Smart product classification tool.
    
    This tool does ALL the work:
    1. Infers category if missing
    2. Retrieves relevant specification documents
    3. Analyzes eligibility using LLM
    4. Returns structured classification result
    
    The agent just needs to use the returned data.
    """
    # Convert price
    try:
        price_float = float(price) if price else 0.0
    except (ValueError, TypeError):
        price_float = 0.0
    
    # Determine market
    market = "UAE" if currency == "AED" else "Tunisia" if currency == "TND" else "UAE"
    
    # STEP 1: INFER CATEGORY IF MISSING
    original_category = category
    if not category or category in ["N/A", "", "Unknown", "General", None]:
        print(f" Inferring category for: {product_name[:50]}...")
        category = infer_category_with_llm(product_name, description, brand)
        print(f" Category: '{original_category or 'N/A'}' → '{category}'")
    
    print(f"\n{'='*70}")
    print(f" CLASSIFYING: {product_name}")
    print(f"   Category: {category} | Market: {market} | Price: {price_float} {currency}")
    print(f"{'='*70}\n")
    # ===== ADDED LUXURY CLASSIFICATION LOGIC =====
    is_luxury_product = False
    
    # Luxury brands list
    luxury_brands = ["gucci", "prada", "louis vuitton", "lv", "rolex", "cartier", 
                     "omega", "tiffany", "hermes", "chanel", "dior", "versace",
                     "burberry", "givenchy", "balenciaga", "chloe", "chloé", "fendi"]
    
    # Luxury categories/keywords
    luxury_categories = ["luxury", "premium", "watch", "jewelry", "handbag", "leather",
                        "watches", "jewellery", "briefcase", "trunk", "luggage"]
    
    # Convert price to AED for comparison
    price_in_aed = price_float
    if currency == "USD" and price_float > 0:
        price_in_aed = price_float * 3.67  # Approximate conversion
    
    # Check 1: Brand-based luxury detection
    if brand:
        brand_lower = brand.lower()
        for luxury_brand in luxury_brands:
            if luxury_brand in brand_lower:
                if price_in_aed >= 3000:
                    is_luxury_product = True
                    print(f"  LUXURY DETECTED: Brand '{brand}' at {price_float} {currency} (~{price_in_aed:.0f} AED)")
                break
    
    # Check 2: Category-based luxury detection
    if not is_luxury_product and category:
        category_lower = category.lower()
        for luxury_cat in luxury_categories:
            if luxury_cat in category_lower:
                if price_in_aed >= 3000:
                    is_luxury_product = True
                    print(f"  LUXURY DETECTED: Category '{category}' at {price_float} {currency} (~{price_in_aed:.0f} AED)")
                break
    
    # Check 3: Description-based luxury detection
    if not is_luxury_product and description:
        desc_lower = description.lower()
        if any(word in desc_lower for word in ["luxury", "premium", "high-end", "designer"]):
            if price_in_aed >= 3000:
                is_luxury_product = True
                print(f"  LUXURY DETECTED: Description indicates luxury at {price_float} {currency} (~{price_in_aed:.0f} AED)")
    # ===== END LUXURY CLASSIFICATION =====
    #  STEP 2: RETRIEVE SPECIFICATION DOCUMENTS
    from ai_agent.rag.retriever import retrieve_specs_raw
    
    all_docs = []
    
    # Query 1: Get GarantyAffinity document
    if is_luxury_product:
        # Prioritize OPULENCIA for luxury products
        query1 = f"OPULENCIA PREMIUM LUXURY {brand or ''} {category} {market} specification eligible products"
        print(f" QUERY 1 (LUXURY PRIORITY): {query1}")
    else:
        query1 = f"{product_name} {category} {brand} {market} {currency} GarantyAffinity specification risk profile eligible products"
        print(f" QUERY 1 (GarantyAffinity): {query1}")
    
    try:
        docs1 = retrieve_specs_raw(query1, k=3)
        all_docs.extend(docs1)
        print(f"    Retrieved {len(docs1)} documents")
    except Exception as e:
        print(f"    Query 1 failed: {e}")
    
    
    # Query 2: Get ASSURMAX document if applicable
    assurmax_keywords = ["phone","smartwatches","smartphone", "laptop", "tablet", "tv", "watch", "jewelry", "clothing", "electronics", "luxury", "textile","footwear","console","audio"]
    if any(kw in (product_name + " " + category + " " + description).lower() for kw in assurmax_keywords):
        query2 = f"{product_name} {category} {brand} {market} {currency} ASSURMAX pricing caps"
        print(f" QUERY 2 (ASSURMAX): {query2}")
        
        try:
            docs2 = retrieve_specs_raw(query2, k=3)
            all_docs.extend(docs2)
            print(f"    Retrieved {len(docs2)} documents")
        except Exception as e:
            print(f"    Query 2 failed: {e}")
    
    # Remove duplicates
    seen_files = set()
    unique_docs = []
    for doc in all_docs:
        filename = doc.metadata.get('file_name', '')
        if filename and filename not in seen_files:
            seen_files.add(filename)
            unique_docs.append(doc)
    
    # Sort: GarantyAffinity first
    unique_docs.sort(key=lambda d: 0 if 'garantyaffinity' in d.metadata.get('file_name', '').lower() else 1)
    
    print(f"\n Retrieved {len(unique_docs)} unique documents:")
    for doc in unique_docs:
        print(f"   - {doc.metadata.get('file_name', 'Unknown')}")
    
    if not unique_docs:
        print(f" No specification documents found for {category}\n")
        return {
            "product_name": product_name,
            "brand": brand,
            "category": category,
            "price": price_float,
            "currency": currency,
            "market": market,
            "classification": {
                "eligible": False,
                "reason": f"No insurance specification documents found for product category '{category}'",
                "risk_profile": None,
                "document_type": "STANDARD",
                "coverage_modules": [],
                "exclusions": [],
                "assurmax_caps": None
            }
        }
    
    #  STEP 3: ANALYZE ELIGIBILITY WITH LLM
    print(f"\n Analyzing eligibility with LLM...")
    classification = analyze_eligibility_with_llm(product_name, category, unique_docs)
    print(f"   Result: {' ELIGIBLE' if classification['eligible'] else ' NOT ELIGIBLE'}")
    if not classification['eligible']:
        print(f"   Reason: {classification['reason']}")
    print(f"{'='*70}\n")
    
    #  STEP 4: RETURN STRUCTURED RESULT
    return {
        "product_name": product_name,
        "brand": brand,
        "category": category,
        "price": price_float,
        "currency": currency,
        "market": market,
        "classification": classification
    }
