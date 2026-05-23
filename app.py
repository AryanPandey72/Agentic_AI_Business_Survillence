import streamlit as st
import pandas as pd
import plotly.express as px
from database import engine

# Page configuration
st.set_page_config(page_title="Competitor Intel Dashboard", layout="wide")

st.title("🚀 Competitor Intelligence Command Center")

# Use caching to prevent excessive database hits
@st.cache_data(ttl=600)  # Caches data for 10 minutes
def fetch_data(query):
    return pd.read_sql(query, engine)

# Sidebar Navigation
page = st.sidebar.selectbox("Select Intelligence Module", ["Pricing Trends", "HR Expansion Tracker"])

# --- Pricing Module ---
if page == "Pricing Trends":
    st.header("📊 Pricing & Quota Analysis")
    df = fetch_data("SELECT * FROM pricing_records")
    
    if not df.empty:
        vendor = st.selectbox("Select Vendor", df['vendor'].unique())
        filtered_df = df[df['vendor'] == vendor]
        
        # Trend Chart
        st.subheader(f"Pricing History for {vendor}")
        fig = px.line(filtered_df, x="extraction_date", y="value", color="metric", 
                      title=f"Evolution of Limits/Pricing ({vendor})", markers=True)
        st.plotly_chart(fig, use_container_width=True)
        
        st.dataframe(filtered_df.sort_values(by="extraction_date", ascending=False))
    else:
        st.info("No pricing data found in the cloud yet.")

# --- HR Module ---
elif page == "HR Expansion Tracker":
    st.header("👥 Hiring Velocity Tracker")
    df = fetch_data("SELECT * FROM hiring_records")
    
    if not df.empty:
        # Metrics Row
        col1, col2 = st.columns(2)
        col1.metric("Total Open Roles", len(df))
        col2.metric("Companies Tracked", df['vendor'].nunique())
        
        # Hiring Bar Chart
        st.subheader("Hiring Volume by Vendor")
        hiring_counts = df.groupby('vendor').size().reset_index(name='count')
        fig = px.bar(hiring_counts, x='vendor', y='count', color='vendor', title="Total Open Roles per Competitor")
        st.plotly_chart(fig, use_container_width=True)
        
        # Job Details Table
        st.subheader("Recent Job Postings")
        st.dataframe(df.sort_values(by="extraction_date", ascending=False))
    else:
        st.info("No hiring data found in the cloud yet.")