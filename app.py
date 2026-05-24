import streamlit as st
import pandas as pd
import plotly.express as px
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
    "Strategic Market Moves"
])

# --- Pricing Module ---
if page == "Pricing Trends":
    st.header("📊 Pricing & Quota Analysis")
    df = fetch_data("SELECT * FROM pricing_records")
    
    if not df.empty:
        vendor = st.selectbox("Select Vendor", df['vendor'].unique())
        
        # Filter for selected vendor
        vendor_df = df[df['vendor'] == vendor]
        
        # --- RAW TABLE DISPLAY REMOVED HERE ---
        
        st.subheader(f"📈 Quota & Pricing Visualizer for {vendor}")
        
        # Create a copy and force 'value' to be numeric so the graph doesn't break on "N/A"
        plot_df = vendor_df.copy()
        plot_df['value'] = pd.to_numeric(plot_df['value'], errors='coerce')
        plot_df = plot_df.dropna(subset=['value'])
        
        if not plot_df.empty:
            # Let the user pick exactly WHICH metric to look at
            available_metrics = plot_df['metric'].unique()
            selected_metric = st.selectbox("Select a specific metric to compare across plans:", available_metrics)
            
            # Filter the graph data to just that one metric
            metric_df = plot_df[plot_df['metric'] == selected_metric]
            
            # Get the unit to display on the Y-axis (e.g., GB, USD)
            unit_label = metric_df['unit'].iloc[0] if not metric_df['unit'].empty else "Value"
            
            # Build a clean Bar Chart
            fig = px.bar(
                metric_df, 
                x="plan", 
                y="value", 
                color="plan",
                title=f"Comparison of {selected_metric.replace('_', ' ').title()}",
                labels={"value": f"Limit / Cost ({unit_label})", "plan": "Pricing Tier"},
                text_auto=True # Displays the exact number on top of the bar
            )
            
            # Clean up the look of the chart
            fig.update_layout(xaxis_title=None, showlegend=False)
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Not enough numeric data to render a graph for this vendor.")
        
        # Export (Handles N/A natively and drops the index column)
        csv_data = vendor_df.fillna("N/A").to_csv(index=False).encode('utf-8')
        
        st.download_button(
            label="Download Raw Data as CSV",
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
        st.info(f"✅ Intelligence Update: No active core-team hiring listed for {vendor} at the moment.")

# --- Strategic News Module ---
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