import streamlit as st
import pandas as pd
import warnings
import re

# Silence technical warnings
warnings.filterwarnings('ignore', category=pd.errors.DtypeWarning)

# --- SET PAGE CONFIG ---
st.set_page_config(page_title="Weekly Strategic Dashboard", layout="wide", page_icon="📊")

# --- CSS FOR COMPACT MATURE UI ---
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 0rem; }
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
    s = s.replace('%', '').replace(' ', '').replace('\xa0', '')
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
st.sidebar.header("⚙️ Controls")
ex_rate = st.sidebar.number_input("Rate (1€ = X SEK)", value=10.66)
weekly_budget_sek = st.sidebar.number_input("Budget (SEK)", value=4300000)
weekly_prognos_sek = st.sidebar.number_input("Prognos (SEK)", value=4500000)

st.sidebar.markdown("---")
st.sidebar.header("📂 Data Upload")
f_cw = st.sidebar.file_uploader("1. Sales CW", type="csv")
f_lw = st.sidebar.file_uploader("2. Sales LW", type="csv")
f_ly = st.sidebar.file_uploader("3. Last Year Sales", type="csv")
f_inv = st.sidebar.file_uploader("4. Inventory Report", type="csv")
f_mkt = st.sidebar.file_uploader("5. Marketing Full", type="csv")
f_hybrid = st.sidebar.file_uploader("6. Z-Hybrid", type="csv")
f_mcw = st.sidebar.file_uploader("7. Market CW (Country)", type="csv")
f_mlw = st.sidebar.file_uploader("8. Market LW (Country)", type="csv")

# --- MAIN LOGIC ---
if all([f_cw, f_lw, f_ly, f_inv]):
    df_cw_raw = load_csv_robust(f_cw)
    df_lw_raw = load_csv_robust(f_lw)
    df_ly_raw = load_csv_robust(f_ly)
    df_inv_raw = load_csv_robust(f_inv)

    # 1. Process Inventory (Hardcoded Columns based on your description)
    inv_sku_col = 'zalando_article_variant'
    inv_name_col = 'article_name'
    zfs_col = 'sellable_zfs_stock'
    pf_col = 'sellable_pf_stock'
    
    df_inv_raw[zfs_col] = df_inv_raw[zfs_col].apply(clean_val)
    df_inv_raw[pf_col] = df_inv_raw[pf_col].apply(clean_val)
    
    inv_map = df_inv_raw.groupby(inv_sku_col).agg({
        inv_name_col: 'first', 
        zfs_col: 'sum', 
        pf_col: 'sum'
    }).reset_index()
    inv_map['Total Stock'] = inv_map[zfs_col] + inv_map[pf_col]

    # 2. Process Sales - Ensure join_key uses Zalando Variant ID
    def process_sales(df):
        df['NMV_EUR'] = df['NMV'].apply(clean_val)
        df['Sold'] = df[next((c for c in df.columns if 'sold articles' in c.lower()), 'Sold articles')].apply(clean_val)
        df['join_key'] = df['Zalando article variant']
        return df

    df_cw = process_sales(df_cw_raw)
    df_lw = process_sales(df_lw_raw)
    df_ly = process_sales(df_ly_raw)
    
    nmv_cw_sek = df_cw['NMV_EUR'].sum() * ex_rate
    nmv_lw_sek = df_lw['NMV_EUR'].sum() * ex_rate
    nmv_ly_sek = df_ly['NMV_EUR'].sum() * ex_rate

    st.title("🚀 Weekly Strategic Marketplace Board")

    # Metrics Row
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Current NMV", f"€{nmv_cw_sek/ex_rate:,.0f}")
    m2.metric("vs LW (SEK)", f"{nmv_cw_sek:,.0f} kr", delta=f"{((nmv_cw_sek/nmv_lw_sek)-1):.1%}")
    m3.metric("vs LY (SEK)", f"{nmv_ly_sek:,.0f} kr", delta=f"{((nmv_cw_sek/nmv_ly_sek)-1):.1%}")
    m4.metric("vs Budget", f"{weekly_budget_sek:,.0f} kr", delta=f"{(nmv_cw_sek - weekly_budget_sek):,.0f} kr")
    m5.metric("vs Prognos", f"{weekly_prognos_sek:,.0f} kr", delta=f"{(nmv_cw_sek - weekly_prognos_sek):,.0f} kr")

    st.markdown("---")
    tabs = st.tabs(["📈 Health", "🏆 Top 50 Revenue", "❤️ Wishlist Top 50", "📣 Marketing", "🌍 Market Dev", "🔄 Z-Hybrid", "📝 Analysis"])

    with tabs[0]: # Health
        st.subheader("Business Health Tracker (YoY Growth)")
        c1, c2 = st.columns(2)
        for col, grp in zip([c1, c2], ['Brand', 'Article type']):
            cw_g = df_cw.groupby(grp)['NMV_EUR'].sum().reset_index().rename(columns={'NMV_EUR': 'CW_EUR'})
            ly_g = df_ly.groupby(grp)['NMV_EUR'].sum().reset_index().rename(columns={'NMV_EUR': 'LY_EUR'})
            h_m = cw_g.merge(ly_g, on=grp, how='left').fillna(0)
            h_m['Growth %'] = (h_m['CW_EUR'] - h_m['LY_EUR']) / h_m['LY_EUR'].replace(0, 1)
            h_m['Status'] = h_m['Growth %'].apply(lambda x: "🟢 Growth" if x > 0.05 else ("🔻 Decline" if x < -0.05 else "➖ Stable"))
            col.dataframe(h_m.sort_values('CW_EUR', ascending=False).style.format({
                "CW_EUR": "€{:,.0f}", "LY_EUR": "€{:,.0f}", "Growth %": "{:.1%}"
            }), hide_index=True, use_container_width=True)

    with tabs[1]: # 🏆 Top 50 Revenue (CORRECTED JOIN)
        st.subheader("🏆 Top 50 Revenue Performance & Stock Alerts")
        cw_top = df_cw.groupby(['join_key', 'Article variant'])[['NMV_EUR', 'Sold']].sum().reset_index()
        cw_top['Rank_CW'] = cw_top['NMV_EUR'].rank(ascending=False, method='min')
        lw_top = df_lw.groupby(['Zalando article variant'])[['NMV_EUR']].sum().reset_index()
        lw_top['Rank_LW'] = lw_top['NMV_EUR'].rank(ascending=False, method='min')
        
        t50 = cw_top.merge(lw_top[['Zalando article variant', 'Rank_LW']], left_on='join_key', right_on='Zalando article variant', how='left')
        t50 = t50.merge(inv_map, left_on='join_key', right_on=inv_sku_col, how='left').fillna(0)
        
        t50['Status'] = t50.apply(lambda r: "🆕" if r['Rank_LW'] == 0 else ("⬆️" if r['Rank_CW'] < r['Rank_LW'] else ("⬇️" if r['Rank_CW'] > r['Rank_LW'] else "➡️")), axis=1)
        t50_final = t50.sort_values('Rank_CW').head(50)
        
        display_df = t50_final[['Status', 'join_key', inv_name_col, 'NMV_EUR', 'Sold', zfs_col, pf_col]]
        display_df = display_df.rename(columns={'join_key': 'SKU', inv_name_col: 'Article Name', 'NMV_EUR': 'NMV €', zfs_col: 'Stock ZFS', pf_col: 'Stock PF'})

        def highlight_stock_alert(row):
            styles = [''] * len(row)
            sold_val = row['Sold']
            if row['Stock ZFS'] < sold_val and row['Stock ZFS'] > 0: styles[row.index.get_loc('Stock ZFS')] = 'background-color: #ffcccc; color: #990000; font-weight: bold;'
            if row['Stock PF'] < sold_val and row['Stock PF'] > 0: styles[row.index.get_loc('Stock PF')] = 'background-color: #ffcccc; color: #990000; font-weight: bold;'
            return styles

        st.dataframe(display_df.style.format({'NMV €': '€{:,.0f}', 'Sold': '{:,.0f}', 'Stock ZFS': '{:,.0f}', 'Stock PF': '{:,.0f}'}).apply(highlight_stock_alert, axis=1), hide_index=True, use_container_width=True)

    with tabs[2]: # ❤️ WISHLIST (YOUR FIXED SNIPPET)
        if f_mkt:
            st.subheader("❤️ Top 50 Most Added to Wishlist (Latest Data)")
            m_wish_raw = load_csv_robust(f_mkt)
            m_wish_raw.columns = [c.replace(' ', '') for c in m_wish_raw.columns]
            
            # Identify latest week in file
            m_wish_raw['W_Clean'] = m_wish_raw['Week'].apply(clean_val)
            l_week = m_wish_raw['W_Clean'].max()
            
            w_data = m_wish_raw[m_wish_raw['W_Clean'] == l_week].groupby('ConfigSKU')[['Addtowishlist']].sum().reset_index()
            w_data['Addtowishlist'] = w_data['Addtowishlist'].apply(clean_val)
            
            w_merged = w_data.merge(inv_map, left_on='ConfigSKU', right_on=inv_sku_col, how='left').sort_values('Addtowishlist', ascending=False).head(50)
            st.dataframe(w_merged[['ConfigSKU', inv_name_col, 'Addtowishlist', 'Total Stock', zfs_col, pf_col]].style.format(precision=0), hide_index=True, use_container_width=True)

    with tabs[3]: # Marketing Summary
        if f_mkt:
            mkt_df = load_csv_robust(f_mkt); mkt_df.columns = [c.replace(' ', '') for c in mkt_df.columns]
            for c in ['Budgetspent', 'GMV', 'Addtowishlist', 'Clicks', 'Itemssold', 'Viewableadimpressions', 'PDPviews']: mkt_df[c] = mkt_df[c].apply(clean_val)
            w_list = sorted(mkt_df['Week'].apply(clean_val).unique(), reverse=True)
            c1, c2 = st.columns(2)
            s_w1 = c1.selectbox("Active Week", w_list, index=0); s_w2 = c2.selectbox("Comp Week", w_list, index=min(1, len(w_list)-1))
            
            def get_m_stats(df_sub, nmv_val):
                s = df_sub.sum(numeric_only=True)
                return {
                    'Spend': s['Budgetspent'], 'GMV': s['GMV'], 'Wish': s['Addtowishlist'], 'PDP': s['PDPviews'], 
                    'ROAS': s['GMV']/s['Budgetspent'] if s['Budgetspent']>0 else 0, 
                    'Blended': s['Budgetspent']/(nmv_val/ex_rate) if nmv_val>0 else 0
                }
            
            ms1 = get_m_stats(mkt_df[mkt_df['Week'].apply(clean_val) == s_w1], nmv_cw_sek)
            ms2 = get_m_stats(mkt_df[mkt_df['Week'].apply(clean_val) == s_w2], nmv_lw_sek)
            
            r1, r2, r3, r4, r5, r6 = st.columns(6)
            r1.metric("Spend", f"€{ms1['Spend']:,.0f}", delta=f"{(ms1['Spend']/ms2['Spend']-1):.0%}", delta_color="inverse")
            r2.metric("GMV", f"€{ms1['GMV']:,.0f}", delta=f"{(ms1['GMV']/ms2['GMV']-1):.0%}")
            r3.metric("ROAS", f"{ms1['ROAS']:,.0f}x", delta=f"{(ms1['ROAS']-ms2['ROAS']):,.0f}")
            r4.metric("PDP Views", f"{ms1['PDP']:,.0f}", delta=f"{(ms1['PDP']/ms2['PDP']-1):.0%}")
            r5.metric("Wishlist", f"{ms1['Wish']:,.0f}", delta=f"{(ms1['Wish']/ms2['Wish']-1):.0%}")
            r6.metric("Blended COS", f"{ms1['Blended']:.0%}", delta=f"{(ms1['Blended']-ms2['Blended']):.0%}", delta_color="inverse")

    with tabs[4]: # Market Development
        if f_mcw and f_mlw:
            mcw = load_csv_robust(f_mcw); mlw = load_csv_robust(f_mlw)
            for d in [mcw, mlw]: d['NMV_C'] = d['NMV'].apply(clean_val); d['Conv_C'] = d['Conversion rate'].apply(lambda x: clean_val(x, is_pct=True))
            mcw['Share %'] = mcw['NMV_C'] / mcw['NMV_C'].sum()
            m_comp = mcw.merge(mlw[['Country', 'NMV_C']], on='Country', suffixes=('', '_LW'))
            m_comp['Growth'] = (m_comp['NMV_C'] / m_comp['NMV_C_LW']) - 1
            st.dataframe(m_comp[['Country', 'NMV_C', 'Share %', 'Growth', 'Conv_C']].style.format({'NMV_C': '€{:,.0f}', 'Share %': '{:.1%}', 'Growth': '{:+.1%}', 'Conv_C': '{:.2%}'}), hide_index=True, use_container_width=True)

    with tabs[6]: # Analysis
        st.subheader("📝 Weekly Focus Analysis")
        col1, col2 = st.columns(2)
        with col1:
            st.info("**Top Performers**")
            for i, r in t50_final.head(3).iterrows(): st.write(f"🌟 **{r[inv_name_col]}**")
        with col2:
            st.warning("**Stock Attention**")
            crit = t50_final[t50_final['Total Stock'] < t50_final['Sold']].head(3)
            for i, r in crit.iterrows(): st.write(f"⚠️ **{r[inv_name_col]}**: Stock is critical vs sales.")
else:
    st.info("Please upload Sales CW, LW, LY and Inventory to begin.")
