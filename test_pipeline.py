# test_pipeline_directly.py
import sys
import os
import time
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run_pipeline_test():
    """Test the pipeline directly in terminal"""
    print("=" * 70)
    print("DIRECT PIPELINE TEST - TERMINAL")
    print("=" * 70)
    
    # Test 1: Simple import test
    print("\n1. Testing imports...")
    try:
        from pipeline.streaming_pipeline import true_streaming_pipeline
        print("✅ Imports successful")
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Test 2: Check environment
    print("\n2. Checking environment...")
    from dotenv import load_dotenv
    load_dotenv()
    
    api_key = os.getenv("FIRECRAWL_API_KEY")
    if api_key:
        print(f"✅ API Key loaded ({len(api_key)} chars)")
    else:
        print("❌ API Key missing!")
        return
    
    # Test 3: Run pipeline with timing
    print("\n3. Running pipeline...")
    print(f"Start time: {datetime.now().strftime('%H:%M:%S')}")
    
    start_time = time.time()
    
    try:
        # Run with minimal settings for quick test
        result = true_streaming_pipeline(
            start_url="https://www.virginmegastore.ae/en",
            selected_categories=["ELECTRONIC_PRODUCTS"]
        )
        
        total_time = time.time() - start_time
        
        print(f"\nTotal execution time: {total_time:.2f}s ({total_time/60:.2f} minutes)")
        
        if result.get("success"):
            stats = result.get("stats", {})
            print(f"\n✅ SUCCESS!")
            print(f"Scraped: {stats.get('scraped', 0)}")
            print(f"Processed: {stats.get('processed', 0)}")
            print(f"Eligible: {stats.get('eligible', 0)}")
        else:
            print(f"\n❌ FAILED: {result.get('error', 'Unknown error')}")
            
    except KeyboardInterrupt:
        print("\n⚠️ Pipeline interrupted by user")
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\nEnd time: {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 70)

if __name__ == "__main__":
    run_pipeline_test()