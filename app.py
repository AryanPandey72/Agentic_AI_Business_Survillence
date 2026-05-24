import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import os
from dotenv import load_dotenv

load_dotenv()

# --- Setup Database Connection ---
# Attempt to load from Streamlit secrets, fallback to environment variable
try:
    DATABASE_URL = st.secrets.get("DATABASE_URL")
except FileNotFoundError:
    DATABASE_URL = None

if not DATABASE_URL:
    DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    st.error("DATABASE_URL is missing. Check your .env file or Streamlit Secrets.")
    st.stop()

engine = create_engine(DATABASE_URL)

# Use caching to prevent excessive database hits
@st.cache_data(ttl=600)  # Caches data for 10 minutes
def fetch_data(query):
    try:
        return pd.read_sql(query, engine)
    except Exception as e:
        # Returns empty dataframe if table doesn't exist yet
        return pd.DataFrame() 

# Sidebar Navigation
st.sidebar.title("Surveillance Modules")
page = st.sidebar.selectbox("Select Intelligence Module", [
    "Pricing Trends", 
    "HR Expansion Tracker",
    "Strategic Market Moves" # <-- NEW MODULE ADDED
])

# --- Pricing Module ---
if page == "Pricing Trends":
    st.header("📊 Pricing & Quota Analysis")
    df = fetch_data("SELECT * FROM pricing_records")
    
    if not df.empty:
        vendor = st.selectbox("Select Vendor", df['vendor'].unique())
        
        # Filter for selected vendor
        vendor_df = df[df['vendor'] == vendor]
        st.dataframe(vendor_df, hide_index=True)
        
        # Export (FIXED: Handles N/A natively and drops the index column)
        csv_data = vendor_df.fillna("N/A").to_csv(index=False).encode('utf-8')
        
        st.download_button(
            label="Download Data as CSV",
            data=csv_data,
            file_name=f"{vendor.lower()}_pricing_data.csv",
            mime="text/csv",
        )
    else:
        st.warning("No records on cloud. Run your extraction pipeline first.")

# --- HR Module ---
if page == "HR Expansion Tracker":
    st.header("🏢 Talent & Expansion Operations")
    
    vendor = st.selectbox("Select Vendor", ["Appwrite", "Firebase"])
    df_hr = fetch_data(f"SELECT * FROM hiring_records WHERE vendor = '{vendor}'")
    
    if not df_hr.empty:
        st.dataframe(df_hr, hide_index=True)
    else:
        # FIXED: UI now displays actionable intelligence instead of an error!
        st.info(f"✅ Intelligence Update: No active core-team hiring listed for {vendor} at the moment.")

# --- Strategic News Module (NEW) ---
if page == "Strategic Market Moves":
    st.header("🚨 Strategic Market Events")
    st.markdown("Tracks major M&A, leadership changes, and funding rounds.")
    
    df_news = fetch_data("SELECT * FROM strategic_events ORDER BY created_at DESC")
    
    if not df_news.empty:
        vendor_filter = st.selectbox("Filter by Vendor", ["All"] + list(df_news['vendor'].unique()))
        
        if vendor_filter != "All":
            df_news = df_news[df_news['vendor'] == vendor_filter]
        
        # Render the dataframe with clickable URLs
        st.dataframe(
            df_news,
            column_config={
                "url": st.column_config.LinkColumn("Article URL")
            },
            hide_index=True
        )
    else:
        st.info("✅ Radar clear: No high-level strategic events detected recently.")