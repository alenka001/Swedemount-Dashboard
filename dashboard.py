import streamlit as st
import pandas as pd
import warnings
import re

# Tysta tekniska varningar
warnings.filterwarnings('ignore', category=pd.errors.DtypeWarning)

# --- SET PAGE CONFIG ---
st.set_page_config(page_title="Weekly Strategic Dashboard", layout="wide", page_icon="📊")

# --- CSS FÖR PROFESSIONELL DESIGN ---
st.markdown("""
    <style>
    .block-container { padding-top: 4rem !important; padding-bottom: 0rem; }
    [data-testid="stMetricValue"] { font-size: 22px !important; font-weight: 700; }
    [data-testid="stMetricDelta"] { font-size: 13px !important; }
    [data-testid="stDataFrame"] td, [data-testid="stDataFrame"] th { 
        padding: 2px 8px !important; 
        font-size: 13px !important; 
    }
    .stTabs [data-baseweb="tab"] { 
        height: 35px; 
        padding: 5px 15px;
        background-color: #f8f9fb;
    }
    .stTabs [aria-selected="true"] { background-color: #1c2b4d !important; color: white !important; }
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        padding: 8px;
        border-radius: 5px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- UTILITIES ---
def clean_val(val, is_pct=False):
    if pd.isna(val) or val == '' or str(val).lower() == 'undefined': return 0.0
    s = str(val).strip().replace('€', '').replace('kr', '').replace('SEK', '')
    has_pct_sign = '%' in s
    s = re.sub(r'[\s\xa0]+', '', s)
    if not s: return 0.0
    if ',' in s:
        if '.' in s: s = s.replace('.', '') 
        s = s.replace(',', '.')
    try: 
        num = float(s)
        return num / 100.0 if (is_pct or has_pct_sign) else num
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
st.sidebar.header("⚙️ Kontroller")
ex_rate = st.sidebar.number_input("Växelkurs (1€ = X SEK)", value=10.66)
weekly_budget_sek = st.sidebar.number_input("Budget (SEK)", value=4300000)
weekly_prognos_sek = st.sidebar.number_input("Prognos (SEK)", value=4500000)
f_cw = st.sidebar.file_uploader("1. Försäljning CW", type="csv")
f_lw = st.sidebar.file_uploader("2. Försäljning LW", type="csv")
f_ly = st.sidebar.file_uploader("3. Försäljning LY", type="csv")
f_inv = st.sidebar.file_uploader("4. Lagerrapport", type="csv")
f_mkt = st.sidebar.file_uploader("5. Marknadsföring Full", type="csv")
f_hybrid = st.sidebar.file_uploader("6. Z-Hybrid", type="csv")
f_mcw = st.sidebar.file_uploader("7. Market CW (Land)", type="csv")
f_mlw = st.sidebar.file_uploader("8. Market LW (Land)", type="csv")

# --- HUVUDLOGIK ---
if all([f_cw, f_lw, f_ly, f_inv]):
    df_cw_raw = load_csv_robust(f_cw)
    df_lw_raw = load_csv_robust(f_lw)
    df_ly_raw = load_csv_robust(f_ly)
    df_inv_raw = load_csv_robust(f_inv)

    inv_sku_col, inv_name_col = 'zalando_article_variant', 'article_name'
    zfs_col, pf_col = 'sellable_zfs_stock', 'sellable_pf_stock'
    df_inv_raw[inv_sku_col] = df_inv_raw[inv_sku_col].str.strip().str.upper()
    df_inv_raw[zfs_col] = df_inv_raw[zfs_col].apply(clean_val)
    df_inv_raw[pf_col] = df_inv_raw[pf_col].apply(clean_val)
    inv_map = df_inv_raw.groupby(inv_sku_col).agg({inv_name_col: 'first', zfs_col: 'sum', pf_col: 'sum'}).reset_index()
    inv_map['Total Stock'] = inv_map[zfs_col] + inv_map[pf_col]
    
    def process_sales(df):
        df.columns = [c.strip() for c in df.columns]
        nmv_col = next((c for c in df.columns if c.lower() == 'nmv'), 'NMV')
        df['NMV_EUR'] = df[nmv_col].apply(clean_val)
        sold_col = next((c for c in df.columns if 'sold articles' in c.lower()), 'Sold articles')
        df['Sold'] = df[sold_col].apply(clean_val)
        sku_col = next((c for c in df.columns if 'zalando article variant' in c.lower()), None)
        if not sku_col: sku_col = next((c for c in df.columns if 'variant' in c.lower()), df.columns[0])
        df['join_key'] = df[sku_col].astype(str).str.strip().str.upper()
        df['Zalando article variant'] = df['join_key']
        return df

    df_cw, df_lw, df_ly = process_sales(df_cw_raw), process_sales(df_lw_raw), process_sales(df_ly_raw)
    nmv_cw_sek = df_cw['NMV_EUR'].sum() * ex_rate
    nmv_lw_sek = df_lw['NMV_EUR'].sum() * ex_rate
    nmv_ly_sek = df_ly['NMV_EUR'].sum() * ex_rate
    total_nmv_cw = df_cw['NMV_EUR'].sum()

    st.title("🚀 Weekly Strategic Marketplace Board")
    
    # Rader och Tabs logik...
    tabs = st.tabs(["📈 Hälsa", "🏆 Top 50 Revenue", "❤️ Wishlist", "📣 Marknadsföring", "🌍 Marknadsutveckling", "🔄 Z-Hybrid", "📝 Analys"])

    with tabs[0]: # HÄLSA
        st.subheader("Business Health Tracker: WoW & YoY Growth")
        c1, c2 = st.columns(2)
        for col, grp in zip([c1, c2], ['Brand', 'Article type']):
            cw_g = df_cw.groupby(grp)['NMV_EUR'].sum().reset_index().rename(columns={'NMV_EUR': 'CW_EUR'})
            lw_g = df_lw.groupby(grp)['NMV_EUR'].sum().reset_index().rename(columns={'NMV_EUR': 'LW_EUR'})
            ly_g = df_ly.groupby(grp)['NMV_EUR'].sum().reset_index().rename(columns={'NMV_EUR': 'LY_EUR'})
            h_m = cw_g.merge(lw_g, on=grp, how='left').merge(ly_g, on=grp, how='left').fillna(0)
            h_m['Andel %'] = h_m['CW_EUR'] / total_nmv_cw if total_nmv_cw > 0 else 0
            h_m['WoW %'] = (h_m['CW_EUR'] - h_m['LW_EUR']) / h_m['LW_EUR'].replace(0, 1)
            h_m['YoY %'] = (h_m['CW_EUR'] - h_m['LY_EUR']) / h_m['LY_EUR'].replace(0, 1)
            h_m['Status'] = h_m['YoY %'].apply(lambda x: "🟢 Growth" if x > 0.05 else ("🔻 Decline" if x < -0.05 else "➖ Stable"))
            col.dataframe(h_m.sort_values('CW_EUR', ascending=False).style.format({"CW_EUR": "€{:,.0f}", "Andel %": "{:.1%}", "WoW %": "{:+.1%}", "YoY %": "{:+.1%}"}), hide_index=True, use_container_width=True)

    with tabs[1]: # TOP 50
        cw_top = df_cw.groupby(['join_key', 'Article variant'])[['NMV_EUR', 'Sold']].sum().reset_index()
        cw_top['Rank_CW'] = cw_top['NMV_EUR'].rank(ascending=False, method='min')
        lw_top = df_lw.groupby(['join_key'])[['NMV_EUR']].sum().reset_index()
        lw_top['Rank_LW'] = lw_top['NMV_EUR'].rank(ascending=False, method='min')
        t50 = cw_top.merge(lw_top[['join_key', 'Rank_LW']], on='join_key', how='left').merge(inv_map, left_on='join_key', right_on=inv_sku_col, how='left').fillna(0)
        t50['Status'] = t50.apply(lambda r: "🆕" if r['Rank_LW'] == 0 else ("⬆️" if r['Rank_CW'] < r['Rank_LW'] else ("⬇️" if r['Rank_CW'] > r['Rank_LW'] else "➡️")), axis=1)
        disp = t50.sort_values('Rank_CW').head(50).rename(columns={'join_key': 'SKU', inv_name_col: 'Article Name', 'NMV_EUR': 'NMV €', zfs_col: 'Stock ZFS', pf_col: 'Stock PF'})
        st.dataframe(disp[['Status', 'SKU', 'Article Name', 'NMV €', 'Sold', 'Stock ZFS', 'Stock PF']].style.format({'NMV €': '€{:,.0f}', 'Sold': '{:,.0f}', 'Stock ZFS': '{:,.0f}', 'Stock PF': '{:,.0f}'}), hide_index=True, use_container_width=True)

    with tabs[6]: # ANALYS - Här lägger du in din analyslogik
        st.subheader("📝 Weekly Strategic Focus")
        # Analys-logik och vinnare/utmanare visas här
        
else:
    st.info("Vänligen ladda upp data för att starta.")
