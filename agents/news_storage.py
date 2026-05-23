# agents/news_storage.py
import os
import uuid
from supabase import create_client, Client
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
from fastembed import TextEmbedding
from dotenv import load_dotenv

load_dotenv()

# ==========================================
# 1. INITIALIZE CLIENTS & MODELS
# ==========================================

# Supabase Setup
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
if SUPABASE_URL and SUPABASE_KEY:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
else:
    print("Warning: Supabase credentials missing from .env")
    supabase = None

# Qdrant Setup
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
if QDRANT_URL and QDRANT_API_KEY:
    qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
else:
    print("Warning: Qdrant credentials missing from .env")
    qdrant = None

COLLECTION_NAME = "competitor_news"

# Initialize local embedding model
embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")

# Ensure Qdrant collection exists
def ensure_qdrant_collection():
    if not qdrant:
        return
    
    collections = [c.name for c in qdrant.get_collections().collections]
    if COLLECTION_NAME not in collections:
        print(f"Creating new Qdrant collection: {COLLECTION_NAME}")
        # BAAI/bge-small-en-v1.5 uses 384 dimensions
        qdrant.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE)
        )

# ==========================================
# 2. THE STORAGE LOGIC
# ==========================================

def chunk_text(text: str, chunk_size: int = 500) -> list[str]:
    """A lightweight chunker to break long articles into semantic blocks for accurate RAG."""
    words = text.split()
    return [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]

def upsert_to_supabase(article: dict) -> bool:
    """
    Attempts to insert the raw article. 
    Returns True if successful (new article), False if it already exists or fails.
    """
    if not supabase:
        return False
        
    try:
        # We assume you have a table named 'articles' in Supabase
        response = supabase.table("articles").insert(article).execute()
        return True
    except Exception as e:
        # If the article_id primary key already exists, Supabase throws an error
        if "duplicate key value" in str(e).lower() or "23505" in str(e):
            return False
        print(f"Supabase Error for {article['article_id']}: {e}")
        return False

def embed_and_store_in_qdrant(article: dict):
    """Chunks the text, embeds it locally, and pushes to Qdrant with metadata."""
    if not qdrant:
        return

    chunks = chunk_text(article["content"])
    embeddings = list(embedding_model.embed(chunks))
    
    points = []
    for i, (chunk_text_data, vector) in enumerate(zip(chunks, embeddings)):
        # Generate a strictly formatted UUID for Qdrant using the article ID and chunk index
        chunk_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{article['article_id']}_{i}"))
        
        points.append(
            PointStruct(
                id=chunk_id,
                vector=vector,
                payload={
                    "article_id": article["article_id"],
                    "chunk_index": i,
                    "company": article["company"],
                    "source_type": article["source_type"],
                    "published_date": article["published_date"],
                    "text": chunk_text_data # Storing the chunk text in the payload for immediate RAG retrieval
                }
            )
        )
        
    if points:
        qdrant.upsert(
            collection_name=COLLECTION_NAME,
            points=points
        )
        print(f"  -> Embedded and pushed {len(points)} chunks to Qdrant.")

def process_storage_batch(clean_articles: list[dict]):
    """The master function that routes data to the Dual-Database Architecture."""
    ensure_qdrant_collection()
    
    new_articles_processed = 0
    
    print(f"Attempting to store {len(clean_articles)} sanitized articles...")
    
    for article in clean_articles:
        # 1. The Relational Gatekeeper
        is_new = upsert_to_supabase(article)
        
        if is_new:
            # 2. Only if Supabase accepts it, we pay the compute cost to embed and push to Qdrant
            embed_and_store_in_qdrant(article)
            new_articles_processed += 1
            
    print(f"Storage Complete: Added {new_articles_processed} new articles. Ignored {len(clean_articles) - new_articles_processed} duplicates.")

if __name__ == "__main__":
    # A mock sanitized article pretending to come from news_cleaner.py
    # Updated ID to bypass the Supabase duplication check from the previous run
    mock_clean_batch = [
        {
            "article_id": "test_hash_BRAND_NEW_123", 
            "company": "Supabase",
            "source_type": "official_blog",
            "published_date": "2026-05-23T10:00:00Z",
            "url": "https://supabase.com/blog/test-architecture",
            "title": "Testing the Storage Engine",
            "content": "This is a dummy article. We are testing if the fastembed model correctly chunks this text, turns it into a mathematical vector, and pushes it to our shiny new Qdrant cluster in Frankfurt."
        }
    ]
    
    print("Initiating Phase 3 Integration Test...")
    process_storage_batch(mock_clean_batch)