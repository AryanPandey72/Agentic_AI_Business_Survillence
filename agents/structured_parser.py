# agents/structured_parser.py
import os
import json
from pydantic import BaseModel, Field
from google import genai
from dotenv import load_dotenv

load_dotenv()

# ==========================================
# 1. ENTITY RESOLUTION (ALIAS MAPPING)
# ==========================================
# We normalize marketing terms into standard internal names before saving to the database.
# This prevents the system from breaking if a company renames a pricing tier.
PLAN_ALIASES = {
    "firebase": {
        "spark": "free_tier",
        "spark plan": "free_tier",
        "free": "free_tier",
        "hobby": "free_tier",
        "blaze": "pay_as_you_go",
        "blaze plan": "pay_as_you_go",
        "pay to go": "pay_as_you_go"
    },
    "appwrite": {
        "starter": "free_tier",
        "free": "free_tier",
        "pro": "pro_tier",
        "scale": "scale_tier",
        "enterprise": "enterprise_tier"
    }
}

def normalize_plan_name(vendor: str, raw_plan: str) -> str:
    """Converts extracted marketing plan names to standard internal IDs."""
    vendor_lower = vendor.lower()
    plan_lower = raw_plan.lower().strip()
    
    if vendor_lower in PLAN_ALIASES:
        # Check if the extracted plan matches any known alias
        for alias, standard_name in PLAN_ALIASES[vendor_lower].items():
            if alias in plan_lower:
                return standard_name
                
    # Fallback: If no alias matches, return a clean version of whatever the LLM found
    return plan_lower.replace(" ", "_")

# ==========================================
# 2. DEFINE THE STRICT SCHEMA
# ==========================================
class PricingRecord(BaseModel):
    vendor: str = Field(description="The company name, e.g., Firebase, Appwrite")
    product: str = Field(description="The specific product, e.g., Cloud Firestore")
    plan: str = Field(description="The pricing tier, e.g., Spark, Blaze")
    billing_cycle: str = Field(description="Strictly 'monthly', 'annually', or 'N/A' if it's a usage limit, not a price.")
    metric: str = Field(description="What is being measured, e.g., document_reads, base_price")
    value: str = Field(description="The numeric limit or cost, e.g., 50000, 10, 0.90")
    unit: str = Field(description="The unit of measurement, e.g., reads/day, GiB/month, USD")
    source_section: str = Field(description="The heading this was found under")

class PricingPageData(BaseModel):
    records: list[PricingRecord]

# ==========================================
# 3. THE EXTRACTION ENGINE
# ==========================================
def parse_pricing_page(raw_markdown: str, vendor_name: str) -> list[dict]:
    """
    Forces Gemini to read the raw scraped markdown and output strict, 
    atomic JSON records, and normalizes the tier names.
    """
    print(f"Extracting structured atomic records for {vendor_name}...")
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not found in .env")
        return []

    client = genai.Client(api_key=api_key)
    
    prompt = f"""
    You are a highly precise, deterministic data extraction tool. 
    Analyze the following raw pricing page markdown for {vendor_name}.
    Extract EVERY pricing limit, quota, free tier, and cost into distinct, atomic records.
    
    CRITICAL RULES:
    1. Do not mix products (e.g., keep Firestore reads completely separate from SQL Connect operations).
    2. Do not mix plans (e.g., keep Spark limits separate from Blaze limits).
    3. Do not infer or calculate new numbers. Extract exactly what is written.
    4. Ensure the 'value' field contains ONLY numbers if possible, moving words like 'per month' to the 'unit' field.
    5. If a feature is simply a checkmark, 'included', or boolean state, set the value strictly to '1' and the unit to 'included'.
    
    Raw Markdown:
    {raw_markdown}
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={
                'response_mime_type': 'application/json',
                'response_schema': PricingPageData,
                'temperature': 0.0 # Force deterministic extraction
            },
        )
        
        # The new SDK automatically parses the output into our Pydantic schema
        structured_data = response.parsed
        
        records = []
        for record in structured_data.records:
            record_dict = record.model_dump()
            
            # Intercept the record and normalize the plan name before it finishes
            record_dict["plan"] = normalize_plan_name(vendor_name, record_dict["plan"])
            records.append(record_dict)
        
        print(f"Successfully extracted and normalized {len(records)} atomic records.")
        return records
        
    except Exception as e:
        print(f"Extraction Error for {vendor_name}: {e}")
        return []

if __name__ == "__main__":
    import glob
    
    appwrite_files = glob.glob(os.path.join("data", "raw", "appwrite_pricing_*.md"))
    if appwrite_files:
        latest_file = max(appwrite_files, key=os.path.getctime)
        with open(latest_file, "r", encoding="utf-8") as f:
            real_markdown = f.read()
        
        result = parse_pricing_page(real_markdown, "Appwrite")
        
        # Save it to a file so we can actually look at the massive output
        os.makedirs(os.path.join("data", "structured"), exist_ok=True)
        save_path = os.path.join("data", "structured", "appwrite_parsed_test.json")
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
            
        print(f"Check {save_path} to see the full extraction!")
    else:
        print("No raw Appwrite markdown files found.")