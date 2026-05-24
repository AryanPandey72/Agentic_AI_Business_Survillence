# agents/news_trigger.py
import os
import requests
from datetime import datetime
from google import genai
from dotenv import load_dotenv

# Import your database engine and email agent
from database import engine
from sqlalchemy import text
from agents.email_agent import send_email_alert

load_dotenv()

STRATEGIC_TRIGGERS = {
    "Mergers & Acquisitions": ["acquires", "acquired", "merger", "buyout", "takeover", "consolidation"],
    "Partnerships & Integrations": ["partnership", "partners with", "joint venture", "integrates with", "strategic alliance"],
    "Financial & Funding": ["funding", "raised", "series a", "series b", "ipo", "goes public", "valuation"],
    "Leadership Changes": ["steps down", "appointed ceo", "new cto", "board of directors", "poaches"],
    "Product & Market Shifts": ["pivots", "spins off", "rebrands", "expands into", "enters market", "sunsets"],
    "Crisis & Operations": ["layoffs", "cuts jobs", "downsizes", "data breach", "hacked", "lawsuit", "fined"]
}

def fetch_recent_news(vendor: str) -> list:
    """Fetches recent news articles for the vendor using GNews API."""
    api_key = os.getenv("GNEWS_API_KEY")
    if not api_key:
        print("❌ GNews API Key missing.")
        return []
        
    url = f"https://gnews.io/api/v4/search?q={vendor}&lang=en&max=10&apikey={api_key}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return data.get("articles", [])
    except Exception as e:
        print(f"Failed to fetch news for {vendor}: {e}")
        return []

def scan_for_triggers(articles: list) -> list:
    """Scans articles against the strategic trigger matrix."""
    flagged_articles = []
    
    for article in articles:
        content_to_scan = f"{article['title']} {article['description']}".lower()
        
        for category, keywords in STRATEGIC_TRIGGERS.items():
            for keyword in keywords:
                if keyword in content_to_scan:
                    flagged_articles.append({
                        "title": article['title'],
                        "url": article['url'],
                        "category": category,
                        "trigger_word": keyword,
                        "description": article['description']
                    })
                    break # Stop scanning this article once a trigger is found
    
    return flagged_articles

def analyze_strategic_event(vendor: str, articles: list) -> str:
    """Uses Gemini to synthesize the raw flagged articles into a brief."""
    api_key = os.getenv("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)
    
    context = "\n".join([f"- [{a['category']}] {a['title']}: {a['description']} (URL: {a['url']})" for a in articles])
    
    prompt = f"""
    You are a Senior Threat Intelligence Analyst. 
    Review the following high-signal news events detected for {vendor} today.
    
    Provide a clinical, actionable executive summary formatted for an email. 
    State exactly what happened, the entities involved, and the potential strategic threat or opportunity this presents to our market position.
    
    === DETECTED EVENTS ===
    {context}
    """
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config={'temperature': 0.2}
    )
    return response.text

def run_news_pipeline(vendor: str):
    print(f"\n📡 Scanning strategic news radar for {vendor}...")
    
    articles = fetch_recent_news(vendor)
    if not articles:
        return
        
    flagged_events = scan_for_triggers(articles)
    
    if not flagged_events:
        print(f"✅ No high-level strategic events detected for {vendor} today.")
        return
        
    print(f"🚨 {len(flagged_events)} Strategic Event(s) Detected! Analyzing...")
    
    # 1. Generate Executive Summary
    brief = analyze_strategic_event(vendor, flagged_events)
    
    # 2. Fire the Email Alert
    send_email_alert(vendor, brief)
    
    # 3. Log to Database
    current_date = datetime.now().strftime("%Y-%m-%d")
    try:
        with engine.connect() as conn:
            stmt = text('''
                INSERT INTO strategic_events (extraction_date, vendor, category, title, url)
                VALUES (:date, :vendor, :category, :title, :url)
            ''')
            
            data = [
                {"date": current_date, "vendor": vendor, "category": a["category"], "title": a["title"], "url": a["url"]}
                for a in flagged_events
            ]
            
            conn.execute(stmt, data)
            conn.commit()
            print("💾 Strategic events logged to cloud database.")
    except Exception as e:
        print(f"Database Error: {e}")

if __name__ == "__main__":
    # Test the pipeline
    run_news_pipeline("Appwrite")
    run_news_pipeline("Firebase")