import streamlit as st
import pandas as pd
import os
import warnings
import re

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
def clean_val(val, is_pct=False):
    if pd.isna(val) or val == '' or str(val).lower() == 'undefined': return 0.0
    s = str(val).strip().replace('€', '').replace('kr', '').replace('SEK', '')
    has_pct_sign = '%' in s
    s = s.replace('%', '')
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

st.sidebar.subheader("🌍 Market Development")
f_market_cw = st.sidebar.file_uploader("Market Performance CW", type="csv")
f_market_lw = st.sidebar.file_uploader("Market Performance LW", type="csv")

# --- MAIN LOGIC ---
if all([f_cw, f_lw, f_ly, f_inv]):
    df_cw = load_csv_robust(f_cw)
    df_lw = load_csv_robust(f_lw)
    df_ly = load_csv_robust(f_ly)
    df_inv = load_csv_robust(f_inv)
    
    # Process Inventory - PIVOT BY VARIANT
    inv_var_col = next((c for c in df_inv.columns if 'zalando_article_variant' in c.lower()), 'zalando_article_variant')
    name_col = next((c for c in df_inv.columns if 'article_name' in c.lower()), 'article_name')
    zfs_col = next((c for c in df_inv.columns if 'zfs' in c.lower()), 'sellable_zfs_stock')
    pf_col = next((c for c in df_inv.columns if 'pf' in c.lower()), 'sellable_pf_stock')
    
    df_inv[zfs_col] = df_inv[zfs_col].apply(clean_val)
    df_inv[pf_col] = df_inv[pf_col].apply(clean_val)
    # Pivot logic: Group by config to get total stock levels
    inv_pivoted = df_inv.groupby(inv_var_col).agg({
        name_col: 'first',
        zfs_col: 'sum',
        pf_col: 'sum'
    }).reset_index()
    inv_pivoted['Total Stock'] = inv_pivoted[zfs_col] + inv_pivoted[pf_col]

    for df in [df_cw, df_lw, df_ly]:
        src_sold_col = next((c for c in df.columns if 'sold articles' in c.lower()), None)
        df['NMV_EUR'] = df['NMV'].apply(clean_val)
        df['Sold_Units'] = df[src_sold_col].apply(clean_val) if src_sold_col else 0.0
        df['NMV_SEK'] = df['NMV_EUR'] * ex_rate

    nmv_cw_sek = df_cw['NMV_SEK'].sum()
    nmv_lw_sek = df_lw['NMV_SEK'].sum()
    nmv_ly_sek = df_ly['NMV_SEK'].sum()

    st.title("🚀 Weekly Strategic Marketplace Board")

    # Metrics
    st.subheader("📊 Performance Overview")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Current NMV", f"€{nmv_cw_sek/ex_rate:,.0f}")
    m2.metric("vs LW (SEK)", f"{nmv_cw_sek:,.0f} kr", delta=f"{((nmv_cw_sek/nmv_lw_sek)-1) if nmv_lw_sek>0 else 0:.1%}")
    m3.metric("vs LY (SEK)", f"{nmv_ly_sek:,.0f} kr", delta=f"{((nmv_cw_sek/nmv_ly_sek)-1) if nmv_ly_sek>0 else 0:.1%}")
    m4.metric("vs Budget", f"{weekly_budget_sek:,.0f} kr", delta=f"{(nmv_cw_sek/weekly_budget_sek-1):.1%}")
    m5.metric("vs Prognos", f"{weekly_prognos_sek:,.0f} kr", delta=f"{(nmv_cw_sek/weekly_prognos_sek-1):.1%}")

    st.markdown("---")
    tabs = st.tabs(["📈 Health", "🏆 Top 50 Articles", "📣 Marketing", "🌍 Market Dev", "🔄 Z-Hybrid", "📝 Commentary"])

    with tabs[1]:
        st.subheader("🏆 Top 50 Sales & Wishlist")
        # Sales Table
        st.write("**Top 50 by Revenue**")
        top_sales = df_cw.groupby('Article variant')[['NMV_EUR', 'Sold_Units']].sum().reset_index()
        top_sales = top_sales.merge(inv_pivoted, left_on='Article variant', right_on=inv_var_col, how='left')
        st.dataframe(top_sales.sort_values('NMV_EUR', ascending=False).head(50).style.format({
            "NMV_EUR": "€{:,.0f}", "Sold_Units": "{:,.0f}", "Total Stock": "{:,.0f}", zfs_col: "{:,.0f}", pf_col: "{:,.0f}"
        }), hide_index=True, use_container_width=True)

        if f_mkt:
            st.markdown("---")
            st.subheader("❤️ Top 50 Most Added to Wishlist (Latest Week)")
            mkt_wish = load_csv_robust(f_mkt)
            mkt_wish.columns = [c.replace(' ', '') for c in mkt_wish.columns]
            mkt_wish['Wishlist'] = mkt_wish['Addtowishlist'].apply(clean_val)
            mkt_wish['Week'] = mkt_wish['Week'].apply(clean_val).astype(int)
            latest_w = mkt_wish['Week'].max()
            
            wish_data = mkt_wish[mkt_wish['Week'] == latest_w].groupby('ConfigSKU')['Wishlist'].sum().reset_index()
            # Map against pivoted inventory
            wish_merged = wish_data.merge(inv_pivoted, left_on='ConfigSKU', right_on=inv_var_col, how='left')
            st.dataframe(wish_merged.sort_values('Wishlist', ascending=False).head(50)[['ConfigSKU', name_col, 'Wishlist', 'Total Stock', zfs_col, pf_col]].style.format({
                "Wishlist": "{:,.0f}", "Total Stock": "{:,.0f}", zfs_col: "{:,.0f}", pf_col: "{:,.0f}"
            }), hide_index=True, use_container_width=True)

    with tabs[2]:
        if f_mkt:
            mkt = load_csv_robust(f_mkt)
            mkt.columns = [c.replace(' ', '') for c in mkt.columns]
            for col in ['Budgetspent', 'GMV', 'Addtowishlist', 'Itemssold']:
                mkt[col] = mkt[col].apply(clean_val)
            mkt['Week'] = mkt['Week'].apply(clean_val).astype(int)
            mkt['Year'] = mkt['Year'].apply(clean_val).astype(int) if 'Year' in mkt.columns else 2026

            st.subheader("📅 Period Comparison")
            c_p1, c_p2 = st.columns(2)
            y1 = c_p1.selectbox("Year P1", sorted(mkt['Year'].unique(), reverse=True))
            w1 = c_p1.selectbox("Week P1", sorted(mkt[mkt['Year']==y1]['Week'].unique(), reverse=True))
            y2 = c_p2.selectbox("Year P2", sorted(mkt['Year'].unique(), reverse=True), index=min(1, len(mkt['Year'].unique())-1))
            w2 = c_p2.selectbox("Week P2", sorted(mkt[mkt['Year']==y2]['Week'].unique(), reverse=True))

            p1_df = mkt[(mkt['Year']==y1) & (mkt['Week']==w1)]
            p2_df = mkt[(mkt['Year']==y2) & (mkt['Week']==w2)]

            # Campaign Performance RESTORED
            st.markdown("### 📣 Campaign Analytics (P1 vs P2)")
            cp1 = p1_df.groupby('ZMSCampaign')[['Budgetspent', 'GMV']].sum()
            cp2 = p2_df.groupby('ZMSCampaign')[['Budgetspent', 'GMV']].sum()
            camp_comp = cp1.join(cp2, rsuffix='_P2', how='left').fillna(0).reset_index()
            camp_comp['ROAS P1'] = camp_comp['GMV'] / camp_comp['Budgetspent'].replace(0, 1)
            camp_comp['ROAS P2'] = camp_comp['GMV_P2'] / camp_comp['Budgetspent_P2'].replace(0, 1)
            camp_comp['Delta ROAS'] = camp_comp['ROAS P1'] - camp_comp['ROAS P2']

            def style_camp(row):
                return ['color: #28a745' if row['Delta ROAS'] > 0 else 'color: #dc3545'] * len(row)

            st.dataframe(camp_comp[['ZMSCampaign', 'Budgetspent', 'GMV', 'ROAS P1', 'Delta ROAS']].style.format({
                'Budgetspent': '€{:,.0f}', 'GMV': '€{:,.0f}', 'ROAS P1': '{:.2f}x', 'Delta ROAS': '{:+.2f}'
            }).apply(style_camp, axis=1), hide_index=True, use_container_width=True)

            # Gender Breakdown
            st.markdown("### 🚻 Gender Performance (P1)")
            if 'Gender' in mkt.columns:
                g_df = p1_df.groupby('Gender')[['Budgetspent', 'GMV']].sum()
                g_df['ROAS'] = g_df['GMV'] / g_df['Budgetspent'].replace(0, 1)
                st.dataframe(g_df.style.format({'Budgetspent': '€{:,.0f}', 'GMV': '€{:,.0f}', 'ROAS': '{:.2f}x'}), use_container_width=True)

    with tabs[3]:
        st.subheader("🌍 Market Development")
        if f_market_cw and f_market_lw:
            m_cw = load_csv_robust(f_market_cw)
            m_lw = load_csv_robust(f_market_lw)
            for df_m in [m_cw, m_lw]:
                df_m['NMV_Clean'] = df_m['NMV'].apply(clean_val)
                df_m['Basket'] = df_m['Add to basket'].apply(lambda x: clean_val(x, is_pct=True))
                df_m['Conv'] = df_m['Conversion rate'].apply(lambda x: clean_val(x, is_pct=True))
                df_m['Sold'] = df_m['Sold articles'].apply(clean_val)
                df_m['Dropout'] = (df_m['Basket'] - df_m['Conv']) / df_m['Basket'].replace(0, 1) # Simplified logic for dropout

            m_merged = m_cw.merge(m_lw[['Country', 'NMV_Clean']], on='Country', suffixes=('', '_LW'))
            m_merged['Share %'] = m_merged['NMV_Clean'] / m_merged['NMV_Clean'].sum()
            m_merged['Growth WoW'] = (m_merged['NMV_Clean'] / m_merged['NMV_Clean_LW']) - 1
            
            st.dataframe(m_merged[['Country', 'NMV_Clean', 'Share %', 'Growth WoW', 'Conv', 'Dropout']].sort_values('NMV_Clean', ascending=False).style.format({
                'NMV_Clean': '€{:,.0f}', 'Share %': '{:.1%}', 'Growth WoW': '{:.1%}', 'Conv': '{:.2%}', 'Dropout': '{:.1%}'
            }), hide_index=True, use_container_width=True)

    with tabs[5]:
        st.subheader("📝 Strategic Analysis & To-Dos")
        col_c1, col_c2 = st.columns(2)
        
        with col_c1:
            st.markdown("### 🏆 Top Focus Articles (Marketing)")
            if f_mkt:
                top5 = camp_comp.sort_values('GMV', ascending=False).head(5)
                for i, row in top5.iterrows():
                    st.write(f"✅ **{row['ZMSCampaign']}**: High ROAS ({row['ROAS P1']:.2f}x). Maintain budget.")
                
                bad5 = camp_comp[camp_comp['Budgetspent'] > 100].sort_values('ROAS P1').head(3)
                for i, row in bad5.iterrows():
                    st.write(f"⚠️ **{row['ZMSCampaign']}**: Underperforming ({row['ROAS P1']:.2f}x). Review targeting.")

        with col_c2:
            st.markdown("### 📍 Country Focus")
            if f_market_cw and f_market_lw:
                low_conv = m_merged.sort_values('Conv').head(2)
                for i, row in low_conv.iterrows():
                    st.error(f"Attention: **{row['Country']}** has the lowest conversion ({row['Conv']:.2%}).")
                high_drop = m_merged.sort_values('Dropout', ascending=False).head(2)
                for i, row in high_drop.iterrows():
                    st.warning(f"Strategy: **{row['Country']}** shows high dropout. Check pricing vs competitors.")

        st.markdown("### 🚀 To-Do List")
        st.write("- [ ] **Replenishment:** Check stock for top 5 Wishlist items with < 50 units total stock.")
        st.write("- [ ] **Marketing:** Shift budget from 'Attention' campaigns to 'Top Focus' ZMS campaigns.")
        st.write("- [ ] **Market Action:** Investigate why conversion dropped in markets with > 10% WoW decline.")

else:
    st.info("Awaiting file uploads 1-4 to generate board.")
