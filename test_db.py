"""Quick database connection test"""
from database.models import SessionLocal, Partner, Product
from database.crud import get_processing_stats

print("Testing database connection...\n")

db = SessionLocal()

try:
    # Test query
    partner_count = db.query(Partner).count()
    product_count = db.query(Product).count()
    
    print(f"✅ Database connected successfully!")
    print(f"   Partners: {partner_count}")
    print(f"   Products: {product_count}")
    
    # Test new columns
    products = db.query(Product).limit(3).all()
    for p in products:
        print(f"\n📦 {p.product_name[:50]}")
        print(f"   Processing status: {p.processing_status}")
        print(f"   Processed: {p.processed}")
    
    print("\n✅ All database checks passed!")
    
except Exception as e:
    print(f"❌ Database error: {e}")
    
finally:
    db.close()
