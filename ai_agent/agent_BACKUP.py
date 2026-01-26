import os
import json
import re
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from ai_agent.tools.classify_product import classify_product
from ai_agent.tools.calculate_pricing import calculate_pricing

load_dotenv()

llm = ChatOpenAI(
    model="gpt-5-mini-2025-08-07",
    temperature=0,
    openai_api_key=os.getenv("OPENAI_API_KEY")
)

tools = [classify_product, calculate_pricing]

prompt = ChatPromptTemplate.from_messages([
    ("system", """
You are the Garanty Affinity AI Insurance Agent.

Your job is simple:
1. Call classify_product tool - it does all the classification work
2. If product is NOT eligible - return the NOT ELIGIBLE JSON
3. If product IS eligible - call calculate_pricing to get premiums
4. Return the final insurance package JSON

WORKFLOW

STEP 1: Call classify_product Tool

Pass all product information to the classify_product tool.

The tool will return:
{{
  "product_name": "...",
  "category": "...",
  "classification": {{
    "eligible": true/false,
    "reason": "...",
    "risk_profile": "...",
    "document_type": "ASSURMAX or STANDARD",
    "coverage_modules": [...],
    "exclusions": [...],
    "assurmax_caps": null or {{...}}  ← CHECK THIS!
  }}
}}

STEP 2: Check Classification Result

If classification.eligible = FALSE:
Return NOT ELIGIBLE JSON:
{{
  "product": {{
    "name": "...",
    "brand": "...",
    "category": "USE THE INFERRED CATEGORY FROM TOOL",
    "price": "USE THE ACTUAL PRICE",
    "currency": "..."
  }},
  "eligible": false,
  "reason": "USE classification.reason FROM TOOL"
}}
STOP - Do not call pricing.

If classification.eligible = TRUE:
Continue to STEP 3.

STEP 3: Determine Product Type and Call calculate_pricing

CRITICAL: Check the assurmax_caps field from classification result!

If classification.assurmax_caps is NOT null (contains cap values):
  → This is an ASSURMAX product
  → Call calculate_pricing 4 times:
    1. plan="ASSURMAX", duration_months=12
    2. plan="ASSURMAX", duration_months=24
    3. plan="ASSURMAX+", duration_months=12
    4. plan="ASSURMAX+", duration_months=24

If classification.assurmax_caps is null:
  → This is a STANDARD product
  → Call calculate_pricing 2 times:
    1. plan="standard", duration_months=12
    2. plan="standard", duration_months=24

For all calls, use:
- risk_profile from classification.risk_profile
- product_value from original product price
- market: "UAE" if currency is AED, "Tunisia" if TND

STEP 4: Return Final JSON

If ASSURMAX product (assurmax_caps was not null):
{{
  "product": {{
    "name": "...",
    "brand": "...",
    "category": "from classification",
    "price": [actual price],
    "currency": "AED or TND",
    "description": "..."
  }},
  "eligible": true,
  "risk_profile": "from classification.risk_profile",
  "market": "UAE or Tunisia",
  "document_type": "ASSURMAX",
  "value_bucket": "from calculate_pricing response",
  "plans": {{
    "ASSURMAX": {{
      "12_months": {{"annual_premium": X, "currency": "...", "per_item_cap": "from assurmax_caps", "pack_cap": "from assurmax_caps"}},
      "24_months": {{"total_premium": Y, "currency": "...", "per_item_cap": "from assurmax_caps", "pack_cap": "from assurmax_caps"}}
    }},
    "ASSURMAX+": {{
      "12_months": {{"annual_premium": X, "currency": "...", "per_item_cap": "from assurmax_caps", "pack_cap": "from assurmax_caps"}},
      "24_months": {{"total_premium": Y, "currency": "...", "per_item_cap": "from assurmax_caps", "pack_cap": "from assurmax_caps"}}
    }}
  }},
  "coverage_modules": "from classification.coverage_modules",
  "exclusions": "from classification.exclusions"
}}

If STANDARD product (assurmax_caps was null):
{{
  "product": {{
    "name": "...",
    "brand": "...",
    "category": "from classification",
    "price": [actual price],
    "currency": "AED or TND",
    "description": "..."
  }},
  "eligible": true,
  "risk_profile": "from classification.risk_profile",
  "market": "UAE or Tunisia",
  "document_type": "STANDARD",
  "value_bucket": "from calculate_pricing response",
  "premium": {{
    "12_months": {{"annual_premium": X, "currency": "..."}},
    "24_months": {{"total_premium": Y, "currency": "..."}}
  }},
  "coverage_modules": "from classification.coverage_modules",
  "exclusions": "from classification.exclusions"
}}

CRITICAL RULES:
- Check classification.assurmax_caps to determine if ASSURMAX or STANDARD
- If assurmax_caps exists and is not null → ASSURMAX product (call pricing 4 times)
- If assurmax_caps is null → STANDARD product (call pricing 2 times)
- Use the category inferred by the tool (never return "N/A")
- Include actual product price in the output (not 0)
- Extract per_item_cap and pack_cap from the assurmax_caps field

Return JSON only. Stop immediately.
"""),

    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}")
])


agent = create_tool_calling_agent(llm, tools, prompt)
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,
    max_iterations=10,
    handle_parsing_errors=True,
    return_intermediate_steps=False,
    early_stopping_method="generate"
)

def extract_json_from_output(output: str):
    """Extract JSON from agent output."""
    if not output:
        return {"error": "Empty output from agent"}
    
    cleaned = output.strip()
    
    patterns = [
        (r'```json\s*(.*?)\s*```', re.DOTALL),  
        (r'```\s*(.*?)\s*```', re.DOTALL),     
        (r'(\{.*\})', re.DOTALL),               
    ]
    
    for pattern, flags in patterns:
        match = re.search(pattern, cleaned, flags)
        if match:
            try:
                json_str = match.group(1).strip()
                return json.loads(json_str)
            except json.JSONDecodeError:
                continue
    
    if cleaned.startswith('{') and cleaned.endswith('}'):
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
    
    return {
        "raw_output": cleaned[:500] + "..." if len(cleaned) > 500 else cleaned,
        "note": "Agent did not return valid JSON",
        "eligible": False
    }

def generate_packages(product: dict):
    """Generate insurance packages for a product."""
    product_name = product.get("product_name")
    price = product.get("price")
    currency = product.get("currency", "AED")
    brand = product.get("brand", "N/A")
    category = product.get("category", "N/A")
    description = product.get("description", "N/A")
    
    if not product_name or price is None:
        return {
            "error": "Missing required fields: product_name and price",
            "eligible": False
        }

    input_text = f"""
Generate insurance quotes for this product:

Product Name: {product_name}
Brand: {brand}
Category: {category}
Price: {price} {currency}
Description: {description}

Market: {currency} = {"UAE" if currency == "AED" else "Tunisia"}

Begin now.
"""
    
    try:
        result = agent_executor.invoke({"input": input_text})
        output = result.get("output", "")
        
        if isinstance(output, str):
            return extract_json_from_output(output)
        elif isinstance(output, dict):
            return output
        else:
            return {
                "error": f"Unexpected output type: {type(output)}",
                "raw_output": str(output),
                "eligible": False
            }
        
    except Exception as e:
        return {
            "error": str(e),
            "product": product_name,
            "eligible": False
        }

if __name__ == "__main__":
    tests = [
        {
            "product_name": "Watch 5 46mm Smartwatch",
            "brand": "huawei",
            "category": "Smartwatch",
            "price": 1123,
            "currency": "AED",
            "description": "Latest Apple smartwatch "
        },
        {
            "product_name": "Rolex Watch",
            "brand": "Rolex",
            "category": "Luxury Watch",
            "price": 25000,
            "currency": "AED",
            "description": "Luxury wristwatch"
        },
        {
            "product_name": "Apple iPhone 17 256GB Lavender",
            "brand": "Apple",
            "category": "Smartphone",
            "price": 1299,
            "currency": "AED",
            "description": "Apple iPhone 17 with 256GB storage in Lavender color"
        },
         {
            "product_name": "Apple MacBook Air MC7X4 13.6-Inch",
            "brand": "Apple",
            "category": "Laptop",
            "price": 2349,
            "currency": "AED",
            "description": "Apple MacBook Air MC7X4 13.6-Inch Display : Apple M2 chip with 8-core CPU and 8-core GPU, 16GB RAM/256GB SSD"
        }
    ]

    print("\n" + "="*100)
    print("GARANTY AFFINITY INSURANCE QUOTE GENERATOR")
    print("="*100)
    print("ASSURMAX products: Show ASSURMAX & ASSURMAX+ plans")
    print("Standard products: Show annual premium only")
    print("All products use normal spec docs for coverage details")
    print("="*100)

    for i, p in enumerate(tests, 1):
        print("\n" + "="*100)
        print(f"TEST {i}: {p['product_name']} | {p['price']} {p['currency']}")
        print("="*100 + "\n")
        
        output = generate_packages(p)
        
        if isinstance(output, dict):
            print(json.dumps(output, indent=2, ensure_ascii=False))
        else:
            print(output)
        
        print("\n")