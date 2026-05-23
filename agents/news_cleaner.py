# agents/news_sanitizer.py
import urllib.parse
import hashlib
from bs4 import BeautifulSoup
from dateutil import parser
from datetime import datetime

def clean_url(raw_url: str) -> str:
    """
    Strips UTM parameters, tracking codes, and trailing slashes to create a canonical URL.
    This is critical to prevent the exact same article from being embedded twice.
    """
    if not raw_url:
        return ""
        
    parsed = urllib.parse.urlparse(raw_url)
    
    # Keep only specific query parameters if needed, but usually we drop them all for news
    clean_query = urllib.parse.urlencode({
        k: v for k, v in urllib.parse.parse_qsl(parsed.query) 
        if not k.startswith('utm_') and k not in ['ref', 'source']
    })
    
    # Rebuild the URL without the junk
    canonical = urllib.parse.urlunparse(
        (parsed.scheme, parsed.netloc.lower(), parsed.path.rstrip('/'), parsed.params, clean_query, '')
    )
    
    return canonical

def generate_article_id(canonical_url: str) -> str:
    """Creates a deterministic SHA-256 hash from the clean URL to act as the primary key."""
    return hashlib.sha256(canonical_url.encode('utf-8')).hexdigest()

def strip_html(raw_content: str) -> str:
    """Surgically extracts human-readable text from HTML payloads."""
    if not raw_content:
        return ""
        
    # BeautifulSoup parses the HTML tree and get_text() extracts only the visible text
    soup = BeautifulSoup(raw_content, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    
    return text

def normalize_date(date_str: str) -> str:
    """Converts chaotic RSS/API date formats into strict ISO 8601 strings."""
    if not date_str:
        return datetime.now().isoformat()
        
    try:
        parsed_date = parser.parse(date_str)
        return parsed_date.isoformat()
    except (ValueError, TypeError):
        # Fallback to current time if parsing completely fails
        return datetime.now().isoformat()

def sanitize_article(raw_article: dict) -> dict | None:
    """
    The master function that takes a raw article from Phase 1 and returns a clean, 
    database-ready record. Returns None if the article is too short/useless.
    """
    canonical_url = clean_url(raw_article.get("url", ""))
    
    # 1. Generate the immutable Primary Key
    article_id = generate_article_id(canonical_url)
    
    # 2. Clean the text payload
    clean_text = strip_html(raw_article.get("raw_content", ""))
    clean_title = strip_html(raw_article.get("title", ""))
    
    # The Minimum Viable Signal Check:
    # If the extracted text is less than 100 characters, it's likely a broken link or a useless stub.
    # We drop it entirely to save database space.
    if len(clean_text) < 100:
        return None
        
    # 3. Standardize the temporal data
    iso_date = normalize_date(raw_article.get("published_date", ""))
    
    # 4. Construct the final Payload
    return {
        "article_id": article_id,
        "company": raw_article.get("company"),
        "source_type": raw_article.get("source_type"),
        "published_date": iso_date,
        "url": canonical_url,
        "title": clean_title,
        "content": clean_text
    }

def process_firehose_batch(raw_articles: list[dict]) -> list[dict]:
    """Processes an entire batch of raw articles and returns only the clean, valid ones."""
    print(f"Sanitizing batch of {len(raw_articles)} raw articles...")
    clean_batch = []
    
    for raw in raw_articles:
        clean = sanitize_article(raw)
        if clean:
            clean_batch.append(clean)
            
    print(f"Yielded {len(clean_batch)} clean, database-ready articles.")
    return clean_batch