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


def retrieve_specs_raw(query: str, k: int = 3) -> List[Document]:
    """
    Retrieve raw document objects without formatting.
    
    Args:
        query: Search query
        k: Number of documents to retrieve
    
    Returns:
        List of Document objects
    """
    try:
        return vectorstore.similarity_search(query, k=k)
    except Exception as e:
        print(f"❌ Error retrieving raw specs: {e}")
        return []


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
        "iPhone smartphone electronics UAE",
        "laptop computer gaming",
        "washing machine appliance"
    ]
    
    for query in test_queries:
        print(f"\n{'='*80}")
        print(f"TEST QUERY: {query}")
        print(f"{'='*80}")
        
        try:
            specs = retrieve_product_specs(query, k=3)
            
            # Show first 1500 characters
            if len(specs) > 1500:
                print(specs[:1500])
                print("\n... [truncated] ...")
            else:
                print(specs)
                
        except Exception as e:
            print(f"❌ Error: {e}")
