import streamlit as st
import pandas as pd
import os
import warnings
import re
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Silence technical warnings
warnings.filterwarnings('ignore', category=pd.errors.DtypeWarning)

# --- SET PAGE CONFIG ---
st.set_page_config(page_title="Weekly Strategic Board", layout="wide", page_icon="📊")

# --- CSS FOR PRESENTATION MODE ---
st.markdown("""
    <style>
    [data-testid="stDataFrame"] td, [data-testid="stDataFrame"] th { padding: 1px 4px !important; }
    [data-testid="stDataFrame"] { font-weight: 500 !important; font-size: 13px !important; }
    [data-testid="stDataFrame"] th { background-color: #f0f2f6 !important; color: black !important; font-weight: bold !important; }
    .stMetric { background-color: #ffffff; padding: 10px; border-radius: 8px; border: 1px solid #f0f2f6; }
    </style>
    """, unsafe_allow_html=True)

# --- ADVANCED CLEANING FUNCTION ---
def clean_val(val):
    if pd.isna(val) or val == '' or str(val).lower() == 'undefined': return 0.0
    s = str(val).strip().replace('€', '').replace('%', '').replace('kr', '').replace('SEK', '')
    s = re.sub(r'[\s\xa0]+', '', s) 
    if not s: return 0.0
    if ',' in s:
        if '.' in s: s = s.replace('.', '') 
        s = s.replace(',', '.')
    try: return float(s)
    except: return 0.0

def load_csv_robust(file_path_or_buffer):
    if file_path_or_buffer is None: return None
    if hasattr(file_path_or_buffer, 'seek'): file_path_or_buffer.seek(0)
    try:
        content = file_path_or_buffer.read(8192).decode('utf-8', errors='ignore')
    except:
        file_path_or_buffer.seek(0)
        content = file_path_or_buffer.read(8192).decode('latin1', errors='ignore')
    if hasattr(file_path_or_buffer, 'seek'): file_path_or_buffer.seek(0)
    
    skip = 2 if "Swedemount - SKU Report;;" in content else 0
    sep = ';' if content.count(';') > content.count(',') else ','
    
    for enc in ['utf-8', 'latin1', 'cp1252']:
        try:
            if hasattr(file_path_or_buffer, 'seek'): file_path_or_buffer.seek(0)
            return pd.read_csv(file_path_or_buffer, sep=sep, encoding=enc, skiprows=skip, low_memory=False, dtype=str)
        except: continue
    return None

# --- SIDEBAR SETTINGS ---
st.sidebar.header("⚙️ Global Controls")
ex_rate = st.sidebar.number_input("Exchange Rate (1€ = X SEK)", value=10.66)
weekly_budget_sek = st.sidebar.number_input("Budget (SEK)", value=4300000)
weekly_prognos_sek = st.sidebar.number_input("Prognos (SEK)", value=4500000)

st.sidebar.markdown("---")
st.sidebar.header("📂 Data Upload")
f_cw = st.sidebar.file_uploader("1. Sales CW (CSV)", type="csv")
f_lw = st.sidebar.file_uploader("2. Sales LW (CSV)", type="csv")
f_ly = st.sidebar.file_uploader("3. Last Year Sales (CSV)", type="csv")
f_inv = st.sidebar.file_uploader("4. Inventory Report (CSV)", type="csv")
f_mkt = st.sidebar.file_uploader("5. Marketing Full (CSV)", type="csv")
f_hybrid = st.sidebar.file_uploader("6. Z-Hybrid Daily Sales (CSV)", type="csv")

# --- MAIN LOGIC ---
if all([f_cw, f_lw, f_ly, f_inv]):
    df_cw = load_csv_robust(f_cw); df_lw = load_csv_robust(f_lw)
    df_ly = load_csv_robust(f_ly); df_inv = load_csv_robust(f_inv)
    
    for df in [df_cw, df_lw, df_ly]:
        df['NMV_EUR'] = df['NMV'].apply(clean_val)
        df['NMV_SEK'] = df['NMV_EUR'] * ex_rate

    nmv_cw_sek = df_cw['NMV_SEK'].sum()
    nmv_lw_sek = df_lw['NMV_SEK'].sum()
    nmv_ly_sek = df_ly['NMV_SEK'].sum()

    st.title("🚀 Weekly Strategic Marketplace Board")

    # ROW 1: EUR
    st.subheader("🇪🇺
