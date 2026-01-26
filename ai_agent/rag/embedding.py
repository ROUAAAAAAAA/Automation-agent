

from pathlib import Path
import json
from typing import List, Dict
import os
import torch

from dotenv import load_dotenv
from tqdm import tqdm

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_pinecone import PineconeVectorStore

from pinecone import Pinecone as PineconeClient, ServerlessSpec

load_dotenv()

INPUT_FILE = Path("C:\\Users\\rouam\\OneDrive\\Bureau\\Automation\\ai_agent\\rag\\knowledge_base\\extracted\\documents.jsonl")
PINECONE_INDEX_NAME = "insurance-product-specs"  


CHUNK_SIZE = 3000        
CHUNK_OVERLAP = 200     
BATCH_SIZE = 100         

EMBEDDING_DIMENSION = 1024  

def load_documents() -> List[Dict]:
    """Load extracted documents from JSONL file"""
    print(f" Loading documents from {INPUT_FILE}")

    documents = []
    with INPUT_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                documents.append(json.loads(line))

    print(f" Loaded {len(documents)} document pages")
    return documents



def chunk_documents(documents: List[Dict]) -> List[Dict]:
    """Split documents, but try to keep product specs together"""
    print("\n Chunking documents (keeping specs together)...")

    # First group pages by document
    docs_by_file = {}
    for doc in documents:
        file_name = doc["file_name"]
        if file_name not in docs_by_file:
            docs_by_file[file_name] = []
        docs_by_file[file_name].append(doc)
    
    print(f" Found {len(docs_by_file)} unique specification documents")
    
    # Sort pages within each document
    for file_name in docs_by_file:
        docs_by_file[file_name].sort(key=lambda x: x["page"])
    
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n\n", "\n\n", "\n", ". ", " ", ""],  
    )

    chunked_docs: List[Dict] = []
    
    for file_name, pages in tqdm(docs_by_file.items(), desc="Chunking specs"):
        # Combine all pages of this document
        full_text = ""
        for page in pages:
            full_text += f"\n\n--- Page {page['page']} ---\n\n{page['text']}"
        
        # Check if document can fit in one or two chunks
        if len(full_text) <= CHUNK_SIZE * 1.5:  # Allow 50% overflow
            # Keep as single chunk
            chunks = [full_text]
            is_complete = True
        else:
            # Split into multiple chunks
            chunks = splitter.split_text(full_text)
            is_complete = False
        
        for i, chunk_text in enumerate(chunks):
            # Extract page numbers from chunk for metadata
            page_lines = [line for line in chunk_text.split('\n') if '--- Page' in line]
            page_numbers = []
            for line in page_lines:
                try:
                    page_num = line.split('--- Page ')[1].split(' ---')[0]
                    page_numbers.append(float(page_num))
                except:
                    pass
            
            page_range = f"{min(page_numbers):g}-{max(page_numbers):g}" if page_numbers else "1"
            
            
            category = pages[0]["category"] if pages else "N/A"
            
            chunked_docs.append({
                "text": chunk_text,
                "metadata": {
                    "doc_id": pages[0]["doc_id"] if pages else "",
                    "file_name": file_name,
                    "category": category,
                    "page_range": page_range,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "is_complete": is_complete,  
                    "source": pages[0]["source_path"] if pages else "",
                },
            })

    print(f"\n Created {len(chunked_docs)} chunks")
    print(f"   Complete documents (single chunk): {sum(1 for c in chunked_docs if c['metadata']['is_complete'])}")
    print(f"   Average chunks per document: {len(chunked_docs) / len(docs_by_file):.1f}")

    return chunked_docs



def initialize_pinecone() -> PineconeClient:
    """Initialize Pinecone client and ensure index exists"""
    print("\n Initializing Pinecone...")

    api_key = os.getenv("PINECONE_API_KEY")
    if not api_key:
        raise RuntimeError("PINECONE_API_KEY not found in environment variables")

    pc = PineconeClient(api_key=api_key)

    existing_indexes = pc.list_indexes().names()

   
    if PINECONE_INDEX_NAME in existing_indexes:
        print(f"  Deleting existing index: {PINECONE_INDEX_NAME}")
        pc.delete_index(PINECONE_INDEX_NAME)
    
    print(f" Creating new index: {PINECONE_INDEX_NAME}")
    pc.create_index(
        name=PINECONE_INDEX_NAME,
        dimension=EMBEDDING_DIMENSION,
        metric="cosine",
        spec=ServerlessSpec(    
            cloud="aws",
            region="us-east-1",
        ),
    )
    print(" ✓ Index created successfully")
    
    
    import time
    print(" Waiting for index to be ready...")
    time.sleep(5)

    return pc



def embed_and_store_pinecone(chunks: List[Dict]):
    """Embed text chunks and store them in Pinecone"""
    print("\n Embedding and storing vectors...")
    print(" Loading BAAI/bge-large-en-v1.5 model on GPU...")
    device = "cuda" if torch.cuda.is_available() else "cpu"

    embeddings = HuggingFaceEmbeddings(
        model_name="BAAI/bge-large-en-v1.5",
        model_kwargs={
            'device': device,
        },
        encode_kwargs={
            'normalize_embeddings': True,
            "batch_size": 32 if device == "cuda" else 8,
        }
    )

    print(f" Model loaded on {device.upper()}")

    # Initialize Pinecone
    pc = initialize_pinecone()

    texts = [c["text"] for c in chunks]
    metadatas = [c["metadata"] for c in chunks]

    print(f" Uploading {len(texts)} chunks to Pinecone...")
    
    # Use PineconeVectorStore with progress bar
    vectorstore = PineconeVectorStore.from_texts(
        texts=texts,
        embedding=embeddings,
        index_name=PINECONE_INDEX_NAME,
        metadatas=metadatas,
        batch_size=BATCH_SIZE,
    )

    print(" ✓ Embeddings successfully stored in Pinecone")
    return vectorstore



def test_retrieval(vectorstore):
    """Run sanity-check similarity searches"""
    print("\n" + "="*60)
    print(" TESTING RETRIEVAL")
    print("="*60)

    # Test queries based on your product examples
    queries = [
        "iPhone smartphone mobile insurance UAE",
        "lawn mower gardening equipment",
        "exercise bike fitness Tunisia",
        "welding station industrial",
    ]

    for query in queries:
        print(f"\n{'='*60}")
        print(f" Query: {query}")
        print(f"{'='*60}")

        results = vectorstore.similarity_search(query, k=2)

        for i, doc in enumerate(results, start=1):
            meta = doc.metadata
            print(f"\nResult {i}")
            print(f"   File: {meta.get('file_name', 'Unknown')}")
            print(f"   Category: {meta.get('category', 'N/A')}")
            print(f"   Pages: {meta.get('page_range', 'N/A')}")
            print(f"   Complete: {'✓' if meta.get('is_complete', False) else '✗'}")
            print(f"   Preview: {doc.page_content[:150]}...")



def main():
    print("=" * 60)
    print(" GARANTY AFFINITY RAG KNOWLEDGE BASE BUILDER")
    print("=" * 60)
    print(f"Index name: {PINECONE_INDEX_NAME}")
    print(f"Chunk size: {CHUNK_SIZE} characters")
    print(f"Strategy: Keep product specs together")
    print("=" * 60)

    documents = load_documents()
    chunks = chunk_documents(documents)
    vectorstore = embed_and_store_pinecone(chunks)
    test_retrieval(vectorstore)

    print("\n" + "=" * 60)
    print(" RAG KNOWLEDGE BASE READY!")
    print("=" * 60)
    print(f"Index: {PINECONE_INDEX_NAME}")
    print(f"Total chunks: {len(chunks)}")
    print(f"Complete specs: {sum(1 for c in chunks if c['metadata']['is_complete'])}")
    print(f"Model: BAAI/bge-large-en-v1.5")
    print("=" * 60)
    
   

if __name__ == "__main__":
    main()