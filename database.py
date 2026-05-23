# database.py
import sqlite3
import os
from datetime import datetime
from typing import List, Dict

# Force an absolute path so Python never gets confused about the file location
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'competitor_intelligence.db')

def init_db():
    """Ultimate failsafe: Creates the atomic schemas if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Existing Pricing Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pricing_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_lookup ON pricing_records(vendor, extraction_date)')
    
    # 2. NEW Hiring Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS hiring_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            extraction_date TEXT NOT NULL,
            vendor TEXT NOT NULL,
            department TEXT NOT NULL,
            title TEXT NOT NULL,
            location TEXT NOT NULL,
            employment_type TEXT NOT NULL,
            status TEXT DEFAULT 'Open',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_hiring_lookup ON hiring_records(vendor, extraction_date)')
    
    conn.commit()
    conn.close()
def insert_atomic_records(records: List[Dict], extraction_date: str = None) -> bool:
    """Inserts a list of flat, atomic pricing records into the database."""
    if not records:
        return False
        
    if not extraction_date:
        extraction_date = datetime.now().strftime('%Y-%m-%d')

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        rows_to_insert = [
            (
                extraction_date,
                r.get('vendor'),
                r.get('product'),
                r.get('plan'),
                r.get('billing_cycle', 'N/A'),
                r.get('metric'),
                r.get('value'),
                r.get('unit'),
                r.get('source_section')
            )
            for r in records
        ]
        
        cursor.executemany('''
            INSERT INTO pricing_records 
            (extraction_date, vendor, product, plan, billing_cycle, metric, value, unit, source_section)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', rows_to_insert)
        
        conn.commit()
        conn.close()
        
        vendor_name = records[0].get('vendor') if records else 'Unknown'
        print(f"Database: Inserted {len(records)} atomic records for {vendor_name} ({extraction_date})")
        return True
        
    except Exception as e:
        print(f"Database Error: Failed bulk insert. {e}")
        return False

def get_records_for_date(vendor: str, extraction_date: str) -> List[Dict]:
    """Retrieves all atomic records for a specific vendor on a specific date."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row 
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM pricing_records 
        WHERE vendor COLLATE NOCASE = ? AND extraction_date = ?
    ''', (vendor, extraction_date))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

def get_latest_two_dates(vendor: str) -> List[str]:
    """Finds the two most recent dates we have data for."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT DISTINCT extraction_date 
        FROM pricing_records 
        WHERE vendor COLLATE NOCASE = ? 
        ORDER BY extraction_date DESC 
        LIMIT 2
    ''', (vendor,))
    
    dates = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    return dates