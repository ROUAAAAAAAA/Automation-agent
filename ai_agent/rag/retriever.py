from typing import List  
import os
import torch
from dotenv import load_dotenv
from langchain_pinecone import PineconeVectorStore
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document  

load_dotenv()

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"🖥️ Device: {device}")

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

def retrieve_specs_raw(query: str, k: int = 3, market: str = None) -> List[Document]:
    """
    Retrieve raw document objects with MARKET FILTERING.
    
    Args:
        query: Search query
        k: Number of documents to retrieve (will retrieve k*2 then filter)
        market: "UAE" or "Tunisia" - filters documents by market
    
    Returns:
        List of Document objects (market-filtered)
    """
    try:
        # Retrieve more docs to account for filtering
        docs = vectorstore.similarity_search(query, k=k*3)
        
        if not market:
            return docs[:k]
        
        # CRITICAL: Filter by market
        market_docs = []
        for doc in docs:
            filename = doc.metadata.get('file_name', '').lower()
            
            if market == "UAE":
                # UAE specs: contain "uae" or "essential" but NOT "tunisia" or "_tn"
                is_uae = ("uae" in filename or "essential" in filename) and \
                         "tunisia" not in filename and "_tn." not in filename
                if is_uae:
                    market_docs.append(doc)
                    
            elif market == "Tunisia":
                # Tunisia specs: contain "tunisia" or "_tn"
                is_tunisia = "tunisia" in filename or "_tn." in filename
                if is_tunisia:
                    market_docs.append(doc)
        
        # Return top k market-specific docs
        return market_docs[:k] if market_docs else docs[:k]
        
    except Exception as e:
        print(f"❌ Error retrieving raw specs: {e}")
        return []

def retrieve_product_specs(query: str, k: int = 5) -> str:
    """
    Retrieve product specification documents from Pinecone.
    
    Returns formatted document content for downstream processing.
    
    Args:
        query: Search query (product name, category, etc.)
        k: Number of documents to retrieve
    
    Returns:
        Formatted string with document content and metadata
    """
    try:
        # Enhanced query for better retrieval
        enhanced_query = f"{query} insurance specification coverage"
        
        # Retrieve documents
        docs = vectorstore.similarity_search(enhanced_query, k=k)
        
        if not docs:
            return "No relevant product specifications found."
        
        # Sort by document priority (STANDARD specs first)
        def sort_priority(doc):
            filename = doc.metadata.get('file_name', '').lower()
            
            # Priority 1: STANDARD specifications
            if 'garantyaffinity' in filename or 'standard' in filename:
                return 0
            
            # Priority 2: NEW ASSURMAX (simplified)
            elif 'assurmax_simplified' in filename:
                return 1
            
            # Priority 3: OLD ASSURMAX (deprecated, lower priority)
            elif 'assurmax' in filename:
                return 2
            
            # Priority 4: Other documents
            else:
                return 3
        
        docs.sort(key=sort_priority)
        
        # Format results
        results = []
        results.append("=" * 70)
        results.append("RETRIEVED PRODUCT SPECIFICATION DOCUMENTS")
        results.append("=" * 70)
        
        for i, doc in enumerate(docs, 1):
            meta = doc.metadata
            filename = meta.get('file_name', 'Unknown')
            category = meta.get('category', 'N/A')
            pages = meta.get('page_range', 'N/A')
            
            # Document status
            is_complete = meta.get('is_complete', False)
            if is_complete:
                status = "✓ COMPLETE"
            else:
                chunk_idx = meta.get('chunk_index', 0) + 1
                total_chunks = meta.get('total_chunks', 1)
                status = f"Part {chunk_idx}/{total_chunks}"
            
            # Clean document content
            content = doc.page_content.strip()
            content = content.replace("\n- ", "\n  - ")
            
            results.append(f"""
{'='*70}
[DOCUMENT {i}]
{'='*70}
File: {filename}
Category: {category}
Pages: {pages}
Status: {status}

CONTENT:
{content}
""")
        
        results.append("=" * 70)
        results.append(f"Retrieved {len(docs)} documents")
        results.append("=" * 70)
        
        return "\n".join(results)
        
    except Exception as e:
        error_msg = f"Error retrieving product specifications: {str(e)}"
        print(f"❌ {error_msg}")
        return error_msg

# Alias for backward compatibility
retrieve_specs = retrieve_product_specs

if __name__ == "__main__":
    print("="*80)
    print("PRODUCT SPECIFICATION RETRIEVER")
    print("="*80)
    print(f"Device: {device}")
    print(f"Index: {os.getenv('PINECONE_INDEX_NAME', 'insurance-product-specs')}")
    print("="*80)
    
    # Test queries
    test_queries = [
        ("iPhone smartphone electronics", "UAE"),
        ("laptop computer gaming", "Tunisia"),
        ("washing machine appliance", "UAE")
    ]
    
    for query, market in test_queries:
        print(f"\n{'='*80}")
        print(f"TEST QUERY: {query} (Market: {market})")
        print(f"{'='*80}")
        
        try:
            docs = retrieve_specs_raw(query, k=3, market=market)
            print(f"Retrieved {len(docs)} {market}-specific documents:")
            for doc in docs:
                print(f"  - {doc.metadata.get('file_name', 'Unknown')}")
                
        except Exception as e:
            print(f"❌ Error: {e}")
