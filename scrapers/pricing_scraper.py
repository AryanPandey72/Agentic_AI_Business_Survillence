# scrapers/pricing_scraper.py
import os
from datetime import datetime
from firecrawl import Firecrawl
from dotenv import load_dotenv
import sys

# Add the parent directory to the system path so it can find config.py
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import COMPETITORS

# Load environment variables from .env
load_dotenv()

def scrape_and_save_pricing(company_name: str, url: str) -> bool:
    """Scrapes a pricing page and saves the raw Markdown locally."""
    
    api_key = os.getenv('FIRECRAWL_API_KEY')
    if not api_key:
        print("Error: FIRECRAWL_API_KEY not found in .env file.")
        return False
        
    # Use the new v2 Firecrawl class
    app = Firecrawl(api_key=api_key)
    print(f"Scraping pricing for {company_name} at {url}...")
    
    try:
        # Use the v2 scrape method and request markdown format
        scraped_data = app.scrape(url, formats=['markdown'])
        
        # In v2, the response is often a dictionary or object containing the markdown
        # If it's an object with a 'markdown' attribute, we can access it directly,
        # but safely using dict access or getattr is best depending on the SDK return type.
        if isinstance(scraped_data, dict):
            markdown_content = scraped_data.get('markdown', '')
        else:
            # If it returns a document object in the new SDK
            markdown_content = getattr(scraped_data, 'markdown', '')
            
        if not markdown_content:
            print(f"Failed to extract markdown for {company_name}")
            return False

        # Create the directory structure if it doesn't exist
        save_dir = os.path.join("data", "raw")
        os.makedirs(save_dir, exist_ok=True)
        
        # Create a timestamped filename
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{company_name}_pricing_{timestamp}.md"
        filepath = os.path.join(save_dir, filename)
        
        # Save the raw markdown file
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(markdown_content)
            
        print(f"Successfully saved {company_name} data to {filepath}")
        return True
        
    except Exception as e:
        print(f"Error scraping {company_name}: {e}")
        return False

if __name__ == "__main__":
    # Test the scraper by running it for Appwrite
    appwrite_url = COMPETITORS["appwrite"]["pricing_url"]
    scrape_and_save_pricing("appwrite", appwrite_url)