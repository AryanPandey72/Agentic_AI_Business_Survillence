# agents/news_ingestion.py
import os
import feedparser
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Centralized configuration for the competitors you are tracking
COMPETITOR_FEEDS = {
    "Firebase": [
        "https://firebase.blog/rss.xml", 
        "https://github.com/firebase/firebase-ios-sdk/releases.atom"
    ],
    "Supabase": [
        "https://supabase.com/rss.xml", 
        "https://github.com/supabase/supabase/releases.atom"
    ],
    "Appwrite": [
        "https://appwrite.io/blog/rss.xml", 
        "https://github.com/appwrite/appwrite/releases.atom"
    ]
}

def fetch_official_rss(company_name: str, feed_urls: list) -> list[dict]:
    """Pulls high-signal, first-party updates from official engineering blogs and GitHub."""
    print(f"Fetching official RSS feeds for {company_name}...")
    articles = []
    
    for url in feed_urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:10]: # Limit to 10 most recent per feed to avoid overload
                
                # Handle varying RSS formats for content
                content = ""
                if hasattr(entry, 'content'):
                    content = entry.content[0].value
                elif hasattr(entry, 'summary'):
                    content = entry.summary
                
                articles.append({
                    "company": company_name,
                    "source_type": "official_rss",
                    "title": entry.get("title", "No Title"),
                    "url": entry.get("link", url),
                    "published_date": entry.get("published", datetime.now().isoformat()),
                    "raw_content": content
                })
        except Exception as e:
            print(f"Error parsing RSS {url}: {e}")
            
    return articles

def fetch_gnews_fallback(company_name: str) -> list[dict]:
    """Acts as the secondary net to catch external market events (acquisitions, outages)."""
    print(f"Fetching GNews market data for {company_name}...")
    api_key = os.getenv("GNEWS_API_KEY")
    if not api_key:
        print("Warning: GNEWS_API_KEY not found. Skipping external news fetch.")
        return []

    articles = []
    # Querying the competitor name, limiting to recent tech news
    url = f"https://gnews.io/api/v4/search?q={company_name}&lang=en&max=5&apikey={api_key}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        for item in data.get("articles", []):
            articles.append({
                "company": company_name,
                "source_type": "external_news",
                "title": item.get("title"),
                "url": item.get("url"),
                "published_date": item.get("publishedAt"),
                "raw_content": item.get("content") # GNews provides snippets; full text requires scraping later if needed
            })
    except requests.exceptions.RequestException as e:
        print(f"Error fetching from GNews API: {e}")
        
    return articles

def run_firehose(company_name: str) -> list[dict]:
    """Orchestrates the ingestion layer and returns a unified list of raw articles."""
    all_articles = []
    
    feed_urls = COMPETITOR_FEEDS.get(company_name)
    if feed_urls:
        all_articles.extend(fetch_official_rss(company_name, feed_urls))
        
    all_articles.extend(fetch_gnews_fallback(company_name))
    
    print(f"Total raw articles ingested for {company_name}: {len(all_articles)}")
    return all_articles

if __name__ == "__main__":
    # Quick test to verify the ingestion layer
    raw_data = run_firehose("Supabase")
    
    if raw_data:
        print("\nSample Output (First Record):")
        sample = raw_data[0]
        print(f"Title: {sample['title']}")
        print(f"URL: {sample['url']}")
        print(f"Source: {sample['source_type']}")
        print(f"Content Length: {len(sample['raw_content'])} characters")