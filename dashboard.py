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
f_cw = st.sidebar.file_uploader("1. Sales CW (Article Level) (CSV)", type="csv")
f_lw = st.sidebar.file_uploader("2. Sales LW (Article Level) (CSV)", type="csv")
f_ly = st.sidebar.file_uploader("3. Last Year Sales (Article Level) (CSV)", type="csv")
f_inv = st.sidebar.file_uploader("4. Inventory Report (CSV)", type="csv")
f_mkt = st.sidebar.file_uploader("5. Marketing Full (CSV)", type="csv")
f_hybrid = st.sidebar.file_uploader("6. Z-Hybrid Daily Sales (CSV)", type="csv")

st.sidebar.subheader("🌍 Market Development Files")
f_market_cw = st.sidebar.file_uploader("Market Performance CW (Country Report)", type="csv")
f_market_lw = st.sidebar.file_uploader("Market Performance LW (Country Report)", type="csv")

# --- MAIN LOGIC ---
if all([f_cw, f_lw, f_ly, f_inv]):
    df_cw = load_csv_robust(f_cw)
    df_lw = load_csv_robust(f_lw)
    df_ly = load_csv_robust(f_ly)
    df_inv = load_csv_robust(f_inv)
    
    for df in [df_cw, df_lw, df_ly]:
        src_sold_col = next((c for c in df.columns if 'sold articles' in c.lower()), None)
        df['NMV_EUR'] = df['NMV'].apply(clean_val)
        df['Sold_Units'] = df[src_sold_col].apply(clean_val) if src_sold_col else 0.0
        df['NMV_SEK'] = df['NMV_EUR'] * ex_rate

    nmv_cw_sek = df_cw['NMV_SEK'].sum()
    nmv_lw_sek = df_lw['NMV_SEK'].sum()
    nmv_ly_sek = df_ly['NMV_SEK'].sum()

    st.title("🚀 Weekly Strategic Marketplace Board")

    # Metrics Rows
    st.subheader("📊 High-Level Performance")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Current NMV", f"€{nmv_cw_sek/ex_rate:,.0f}")
    m2.metric("vs LW (SEK)", f"{nmv_cw_sek:,.0f} kr", delta=f"{((nmv_cw_sek/nmv_lw_sek)-1) if nmv_lw_sek>0 else 0:.1%}")
    m3.metric("vs LY (SEK)", f"{nmv_ly_sek:,.0f} kr", delta=f"{((nmv_cw_sek/nmv_ly_sek)-1) if nmv_ly_sek>0 else 0:.1%}")
    b_gap = (nmv_cw_sek / weekly_budget_sek) - 1
    m4.metric("vs Budget", f"{weekly_budget_sek:,.0f} kr", delta=f"{b_gap:.1%} {'Ahead' if b_gap > 0 else 'Behind'}")
    p_gap = (nmv_cw_sek / weekly_prognos_sek) - 1
    m5.metric("vs Prognos", f"{weekly_prognos_sek:,.0f} kr", delta=f"{p_gap:.1%} {'Ahead' if p_gap > 0 else 'Behind'}")

    st.markdown("---")
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📈 Health", "🏆 Top 50", "📣 Marketing", "🌍 Market Dev", "🔄 Z-Hybrid", "📝 Commentary"])

    with tab1:
        st.subheader("Health Tracker: YoY Growth (SEK)")
        c1, c2 = st.columns(2)
        for col, grp in zip([c1, c2], ['Brand', 'Article type']):
            cw_g = df_cw.groupby(grp)['NMV_SEK'].sum().reset_index().rename(columns={'NMV_SEK': 'CW_kr'})
            ly_g = df_ly.groupby(grp)['NMV_SEK'].sum().reset_index().rename(columns={'NMV_SEK': 'LY_kr'})
            m = cw_g.merge(ly_g, on=grp, how='left').fillna(0)
            m['Growth %'] = (m['CW_kr'] - m['LY_kr']) / m['LY_kr'].replace(0, 1)
            m['Status'] = m['Growth %'].apply(lambda x: "🟢 Growth" if x > 0.05 else ("🔻 Decline" if x < -0.05 else "➖ Stable"))
            col.dataframe(m.sort_values('CW_kr', ascending=False).style.format({"CW_kr": "{:,.0f} kr", "LY_kr": "{:,.0f} kr", "Growth %": "{:.1%}"}), hide_index=True, use_container_width=True)

    with tab2:
        # TOP 50 BY REVENUE
        st.subheader("🏆 Top 50 Articles by NMV")
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
        top = top.merge(inv_map, left_on='Article variant', right_on=inv_var_col, how='left')
        top = top.rename(columns={name_col: "Article Name", zfs_col: "Stock ZFS", pf_col: "Stock PF", "Sold_Units": "Sold", "NMV_EUR": "NMV €"})
        st.dataframe(top.sort_values('NMV €', ascending=False).head(50)[['Article variant', 'Article Name', 'NMV €', 'Sold', 'Stock ZFS', 'Stock PF']].style.format({"NMV €": "€{:,.0f}"}), hide_index=True, use_container_width=True)

        # TOP 50 BY WISHLIST (NEW)
        if f_mkt:
            st.markdown("---")
            st.subheader("❤️ Top 50 Most Added to Wishlist (Latest Week)")
            mkt_df = load_csv_robust(f_mkt)
            mkt_df.columns = [c.replace(' ', '') for c in mkt_df.columns]
            mkt_df['Wishlist'] = mkt_df['Addtowishlist'].apply(clean_val)
            mkt_df['Week'] = mkt_df['Week'].apply(clean_val).astype(int)
            mkt_df['Year'] = mkt_df['Year'].apply(clean_val).astype(int) if 'Year' in mkt_df.columns else 2026
            
            latest_week = mkt_df['Week'].max()
            latest_year = mkt_df['Year'].max()
            
            wish_data = mkt_df[(mkt_df['Week'] == latest_week) & (mkt_df['Year'] == latest_year)].groupby('ConfigSKU')['Wishlist'].sum().reset_index()
            wish_merged = wish_data.merge(inv_map, left_on='ConfigSKU', right_on=inv_var_col, how='left')
            wish_merged['Total Stock'] = wish_merged[zfs_col] + wish_merged[pf_col]
            wish_merged = wish_merged.rename(columns={name_col: "Article Name"}).sort_values('Wishlist', ascending=False).head(50)
            
            st.dataframe(wish_merged[['ConfigSKU', 'Article Name', 'Wishlist', 'Total Stock', zfs_col, pf_col]].style.format({"Wishlist": "{:,.0f}", "Total Stock": "{:,.0f}"}), hide_index=True, use_container_width=True)

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
            mkt['Month'] = mkt['Month'].apply(clean_val).astype(int) if 'Month' in mkt.columns else 0

            st.subheader("📅 Marketing Period Comparison")
            comp_mode = st.radio("Comparison Mode", ["Weekly", "Monthly"], horizontal=True)
            
            col_p1, col_p2 = st.columns(2)
            if comp_mode == "Weekly":
                years = sorted(mkt['Year'].unique(), reverse=True)
                y1 = col_p1.selectbox("Period 1 Year", years, index=0)
                w1 = col_p1.selectbox("Period 1 Week", sorted(mkt[mkt['Year']==y1]['Week'].unique(), reverse=True), key="w1")
                y2 = col_p2.selectbox("Period 2 Year", years, index=0 if len(years)==1 else 1)
                w2 = col_p2.selectbox("Period 2 Week", sorted(mkt[mkt['Year']==y2]['Week'].unique(), reverse=True), key="w2")
                mkt_p1 = mkt[(mkt['Year']==y1) & (mkt['Week']==w1)]
                mkt_p2 = mkt[(mkt['Year']==y2) & (mkt['Week']==w2)]
            else:
                months = sorted(mkt['Month'].unique(), reverse=True)
                m1_sel = col_p1.selectbox("Period 1 Month", months)
                m2_sel = col_p2.selectbox("Period 2 Month", months)
                mkt_p1 = mkt[mkt['Month'] == m1_sel]
                mkt_p2 = mkt[mkt['Month'] == m2_sel]

            def get_stats(df_subset):
                s = df_subset[['Spend', 'GMV', 'Wish', 'Clicks', 'Sold']].sum()
                s['ROAS'] = s['GMV'] / s['Spend'] if s['Spend'] > 0 else 0
                return s

            s1, s2 = get_stats(mkt_p1), get_stats(mkt_p2)
            mk_c1, mk_c2, mk_c3, mk_c4 = st.columns(4)
            mk_c1.metric("Spend", f"€{s1['Spend']:,.0f}", delta=f"{((s1['Spend']/s2['Spend'])-1):.1%}" if s2['Spend']>0 else None, delta_color="inverse")
            mk_c2.metric("GMV", f"€{s1['GMV']:,.0f}", delta=f"{((s1['GMV']/s2['GMV'])-1):.1%}" if s2['GMV']>0 else None)
            mk_c3.metric("ROAS", f"{s1['ROAS']:.2f}x", delta=f"{((s1['ROAS']/s2['ROAS'])-1):.1%}" if s2['ROAS']>0 else None)
            mk_c4.metric("Wishlist", f"{s1['Wish']:,.0f}", delta=f"{((s1['Wish']/s2['Wish'])-1):.1%}" if s2['Wish']>0 else None)

            st.markdown("---")
            st.subheader("🚻 Performance per Gender")
            if 'Gender' in mkt.columns:
                g_perf = mkt_p1.groupby('Gender')[['Spend', 'GMV']].sum()
                g_perf['ROAS'] = g_perf['GMV'] / g_perf['Spend'].replace(0, 1)
                st.dataframe(g_perf.style.format({'Spend': '€{:,.0f}', 'GMV': '€{:,.0f}', 'ROAS': '{:.2f}x'}), use_container_width=True)

    with tab4:
        st.subheader("🌍 Market Development")
        if f_market_cw and f_market_lw:
            df_mcw = load_csv_robust(f_market_cw)
            df_mlw = load_csv_robust(f_market_lw)
            
            for d in [df_mcw, df_mlw]:
                d['NMV_Clean'] = d['NMV'].apply(clean_val)
                d['Basket'] = d['Add to basket'].apply(clean_val)
                d['Sold'] = d['Sold articles'].apply(clean_val)
                d['Offerable'] = d['Offerable articles'].apply(clean_val)
                d['Conv'] = d['Conversion rate'].apply(clean_val)

            total_nmv = df_mcw['NMV_Clean'].sum()
            df_mcw['Market Share'] = df_mcw['NMV_Clean'] / total_nmv if total_nmv > 0 else 0
            df_mcw['Drop-out Rate'] = (df_mcw['Basket'] - df_mcw['Sold']) / df_mcw['Basket'].replace(0, 1)
            
            # Live Articles calculation (from inventory if possible)
            if 'country' in df_inv.columns:
                live_map = df_inv[df_inv['visibility'].str.lower() == 'live'].groupby('country').size().to_dict()
                df_mcw['LIVE Articles'] = df_mcw['Country'].str.lower().map(live_map).fillna(0)
            
            comp_market = df_mcw.merge(df_mlw[['Country', 'NMV_Clean']], on='Country', suffixes=('', '_LW'))
            comp_market['WoW Growth'] = (comp_market['NMV_Clean'] - comp_market['NMV_Clean_LW']) / comp_market['NMV_Clean_LW'].replace(0, 1)
            
            st.dataframe(comp_market[['Country', 'NMV_Clean', 'Market Share', 'WoW Growth', 'Offerable', 'Conv', 'Drop-out Rate']].sort_values('NMV_Clean', ascending=False).style.format({
                'NMV_Clean': '€{:,.0f}', 'Market Share': '{:.1%}', 'WoW Growth': '{:.1%}', 'Conv': '{:.2%}', 'Drop-out Rate': '{:.1%}'
            }), hide_index=True, use_container_width=True)
        else:
            st.info("Upload Market CW and LW files in the sidebar to unlock this tab.")

    with tab5:
        st.subheader("🔄 Z-Hybrid Performance")
        if f_hybrid:
            hy = load_csv_robust(f_hybrid)
            hy.columns = [c.strip() for c in hy.columns]
            v_col, l_col, d_col = 'Ordervärde ex.moms', 'Ordervärde ex. moms LY', 'Datum'
            if v_col in hy.columns:
                hy_clean = hy[hy[d_col].str.lower() != 'total'].copy()
                hy_clean['Sales_CW'] = hy_clean[v_col].apply(clean_val)
                total_hy = hy_clean['Sales_CW'].sum()
                st.metric("Hybrid Share of Total", f"{(total_hy/nmv_cw_sek):.1%}")
                st.dataframe(hy_clean.groupby([d_col])[['Sales_CW']].sum(), use_container_width=True)

    with tab6:
        st.subheader("📝 Strategic Commentary & To-Do List")
        c_perf = (nmv_cw_sek / nmv_lw_sek) - 1 if nmv_lw_sek > 0 else 0
        
        st.markdown("### 🔍 Key Insights")
        if c_perf > 0:
            st.success(f"Positive momentum: Sales are up {c_perf:.1%} vs last week. High conversion markets are driving the growth.")
        else:
            st.error(f"Sales decline: Performance is down {c_perf:.1%} vs last week. Review high drop-out rate markets.")

        # Wishlist Insight
        if f_mkt:
            low_stock_wish = wish_merged[wish_merged['Total Stock'] < 10].shape[0]
            if low_stock_wish > 0:
                st.warning(f"Inventory Alert: {low_stock_wish} items in the Top 50 Wishlist have critical stock levels (<10 units).")

        st.markdown("### 🚀 To-Do List (Next Week)")
        st.write("- [ ] **Restock High-Demand Items:** Prioritize items found in the Top 50 Wishlist table with low 'Total Stock'.")
        if f_mkt and 's1' in locals():
            if s1['ROAS'] < 4:
                st.write("- [ ] **Marketing Optimization:** Current ROAS is below target. Shift budget from low-performing Gender categories to high-GMV segments.")
        st.write("- [ ] **Market Expansion:** Review markets with high 'Drop-out Rates' - consider adjusting pricing or shipping messaging in those regions.")

else:
    st.info("Awaiting file uploads 1-4 in the sidebar to generate board.")
