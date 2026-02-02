"""
Comprehensive Classification Testing Script
============================================
Tests the classify_product.py tool against all 14 insurance categories
from the productslistpricing folder.

This script tests:
1. Positive cases (products that SHOULD be eligible)
2. Negative cases (products that SHOULD NOT be eligible)
3. Edge cases (brand names, synonyms, variants)
4. Consistency (same category = same result)
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from ai_agent.tools.classify_product import classify_product
import json
from datetime import datetime


# ============================================================
# TEST PRODUCT DATABASE - Based on Category Spec Files
# ============================================================

TEST_PRODUCTS = {
    "ELECTRONICS": {
        "category_name": "Electronics",
        "spec_file": "GarantyAffinity_DEV_SPEC_ELECTRONICS_ONLY_FINAL_UAE_v2.pdf",
        "risk_profile": "ELECTRONIC_PRODUCTS",
        "positive_tests": [
            # Smartphones - different variants
            {"name": "iPhone 15 Pro Max", "category": "Smartphone", "brand": "Apple", "price": 4500},
            {"name": "Samsung Galaxy S24 Ultra", "category": "Mobile", "brand": "Samsung", "price": 4200},
            {"name": "Google Pixel 8 Pro", "category": "Phone", "brand": "Google", "price": 3500},
            {"name": "OnePlus 12", "category": "Cell Phone", "brand": "OnePlus", "price": 3000},
            
            # Laptops - different variants
            {"name": "MacBook Pro 16-inch M3", "category": "Laptop", "brand": "Apple", "price": 12000},
            {"name": "Dell XPS 15", "category": "Notebook", "brand": "Dell", "price": 8000},
            {"name": "HP Pavilion", "category": "Portable Computer", "brand": "HP", "price": 3500},
            {"name": "Lenovo ThinkPad X1", "category": "MacBook", "brand": "Lenovo", "price": 7000},  # Brand confusion test
            
            # Tablets
            {"name": "iPad Pro 12.9", "category": "Tablet", "brand": "Apple", "price": 5000},
            {"name": "Samsung Galaxy Tab S9", "category": "iPad", "brand": "Samsung", "price": 3000},  # Brand confusion test
            
            # TVs - different variants
            {"name": "Samsung QLED 65 inch", "category": "TV", "brand": "Samsung", "price": 5000},
            {"name": "LG OLED C3 55 inch", "category": "Television", "brand": "LG", "price": 4500},
            {"name": "Sony Bravia 75 inch", "category": "Smart TV", "brand": "Sony", "price": 7000},
            
            # Smartwatches
            {"name": "Apple Watch Series 9", "category": "Smartwatch", "brand": "Apple", "price": 1800},
            {"name": "Samsung Galaxy Watch 6", "category": "Smart Watch", "brand": "Samsung", "price": 1200},
            
            # Headphones
            {"name": "AirPods Pro 2", "category": "Headphones", "brand": "Apple", "price": 899},
            {"name": "Sony WH-1000XM5", "category": "Wireless Headphones", "brand": "Sony", "price": 1200},
            {"name": "Bose QuietComfort", "category": "Earbuds", "brand": "Bose", "price": 1000},
            
            # Gaming Consoles
            {"name": "PlayStation 5", "category": "Gaming Console", "brand": "Sony", "price": 2000},
            {"name": "Xbox Series X", "category": "Game Console", "brand": "Microsoft", "price": 2000},
            
            # Cameras
            {"name": "Canon EOS R5", "category": "Camera", "brand": "Canon", "price": 15000},
            {"name": "Sony A7 IV", "category": "Digital Camera", "brand": "Sony", "price": 12000},
        ],
        "negative_tests": [
            {"name": "Office Chair", "category": "Furniture", "brand": "IKEA", "price": 500},
            {"name": "Running Shoes", "category": "Footwear", "brand": "Nike", "price": 400},
        ]
    },
    
    "HOME_APPLIANCES": {
        "category_name": "Home Appliances",
        "spec_file": "GarantyAffinity_DEV_SPEC_HOME_APPLIANCES_FINAL_UAE.pdf",
        "risk_profile": "HOME_APPLIANCES",
        "positive_tests": [
            # Washing Machines
            {"name": "Samsung Front Load Washer", "category": "Washing Machine", "brand": "Samsung", "price": 2500},
            {"name": "LG TurboWash", "category": "Washer", "brand": "LG", "price": 2200},
            
            # Refrigerators
            {"name": "Samsung French Door Fridge", "category": "Refrigerator", "brand": "Samsung", "price": 4000},
            {"name": "LG InstaView", "category": "Fridge", "brand": "LG", "price": 3500},
            
            # Dishwashers
            {"name": "Bosch Series 6", "category": "Dishwasher", "brand": "Bosch", "price": 3000},
            
            # Microwaves
            {"name": "Samsung Microwave Oven", "category": "Microwave", "brand": "Samsung", "price": 800},
            
            # Air Conditioners
            {"name": "Daikin Split AC", "category": "Air Conditioner", "brand": "Daikin", "price": 2500},
            {"name": "Midea AC Unit", "category": "AC", "brand": "Midea", "price": 1800},
        ],
        "negative_tests": [
            {"name": "iPhone 15", "category": "Smartphone", "brand": "Apple", "price": 4000},
        ]
    },
    
    "MICROMOBILITY": {
        "category_name": "Micromobility",
        "spec_file": "GarantyAffinity_DEV_SPEC_MICROMOBILITY_ESSENTIAL_UAE.pdf",
        "risk_profile": "MICRO_MOBILITY_ESSENTIAL",
        "positive_tests": [
            # Electric Bikes
            {"name": "Trek Electric Bike", "category": "Electric Bike", "brand": "Trek", "price": 5000},
            {"name": "Specialized Turbo", "category": "E-Bike", "brand": "Specialized", "price": 6000},
            {"name": "Rad Power Bike", "category": "Electric Bicycle", "brand": "Rad", "price": 4000},
            
            # Electric Scooters
            {"name": "Xiaomi M365", "category": "Electric Scooter", "brand": "Xiaomi", "price": 1500},
            {"name": "Segway Ninebot", "category": "E-Scooter", "brand": "Segway", "price": 2000},
            
            # Hoverboards
            {"name": "Segway MiniPro", "category": "Hoverboard", "brand": "Segway", "price": 1200},
        ],
        "negative_tests": [
            {"name": "Mountain Bike", "category": "Bicycle", "brand": "Trek", "price": 2000},  # Non-electric
        ]
    },
    
    "BABY_EQUIPMENT": {
        "category_name": "Baby Equipment",
        "spec_file": "GarantyAffinity_DEV_SPEC_BABY_ESSENTIAL_UAE.pdf",
        "risk_profile": "BABY_EQUIPMENT_ESSENTIAL",
        "positive_tests": [
            {"name": "Bugaboo Fox 5", "category": "Stroller", "brand": "Bugaboo", "price": 4000},
            {"name": "Maxi-Cosi AxissFix", "category": "Car Seat", "brand": "Maxi-Cosi", "price": 2000},
            {"name": "SNOO Smart Sleeper", "category": "Baby Crib", "brand": "Happiest Baby", "price": 6000},
            {"name": "Owlet Baby Monitor", "category": "Baby Monitor", "brand": "Owlet", "price": 1200},
        ],
        "negative_tests": [
            {"name": "Baby Clothes", "category": "Clothing", "brand": "Carter's", "price": 50},
        ]
    },
    
    "BAGS_LUGGAGE": {
        "category_name": "Bags & Luggage",
        "spec_file": "GarantyAffinity_DEV_SPEC_BAGS_LUGGAGE_ESSENTIAL_UAE.pdf",
        "risk_profile": "BAGS_LUGGAGE_ESSENTIAL",
        "positive_tests": [
            {"name": "Samsonite Spinner", "category": "Luggage", "brand": "Samsonite", "price": 1200},
            {"name": "Tumi Alpha Bravo", "category": "Backpack", "brand": "Tumi", "price": 2000},
            {"name": "Rimowa Original", "category": "Suitcase", "brand": "Rimowa", "price": 4000},
        ],
        "negative_tests": [
            {"name": "Plastic Shopping Bag", "category": "Bag", "brand": "Generic", "price": 5},
        ]
    },
    
    "GARDEN_DIY": {
        "category_name": "Garden & DIY",
        "spec_file": "GarantyAffinity_DEV_SPEC_GARDEN_DIY_ESSENTIAL_UAE.pdf",
        "risk_profile": "GARDEN_DIY_ESSENTIAL",
        "positive_tests": [
            {"name": "Honda Lawn Mower", "category": "Lawn Mower", "brand": "Honda", "price": 2000},
            {"name": "Bosch Drill Set", "category": "Power Drill", "brand": "Bosch", "price": 800},
            {"name": "Weber Genesis II", "category": "Grill", "brand": "Weber", "price": 3500},
        ],
        "negative_tests": [
            {"name": "Garden Gloves", "category": "Gardening Accessories", "brand": "Generic", "price": 20},
        ]
    },
    
    "HEALTH_WELLNESS": {
        "category_name": "Health & Wellness",
        "spec_file": "GarantyAffinity_DEV_SPEC_HEALTH_WELLNESS_ESSENTIAL_UAE.pdf",
        "risk_profile": "HEALTH_WELLNESS_ESSENTIAL",
        "positive_tests": [
            {"name": "Omron Blood Pressure Monitor", "category": "Blood Pressure Monitor", "brand": "Omron", "price": 400},
            {"name": "Withings Body+", "category": "Smart Scale", "brand": "Withings", "price": 500},
            {"name": "Theragun Pro", "category": "Massage Gun", "brand": "Theragun", "price": 2000},
        ],
        "negative_tests": [
            {"name": "Vitamin C Pills", "category": "Supplements", "brand": "Generic", "price": 30},
        ]
    },
    
    "LIVING_FURNITURE": {
        "category_name": "Living & Furniture",
        "spec_file": "GarantyAffinity_DEV_SPEC_LIVING_FURNITURE_ESSENTIAL_UAE.pdf",
        "risk_profile": "LIVING_FURNITURE_ESSENTIAL",
        "positive_tests": [
            {"name": "Herman Miller Aeron", "category": "Office Chair", "brand": "Herman Miller", "price": 5000},
            {"name": "IKEA KIVIK Sofa", "category": "Sofa", "brand": "IKEA", "price": 3000},
            {"name": "West Elm Dining Table", "category": "Table", "brand": "West Elm", "price": 4000},
        ],
        "negative_tests": [
            {"name": "Table Lamp", "category": "Lighting", "brand": "IKEA", "price": 100},
        ]
    },
    
    "OPTICAL_HEARING": {
        "category_name": "Optical & Hearing",
        "spec_file": "GarantyAffinity_DEV_SPEC_OPTICAL_HEARING_ESSENTIAL_UAE.pdf",
        "risk_profile": "OPTICAL_HEARING_ESSENTIAL",
        "positive_tests": [
            {"name": "Ray-Ban Aviator", "category": "Sunglasses", "brand": "Ray-Ban", "price": 600},
            {"name": "Oakley Prescription Glasses", "category": "Glasses", "brand": "Oakley", "price": 800},
            {"name": "Phonak Hearing Aid", "category": "Hearing Aid", "brand": "Phonak", "price": 5000},
        ],
        "negative_tests": [
            {"name": "Contact Lens Solution", "category": "Accessories", "brand": "Bausch+Lomb", "price": 30},
        ]
    },
    
    "PERSONAL_CARE": {
        "category_name": "Personal Care Devices",
        "spec_file": "GarantyAffinity_DEV_SPEC_PERSONAL_CARE_FINAL_UAE.pdf",
        "risk_profile": "PERSONAL_CARE_DEVICES",
        "positive_tests": [
            {"name": "Dyson Supersonic", "category": "Hair Dryer", "brand": "Dyson", "price": 1500},
            {"name": "Philips OneBlade", "category": "Electric Shaver", "brand": "Philips", "price": 300},
            {"name": "Oral-B iO", "category": "Electric Toothbrush", "brand": "Oral-B", "price": 900},
            {"name": "GHD Platinum+", "category": "Hair Straightener", "brand": "GHD", "price": 800},
        ],
        "negative_tests": [
            {"name": "Shampoo", "category": "Hair Care", "brand": "Pantene", "price": 20},
        ]
    },
    
    "OPULENCIA_PREMIUM": {
        "category_name": "Premium & Luxury",
        "spec_file": "GarantyAffinity_DEV_SPEC_OPULENCIA_PREMIUM_UAE.pdf",
        "risk_profile": "OPULENCIA_PREMIUM",
        "positive_tests": [
            {"name": "Rolex Submariner", "category": "Luxury Watch", "brand": "Rolex", "price": 35000},
            {"name": "Louis Vuitton Speedy", "category": "Handbag", "brand": "Louis Vuitton", "price": 5000},
            {"name": "Hermès Birkin", "category": "Designer Bag", "brand": "Hermès", "price": 45000},
            {"name": "Cartier Love Bracelet", "category": "Jewelry", "brand": "Cartier", "price": 25000},
        ],
        "negative_tests": [
            {"name": "Regular Watch", "category": "Watch", "brand": "Casio", "price": 100},
        ]
    },
    
    "SOUND_MUSIC": {
        "category_name": "Sound & Music",
        "spec_file": "GarantyAffinity_DEV_SPEC_SOUND_MUSIC_ESSENTIAL_UAE.pdf",
        "risk_profile": "SOUND_MUSIC_ESSENTIAL",
        "positive_tests": [
            {"name": "Fender Stratocaster", "category": "Guitar", "brand": "Fender", "price": 6000},
            {"name": "Yamaha P-125", "category": "Digital Piano", "brand": "Yamaha", "price": 3000},
            {"name": "Marshall JCM800", "category": "Amplifier", "brand": "Marshall", "price": 4000},
        ],
        "negative_tests": [
            {"name": "Guitar Strings", "category": "Accessories", "brand": "Ernie Ball", "price": 20},
        ]
    },
    
    "SPORT_OUTDOOR": {
        "category_name": "Sport & Outdoor",
        "spec_file": "GarantyAffinity_DEV_SPEC_SPORT_OUTDOOR_ESSENTIAL_UAE.pdf",
        "risk_profile": "SPORT_OUTDOOR_ESSENTIAL",
        "positive_tests": [
            {"name": "Peloton Bike+", "category": "Exercise Bike", "brand": "Peloton", "price": 8000},
            {"name": "NordicTrack Treadmill", "category": "Treadmill", "brand": "NordicTrack", "price": 6000},
            {"name": "North Face Tent", "category": "Camping Tent", "brand": "The North Face", "price": 1500},
            {"name": "Callaway Golf Clubs", "category": "Golf Equipment", "brand": "Callaway", "price": 5000},
        ],
        "negative_tests": [
            {"name": "Yoga Mat", "category": "Fitness Accessories", "brand": "Lululemon", "price": 80},
        ]
    },
    
    "TEXTILE_FOOTWEAR": {
        "category_name": "Textile & Footwear",
        "spec_file": "GarantyAffinity_DEV_SPEC_TEXTILE_FOOTWEAR_ZARA_ONLY_UAE.pdf",
        "risk_profile": "TEXTILE_FOOTWEAR_ZARA",
        "positive_tests": [
            {"name": "Canada Goose Parka", "category": "Jacket", "brand": "Canada Goose", "price": 4000},
            {"name": "Nike Air Jordan", "category": "Sneakers", "brand": "Nike", "price": 800},
            {"name": "Christian Louboutin Heels", "category": "Shoes", "brand": "Christian Louboutin", "price": 3000},
        ],
        "negative_tests": [
            {"name": "Basic T-Shirt", "category": "Clothing", "brand": "H&M", "price": 20},
        ]
    }
}


# ============================================================
# TEST EXECUTION ENGINE
# ============================================================

class TestResults:
    def __init__(self):
        self.total_tests = 0
        self.passed = 0
        self.failed = 0
        self.errors = 0
        self.results_by_category = {}
        self.consistency_failures = []
        
    def add_result(self, category, test_type, product_name, expected, actual, passed, error=None):
        self.total_tests += 1
        if passed:
            self.passed += 1
        elif error:
            self.errors += 1
        else:
            self.failed += 1
            
        if category not in self.results_by_category:
            self.results_by_category[category] = {
                "passed": 0,
                "failed": 0,
                "errors": 0,
                "tests": []
            }
        
        if passed:
            self.results_by_category[category]["passed"] += 1
        elif error:
            self.results_by_category[category]["errors"] += 1
        else:
            self.results_by_category[category]["failed"] += 1
            
        self.results_by_category[category]["tests"].append({
            "product": product_name,
            "type": test_type,
            "expected": expected,
            "actual": actual,
            "passed": passed,
            "error": error
        })
    
    def add_consistency_failure(self, category, products, eligibilities):
        self.consistency_failures.append({
            "category": category,
            "products": products,
            "eligibilities": eligibilities
        })
    
    def print_summary(self):
        print(f"\n{'='*80}")
        print("CLASSIFICATION TEST RESULTS SUMMARY")
        print(f"{'='*80}\n")
        
        print(f"Total Tests: {self.total_tests}")
        print(f"✅ Passed: {self.passed} ({self.passed/self.total_tests*100:.1f}%)")
        print(f"❌ Failed: {self.failed} ({self.failed/self.total_tests*100:.1f}%)")
        print(f"⚠️  Errors: {self.errors} ({self.errors/self.total_tests*100:.1f}%)")
        
        print(f"\n{'='*80}")
        print("RESULTS BY CATEGORY")
        print(f"{'='*80}\n")
        
        for category, results in self.results_by_category.items():
            total = results["passed"] + results["failed"] + results["errors"]
            pass_rate = results["passed"] / total * 100 if total > 0 else 0
            
            status = "✅" if pass_rate == 100 else "⚠️" if pass_rate >= 70 else "❌"
            
            print(f"{status} {category:30} | Pass Rate: {pass_rate:5.1f}% | "
                  f"Passed: {results['passed']:3} | Failed: {results['failed']:3} | Errors: {results['errors']:3}")
        
        # Consistency check failures
        if self.consistency_failures:
            print(f"\n{'='*80}")
            print("⚠️  CONSISTENCY CHECK FAILURES")
            print(f"{'='*80}\n")
            
            for failure in self.consistency_failures:
                print(f"❌ Category: {failure['category']}")
                for i, (product, eligible) in enumerate(zip(failure['products'], failure['eligibilities'])):
                    print(f"   {i+1}. {product:40} → {'ELIGIBLE' if eligible else 'NOT ELIGIBLE'}")
                print()
        
        # Detailed failures
        print(f"\n{'='*80}")
        print("DETAILED FAILURE REPORT")
        print(f"{'='*80}\n")
        
        for category, results in self.results_by_category.items():
            failures = [t for t in results["tests"] if not t["passed"]]
            if failures:
                print(f"\n{category}:")
                for test in failures:
                    print(f"  ❌ {test['product'][:50]:50}")
                    print(f"     Expected: {test['expected']:15} | Got: {test['actual']}")
                    if test['error']:
                        print(f"     Error: {test['error'][:100]}")


def run_classification_test(product, expected_eligible, test_type, category_name):
    """Run a single classification test"""
    try:
        result = classify_product.invoke({
            "product_name": product["name"],
            "category": product["category"],
            "brand": product["brand"],
            "price": product["price"],
            "currency": "AED"
        })
        
        actual_eligible = result["classification"]["eligible"]
        passed = actual_eligible == expected_eligible
        
        return {
            "passed": passed,
            "expected": expected_eligible,
            "actual": actual_eligible,
            "reason": result["classification"].get("reason", "N/A"),
            "risk_profile": result["classification"].get("risk_profile", "N/A"),
            "error": None
        }
        
    except Exception as e:
        return {
            "passed": False,
            "expected": expected_eligible,
            "actual": None,
            "reason": None,
            "risk_profile": None,
            "error": str(e)
        }


def check_consistency(category_name, products):
    """Check if all products in the same conceptual category get the same result"""
    results = []
    
    for product in products:
        try:
            result = classify_product.invoke({
                "product_name": product["name"],
                "category": product["category"],
                "brand": product["brand"],
                "price": product["price"],
                "currency": "AED"
            })
            results.append(result["classification"]["eligible"])
        except:
            results.append(None)
    
    # Check if all results are the same
    if None not in results:
        return all(r == results[0] for r in results), results
    else:
        return False, results


def run_all_tests():
    """Run all classification tests"""
    print(f"\n{'='*80}")
    print("STARTING COMPREHENSIVE CLASSIFICATION TESTS")
    print(f"{'='*80}\n")
    print(f"Testing {len(TEST_PRODUCTS)} categories")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    test_results = TestResults()
    
    for category_key, category_data in TEST_PRODUCTS.items():
        category_name = category_data["category_name"]
        
        print(f"\n{'='*80}")
        print(f"Testing: {category_name} ({category_key})")
        print(f"Spec File: {category_data['spec_file']}")
        print(f"{'='*80}\n")
        
        # Test positive cases (should be ELIGIBLE)
        print(f"Running {len(category_data['positive_tests'])} positive tests...")
        for product in category_data["positive_tests"]:
            result = run_classification_test(product, True, "positive", category_name)
            test_results.add_result(
                category_name,
                "positive",
                product["name"],
                "ELIGIBLE",
                "ELIGIBLE" if result["actual"] else "NOT ELIGIBLE",
                result["passed"],
                result["error"]
            )
            
            status = "✅" if result["passed"] else "❌"
            print(f"  {status} {product['name'][:50]:50} ({product['category']:20})")
            if not result["passed"] and not result["error"]:
                print(f"     Reason: {result['reason'][:80]}")
        
        # Test negative cases (should be NOT ELIGIBLE)
        print(f"\nRunning {len(category_data['negative_tests'])} negative tests...")
        for product in category_data["negative_tests"]:
            result = run_classification_test(product, False, "negative", category_name)
            test_results.add_result(
                category_name,
                "negative",
                product["name"],
                "NOT ELIGIBLE",
                "ELIGIBLE" if result["actual"] else "NOT ELIGIBLE",
                result["passed"],
                result["error"]
            )
            
            status = "✅" if result["passed"] else "❌"
            print(f"  {status} {product['name'][:50]:50} ({product['category']:20})")
        
        # Consistency check for categories with multiple variants
        if category_key == "ELECTRONICS":
            print(f"\nRunning consistency checks...")
            
            # Check smartphones
            smartphones = [p for p in category_data["positive_tests"] if "Phone" in p["category"] or "Mobile" in p["category"] or "Smartphone" in p["category"]][:4]
            consistent, results = check_consistency(category_name, smartphones)
            if not consistent:
                test_results.add_consistency_failure(
                    "Smartphones",
                    [p["name"] for p in smartphones],
                    results
                )
                print(f"  ❌ Smartphones consistency check FAILED")
            else:
                print(f"  ✅ Smartphones consistency check PASSED")
            
            # Check laptops
            laptops = [p for p in category_data["positive_tests"] if "Laptop" in p["category"] or "Notebook" in p["category"] or "MacBook" in p["category"]][:3]
            consistent, results = check_consistency(category_name, laptops)
            if not consistent:
                test_results.add_consistency_failure(
                    "Laptops",
                    [p["name"] for p in laptops],
                    results
                )
                print(f"  ❌ Laptops consistency check FAILED")
            else:
                print(f"  ✅ Laptops consistency check PASSED")
    
    # Print final summary
    test_results.print_summary()
    
    print(f"\n{'='*80}")
    print(f"Testing completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*80}\n")
    
    # Save results to JSON
    output_file = f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump({
            "summary": {
                "total": test_results.total_tests,
                "passed": test_results.passed,
                "failed": test_results.failed,
                "errors": test_results.errors
            },
            "by_category": test_results.results_by_category,
            "consistency_failures": test_results.consistency_failures
        }, f, indent=2)
    
    print(f"📄 Detailed results saved to: {output_file}\n")
    
    return test_results


if __name__ == "__main__":
    results = run_all_tests()
    
    # Exit with appropriate code
    exit_code = 0 if results.failed == 0 and results.errors == 0 else 1
    exit(exit_code)