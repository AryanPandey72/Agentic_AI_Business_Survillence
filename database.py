import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from datetime import datetime
from typing import List, Dict

load_dotenv()

# Attempt to load from Streamlit secrets, fallback to environment variable
try:
    import streamlit as st
    DATABASE_URL = st.secrets.get("DATABASE_URL")
except ImportError:
    DATABASE_URL = None

# If not found in Streamlit secrets, try environment variable
if not DATABASE_URL:
    DATABASE_URL = os.getenv("DATABASE_URL")

# Raise a clear error if neither source provides the URL
if not DATABASE_URL:
    raise ValueError("❌ DATABASE_URL is not set! Please check your Streamlit Cloud Secrets or .env file.")

# Create the engine
engine = create_engine(DATABASE_URL)

def init_db():
    """Ensures tables exist."""
    with engine.connect() as conn:
        # Pricing Table
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS pricing_records (
                id SERIAL PRIMARY KEY,
                extraction_date TEXT NOT NULL,
                vendor TEXT NOT NULL,
                product TEXT NOT NULL,
                plan TEXT NOT NULL,
                billing_cycle TEXT NOT NULL,
                metric TEXT NOT NULL,
                value TEXT NOT NULL,
                unit TEXT NOT NULL,
                source_section TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        '''))
        
        # Hiring Table
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS hiring_records (
                id SERIAL PRIMARY KEY,
                extraction_date TEXT NOT NULL,
                vendor TEXT NOT NULL,
                department TEXT NOT NULL,
                title TEXT NOT NULL,
                location TEXT NOT NULL,
                employment_type TEXT NOT NULL,
                status TEXT DEFAULT 'Open',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        '''))

        # Strategic Events Table (NEW)
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS strategic_events (
                id SERIAL PRIMARY KEY,
                extraction_date TEXT NOT NULL,
                vendor TEXT NOT NULL,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        '''))
        conn.commit()

def insert_atomic_records(records: List[Dict], extraction_date: str = None) -> bool:
    """Inserts records using SQLAlchemy."""
    if not records:
        return False
        
    if not extraction_date:
        extraction_date = datetime.now().strftime('%Y-%m-%d')

    try:
        with engine.connect() as conn:
            data_to_insert = [
                {
                    "extraction_date": extraction_date,
                    "vendor": r.get('vendor'),
                    "product": r.get('product'),
                    "plan": r.get('plan'),
                    "billing_cycle": r.get('billing_cycle', 'N/A'),
                    "metric": r.get('metric'),
                    "value": r.get('value'),
                    "unit": r.get('unit'),
                    "source_section": r.get('source_section')
                }
                for r in records
            ]
            
            stmt = text('''
                INSERT INTO pricing_records 
                (extraction_date, vendor, product, plan, billing_cycle, metric, value, unit, source_section)
                VALUES (:extraction_date, :vendor, :product, :plan, :billing_cycle, :metric, :value, :unit, :source_section)
            ''')
            
            conn.execute(stmt, data_to_insert)
            conn.commit()
            
        print(f"Cloud DB: Inserted {len(records)} records for {records[0].get('vendor')}")
        return True
        
    except Exception as e:
        print(f"Database Error: {e}")
        return False

def get_records_for_date(vendor: str, extraction_date: str) -> List[Dict]:
    """Retrieves records using SQLAlchemy."""
    with engine.connect() as conn:
        stmt = text('''
            SELECT * FROM pricing_records 
            WHERE vendor ILIKE :vendor AND extraction_date = :date
        ''')
        result = conn.execute(stmt, {"vendor": vendor, "date": extraction_date})
        return [dict(row._mapping) for row in result]

def get_latest_two_dates(vendor: str) -> List[str]:
    """Finds the two most recent dates."""
    with engine.connect() as conn:
        stmt = text('''
            SELECT DISTINCT extraction_date 
            FROM pricing_records 
            WHERE vendor ILIKE :vendor 
            ORDER BY extraction_date DESC 
            LIMIT 2
        ''')
        result = conn.execute(stmt, {"vendor": vendor})
        return [row[0] for row in result]