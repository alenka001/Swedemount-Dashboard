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
    [data-testid="stDataFrame"] td, [data-testid="stDataFrame"] th { padding: 2px 8px !important; }
    [data-testid="stDataFrame"] { font-weight: 500 !important; font-size: 14px !important; }
    [data-testid="stDataFrame"] th { background-color: #f8f9fb !important; color: #1c1c1c !important; font-weight: bold !important; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #eef0f4; box-shadow: 0 2px 4px rgba(0,0,0,0.02); }
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
        src_sold_col = next((c for c in df.columns if 'sold articles' in c.lower()), None)
        df['NMV_EUR'] = df['NMV'].apply(clean_val)
        df['Sold_Units'] = df[src_sold_col].apply(clean_val) if src_sold_col else 0.0
        df['NMV_SEK'] = df['NMV_EUR'] * ex_rate

    nmv_cw_sek = df_cw['NMV_SEK'].sum()
    nmv_lw_sek = df_lw['NMV_SEK'].sum()
    nmv_ly_sek = df_ly['NMV_SEK'].sum()

    st.title("🚀 Weekly Strategic Marketplace Board")

    # ROW 1: EUR
    st.subheader("🇪🇺 Row 1: EUR Performance")
    e1, e2, e3 = st.columns(3)
    e1.metric("Current EUR", f"€{nmv_cw_sek/ex_rate:,.0f}")
    e2.metric("LW EUR", f"€{nmv_lw_sek/ex_rate:,.0f}", delta=f"{((nmv_cw_sek/nmv_lw_sek)-1) if nmv_lw_sek>0 else 0:.1%} vs LW")
    e3.metric("LY EUR", f"€{nmv_ly_sek/ex_rate:,.0f}", delta=f"{((nmv_cw_sek/nmv_ly_sek)-1) if nmv_ly_sek>0 else 0:.1%} vs LY")

    # ROW 2: SEK
    st.subheader("🇸🇪 Row 2: SEK Performance & Target Gaps")
    s1, s2, s3, s4, s5 = st.columns(5)
    s1.metric("LW SEK", f"{nmv_lw_sek:,.0f} kr", delta=f"{((nmv_cw_sek/nmv_lw_sek)-1) if nmv_lw_sek>0 else 0:.1%} vs LW")
    s2.metric("LY SEK", f"{nmv_ly_sek:,.0f} kr", delta=f"{((nmv_cw_sek/nmv_ly_sek)-1) if nmv_ly_sek>0 else 0:.1%} vs LY")
    
    b_gap = (nmv_cw_sek / weekly_budget_sek) - 1
    s3.metric("vs Budget", f"{weekly_budget_sek:,.0f} kr", delta=f"{b_gap:.1%} {'Ahead' if b_gap > 0 else 'Behind'}")
    
    p_gap = (nmv_cw_sek / weekly_prognos_sek) - 1
    s4.metric("vs Prognos", f"{weekly_prognos_sek:,.0f} kr", delta=f"{p_gap:.1%} {'Ahead' if p_gap > 0 else 'Behind'}")
    s5.metric("Current Total", f"{nmv_cw_sek:,.0f} kr")

    st.markdown("---")
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Brand Health", "🏆 Top 50 Articles", "📣 Marketing", "🔄 Z-Hybrid"])

    with tab1:
        st.subheader("Health Tracker: YoY Growth (SEK)")
        c1, c2 = st.columns(2)
        for col, grp in zip([c1, c2], ['Brand', 'Article type']):
            cw_g = df_cw.groupby(grp)['NMV_SEK'].sum().reset_index().rename(columns={'NMV_SEK': 'CW_kr'})
            ly_g = df_ly.groupby(grp)['NMV_SEK'].sum().reset_index().rename(columns={'NMV_SEK': 'LY_kr'})
            m = cw_g.merge(ly_g, on=grp, how='left').fillna(0)
            m['Growth %'] = (m['CW_kr'] - m['LY_kr']) / m['LY_kr'].replace(0, 1)
            
            col.dataframe(m.sort_values('CW_kr', ascending=False).style.format({
                "CW_kr": "{:,.0f} kr", "LY_kr": "{:,.0f} kr", "Growth %": "{:.1%}"
            }), hide_index=True, use_container_width=True)

    with tab2:
        st.subheader("🏆 Top 50 Articles: Performance & Stock Alerts")
        inv_var_col = next((c for c in df_inv.columns if 'variant' in c.lower()), 'Article variant')
        name_col = next((c for c in df_inv.columns if any(k in c.lower() for k in ['article_name', 'product title']) and 'partner' not in c.lower()), 'article_name')
        zfs_col = next((c for c in df_inv.columns if 'zfs' in c.lower()), 'sellable_zfs_stock')
        pf_col = next((c for c in df_inv.columns if 'pf' in c.lower() and 'stock' in c.lower()), 'sellable_pf_stock')
        
        df_inv[zfs_col] = df_inv[zfs_col].apply(clean_val)
        df_inv[pf_col] = df_inv[pf_col].apply(clean_val)
        inv_map = df_inv.groupby(inv_var_col).agg({name_col: 'first', zfs_col: 'sum', pf_col: 'sum'}).reset_index()

        cw_art = df_cw.groupby('Article variant')[['NMV_EUR', 'Sold_Units']].sum().reset_index()
        lw_art = df_lw.groupby('Article variant')[['NMV_EUR']].sum().reset_index().rename(columns={'NMV_EUR': 'NMV_LW'})
        top = cw_art.merge(lw_art, on='Article variant', how='left').fillna(0)
        top['Status sales'] = top.apply(lambda r: "🟢 Up" if r['NMV_EUR'] > r['NMV_LW'] else "🔴 Down", axis=1)
        top = top.merge(inv_map, left_on='Article variant', right_on=inv_var_col, how='left')
        
        top = top.rename(columns={name_col: "Article Name", zfs_col: "Stock ZFS", pf_col: "Stock PF", "Sold_Units": "Sold items", "NMV_EUR": "NMV €"})
        top = top.sort_values('NMV €', ascending=False).head(50)
        
        st.dataframe(top[['Status sales', 'Article variant', 'Article Name', 'NMV €', 'Sold items', 'Stock ZFS', 'Stock PF']].style.format({
            "NMV €": "€{:,.0f}", "Sold items": "{:,.0f}", "Stock ZFS": "{:,.0f}", "Stock PF": "{:,.0f}"
        }).apply(lambda x: ['background-color: #fff0f0' if (c in ['Stock ZFS', 'Stock PF'] and 0 < v < x['Sold items']) else '' for c, v in x.items()], axis=1), hide_index=True, use_container_width=True)

    with tab3:
        if f_mkt:
            mkt = load_csv_robust(f_mkt)
            mkt.columns = [c.replace(' ', '') for c in mkt.columns]
            m_cols = {'Spend': 'Budgetspent', 'GMV': 'GMV', 'Wish': 'Addtowishlist', 'Clicks': 'Clicks', 'Sold': 'Itemssold', 'Impressions': 'Impressions'}
            for k, v in m_cols.items():
                t_col = v if v in mkt.columns else next((c for c in mkt.columns if k.lower() in c.lower()), None)
                mkt[k] = mkt[t_col].apply(clean_val) if t_col else 0.0
            
            mkt['Week'] = mkt['Week'].apply(clean_val).astype(int)
            mkt['Year'] = mkt['Year'].apply(clean_val).astype(int) if 'Year' in mkt.columns else 2026
            
            weeks = sorted(mkt['Week'].unique())
            if len(weeks) >= 2:
                cw_w, lw_w = weeks[-1], weeks[-2]
                curr_yr = sorted(mkt['Year'].unique())[-1]
                
                def get_mkt_stats(y, w):
                    subset = mkt[(mkt['Year'] == y) & (mkt['Week'] == w)]
                    s = subset[['Spend', 'GMV', 'Wish', 'Clicks', 'Sold', 'Impressions']].sum()
                    s['ROAS'] = s['GMV'] / s['Spend'] if s['Spend'] > 0 else 0
                    s['COS'] = s['Spend'] / s['GMV'] if s['GMV'] > 0 else 0
                    return s

                s_cw, s_lw = get_mkt_stats(curr_yr, cw_w), get_mkt_stats(curr_yr, lw_w)
                total_sales_cw_eur = (nmv_cw_sek / ex_rate)
                total_sales_lw_eur = (nmv_lw_sek / ex_rate)
                blended_cw = s_cw['Spend'] / total_sales_cw_eur if total_sales_cw_eur > 0 else 0
                blended_lw = s_lw['Spend'] / total_sales_lw_eur if total_sales_lw_eur > 0 else 0
                
                st.subheader(f"Marketing Performance Week {cw_w}")
                mk1, mk2, mk3, mk4, mk5, mk6 = st.columns(6)
                
                mk1.metric("Ad Spend", f"€{s_cw['Spend']:,.0f}", delta=f"{((s_cw['Spend']/s_lw['Spend'])-1):.1%}" if s_lw['Spend']>0 else None, delta_color="inverse")
                mk2.metric("Total GMV", f"€{s_cw['GMV']:,.0f}", delta=f"{((s_cw['GMV']/s_lw['GMV'])-1):.1%}" if s_lw['GMV']>0 else None)
                mk3.metric("ROAS", f"{s_cw['ROAS']:,.2f}x", delta=f"{((s_cw['ROAS']/s_lw['ROAS'])-1):.1%}" if s_lw['ROAS']>0 else None)
                mk4.metric("COS", f"{s_cw['COS']:.1%}", delta=f"{(s_cw['COS'] - s_lw['COS']):.1%}", delta_color="inverse")
                mk5.metric("Blended COS", f"{blended_cw:.1%}", delta=f"{(blended_cw - blended_lw):.1%}", delta_color="inverse")
                mk6.metric("Impressions", f"{s_cw['Impressions']:,.0f}", delta=f"{((s_cw['Impressions']/s_lw['Impressions'])-1):.1%}" if s_lw['Impressions']>0 else None)

                st.markdown("---")
                st.subheader("📣 Campaign Analytics (WoW Comparison)")
                c_cw = mkt[(mkt['Year']==curr_yr) & (mkt['Week']==cw_w)].groupby('ZMSCampaign')[['Spend', 'GMV']].sum()
                c_lw = mkt[(mkt['Year']==curr_yr) & (mkt['Week']==lw_w)].groupby('ZMSCampaign')[['Spend', 'GMV']].sum()
                camp_df = c_cw.join(c_lw, rsuffix='_LW', how='left').fillna(0).reset_index()
                camp_df['ROAS CW'] = camp_df['GMV'] / camp_df['Spend'].replace(0, 1)
                camp_df['ROAS LW'] = camp_df['GMV_LW'] / camp_df['Spend_LW'].replace(0, 1)
                camp_df['COS CW'] = camp_df['Spend'] / camp_df['GMV'].replace(0, 1)
                camp_df['COS LW'] = camp_df['Spend_LW'] / camp_df['GMV_LW'].replace(0, 1)

                def style_mkt(row):
                    styles = [''] * len(row)
                    if row['Spend'] > row['Spend_LW']: styles[row.index.get_loc('Spend')] = 'color: #ff4b4b; font-weight: bold'
                    if row['ROAS CW'] < row['ROAS LW']: styles[row.index.get_loc('ROAS CW')] = 'color: #ff4b4b; font-weight: bold'
                    if row['COS CW'] > row['COS LW']: styles[row.index.get_loc('COS CW')] = 'color: #ff4b4b; font-weight: bold'
                    return styles

                st.dataframe(camp_df[['ZMSCampaign', 'Spend', 'GMV', 'ROAS CW', 'COS CW']].style.format({
                    'Spend': '€{:,.0f}', 'GMV': '€{:,.0f}', 'ROAS CW': '{:,.2f}x', 'COS CW': '{:.1%}'
                }).apply(style_mkt, axis=1), hide_index=True, use_container_width=True)
            else:
                st.warning("Upload a marketing file with at least two weeks of data.")
        else:
            st.info("Upload Marketing CSV to view performance.")

    with tab4:
        st.subheader("🔄 Z-Hybrid Performance & Fulfillment Share")
        if f_hybrid:
            hy = load_csv_robust(f_hybrid)
            hy.columns = [c.strip() for c in hy.columns]
            v_col, l_col, d_col = 'Ordervärde ex.moms', 'Ordervärde ex. moms LY', 'Datum'
            if v_col in hy.columns:
                hy_clean = hy[hy[d_col].str.lower() != 'total'].copy()
                hy_clean['Sales_CW'] = hy_clean[v_col].apply(clean_val)
                hy_clean['Sales_LY'] = hy_clean[l_col].apply(clean_val) if l_col in hy_clean.columns else 0.0
                total_hy = hy_clean['Sales_CW'].sum()
                total_ly = hy_clean['Sales_LY'].sum()
                h1, h2, h3 = st.columns(3)
                h1.metric("Total Z-Hybrid Sales", f"{total_hy:,.0f} kr")
                h2.metric("Total Zalando Sales (SEK)", f"{nmv_cw_sek:,.0f} kr")
                h3.metric("Hybrid Share", f"{(total_hy/nmv_cw_sek):.1%}", delta=f"{((total_hy/total_ly)-1):.1%} YoY" if total_ly > 0 else None)
                st.dataframe(hy_clean.groupby([d_col, 'Veckodag'])[['Sales_CW', 'Sales_LY']].sum().reset_index().style.format({
                    "Sales_CW": "{:,.0f} kr", "Sales_LY": "{:,.0f} kr"
                }), hide_index=True, use_container_width=True)
else:
    st.info("Awaiting file uploads 1-4 in the sidebar to generate board.")
