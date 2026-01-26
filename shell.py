from database.models import SessionLocal, InsurancePackage

db = SessionLocal()
pkg = db.query(InsurancePackage).first()

print(type(pkg.package_data))
print(pkg.package_data.keys())
