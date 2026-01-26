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

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent  # Go up 3 levels
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
    
    Returns structured classification with:
    - eligible: bool
    - reason: str
    - risk_profile: str (e.g., "ELECTRONIC_PRODUCTS")
    - document_type: "STANDARD" (always - workflow handles ASSURMAX logic)
    - coverage_modules: list
    - exclusions: list
    """
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        openai_api_key=os.getenv("OPENAI_API_KEY")
    )
    
    # Format documents for LLM
    docs_text = ""
    doc_filenames = []
    
    for i, doc in enumerate(documents[:6]):  # Limit to 6 most relevant docs
        filename = doc.metadata.get('file_name', 'Unknown')
        doc_filenames.append(filename)
        docs_text += f"\n\n{'='*70}\n[DOCUMENT {i+1}]: {filename}\n{'='*70}\n{doc.page_content}\n"
    
    # Determine market
    market = "UAE" if currency == "AED" else "Tunisia"
    
    # Build prompt
    prompt = f"""You are an insurance product classifier. Analyze the specification documents to determine if a product is eligible for insurance coverage.

PRODUCT TO CLASSIFY:
==================
Name: {product_name}
Category: {category}
Brand: {brand}
Price: {price} {currency}
Market: {market}

SPECIFICATION DOCUMENTS:
==================
{docs_text}

YOUR TASK:
==================

STEP 1: FIND MATCHING SPECIFICATION
- Read all specification documents above
- Find the document whose "Eligible Products" section matches this product's category
- Use the MOST SPECIFIC matching specification

STEP 2: CHECK ELIGIBILITY
- Is the product category listed in "Eligible Products" or "Included Products"?
- Does it meet any price requirements mentioned?
- Check "Exclusions" - is the product explicitly excluded?
- Result: eligible = true if product matches eligible list AND not excluded

STEP 3: EXTRACT DETAILS (from matching specification)
- risk_profile: Extract the exact risk profile code
  Examples: "ELECTRONIC_PRODUCTS", "HOME_APPLIANCES", "BAGS_LUGGAGE_ESSENTIAL", "OPULENCIA_PREMIUM"
- coverage_modules: List of coverage types (Accidental Damage, Theft, etc.)
- exclusions: List of what's NOT covered
- document_used: Filename of the specification document you used

IMPORTANT RULES:
==================
✅ Match by CATEGORY, not by price
   - If category is in the eligible list → eligible (even if price is high)
   
✅ Ignore ASSURMAX pricing documents for eligibility
   - ASSURMAX documents only contain pricing caps
   - Use STANDARD specification documents for eligibility check
   
✅ Always return document_type as "STANDARD"
   - The workflow will determine ASSURMAX eligibility separately
   - Your job is to determine if product is insurable at all
   
✅ Common eligible categories:
   - Electronics: Smartphones, Laptops, Tablets, TVs, Smartwatches, Gaming Consoles
   - Home: Washing machines, Refrigerators, Ovens, Dishwashers
   - Baby: Strollers, Car seats, Cribs
   - Sports: Bicycles, Treadmills, Fitness equipment
   - Bags/Luggage: Suitcases, Backpacks, Handbags
   
❌ Common INELIGIBLE categories:
   - Beauty & Cosmetics (makeup, perfume, skincare)
   - Food & Beverages
   - Clothing & Footwear (unless textile spec exists)
   - Books & Media
   - Consumables

RESPONSE FORMAT:
==================
Return ONLY a valid JSON object (no markdown, no code blocks):

{{
  "eligible": true or false,
  "reason": "Clear explanation of why eligible/not eligible and which specification was used",
  "risk_profile": "EXACT_RISK_PROFILE_CODE" or null,
  "document_used": "filename.pdf" or null,
  "document_type": "STANDARD",
  "coverage_modules": ["Module 1", "Module 2", ...],
  "exclusions": ["Exclusion 1", "Exclusion 2", ...]
}}

JSON Response:"""
    
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
        
        # Force document_type to STANDARD (workflow handles ASSURMAX)
        result["document_type"] = "STANDARD"
        
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
            "exclusions": []
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
            "exclusions": []
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
    
    This tool:
    1. Infers category if missing (using LLM)
    2. Retrieves relevant specification documents from RAG
    3. Analyzes eligibility using LLM
    4. Returns structured classification
    
    The workflow then decides:
    - Calculate STANDARD pricing (always)
    - Calculate ASSURMAX pricing (if UAE electronics ≤ 5000 AED)
    
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
    
    # ==========================================
    # STEP 1: INFER CATEGORY IF MISSING
    # ==========================================
    original_category = category
    if not category or category.strip() in ["N/A", "", "Unknown", "General", "None"]:
        print(f"🔍 Inferring category for: {product_name[:50]}...")
        category = infer_category_with_llm(product_name, description, brand)
        print(f"   ✅ Category: '{original_category or 'N/A'}' → '{category}'")
    
    print(f"\n{'='*70}")
    print(f"📦 CLASSIFYING PRODUCT")
    print(f"{'='*70}")
    print(f"Name: {product_name[:60]}")
    print(f"Category: {category}")
    print(f"Brand: {brand or 'N/A'}")
    print(f"Price: {price_float} {currency}")
    print(f"Market: {market}")
    print(f"{'='*70}\n")
    
    # ==========================================
    # STEP 2: RETRIEVE SPECIFICATION DOCUMENTS
    # ==========================================
    from ai_agent.rag.retriever import retrieve_specs_raw
    
    # Build search query
    query = f"{product_name} {category} {brand} {market} insurance specification eligible coverage"
    print(f"🔍 Retrieving specifications...")
    print(f"   Query: {query[:80]}...")
    
    try:
        docs = retrieve_specs_raw(query, k=6)
        print(f"   ✅ Retrieved {len(docs)} documents")
    except Exception as e:
        print(f"   ❌ Retrieval failed: {e}")
        docs = []
    
    # Remove duplicates
    seen_files = set()
    unique_docs = []
    for doc in docs:
        filename = doc.metadata.get('file_name', '')
        if filename and filename not in seen_files:
            seen_files.add(filename)
            unique_docs.append(doc)
    
    # Sort: STANDARD specs first (they have eligibility info)
    def sort_key(doc):
        filename = doc.metadata.get('file_name', '').lower()
        if 'garantyaffinity' in filename or 'dev_spec' in filename:
            return 0  # STANDARD specs (highest priority)
        elif 'opulencia' in filename:
            return 1  # OPULENCIA (also good for eligibility)
        elif 'assurmax' in filename:
            return 2  # ASSURMAX (reference only, not for eligibility)
        else:
            return 3
    
    unique_docs.sort(key=sort_key)
    
    print(f"\n📚 Using {len(unique_docs)} unique documents:")
    for doc in unique_docs:
        filename = doc.metadata.get('file_name', 'Unknown')
        doc_type = "📋" if any(x in filename.lower() for x in ['garantyaffinity', 'dev_spec', 'opulencia']) else "⚡"
        print(f"   {doc_type} {filename}")
    
    if not unique_docs:
        print(f"\n⚠️ No specification documents found for category '{category}'\n")
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
                "document_used": None,
                "document_type": "STANDARD",
                "coverage_modules": [],
                "exclusions": []
            }
        }
    
    # ==========================================
    # STEP 3: ANALYZE ELIGIBILITY WITH LLM
    # ==========================================
    print(f"\n🤖 Analyzing eligibility...")
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
        print(f"   ✅ ELIGIBLE for insurance")
        print(f"   Risk Profile: {classification.get('risk_profile', 'N/A')}")
        print(f"   Document Used: {classification.get('document_used', 'N/A')}")
    else:
        print(f"   ❌ NOT ELIGIBLE")
        print(f"   Reason: {classification.get('reason', 'Unknown')[:100]}")
    
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
    """Test the classification tool"""
    
    print("\n" + "="*80)
    print("TESTING PRODUCT CLASSIFICATION TOOL")
    print("="*80)
    
    test_products = [
        {
            "product_name": "iPhone 15 Pro",
            "category": "Smartphone",
            "brand": "Apple",
            "price": 4500,
            "currency": "AED"
        },
        {
            "product_name": "MacBook Pro 16-inch",
            "category": "Laptop",
            "brand": "Apple",
            "price": 12000,
            "currency": "AED"
        },
        {
            "product_name": "MAC Lipstick Set",
            "category": "Beauty & Cosmetics",
            "brand": "MAC",
            "price": 150,
            "currency": "AED"
        }
    ]
    
    for product in test_products:
        result = classify_product.invoke(product)
        
        print(f"\n{'='*80}")
        print(f"RESULT: {result['product_name']}")
        print(f"{'='*80}")
        print(f"Eligible: {result['classification']['eligible']}")
        print(f"Risk Profile: {result['classification'].get('risk_profile', 'N/A')}")
        if not result['classification']['eligible']:
            print(f"Reason: {result['classification']['reason']}")
        print()
