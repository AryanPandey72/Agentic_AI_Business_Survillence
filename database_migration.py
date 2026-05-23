# database_migration.py
import os
import sqlite3
import shutil

OLD_DB = 'competitor_intelligence.db'
LEGACY_DB = 'competitor_intelligence_legacy.db'

def migrate_database():
    print("Starting Database Migration...")

    # 1. Safely Backup the Old Database
    if os.path.exists(OLD_DB):
        shutil.copy(OLD_DB, LEGACY_DB)
        os.remove(OLD_DB)
        print(f"✅ Backed up old database to {LEGACY_DB} and cleared the slate.")
    else:
        print("No existing database found. Skipping backup.")

    # 2. Build the New Atomic Schema
    conn = sqlite3.connect(OLD_DB)
    cursor = conn.cursor()
    
    # Notice how this perfectly mirrors our Pydantic 'PricingRecord' class, 
    # plus an extraction_date to track history!
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
    
    # Create an index to make our historical lookups lightning fast
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_lookup ON pricing_records(vendor, extraction_date)')
    
    conn.commit()
    conn.close()
    
    print("✅ New atomic database schema created successfully: 'pricing_records' table.")

if __name__ == "__main__":
    migrate_database()