ALTER TABLE products 
ADD COLUMN IF NOT EXISTS processed BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS processing_status VARCHAR(50) DEFAULT 'pending',
ADD COLUMN IF NOT EXISTS processing_started_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS processing_completed_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS processing_error TEXT;

CREATE INDEX IF NOT EXISTS idx_products_processed ON products(processed);
CREATE INDEX IF NOT EXISTS idx_products_status ON products(processing_status);
CREATE INDEX IF NOT EXISTS idx_products_partner_processed ON products(partner_id, processed);
CREATE INDEX IF NOT EXISTS idx_products_partner_status ON products(partner_id, processing_status);

-- Verify
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'products' 
  AND column_name IN ('processed', 'processing_status', 'processing_started_at');
