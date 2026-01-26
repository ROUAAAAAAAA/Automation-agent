"""
CRUD (Create, Read, Update, Delete) Operations
Reusable database functions for the insurance workflow
"""

from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import List, Optional, Dict, Tuple
from datetime import datetime, timedelta
from database.models import Partner, Product, InsurancePackage


# ============================================================
# PARTNER OPERATIONS
# ============================================================

def get_or_create_partner(db: Session, company_name: str, website_url: str, country: str) -> Partner:
    """
    Get existing partner or create new one
    
    Args:
        db: Database session
        company_name: Partner company name (e.g., "Noon")
        website_url: Partner website URL
        country: ISO country code (e.g., "AE", "TN")
    
    Returns:
        Partner object
    """
    partner = db.query(Partner).filter_by(company_name=company_name).first()
    
    if not partner:
        partner = Partner(
            company_name=company_name,
            website_url=website_url,
            country=country,
            status="active"
        )
        db.add(partner)
        db.commit()
        db.refresh(partner)
    
    return partner


def get_partner_by_name(db: Session, company_name: str) -> Optional[Partner]:
    """Get partner by company name"""
    return db.query(Partner).filter_by(company_name=company_name).first()


def get_all_partners(db: Session) -> List[Partner]:
    """Get all partners"""
    return db.query(Partner).order_by(Partner.created_at.desc()).all()


# ============================================================
# PRODUCT OPERATIONS
# ============================================================

def get_unprocessed_products(
    db: Session, 
    partner_id: str, 
    limit: Optional[int] = None
) -> List[Product]:
    """
    Get products that haven't been processed by AI yet
    
    Args:
        db: Database session
        partner_id: Partner UUID
        limit: Maximum number of products to return
    
    Returns:
        List of unprocessed Product objects
    """
    query = db.query(Product).filter(
        and_(
            Product.partner_id == partner_id,
            Product.processed == False,
            Product.processing_status == 'pending',
            Product.price > 0,
            Product.currency.isnot(None)
        )
    ).order_by(Product.scraped_at.desc())
    
    if limit:
        query = query.limit(limit)
    
    return query.all()


def mark_product_processing(db: Session, product_id: str) -> Product:
    """
    Mark product as currently being processed
    
    Args:
        db: Database session
        product_id: Product UUID
    
    Returns:
        Updated Product object
    """
    product = db.query(Product).filter_by(product_id=product_id).first()
    
    if product:
        product.processing_status = 'processing'
        product.processing_started_at = datetime.utcnow()
        db.commit()
        db.refresh(product)
    
    return product


def mark_product_completed(db: Session, product_id: str) -> Product:
    """
    Mark product as successfully processed
    
    Args:
        db: Database session
        product_id: Product UUID
    
    Returns:
        Updated Product object
    """
    product = db.query(Product).filter_by(product_id=product_id).first()
    
    if product:
        product.processed = True
        product.processing_status = 'completed'
        product.processing_completed_at = datetime.utcnow()
        db.commit()
        db.refresh(product)
    
    return product


def mark_product_failed(db: Session, product_id: str, error_message: str) -> Product:
    """
    Mark product processing as failed
    
    Args:
        db: Database session
        product_id: Product UUID
        error_message: Error description
    
    Returns:
        Updated Product object
    """
    product = db.query(Product).filter_by(product_id=product_id).first()
    
    if product:
        product.processing_status = 'failed'
        product.processing_error = error_message
        product.processing_completed_at = datetime.utcnow()
        db.commit()
        db.refresh(product)
    
    return product


def get_products_with_packages(
    db: Session, 
    partner_id: str, 
    limit: Optional[int] = None
) -> List[Tuple[Product, InsurancePackage]]:
    """
    Get products with their insurance packages
    
    Args:
        db: Database session
        partner_id: Partner UUID
        limit: Maximum number to return
    
    Returns:
        List of (Product, InsurancePackage) tuples
    """
    query = db.query(Product, InsurancePackage)\
        .join(InsurancePackage, Product.product_id == InsurancePackage.product_id)\
        .filter(Product.partner_id == partner_id)\
        .order_by(Product.processing_completed_at.desc())
    
    if limit:
        query = query.limit(limit)
    
    return query.all()


# ============================================================
# INSURANCE PACKAGE OPERATIONS
# ============================================================

def create_insurance_package(
    db: Session, 
    partner_id: str, 
    product_id: str, 
    package_data: dict,
    is_eligible: bool
) -> InsurancePackage:
    """
    Create insurance package in database
    
    Args:
        db: Database session
        partner_id: Partner UUID
        product_id: Product UUID
        package_data: Complete AI-generated package (dict)
        is_eligible: True if product is eligible for insurance
    
    Returns:
        Created InsurancePackage object
    """
    package = InsurancePackage(
        partner_id=partner_id,
        product_id=product_id,
        package_data=package_data,
        status="eligible" if is_eligible else "not_eligible",
        ai_confidence=0.95 if is_eligible else 0.0
    )
    
    db.add(package)
    db.commit()
    db.refresh(package)
    
    return package


def get_eligible_packages(db: Session, partner_id: str) -> List[InsurancePackage]:
    """
    Get all eligible insurance packages for a partner
    
    Args:
        db: Database session
        partner_id: Partner UUID
    
    Returns:
        List of eligible InsurancePackage objects
    """
    return db.query(InsurancePackage)\
        .filter(
            InsurancePackage.partner_id == partner_id,
            InsurancePackage.status == "eligible"
        )\
        .all()


# ============================================================
# ANALYTICS & REPORTING
# ============================================================

def get_processing_stats(db: Session, partner_id: Optional[str] = None) -> Dict:
    """
    Get processing statistics
    
    Args:
        db: Database session
        partner_id: Optional partner UUID to filter by
    
    Returns:
        Dictionary with statistics
    """
    query = db.query(Product)
    
    if partner_id:
        query = query.filter(Product.partner_id == partner_id)
    
    total = query.count()
    processed = query.filter(Product.processed == True).count()
    pending = query.filter(Product.processing_status == 'pending').count()
    processing = query.filter(Product.processing_status == 'processing').count()
    failed = query.filter(Product.processing_status == 'failed').count()
    
    # Get eligible count
    eligible_query = db.query(InsurancePackage)\
        .filter(InsurancePackage.status == "eligible")
    
    if partner_id:
        eligible_query = eligible_query.filter(InsurancePackage.partner_id == partner_id)
    
    eligible = eligible_query.count()
    
    return {
        "total_products": total,
        "processed": processed,
        "pending": pending,
        "processing": processing,
        "failed": failed,
        "eligible": eligible,
        "eligible_rate": round(eligible / processed * 100, 2) if processed > 0 else 0
    }


def get_recent_activity(db: Session, hours: int = 24, limit: int = 50) -> List[Product]:
    """
    Get recently processed products
    
    Args:
        db: Database session
        hours: Look back this many hours
        limit: Maximum number of products
    
    Returns:
        List of recently processed products
    """
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    
    return db.query(Product)\
        .filter(
            Product.processing_completed_at >= cutoff,
            Product.processed == True
        )\
        .order_by(Product.processing_completed_at.desc())\
        .limit(limit)\
        .all()
