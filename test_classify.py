# test_classify.py
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from ai_agent.tools.classify_product import classify_product

# Test cases
test_products = [
    {
        "name": "Test 1: Eligible Product (Laptop)",
        "product_name": "Apple MacBook Air 13.6-Inch",
        "category": "N/A",
        "brand": "Apple",
        "price": 2349,
        "currency": "AED",
        "description": "Laptop with M2 chip, 8GB RAM, 256GB SSD"
    },
    {
        "name": "Test 2: Not Eligible (Beauty)",
        "product_name": "NCLA Beauty Pink Champagne Lip Care Set",
        "category": "N/A",
        "brand": "NCLA Beauty",
        "price": 155,
        "currency": "AED",
        "description": "Pack of 3 lip care products"
    },
    {
        "name": "Test 3: Not Eligible (Kitchenware)",
        "product_name": "Joseph Joseph Elevate Knives & Carousel",
        "category": "N/A",
        "brand": "Joseph Joseph",
        "price": 359,
        "currency": "AED",
        "description": "Set of 5 kitchen knives"
    },
    {
        "name": "Test 4: Eligible (Audio)",
        "product_name": "JBL Clip5 Bluetooth Speaker",
        "category": "N/A",
        "brand": "JBL",
        "price": 219,
        "currency": "AED",
        "description": "Portable Bluetooth speaker with carabiner"
    },
    {
        "name": "Test 5: Unknown Category",
        "product_name": "Purina Dog Food Premium Kibble",
        "category": "N/A",
        "brand": "Purina",
        "price": 89,
        "currency": "AED",
        "description": "Premium dog food 5kg bag"
    }
]

print("="*80)
print("TESTING CLASSIFY_PRODUCT TOOL")
print("="*80)

for test in test_products:
    print(f"\n{'='*80}")
    print(f"🧪 {test['name']}")
    print(f"{'='*80}\n")
    
    # Call the tool
    result = classify_product.invoke({
        "product_name": test["product_name"],
        "category": test["category"],
        "brand": test["brand"],
        "price": test["price"],
        "currency": test["currency"],
        "description": test["description"]
    })
    
    # Display results
    print("\n📊 RESULT:")
    print(f"   Product: {result['product_name']}")
    print(f"   Category: {result['category']}")
    print(f"   Market: {result['market']}")
    print(f"   Eligible: {'✅ YES' if result['classification']['eligible'] else '❌ NO'}")
    
    if result['classification']['eligible']:
        print(f"   Risk Profile: {result['classification']['risk_profile']}")
        print(f"   Document Type: {result['classification']['document_type']}")
        print(f"   Coverage Modules: {len(result['classification']['coverage_modules'])} items")
    else:
        print(f"   Reason: {result['classification']['reason']}")
    
    print(f"\n{'='*80}\n")

print("✅ All tests completed!")
