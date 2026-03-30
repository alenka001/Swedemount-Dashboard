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
    [data-testid="stDataFrame"] td, [data-testid="stDataFrame"] th { padding: 1px 4px !important; }
    [data-testid="stDataFrame"] { font-weight: 500 !important; font-size: 13px !important; }
    [data-testid="stDataFrame"] th { background-color: #f0f2f6 !important; color: black !important; font-weight: bold !important; }
    </style>
    """, unsafe_allow_html=True)

# --- ADVANCED CLEANING FUNCTION ---
def clean_val(val):
    if pd.isna(val) or val == '' or str(val).lower() == 'undefined': return 0.0
    s = str(val).strip().replace('€', '').replace('%', '').replace('kr', '')
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
        for col, grp in zip([c1, c2], ['Brand', 'Category']):
            cw_g = df_cw.groupby(grp)['NMV_SEK'].sum().reset_index().rename(columns={'NMV_SEK': 'CW_kr'})
            ly_g = df_ly.groupby(grp)['NMV_SEK'].sum().reset_index().rename(columns={'NMV_SEK': 'LY_kr'})
            m = cw_g.merge(ly_g, on=grp, how='left').fillna(0)
            m['Growth %'] = (m['CW_kr'] - m['LY_kr']) / m['LY_kr'].replace(0, 1)
            m['Status'] = m['Growth %'].apply(lambda x: "🟢 Growth" if x > 0.05 else ("🔻 Decline" if x < -0.05 else "➖ Stable"))
            col.dataframe(m.sort_values('CW_kr', ascending=False), hide_index=True, use_container_width=True)

    with tab2:
        st.subheader("Top 50 Articles (Compressed)")
        cw_art = df_cw.groupby(['Brand', 'Article variant', 'Zalando article variant'])[['NMV_EUR', 'Sold articles']].sum().reset_index()
        lw_art = df_lw.groupby('Article variant')['NMV_EUR'].sum().reset_index()
        top = cw_art.merge(lw_art, on='Article variant', how='left', suffixes=('_CW', '_LW')).fillna(0)
        top = top.sort_values('NMV_EUR_CW', ascending=False).head(50)
        st.dataframe(top, hide_index=True, use_container_width=True)

    with tab3:
        if f_mkt:
            mkt = load_csv_robust(f_mkt)
            mkt.columns = [c.replace(' ', '') for c in mkt.columns]
            mkt['Week'] = mkt['Week'].apply(clean_val)
            
            # --- MARKETING TOP LEVEL (CW vs LW) ---
            weeks = sorted(mkt['Week'].dropna().unique())
            if len(weeks) >= 2:
                cw_w, lw_w = weeks[-1], weeks[-2]
                m_cols = {'Spend': 'Budgetspent', 'GMV': 'GMV', 'Wish': 'Addtowishlist', 'Clicks': 'Clicks', 'Sold': 'Itemssold'}
                for k, v in m_cols.items(): mkt[k] = mkt[v].apply(clean_val)
                
                m_cw = mkt[mkt['Week'] == cw_w]; m_lw = mkt[mkt['Week'] == lw_w]
                s_cw = m_cw[['Spend', 'GMV', 'Wish', 'Clicks', 'Sold']].sum()
                s_lw = m_lw[['Spend', 'GMV', 'Wish', 'Clicks', 'Sold']].sum()
                
                mk1, mk2, mk3, mk4, mk5 = st.columns(5)
                mk1.metric("Ad Spend", f"€{s_cw['Spend']:,.0f}")
                mk2.metric("Total GMV", f"€{s_cw['GMV']:,.0f}", delta=f"€{s_cw['GMV']-s_lw['GMV']:,.0f}")
                mk3.metric("ROAS", f"{(s_cw['GMV']/s_cw['Spend'] if s_cw['Spend']>0 else 0):.2f}x")
                mk4.metric("Wishlists", f"{s_cw['Wish']:,.0f}")
                mk5.metric("CVR", f"{(s_cw['Sold']/s_cw['Clicks'] if s_cw['Clicks']>0 else 0):.1%}")

            # --- CAMPAIGN PERFORMANCE YoY ---
            st.markdown("---")
            st.subheader("📣 Campaign Performance vs Last Year (LY)")
            if 'Year' in mkt.columns:
                mkt['Year'] = mkt['Year'].apply(clean_val)
                years = sorted(mkt['Year'].unique())
                if len(years) >= 2:
                    curr_yr, last_yr = years[-1], years[-2]
                    
                    cw_yr_data = mkt[mkt['Year'] == curr_yr].groupby('ZMSCampaign')[['Spend', 'GMV']].sum().reset_index()
                    ly_yr_data = mkt[mkt['Year'] == last_yr].groupby('ZMSCampaign')[['Spend', 'GMV']].sum().reset_index()
                    
                    m_comp = cw_yr_data.merge(ly_yr_data, on='ZMSCampaign', how='left', suffixes=('_CW', '_LY')).fillna(0)
                    m_comp['ROAS CW'] = (m_comp['GMV_CW'] / m_comp['Spend_CW']).fillna(0)
                    m_comp['Spend YoY %'] = (m_comp['Spend_CW'] - m_comp['Spend_LY']) / m_comp['Spend_LY'].replace(0, 1)
                    m_comp['GMV YoY %'] = (m_comp['GMV_CW'] - m_comp['GMV_LY']) / m_comp['GMV_LY'].replace(0, 1)
                    
                    m_comp['Status'] = m_comp.apply(lambda r: "🆕 New" if r['Spend_LY'] == 0 else ("📈 Scaling" if r['GMV YoY %'] > 0.1 else "📉 Optimizing"), axis=1)
                    
                    st.dataframe(
                        m_comp[['Status', 'ZMSCampaign', 'Spend_CW', 'Spend YoY %', 'GMV_CW', 'GMV YoY %', 'ROAS CW']],
                        column_config={
                            "Spend_CW": st.column_config.NumberColumn("Spend €", format="€%.2f"),
                            "Spend YoY %": st.column_config.NumberColumn("Spend vs LY", format="%.1f%%"),
                            "GMV_CW": st.column_config.NumberColumn("GMV €", format="€%.0f"),
                            "GMV YoY %": st.column_config.NumberColumn("GMV vs LY", format="%.1f%%"),
                            "ROAS CW": st.column_config.NumberColumn("ROAS", format="%.2fx")
                        },
                        hide_index=True, use_container_width=True
                    )
            else:
                st.warning("Year column missing in marketing file for YoY comparison.")

    with tab4:
        st.subheader("🔄 Z-Hybrid Performance & Fulfillment Share")
        if f_hybrid:
            hy = load_csv_robust(f_hybrid)
            hy.columns = [c.strip() for c in hy.columns]
            val_col, ly_col, date_col = 'Ordervärde ex.moms', 'Ordervärde ex. moms LY', 'Datum'
            
            if val_col in hy.columns:
                hy_clean = hy[hy[date_col].str.lower() != 'total'].copy()
                hy_clean['Sales_CW'] = hy_clean[val_col].apply(clean_val)
                hy_clean['Sales_LY'] = hy_clean[ly_col].apply(clean_val) if ly_col in hy_clean.columns else 0.0
                total_hybrid_cw = hy_clean['Sales_CW'].sum()
                total_hybrid_ly = hy_clean['Sales_LY'].sum()
                hybrid_share = (total_hybrid_cw / nmv_cw_sek) if nmv_cw_sek > 0 else 0
                
                h1, h2, h3 = st.columns(3)
                h1.metric("Total Z-Hybrid Sales", f"{total_hybrid_cw:,.0f} kr")
                h2.metric("Total Zalando Sales (SEK)", f"{nmv_cw_sek:,.0f} kr")
                h3.metric("Andel Z-hybrid (Share)", f"{hybrid_share:.1%}", delta=f"{((total_hybrid_cw/total_hybrid_ly)-1):.1%} YoY" if total_hybrid_ly > 0 else None)
                
                st.markdown("---")
                st.write("**Daily Comparison (SEK)**")
                daily = hy_clean.groupby([date_col, 'Veckodag'])[['Sales_CW', 'Sales_LY']].sum().reset_index()
                st.dataframe(daily, hide_index=True, use_container_width=True, column_config={"Sales_CW": st.column_config.NumberColumn("Current Year (kr)", format="%d kr"), "Sales_LY": st.column_config.NumberColumn("Last Year (kr)", format="%d kr")})
else:
    st.info("Awaiting file uploads in the sidebar.")