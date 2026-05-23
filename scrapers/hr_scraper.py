# scrapers/hr_scraper.py
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from firecrawl import FirecrawlApp
from config import COMPETITORS

def scrape_and_save_jobs(company_name: str, careers_url: str) -> bool:
    """
    Scrapes the careers page of a competitor and saves it as raw Markdown.
    """
    print(f"Scraping active jobs for {company_name} at {careers_url}...")
    
    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key:
        print("Error: FIRECRAWL_API_KEY not found in .env")
        return False

    app = FirecrawlApp(api_key=api_key)
    current_date = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    
    try:
        # 🔴 THE FIX: v2 SDK uses .scrape() instead of .scrape_url()
        result = app.scrape(careers_url, formats=['markdown'])
        
        # 🔴 THE FIX: Handle the new v2 response object structure
        if isinstance(result, dict):
            markdown_content = result.get('markdown', '')
        else:
            markdown_content = getattr(result, 'markdown', '')
            
        if not markdown_content:
            print(f"Warning: No markdown content returned for {company_name} jobs.")
            return False

        # Ensure the raw directory exists
        os.makedirs(os.path.join("data", "raw"), exist_ok=True)
        
        filename = f"{company_name}_jobs_{current_date}.md"
        filepath = os.path.join("data", "raw", filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(markdown_content)
            
        print(f"✅ Successfully saved {company_name} job data to {filepath}")
        return True
        
    except Exception as e:
        print(f"Failed to scrape {company_name} jobs: {e}")
        return False

if __name__ == "__main__":
    # Quick test to ensure the scraper works before hooking it into the orchestrator
    print("Testing HR Scraper...\n")
    for company, urls in COMPETITORS.items():
        careers_url = urls.get("careers_url")
        if careers_url:
            scrape_and_save_jobs(company.capitalize(), careers_url)
        else:
            print(f"No careers URL found for {company}. Skipping.")