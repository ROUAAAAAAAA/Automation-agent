ALTER USER postgres PASSWORD '123456';
CREATE TABLE partners (
    partner_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name VARCHAR(255) NOT NULL,
    website_url VARCHAR(500) NOT NULL,
    country VARCHAR(10) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE products (
    product_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    partner_id UUID REFERENCES partners(partner_id) ON DELETE CASCADE,
    product_name VARCHAR(500) NOT NULL,
    description TEXT,
    category VARCHAR(255),
    brand VARCHAR(255),
    price DECIMAL(10,2) NOT NULL,
    currency VARCHAR(10) NOT NULL,
    product_url TEXT,
    image_url TEXT,
    source_website VARCHAR(255),
    in_stock BOOLEAN DEFAULT true,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE insurance_packages (
    package_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    partner_id UUID REFERENCES partners(partner_id) ON DELETE CASCADE,
    package_name VARCHAR(100),
    guarantees JSONB,
    monthly_premium DECIMAL(10,2),
    status VARCHAR(50) DEFAULT 'draft',
    ai_confidence DECIMAL(3,2),
    created_by VARCHAR(50),
    approved_by UUID,
    approved_at TIMESTAMP
);