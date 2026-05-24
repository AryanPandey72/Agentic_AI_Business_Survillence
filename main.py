# main.py
import os
import glob
from datetime import datetime
from sqlalchemy import text # Importing text for safe SQL queries
from config import COMPETITORS
from agents.news_trigger import run_news_pipeline
from database import engine, init_db, insert_atomic_records, get_latest_two_dates, get_records_for_date

# Pricing Pipeline Imports
from scrapers.pricing_scraper import scrape_and_save_pricing
from agents.structured_parser import parse_pricing_page
from agents.email_agent import get_todays_hr_roles, generate_executive_summary, send_email_alert
from agents.verification_engine import values_are_mathematically_equal

# HR Pipeline Imports
from scrapers.hr_scraper import scrape_and_save_jobs
from agents.hiring_checker_agent import parse_careers_page

def detect_changes(vendor_name: str, old_records: list, new_records: list):
    """Deterministically compares previous database state to today's scraped state."""
    print(f"\n--- Running Deterministic Diff for {vendor_name} ---")
    changes_found = False

    old_lookup = {
        (r['product'].lower(), r['plan'].lower(), r['billing_cycle'].lower(), r['metric'].lower()): r
        for r in old_records
    }

    for new_rec in new_records:
        key = (new_rec['product'].lower(), new_rec['plan'].lower(), new_rec['billing_cycle'].lower(), new_rec['metric'].lower())
        old_rec = old_lookup.get(key)

        if not old_rec:
            print(f"➕ NEW LIMIT ADDED: [{new_rec['plan']}] {new_rec['product']} -> {new_rec['metric']} = {new_rec['value']} {new_rec['unit']}")
            changes_found = True
            
        elif str(new_rec['value']) != str(old_rec['value']):
            is_math_equal = values_are_mathematically_equal(str(new_rec['value']), str(old_rec['value']))
            
            if not is_math_equal:
                print(f"🚨 STRATEGIC PIVOT: [{new_rec['plan']}] {new_rec['product']} -> {new_rec['metric']} changed!")
                print(f"   Old: {old_rec['value']} {old_rec['unit']}")
                print(f"   New: {new_rec['value']} {new_rec['unit']}")
                changes_found = True

    if not changes_found:
        print("✅ No strategic pricing or limit changes detected.")
    print("---------------------------------------------------\n")

def run_pipeline():
    print("🚀 Starting Competitive Intelligence Pipeline (Pricing)...\n")
    current_run_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    
    for company_key, urls in COMPETITORS.items():
        company_name = company_key.capitalize()
        print(f"=== Processing PRICING for {company_name.upper()} ===")
        pricing_url = urls.get("pricing_url")
        
        if not pricing_url:
            continue
            
        success = scrape_and_save_pricing(company_name, pricing_url)
        if not success:
            continue
            
        raw_files = glob.glob(os.path.join("data", "raw", f"{company_name}_pricing_*.md"))
        if not raw_files:
            continue
            
        latest_raw_file = max(raw_files, key=os.path.getctime)
        with open(latest_raw_file, "r", encoding="utf-8") as f:
            raw_markdown = f.read()
            
        new_records = parse_pricing_page(raw_markdown, company_name)
        
        if not new_records:
            continue

        latest_dates = get_latest_two_dates(company_name)
        
        if latest_dates:
            baseline_date = latest_dates[0] 
            old_records = get_records_for_date(company_name, baseline_date)
            detect_changes(company_name, old_records, new_records)
        else:
            print(f"\n📊 Establishing initial database baseline for {company_name}.\n")

        insert_atomic_records(new_records, current_run_id)
        print(f"=== Finished PRICING for {company_name.upper()} ===\n")

def run_hr_pipeline():
    print("\n🚀 Starting HR Intelligence Pipeline...\n")
    current_run_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    
    for company_key, urls in COMPETITORS.items():
        company_name = company_key.capitalize()
        print(f"=== Processing HR for {company_name.upper()} ===")
        careers_url = urls.get("careers_url")
        
        if not careers_url:
            continue
            
        success = scrape_and_save_jobs(company_name, careers_url)
        if not success:
            continue
            
        raw_files = glob.glob(os.path.join("data", "raw", f"{company_name}_jobs_*.md"))
        if not raw_files:
            continue
            
        latest_raw_file = max(raw_files, key=os.path.getctime)
        with open(latest_raw_file, "r", encoding="utf-8") as f:
            raw_markdown = f.read()
            
        new_jobs = parse_careers_page(raw_markdown, company_name)
        
        if not new_jobs:
            print(f"No active core-team jobs found for {company_name}.")
            continue

        # Use SQLAlchemy engine for cloud insertion
        try:
            with engine.connect() as conn:
                stmt = text('''
                    INSERT INTO hiring_records 
                    (extraction_date, vendor, department, title, location, employment_type, status)
                    VALUES (:date, :vendor, :dept, :title, :loc, :emp_type, 'Open')
                ''')
                
                # Prepare data for insertion
                data = [
                    {
                        "date": current_run_id,
                        "vendor": j.get('vendor'),
                        "dept": j.get('department'),
                        "title": j.get('title'),
                        "loc": j.get('location'),
                        "emp_type": j.get('employment_type')
                    }
                    for j in new_jobs
                ]
                
                conn.execute(stmt, data)
                conn.commit()
            print(f"Cloud DB: Inserted {len(new_jobs)} active job records for {company_name}")
        except Exception as e:
            print(f"Database Error on HR insert: {e}")
            
        print(f"=== Finished HR for {company_name.upper()} ===\n")

if __name__ == "__main__":
    init_db()
    
    # 1. Run Pricing Scraper
    run_pipeline()
    
    # 2. Run HR Scraper
    run_hr_pipeline()

    # 3. Run Strategic News Radar (NEW)
    print("\n🚀 Initiating Strategic News Radar...\n")
    for company_key in COMPETITORS.keys():
        company_name = company_key.capitalize()
        run_news_pipeline(company_name)

    print("\n🚀 Initiating Final Intelligence Synthesis...\n")
    
    vendor_to_track = "Firebase" 
    new_hr_roles = get_todays_hr_roles(vendor_to_track)
    
    if new_hr_roles:
        email_content = generate_executive_summary(vendor_to_track, [], new_hr_roles)
        send_email_alert(vendor_to_track, email_content)
    else:
        print(f"No actionable intelligence found today for {vendor_to_track}.")