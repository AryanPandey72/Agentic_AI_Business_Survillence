# agents/email_agent.py
import os
import sqlite3
from datetime import datetime
from google import genai
from qdrant_client import QdrantClient
from fastembed import TextEmbedding
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

load_dotenv()

# ==========================================
# 1. DATABASE RETRIEVAL (THE TRIGGERS)
# ==========================================
def get_todays_hr_roles(vendor: str, db_path: str) -> list:
    """Fetches any new jobs posted today for the given vendor."""
    current_date = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT title, department, location 
        FROM hiring_records 
        WHERE vendor COLLATE NOCASE = ? AND extraction_date = ?
    ''', (vendor, current_date))
    
    jobs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jobs

# ==========================================
# 2. VECTOR SEARCH (THE CONTEXT)
# ==========================================
def fetch_corroborating_news(vendor: str, search_query: str) -> str:
    """Queries Qdrant for recent news related to the trigger event."""
    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")
    
    if not qdrant_url or not qdrant_api_key:
        return "News database connection unavailable."

    client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
    embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    
    try:
        # Convert the search query into a vector
        query_vector = list(embedding_model.embed([search_query]))[0]
        
        # Search Qdrant for the top 3 most relevant context chunks
        search_result = client.search(
            collection_name="competitor_news",
            query_vector=query_vector,
            limit=3
        )
        
        context = "\n".join([f"- {hit.payload.get('text', '')}" for hit in search_result if hit.payload.get('company', '').lower() == vendor.lower()])
        return context if context else "No relevant news found to corroborate this event."
    except Exception as e:
        return f"Error retrieving news: {e}"

# ==========================================
# 3. LLM SYNTHESIS (THE ANALYST)
# ==========================================
def generate_executive_summary(vendor: str, pricing_changes: list, new_jobs: list) -> str:
    """Forces the LLM to cross-reference hard data with market news."""
    api_key = os.getenv("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)
    
    # Build the contextual query based on what we found
    news_query = f"{vendor} strategy updates"
    if pricing_changes:
        news_query += " pricing plans limits"
    if new_jobs:
        departments = " ".join([j['department'] for j in new_jobs])
        news_query += f" hiring expansion {departments}"
        
    recent_news = fetch_corroborating_news(vendor, news_query)
    
    prompt = f"""
    You are a Senior Threat Intelligence Analyst reporting to the executive team.
    Analyze the following surveillance data for {vendor}. 
    
    CRITICAL INSTRUCTIONS:
    1. If Pricing changed, explicitly state the change AND check the 'Recent News' section to see if there is PR or a blog post explaining why.
    2. If there are New Jobs, check the 'Recent News' to see if it aligns with a newly announced feature or strategic pivot.
    3. If the News mentions a pricing change but the 'Pricing Changes' data is empty, explicitly state: "News indicates a pricing change, but our live scraper has not detected it on their website yet."
    4. Keep the tone clinical, sharp, and highly actionable. Format as an email body.

    === DATA FOR {vendor} ===
    Detected Pricing Changes: {pricing_changes if pricing_changes else 'None detected today.'}
    New Core Jobs Posted: {new_jobs if new_jobs else 'None detected today.'}
    Recent News Context (RAG): {recent_news}
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={'temperature': 0.2} # Keep it mostly deterministic, but allow some narrative flow
        )
        return response.text
    except Exception as e:
        return f"Failed to generate summary: {e}"

# ==========================================
# 4. DELIVERY ENGINE
# ==========================================
def send_email_alert(vendor: str, email_body: str):
    """Fires off the synthesized intelligence via standard SMTP."""
    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_PASSWORD")
    recipient_email = os.getenv("RECIPIENT_EMAIL")
    
    if not sender_email or not sender_password or not recipient_email:
        print("\n" + "="*50)
        print(f"📧 MOCK EMAIL DISPATCH FOR {vendor.upper()}")
        print("="*50)
        print(email_body)
        print("="*50 + "\n")
        return

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = f"🚨 SURVEILLANCE ALERT: Strategic Pivot Detected for {vendor}"
    msg.attach(MIMEText(email_body, 'html' if '<' in email_body else 'plain'))

    try:
        # Defaults to standard Gmail SMTP. Update if using SendGrid/Resend
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        print(f"✅ Intelligence brief emailed successfully for {vendor}.")
    except Exception as e:
        print(f"Failed to send email: {e}")

# ==========================================
# MAIN ORCHESTRATOR
# ==========================================
if __name__ == "__main__":
    print("Initiating Intelligence Synthesis Engine...\n")
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'competitor_intelligence.db')
    
    # For testing, we simulate passing in a detected pricing change from main.py
    mock_pricing_changes = [
        "Increased Document Reads on Free Tier from 50,000 to 100,000",
        "Added new 'Enterprise Connect' tier at $999/mo"
    ]
    
    vendor = "Firebase"
    new_hr_roles = get_todays_hr_roles(vendor, db_path)
    
    email_content = generate_executive_summary(vendor, mock_pricing_changes, new_hr_roles)
    send_email_alert(vendor, email_content)