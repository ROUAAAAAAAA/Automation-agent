# tests/test_spec_truth.py

from ai_agent.tools.classify_product import classify_product

def assert_result(product, expected_eligible, reason_hint):
    result = classify_product.invoke(product)
    eligible = result["classification"]["eligible"]

    print("\n" + "="*80)
    print(product["product_name"])
    print("Expected:", expected_eligible)
    print("Got     :", eligible)
    print("Reason  :", result["classification"]["reason"])

    assert eligible == expected_eligible, f"""
FAILED: {product['product_name']}

Expected eligible = {expected_eligible}
Got eligible      = {eligible}

Hint: {reason_hint}
Reason from LLM: {result['classification']['reason']}
"""


# ------------------------------------------------------------------
# ELECTRONICS — CLASS_BASED + ACCESSORY TRAP
# ------------------------------------------------------------------

assert_result(
    {
        "product_name": "iPhone 15 Pro",
        "category": "Smartphone",
        "brand": "Apple",
        "price": 4500,
        "currency": "AED",
    },
    True,
    "Smartphone belongs to Mobile devices class"
)

assert_result(
    {
        "product_name": "Apple Smart Folio for iPad",
        "category": "",
        "brand": "Apple",
        "price": 400,
        "currency": "AED",
    },
    False,
    "Electronic accessory must NOT be covered unless accessories are explicitly listed"
)

assert_result(
    {
        "product_name": "Samsung Keyboard Case for Tab",
        "category": "",
        "brand": "Samsung",
        "price": 350,
        "currency": "AED",
    },
    False,
    "Accessory trap — should be rejected"
)

assert_result(
    {
        "product_name": "Samsung QLED TV 65",
        "category": "Television",
        "brand": "Samsung",
        "price": 5000,
        "currency": "AED",
    },
    True,
    "TV belongs to televisions class"
)

assert_result(
    {
        "product_name": "Microwave Oven LG",
        "category": "Microwave",
        "brand": "LG",
        "price": 600,
        "currency": "AED",
    },
    False,
    "Home appliances explicitly excluded from electronics spec"
)

# ------------------------------------------------------------------
# BAGS — OBJECT_EXHAUSTIVE (NO INFERENCE ALLOWED)
# ------------------------------------------------------------------

assert_result(
    {
        "product_name": "Samsonite Suitcase Large",
        "category": "Suitcase",
        "brand": "Samsonite",
        "price": 900,
        "currency": "AED",
    },
    True,
    "Suitcase explicitly listed"
)

assert_result(
    {
        "product_name": "Gaming Backpack with LED",
        "category": "Backpack",
        "brand": "ROG",
        "price": 300,
        "currency": "AED",
    },
    True,
    "Backpack explicitly listed even if 'gaming'"
)

assert_result(
    {
        "product_name": "Leather Key Case",
        "category": "Key case",
        "brand": "Generic",
        "price": 80,
        "currency": "AED",
    },
    False,
    "Very small accessories explicitly excluded"
)

# ------------------------------------------------------------------
# FURNITURE — OBJECT_EXHAUSTIVE TRAP
# ------------------------------------------------------------------

assert_result(
    {
        "product_name": "IKEA Gaming Chair",
        "category": "Chair",
        "brand": "IKEA",
        "price": 700,
        "currency": "AED",
    },
    False,
    "Gaming chair is NOT in eligible list (sofa, table, TV stand only)"
)

assert_result(
    {
        "product_name": "Glass Coffee Table",
        "category": "Glass coffee table",
        "brand": "Home",
        "price": 1200,
        "currency": "AED",
    },
    True,
    "Glass table explicitly listed"
)

# ------------------------------------------------------------------
# TEXTILES — ZARA ONLY
# ------------------------------------------------------------------

assert_result(
    {
        "product_name": "ZARA Denim Jacket",
        "category": "Clothing",
        "brand": "ZARA",
        "price": 300,
        "currency": "AED",
    },
    True,
    "ZARA only rule satisfied"
)

assert_result(
    {
        "product_name": "H&M Denim Jacket",
        "category": "Clothing",
        "brand": "H&M",
        "price": 300,
        "currency": "AED",
    },
    False,
    "Brand restriction violated"
)

# ------------------------------------------------------------------
# LUXURY — BRAND_RESTRICTED
# ------------------------------------------------------------------

assert_result(
    {
        "product_name": "Rolex Submariner",
        "category": "",
        "brand": "Rolex",
        "price": 40000,
        "currency": "AED",
    },
    True,
    "Luxury brand watch must be routed to LUXURY spec"
)

assert_result(
    {
        "product_name": "Casio Watch",
        "category": "Watch",
        "brand": "Casio",
        "price": 200,
        "currency": "AED",
    },
    False,
    "Not a luxury brand"
)

# ------------------------------------------------------------------
# BABY — OBJECT_EXHAUSTIVE
# ------------------------------------------------------------------

assert_result(
    {
        "product_name": "Baby Stroller Chicco",
        "category": "Stroller",
        "brand": "Chicco",
        "price": 800,
        "currency": "AED",
    },
    True,
    "Stroller explicitly listed"
)

assert_result(
    {
        "product_name": "Baby Bottle Set",
        "category": "Bottle",
        "brand": "Philips",
        "price": 120,
        "currency": "AED",
    },
    False,
    "Consumables excluded"
)

print("\nALL SPEC TESTS PASSED ✅")
