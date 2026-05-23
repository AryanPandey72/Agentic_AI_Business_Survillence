# news_orchestrator.py
from agents.news_ingestion import run_firehose
from agents.news_cleaner import process_firehose_batch
from agents.news_storage import process_storage_batch

def run_full_pipeline(company_name: str):
    print(f"\n{'='*50}")
    print(f"🚀 STARTING PIPELINE FOR: {company_name}")
    print(f"{'='*50}\n")
    
    # Phase 1: The Firehose (Ingestion)
    print("--- PHASE 1: INGESTION ---")
    raw_articles = run_firehose(company_name)
    
    if not raw_articles:
        print(f"No raw articles found for {company_name}. Pipeline stopping.")
        return
        
    # Phase 2: The Sanitizer (Cleaning)
    print("\n--- PHASE 2: CLEANING ---")
    clean_articles = process_firehose_batch(raw_articles)
    
    if not clean_articles:
        print("No articles passed the cleaning threshold. Pipeline stopping.")
        return
        
    # Phase 3: The Hybrid Engine (Storage)
    print("\n--- PHASE 3: STORAGE ---")
    process_storage_batch(clean_articles)
    
    print(f"\n✅ PIPELINE COMPLETE FOR {company_name}.\n")

if __name__ == "__main__":
    # We loop through our primary competitors
    competitors_to_track = ["Firebase", "Appwrite"]
    
    for competitor in competitors_to_track:
        run_full_pipeline(competitor)