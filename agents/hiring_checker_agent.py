# agents/hiring_checker_agent.py
import os
import json
from pydantic import BaseModel, Field
from google import genai
from dotenv import load_dotenv

load_dotenv()

# ==========================================
# 1. DEFINE THE STRICT SCHEMA
# ==========================================
class JobRecord(BaseModel):
    vendor: str = Field(description="The company name, e.g., Firebase, Appwrite")
    department: str = Field(description="e.g., Engineering, Sales, Marketing, Product. Infer if not explicitly stated.")
    title: str = Field(description="The exact job title, e.g., Senior Go Backend Engineer")
    location: str = Field(description="e.g., Remote, San Francisco, Berlin, or 'Multiple Locations'")
    employment_type: str = Field(description="e.g., Full-time, Contract, Intern. Default to 'Full-time' if missing.")

class JobBoardData(BaseModel):
    records: list[JobRecord]

# ==========================================
# 2. THE EXTRACTION ENGINE
# ==========================================
def parse_careers_page(raw_markdown: str, vendor_name: str) -> list[dict]:
    """
    Forces Gemini to read the raw scraped job board markdown and output strict, 
    atomic JSON job records.
    """
    print(f"Extracting active job listings for {vendor_name}...")
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not found in .env")
        return []

    client = genai.Client(api_key=api_key)
    
    prompt = f"""
    You are a precise HR data extraction tool. Analyze the following raw careers page markdown for {vendor_name}.
    Extract open job positions into a distinct record, but YOU MUST FILTER THE DATA first.
    
    CRITICAL RULES:
    1. STRICT INCLUSION: Only extract roles that are actively building or working directly for the core {vendor_name} platform/team. 
    2. STRICT EXCLUSION: If a job belongs to a different department or product (e.g., Google Search, Ads, Payments, Hardware) and merely lists {vendor_name} as a required skill or tool, YOU MUST IGNORE IT.
    3. Ignore generic text like "Benefits", "Our Culture", or "Join our Talent Network".
    4. If a department is not explicitly listed, make a highly confident inference based on the title (e.g., 'React Developer' -> 'Engineering').
    
    Raw Markdown:
    {raw_markdown}
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={
                'response_mime_type': 'application/json',
                'response_schema': JobBoardData,
                'temperature': 0.0 # Force deterministic extraction
            },
        )
        
        structured_data = response.parsed
        
        records = []
        for record in structured_data.records:
            records.append(record.model_dump())
            
        print(f"Successfully extracted {len(records)} job listings.")
        return records
        
    except Exception as e:
        print(f"HR Extraction Error for {vendor_name}: {e}")
        return []