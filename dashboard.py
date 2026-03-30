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

# --- UTILITIES ---
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
            df = pd.read_csv(file_path_or_buffer, sep=sep, encoding=enc, skiprows=skip, low_memory=False, dtype=str)
            df.columns = [c.strip() for c in df.columns] 
            return df
        except: continue
    return None

# --- SIDEBAR ---
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
    df_cw = load_csv_robust(f_cw)
    df_lw = load_csv_robust(f_lw)
    df_ly = load_csv_robust(f_ly)
    df_inv = load_csv_robust(f_inv)
    
    # Pre-clean primary sales data
    for df in [df_cw, df_lw, df_ly]:
        df['NMV_EUR'] = df['NMV'].apply(clean_val)
        df['Sold_Units'] = df['Sold articles'].apply(clean_val)
        df['NMV_SEK'] = df['NMV_EUR'] * ex_rate

    nmv_cw_sek = df_cw['NMV_SEK'].sum()
    st.title("🚀 Weekly Strategic Marketplace Board")

    tab1, tab2, tab3, tab4 = st.tabs(["📊 Brand Health", "🏆 Top 50 Articles", "📣 Marketing", "🔄 Z-Hybrid"])

    with tab1:
        st.subheader("Health Tracker: YoY Growth (SEK)")
        c1, c2 = st.columns(2)
        for col, grp in zip([c1, c2], ['Brand', 'Article type']):
            cw_g = df_cw.groupby(grp)['NMV_SEK'].sum().reset_index().rename(columns={'NMV_SEK': 'CW_kr'})
            ly_g = df_ly.groupby(grp)['NMV_SEK'].sum().reset_index().rename(columns={'NMV_SEK': 'LY_kr'})
            m = cw_g.merge(ly_g, on=grp, how='left').fillna(0)
            m['Growth %'] = (m['CW_kr'] - m['LY_kr']) / m['LY_kr'].replace(0, 1)
            m['Status'] = m['Growth %'].apply(lambda x: "🟢 Growth" if x > 0.05 else ("🔻 Decline" if x < -0.05 else "➖ Stable"))
            col.dataframe(m.sort_values('CW_kr', ascending=False), hide_index=True, use_container_width=True)

    # --- TAB 2: ARTICLE PERFORMANCE & TRENDS ---
    with tab2:
        st.subheader("🏆 Top 50 Articles: Performance & Stock Alerts")
        
        # 1. Identify Inventory Columns
        inv_var_col = next((c for c in df_inv.columns if 'variant' in c.lower()), 'Article variant')
        
        # Target article_name as priority
        name_col = 'article_name' if 'article_name' in df_inv.columns else \
                   next((c for c in df_inv.columns if any(k in c.lower() for k in ['article name', 'product title', 'title']) and 'partner' not in c.lower()), None)
        
        zfs_col = next((c for c in df_inv.columns if 'zfs' in c.lower()), None)
        pf_col = next((c for c in df_inv.columns if any(k in c.lower() for k in ['partner', 'pf']) and 'stock' in c.lower()), None)
        
        # Safe Slicing
        cols_present = [c for c in [inv_var_col, name_col, zfs_col, pf_col] if c is not None and c in df_inv.columns]
        inv_map = df_inv[cols_present].drop_duplicates(inv_var_col)
        
        if zfs_col: inv_map[zfs_col] = inv_map[zfs_col].apply(clean_val)
        if pf_col: inv_map[pf_col] = inv_map[pf_col].apply(clean_val)

        # 2. Aggregate Sales
        cw_art = df_cw.groupby('Article variant')[['NMV_EUR', 'Sold_Units']].sum().reset_index()
        lw_art = df_lw.groupby('Article variant')[['NMV_EUR']].sum().reset_index().rename(columns={'NMV_EUR': 'NMV_LW'})
        
        # 3. Merge & Status
        top = cw_art.merge(lw_art, on='Article variant', how='left').fillna(0)
        
        def get_status_icon(row):
            if row['NMV_LW'] == 0: return "🆕 New"
            return "🟢 Up" if row['NMV_EUR'] > row['NMV_LW'] else "🔴 Down"
        
        top['Status sales'] = top.apply(get_status_icon, axis=1)
        top = top.merge(inv_map, left_on='Article variant', right_on=inv_var_col, how='left')
        
        # Rename for output
        rename_dict = {
            name_col: "Article Name",
            zfs_col: "Article Stock ZFS",
            pf_col: "Article Stock PF",
            "Sold_Units": "Article sold items",
            "NMV_EUR": "Article NMV €"
        }
        top = top.rename(columns={k: v for k, v in rename_dict.items() if k in top.columns})
        
        top = top.sort_values('Article NMV €', ascending=False).head(50)

        # 4. Styling Function
        def style_stock_alerts(df):
            # Create a copy for styles
            style_df = pd.DataFrame('', index=df.index, columns=df.columns)
            threshold = df["Article sold items"]
            
            if "Article Stock ZFS" in df.columns:
                style_df["Article Stock ZFS"] = df["Article Stock ZFS"].apply(lambda x: 'background-color: #ffcccc' if (0 < x < threshold.iloc[0]) else '')
            if "Article Stock PF" in df.columns:
                style_df["Article Stock PF"] = df["Article Stock PF"].apply(lambda x: 'background-color: #ffcccc' if (0 < x < threshold.iloc[0]) else '')
            return style_df

        # Filter display columns
        final_headers = ['Status sales', 'Article variant', 'Article Name', 'Article NMV €', 'Article sold items', 'Article Stock ZFS', 'Article Stock PF']
        existing_headers = [h for h in final_headers if h in top.columns]

        # Use Styler for red backgrounds
        st.dataframe(
            top[existing_headers].style.apply(lambda x: [
                'background-color: #ffcccc' if (col in ['Article Stock ZFS', 'Article Stock PF'] and 0 < val < x['Article sold items']) else '' 
                for col, val in x.items()
            ], axis=1),
            column_config={
                "Article NMV €": st.column_config.NumberColumn("Article NMV €", format="€%.0f"),
                "Article sold items": st.column_config.NumberColumn("Article sold items"),
                "Article Stock ZFS": st.column_config.NumberColumn("Article Stock ZFS"),
                "Article Stock PF": st.column_config.NumberColumn("Article Stock PF"),
            }, 
            hide_index=True, 
            use_container_width=True
        )
        
        st.caption("💡 Cells highlighted in red indicate stock levels are currently lower than this week's sales volume.")

    # --- TAB 3: MARKETING ---
    with tab3:
        if f_mkt:
            mkt = load_csv_robust(f_mkt)
            if mkt is not None:
                mkt.columns = [c.replace(' ', '') for c in mkt.columns]
                # Filter metrics and show
                st.info("Marketing Data Active. Metrics processing...")
                # (You can insert the previous marketing logic block here)

    with tab4:
        st.subheader("🔄 Z-Hybrid Performance")
        if f_hybrid:
            hy = load_csv_robust(f_hybrid)
            st.dataframe(hy, use_container_width=True)

else:
    st.info("Awaiting file uploads 1-4 in the sidebar to generate board.")
