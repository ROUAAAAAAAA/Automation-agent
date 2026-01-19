from typing import List  
import os
import torch
from dotenv import load_dotenv
from langchain_pinecone import PineconeVectorStore
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document  

load_dotenv()

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f" Device: {device}")

embeddings = HuggingFaceEmbeddings(
    model_name="BAAI/bge-large-en-v1.5",
    model_kwargs={"device": device},
    encode_kwargs={
        "normalize_embeddings": True,
        "batch_size": 32 if device == "cuda" else 8
    }
)

vectorstore = PineconeVectorStore(
    index_name=os.getenv("PINECONE_INDEX_NAME", "insurance-product-specs"),
    embedding=embeddings,
    pinecone_api_key=os.getenv("PINECONE_API_KEY")
)

def retrieve_product_specs(query: str, k: int = 5) -> str:
    """
    Retrieve product specification documents.
    """
    try:
        
        enhanced_query = f"{query} insurance specification"
        
        docs = vectorstore.similarity_search(enhanced_query, k=k)
        
        if not docs:
            return "No relevant product specifications found."
        
        
        def sort_priority(doc):
            filename = doc.metadata.get('file_name', '').lower()
            if 'garantyaffinity' in filename:
                return 0  
            elif 'assurmax' in filename:
                return 1  
            else:
                return 2
        
        docs.sort(key=sort_priority)
        
        results = []
        results.append("=" * 70)
        results.append("PRODUCT SPECIFICATION DOCUMENTS")
        results.append("=" * 70)
        results.append(" SPEC DOCS : Coverage details, exclusions")
        results.append("ASSURMAX DOCS: Pricing caps only (for Electronics, Luxury, Textile)")
        results.append("=" * 70 + "\n")
        
        for i, doc in enumerate(docs, 1):
            meta = doc.metadata
            filename = meta.get('file_name', 'Unknown')
            category = meta.get('category', 'N/A')
            pages = meta.get('page_range', 'N/A')
            is_complete = meta.get('is_complete', False)
            chunk_info = ""
            
            if not is_complete:
                chunk_idx = meta.get('chunk_index', 0) + 1
                total_chunks = meta.get('total_chunks', 1)
                chunk_info = f"Part {chunk_idx} of {total_chunks}"
            else:
                chunk_info = "✓ COMPLETE DOCUMENT"
            
            doc_type = ""
            if 'assurmax' in filename.lower():
                doc_type = " ASSURMAX PRICING DOCUMENT"
            elif 'garantyaffinity' in filename.lower():
                doc_type = " NORMAL SPECIFICATION DOCUMENT"
            
            text = doc.page_content.strip()
            text = text.replace("\n- ", "\n  - ")
            text = text.replace("\n\n", "\n")
            
            results.append(f"""[Document {i}] {doc_type}
File: {filename}
Category: {category}
Pages: {pages}
Status: {chunk_info}
---
{text}
""")
        
      
    

        results.append("\n" + "=" * 70)
        results.append("AGENT INSTRUCTIONS - WHAT TO EXTRACT:")
        results.append("=" * 70)
        results.append("""
CRITICAL: You may receive MULTIPLE document types.

DOCUMENT TYPES & PURPOSES:
1. NORMAL SPECIFICATION DOCUMENTS (GarantyAffinity_...):
   - REQUIRED FOR ALL PRODUCTS
   - Contains: Coverage modules, General exclusions, Risk profile
   - Use for: All coverage details and eligibility

2. ASSURMAX DOCUMENTS (ASSURMAX_...):
   - For Electronics, Luxury, Textile
   - Contains: Pricing caps (Per Item Cap, Pack Cap)
   - Do NOT use for coverage details!

EXTRACTION RULES:

A. ALWAYS USE NORMAL SPEC DOC FOR:
   - Risk profile (REQUIRED for pricing)
   - Coverage modules (Theft, Water Damage, etc.)
   - General exclusions (Cosmetic damage, etc.)
   - Eligibility check

B. CHECK FOR ASSURMAX DOC:
   - Look for "ASSURMAX_" in filename
   - If found: Product is ASSURMAX-eligible
   - Extract: Per Item Cap, Pack Cap

C. PRICING LOGIC:
   - If ASSURMAX doc found: Generate ASSURMAX & ASSURMAX+ plans
   - Call calculate_pricing with: risk_profile, product_value, market, plan
   - plan must be: "ASSURMAX", "ASSURMAX+", or "standard"
   - Include 12-month AND 24-month pricing for all



IMPORTANT: Coverage details always come from normal specification documents!
""")
        
        return "\n".join(results)
        
    except Exception as e:
        error_msg = f"Error retrieving product specifications: {str(e)}"
        print(error_msg)
        return error_msg

def retrieve_specs_raw(query: str, k: int = 3) -> List[Document]:
    """Retrieve raw document objects."""
    try:
        return vectorstore.similarity_search(query, k=k)
    except Exception as e:
        print(f"Error retrieving raw specs: {e}")
        return []


retrieve_specs = retrieve_product_specs

if __name__ == "__main__":
    print("="*80)
    print("PRODUCT SPECIFICATION RETRIEVER")
    print("="*80)
    print(f"Device: {device}")
    print(f"Index: {os.getenv('PINECONE_INDEX_NAME', 'insurance-product-specs')}")
    print("="*80)
    
    test_queries = [
        "iPhone smartphone UAE AED",
        "lawn mower garden UAE AED", 
        "Rolex watch luxury UAE AED"
    ]
    
    for query in test_queries:
        print(f"\n{'='*40}")
        print(f"Testing: {query}")
        print(f"{'='*40}")
        
        try:
            specs = retrieve_product_specs(query, k=5)
            print(specs[:1500])
            if len(specs) > 1500:
                print("\n... [output truncated] ...")
        except Exception as e:
            print(f" Error: {e}")