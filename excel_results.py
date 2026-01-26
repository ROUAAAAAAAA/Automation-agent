"""
Export all 433 processed products to Excel with multiple sheets
"""

import pandas as pd
from database.models import SessionLocal, Product, InsurancePackage
from datetime import datetime

print("📊 Exporting 433 processed products to Excel...\n")

db = SessionLocal()

try:
    # Query all processed products
    query = db.query(
        Product.product_name,
        Product.brand,
        Product.category,
        Product.price,
        Product.currency,
        Product.processing_status,
        InsurancePackage.status.label('insurance_status'),
        InsurancePackage.package_data
    ).join(
        InsurancePackage,
        Product.product_id == InsurancePackage.product_id
    ).filter(
        Product.processed == True
    ).order_by(
        Product.processing_completed_at.desc()
    )
    
    results = query.all()
    
    # Convert to DataFrame
    data = []
    for row in results:
        pkg = row.package_data
        
        # Extract product info
        product_info = pkg.get('product', {})
        
        record = {
            'Product Name': row.product_name,
            'Brand': row.brand or 'N/A',
            'Category': product_info.get('category', 'N/A'),
            'Price': row.price,
            'Currency': row.currency,
            'Eligible': 'Yes' if pkg.get('eligible') else 'No',
            'Insurance Status': row.insurance_status,
            'Risk Profile': pkg.get('risk_profile', 'N/A'),
            'Document Type': pkg.get('document_type', 'N/A'),
            'Value Bucket': pkg.get('value_bucket', 'N/A'),
            'Premium 12M': None,
            'Premium 24M': None,
            'Rejection Reason': pkg.get('reason', '')
        }
        
        # Extract premiums for eligible products
        if pkg.get('eligible'):
            if 'premium' in pkg:
                record['Premium 12M'] = pkg['premium'].get('12_months', {}).get('annual_premium')
                record['Premium 24M'] = pkg['premium'].get('24_months', {}).get('total_premium')
            elif 'plans' in pkg and 'ASSURMAX' in pkg['plans']:
                # ASSURMAX products
                record['ASSURMAX 12M'] = pkg['plans']['ASSURMAX'].get('12_months', {}).get('annual_premium')
                record['ASSURMAX 24M'] = pkg['plans']['ASSURMAX'].get('24_months', {}).get('total_premium')
                record['ASSURMAX+ 12M'] = pkg['plans']['ASSURMAX+'].get('12_months', {}).get('annual_premium')
                record['ASSURMAX+ 24M'] = pkg['plans']['ASSURMAX+'].get('24_months', {}).get('total_premium')
        
        data.append(record)
    
    # Create main DataFrame
    df = pd.DataFrame(data)
    
    # Create Excel with multiple sheets
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    excel_file = f'insurance_results_{timestamp}.xlsx'
    
    with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
        # Sheet 1: All products
        df.to_excel(writer, sheet_name='All Products', index=False)
        
        # Sheet 2: Eligible products only
        eligible_df = df[df['Eligible'] == 'Yes'].copy()
        eligible_df.to_excel(writer, sheet_name='Eligible Products', index=False)
        
        # Sheet 3: Not eligible products
        not_eligible_df = df[df['Eligible'] == 'No'].copy()
        not_eligible_df.to_excel(writer, sheet_name='Not Eligible', index=False)
        
        # Sheet 4: ASSURMAX products
        assurmax_df = df[df['Document Type'] == 'ASSURMAX'].copy()
        if len(assurmax_df) > 0:
            assurmax_df.to_excel(writer, sheet_name='ASSURMAX', index=False)
        
        # Sheet 5: Summary statistics
        summary_data = {
            'Metric': [
                'Total Products',
                'Eligible Products',
                'Not Eligible Products',
                'Eligibility Rate (%)',
                'Average Price (AED)',
                'ASSURMAX Products',
                'STANDARD Products'
            ],
            'Value': [
                len(df),
                len(eligible_df),
                len(not_eligible_df),
                round(len(eligible_df) / len(df) * 100, 2),
                round(df['Price'].mean(), 2),
                len(df[df['Document Type'] == 'ASSURMAX']),
                len(df[df['Document Type'] == 'STANDARD'])
            ]
        }
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
    
    print(f"✅ Exported to: {excel_file}\n")
    print("📊 Summary:")
    print(f"   Total Products: {len(df)}")
    print(f"   Eligible: {len(eligible_df)} ({len(eligible_df)/len(df)*100:.1f}%)")
    print(f"   Not Eligible: {len(not_eligible_df)} ({len(not_eligible_df)/len(df)*100:.1f}%)")
    print(f"   ASSURMAX: {len(assurmax_df)}")
    
    # Category breakdown
    print("\n📁 By Category:")
    category_stats = df.groupby('Category')['Eligible'].apply(
        lambda x: f"{(x == 'Yes').sum()}/{len(x)}"
    )
    for cat, stat in category_stats.head(10).items():
        print(f"   {cat}: {stat}")

finally:
    db.close()
