
import os
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Numeric, Boolean, ForeignKey, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import dotenv
dotenv.load_dotenv()

Base = declarative_base()

class Partner(Base):
    __tablename__ = "partners"

    partner_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_name = Column(String(255), nullable=False)
    website_url = Column(String(500), nullable=False)
    country = Column(String(10), nullable=False)
    status = Column(String(50), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)

    products = relationship("Product", back_populates="partner", cascade="all, delete-orphan")
    packages = relationship("InsurancePackage", back_populates="partner", cascade="all, delete-orphan")


class Product(Base):
    __tablename__ = "products"

    product_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    partner_id = Column(UUID(as_uuid=True), ForeignKey("partners.partner_id", ondelete="CASCADE"), nullable=False)
    
    product_name = Column(String(500), nullable=False)
    description = Column(Text)
    category = Column(String(255))
    brand = Column(String(255))
    price = Column(Numeric(10, 2), nullable=False, default=0.0)
    currency = Column(String(10), nullable=False)
    product_url = Column(Text)
    image_url = Column(Text)
    source_website = Column(String(255))
    in_stock = Column(Boolean, default=True)
    scraped_at = Column(DateTime, default=datetime.utcnow)

    
    partner = relationship("Partner", back_populates="products")


class InsurancePackage(Base):
    __tablename__ = "insurance_packages"

    package_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    partner_id = Column(UUID(as_uuid=True), ForeignKey("partners.partner_id", ondelete="CASCADE"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.product_id", ondelete="CASCADE"), nullable=False)  # Link to product
    
    package_data = Column(JSON, nullable=False) 
    status = Column(String(50), default="ai_generated")
    ai_confidence = Column(Numeric(3, 2), default=0.95)
    created_at = Column(DateTime, default=datetime.utcnow)

    partner = relationship("Partner", back_populates="packages")
    product = relationship("Product")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
       raise RuntimeError("DATABASE_URL not set")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)