import streamlit as st
import pandas as pd
import warnings
import re

# Tysta tekniska varningar
warnings.filterwarnings('ignore', category=pd.errors.DtypeWarning)

# --- SET PAGE CONFIG ---
st.set_page_config(page_title="Weekly Strategic Dashboard", layout="wide", page_icon="📊")

# --- CSS FÖR EN PROFESSIONELL OCH KOMPAKT DESIGN ---
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

# --- UTILITIES / VERKTYG ---
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

# --- SIDEBAR / KONTROLLER ---
st.sidebar.header("⚙️ Kontroller")
ex_rate = st.sidebar.number_input("Växelkurs (1€ = X SEK)", value=10.66)
weekly_budget_sek = st.sidebar.number_input("Budget (SEK)", value=4300000)
weekly_prognos_sek = st.sidebar.number_input("Prognos (SEK)", value=4500000)

st.sidebar.markdown("---")
st.sidebar.header("📂 Datauppladdning")
f_cw = st.sidebar.file_uploader("1. Försäljning CW (CSV)", type="csv")
f_lw = st.sidebar.file_uploader("2. Försäljning LW (CSV)", type="csv")
f_ly = st.sidebar.file_uploader("3. Försäljning LY (CSV)", type="csv")
f_inv = st.sidebar.file_uploader("4. Lagerrapport (CSV)", type="csv")
f_mkt = st.sidebar.file_uploader("5. Marknadsföring (CSV)", type="csv")
f_hybrid = st.sidebar.file_uploader("6. Z-Hybrid (CSV)", type="csv")
f_mcw = st.sidebar.file_uploader("7. Marknad CW (Land)", type="csv")
f_mlw = st.sidebar.file_uploader("8. Marknad LW (Land)", type="csv")

# --- HUVUDLOGIK ---
if all([f_cw, f_lw, f_ly, f_inv]):
    df_cw_raw = load_csv_robust(f_cw)
    df_lw_raw = load_csv_robust(f_lw)
    df_ly_raw = load_csv_robust(f_ly)
    df_inv_raw = load_csv_robust(f_inv)

    # 1. Bearbeta Lager-data
    inv_sku_col, inv_name_col = 'zalando_article_variant', 'article_name'
    zfs_col, pf_col = 'sellable_zfs_stock', 'sellable_pf_stock'

    df_inv_raw[inv_sku_col] = df_inv_raw[inv_sku_col].str.strip().str.upper()
    df_inv_raw[zfs_col] = df_inv_raw[zfs_col].apply(clean_val)
    df_inv_raw[pf_col] = df_inv_raw[pf_col].apply(clean_val)

    inv_map = df_inv_raw.groupby(inv_sku_col).agg({inv_name_col: 'first', zfs_col: 'sum', pf_col: 'sum'}).reset_index()
    inv_map['Total Stock'] = inv_map[zfs_col] + inv_map[pf_col]
    
    # 2. Bearbeta Försäljning (Robust SKU-lookup)
    def process_sales(df):
        df.columns = [c.strip() for c in df.columns]
        nmv_col = next((c for c in df.columns if c.lower() == 'nmv'), 'NMV')
        df['NMV_EUR'] = df[nmv_col].apply(clean_val)
        sold_col = next((c for c in df.columns if 'sold articles' in c.lower()), 'Sold articles')
        df['Sold'] = df[sold_col].apply(clean_val)
        sku_col = next((c for c in df.columns if 'zalando article variant' in c.lower()), None)
        if not sku_col: sku_col = next((c for c in df.columns if 'variant' in c.lower()), df.columns[0])
        df['join_key'] = df[sku_col]
        df['Zalando article variant'] = df[sku_col]
        if 'Article variant' not in df.columns:
            df['Article variant'] = df[next((c for c in df.columns if c.lower() == 'article variant'), sku_col)]
        return df

    df_cw = process_sales(df_cw_raw)
    df_lw = process_sales(df_lw_raw)
    df_ly = process_sales(df_ly_raw)
    
    nmv_cw_sek = df_cw['NMV_EUR'].sum() * ex_rate
    nmv_lw_sek = df_lw['NMV_EUR'].sum() * ex_rate
    nmv_ly_sek = df_ly['NMV_EUR'].sum() * ex_rate

    st.title("🚀 Weekly Strategic Marketplace Board")

    # Topp-rutor (SEK/EUR)
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Current NMV", f"€{nmv_cw_sek/ex_rate:,.0f}")
    m2.metric("vs LW (SEK)", f"{nmv_cw_sek:,.0f} kr", delta=f"{((nmv_cw_sek/nmv_lw_sek)-1):.1%}")
    m3.metric("vs LY (SEK)", f"{nmv_ly_sek:,.0f} kr", delta=f"{((nmv_cw_sek/nmv_ly_sek)-1):.1%}")
    m4.metric("Budget Reach", f"{(nmv_cw_sek / weekly_budget_sek):.1%}", delta=f"Mål: {weekly_budget_sek:,.0f} kr")
    m5.metric("Prognos Reach", f"{(nmv_cw_sek / weekly_prognos_sek):.1%}", delta=f"Mål: {weekly_prognos_sek:,.0f} kr")

    st.markdown("---")
    tabs = st.tabs(["📈 Hälsa", "🏆 Topp 50 Omsättning", "❤️ Wishlist Topp 50", "📣 Marknadsföring", "🌍 Marknadsutveckling", "🔄 Z-Hybrid", "📝 Analys"])

    # --- FLIK 0: HÄLSA ---
    with tabs[0]:
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

    # --- FLIK 1: TOPP 50 REVENUE ---
    with tabs[1]:
        st.subheader("🏆 Topp 50 Revenue Performance & Stock Alerts")
        cw_top = df_cw.groupby(['join_key', 'Article variant'])[['NMV_EUR', 'Sold']].sum().reset_index()
        cw_top['Rank_CW'] = cw_top['NMV_EUR'].rank(ascending=False, method='min')
        lw_top = df_lw.groupby(['join_key'])[['NMV_EUR']].sum().reset_index().rename(columns={'join_key': 'Zalando article variant'})
        lw_top['Rank_LW'] = lw_top['NMV_EUR'].rank(ascending=False, method='min')
        t50 = cw_top.merge(lw_top[['Zalando article variant', 'Rank_LW']], left_on='join_key', right_on='Zalando article variant', how='left')
        t50 = t50.merge(inv_map, left_on='join_key', right_on=inv_sku_col, how='left').fillna(0)
        t50['Status'] = t50.apply(lambda r: "🆕" if r['Rank_LW'] == 0 else ("⬆️" if r['Rank_CW'] < r['Rank_LW'] else ("⬇️" if r['Rank_CW'] > r['Rank_LW'] else "➡️")), axis=1)
        t50_f = t50.sort_values('Rank_CW').head(50)
        disp = t50_f.rename(columns={'join_key': 'SKU', inv_name_col: 'Article Name', 'NMV_EUR': 'NMV €', zfs_col: 'Stock ZFS', pf_col: 'Stock PF'})
        
        def highlight_stock_alert(row):
            styles = [''] * len(row)
            sold_val = row['Sold']
            if 0 < row['Stock ZFS'] < sold_val: styles[row.index.get_loc('Stock ZFS')] = 'background-color: #ffcccc; color: #990000; font-weight: bold;'
            if 0 < row['Stock PF'] < sold_val: styles[row.index.get_loc('Stock PF')] = 'background-color: #ffcccc; color: #990000; font-weight: bold;'
            return styles

        st.dataframe(disp[['Status', 'SKU', 'Article Name', 'NMV €', 'Sold', 'Stock ZFS', 'Stock PF']].style.format({
            'NMV €': '€{:,.0f}', 'Sold': '{:,.0f}', 'Stock ZFS': '{:,.0f}', 'Stock PF': '{:,.0f}'
        }).apply(highlight_stock_alert, axis=1), hide_index=True, use_container_width=True)

    # --- FLIK 2: WISHLIST ---
    with tabs[2]:
        if f_mkt:
            st.subheader("❤️ Topp 50 Mest önskade (Wishlist)")
            m_wish = load_csv_robust(f_mkt)
            m_wish.columns = [c.replace(' ', '') for c in m_wish.columns]
            m_wish['W_Clean'] = m_wish['Week'].apply(clean_val)
            m_wish['Wish_Numeric'] = m_wish['Addtowishlist'].apply(clean_val)
            l_week = m_wish['W_Clean'].max()
            w_data = m_wish[m_wish['W_Clean'] == l_week].groupby('ConfigSKU')[['Wish_Numeric']].sum().reset_index()
            w_data['ConfigSKU'] = w_data['ConfigSKU'].str.strip().str.upper()
            w_merged = w_data.merge(inv_map, left_on='ConfigSKU', right_on=inv_sku_col, how='left').sort_values('Wish_Numeric', ascending=False).head(50)
            st.dataframe(w_merged[['ConfigSKU', inv_name_col, 'Wish_Numeric', 'Total Stock', zfs_col, pf_col]].style.format(precision=0), hide_index=True, use_container_width=True)
        else:
            st.info("Ladda upp Marknadsförings-CSV för att se Wishlist-data.")

    # --- FLIK 3: MARKNADSFÖRING (SUMMERING FIXAD) ---
    with tabs[3]:
        if f_mkt:
            st.subheader("📣 Marketing Performance Overview")
            mkt_df = load_csv_robust(f_mkt)
            mkt_df.columns = [c.replace(' ', '') for c in mkt_df.columns]
            m_cols = ['Budgetspent', 'GMV', 'Addtowishlist', 'Clicks', 'Itemssold', 'Viewableadimpressions', 'PDPviews']
            for c in m_cols:
                if c in mkt_df.columns:
                    mkt_df[c] = pd.to_numeric(mkt_df[c].apply(clean_val), errors='coerce').fillna(0.0)
            
            mkt_df['W_Clean'] = mkt_df['Week'].apply(clean_val)
            w_list = sorted(mkt_df['W_Clean'].unique(), reverse=True)
            sel_w1 = st.selectbox("Aktiv Vecka", w_list, index=0)
            sel_w2 = st.selectbox("Jämförelse Vecka", w_list, index=min(1, len(w_list)-1))

            p1, p2 = mkt_df[mkt_df['W_Clean'] == sel_w1], mkt_df[mkt_df['W_Clean'] == sel_w2]

            def get_m_stats(df_sub, nmv_sek_val):
                s = df_sub[m_cols].sum()
                nmv_eur = (nmv_sek_val/ex_rate) if nmv_sek_val > 0 else 0
                return {
                    'Spend': s['Budgetspent'], 'GMV': s['GMV'], 'Wish': s['Addtowishlist'], 
                    'PDP': s['PDPviews'], 'Impressions': s['Viewableadimpressions'],
                    'ROAS': s['GMV']/s['Budgetspent'] if s['Budgetspent'] > 0 else 0,
                    'COS': s['Budgetspent']/s['GMV'] if s['GMV'] > 0 else 0,
                    'Blended': s['Budgetspent']/nmv_eur if nmv_eur > 0 else 0
                }

            ms1, ms2 = get_m_stats(p1, nmv_cw_sek), get_m_stats(p2, nmv_lw_sek)
            r1, r2, r3, r4, r5, r6 = st.columns(6)
            r1.metric("Ad Spend", f"€{ms1['Spend']:,.0f}", delta=f"{(ms1['Spend']/ms2['Spend']-1):.0%}" if ms2['Spend']>0 else None, delta_color="inverse")
            r2.metric("Marketing GMV", f"€{ms1['GMV']:,.0f}", delta=f"{(ms1['GMV']/ms2['GMV']-1):.0%}" if ms2['GMV']>0 else None)
            r3.metric("Total ROAS", f"{ms1['ROAS']:,.1f}x", delta=f"{(ms1['ROAS']-ms2['ROAS']):.1f}x")
            r4.metric("COS", f"{ms1['COS']:.1%}", delta=f"{(ms1['COS']-ms2['COS']):.1%}", delta_color="inverse")
            r5.metric("Blended COS", f"{ms1['Blended']:.1%}", delta=f"{(ms1['Blended']-ms2['Blended']):.1%}", delta_color="inverse")
            r6.metric("Impressions", f"{ms1['Impressions']:,.0f}", delta=f"{(ms1['Impressions']/ms2['Impressions']-1):.0%}" if ms2['Impressions']>0 else None)

            st.markdown("---")
            c_cw = p1.groupby('ZMSCampaign')[['Budgetspent', 'GMV']].sum()
            c_lw = p2.groupby('ZMSCampaign')[['Budgetspent', 'GMV']].sum()
            camp_tab = c_cw.join(c_lw, rsuffix='_LW', how='left').fillna(0).reset_index()
            camp_tab['ROAS CW'] = camp_tab['GMV'] / camp_tab['Budgetspent'].replace(0, 1)
            camp_tab['ROAS LW'] = camp_tab['GMV_LW'] / camp_tab['Budgetspent_LW'].replace(0, 1)
            camp_tab['Delta ROAS'] = camp_tab['ROAS CW'] - camp_tab['ROAS LW']
            
            def style_trends(row):
                styles = [''] * len(row)
                idx = row.index.get_loc('Delta ROAS')
                if row['Delta ROAS'] > 0: styles[idx] = 'color: #28a745; font-weight: bold'
                elif row['Delta ROAS'] < 0: styles[idx] = 'color: #dc3545; font-weight: bold'
                return styles

            st.dataframe(camp_tab[['ZMSCampaign', 'Budgetspent', 'GMV', 'ROAS CW', 'Delta ROAS']].style.format({
                'Budgetspent': '€{:,.0f}', 'GMV': '€{:,.0f}', 'ROAS CW': '{:,.1f}x', 'Delta ROAS': '{:+.1f}x'
            }).apply(style_trends, axis=1), hide_index=True, use_container_width=True)
        else:
            st.info("Ladda upp Marknadsförings-CSV för att se data.")

    # --- FLIK 4: MARKNADSUTVECKLING ---
    with tabs[4]:
        if f_mcw and f_mlw:
            st.subheader("🌍 Marknadsutveckling per Land")
            mcw = load_csv_robust(f_mcw); mlw = load_csv_robust(f_mlw)
            for d in [mcw, mlw]: 
                d['NMV_C'] = d['NMV'].apply(clean_val)
                c_col = next((c for c in d.columns if 'conversion' in c.lower()), 'Conversion rate')
                d['Conv_C'] = d[c_col].apply(lambda x: clean_val(x, is_pct=True))
            mcw['Share %'] = mcw['NMV_C'] / mcw['NMV_C'].sum()
            m_comp = mcw.merge(mlw[['Country', 'NMV_C']], on='Country', suffixes=('', '_LW'))
            m_comp['Growth'] = (m_comp['NMV_C'] / m_comp['NMV_C_LW'].replace(0, 1)) - 1
            st.dataframe(m_comp[['Country', 'NMV_C', 'Share %', 'Growth', 'Conv_C']].style.format({
                'NMV_C': '€{:,.0f}', 'Share %': '{:.1%}', 'Growth': '{:+.1%}', 'Conv_C': '{:.2%}'
            }), hide_index=True, use_container_width=True)
        else:
            st.info("Ladda upp Land-rapporter (Market CW/LW) för att se utveckling.")

    # --- FLIK 5: Z-HYBRID ---
    with tabs[5]:
        if f_hybrid:
            st.subheader("🔄 Z-Hybrid Daglig Försäljning")
            hy = load_csv_robust(f_hybrid)
            hy.columns = [c.strip() for c in hy.columns]
            v_col, l_col, d_col = 'Ordervärde ex.moms', 'Ordervärde ex. moms LY', 'Datum'
            if v_col in hy.columns:
                hy_clean = hy[hy[d_col].str.lower() != 'total'].copy()
                hy_clean['Sales_CW'] = hy_clean[v_col].apply(clean_val)
                hy_clean['Sales_LY'] = hy_clean[l_col].apply(clean_val) if l_col in hy_clean.columns else 0.0
                total_hy = hy_clean['Sales_CW'].sum()
                share = (total_hy / nmv_cw_sek) if nmv_cw_sek > 0 else 0
                h1, h2 = st.columns(2)
                h1.metric("Total Z-Hybrid Sales", f"{total_hy:,.0f} kr")
                h2.metric("Hybrid Share of Sales", f"{share:.1%}")
                st.dataframe(hy_clean.groupby([d_col, 'Veckodag'])[['Sales_CW', 'Sales_LY']].sum().reset_index().style.format({
                    "Sales_CW": "{:,.0f} kr", "Sales_LY": "{:,.0f} kr"
                }), hide_index=True, use_container_width=True)
        else:
            st.info("Ladda upp Z-Hybrid CSV för att se daglig data.")

    # --- FLIK 6: ANALYS ---
    with tabs[6]:
        st.subheader("📝 Weekly Focus Analysis")
        col1, col2 = st.columns(2)
        with col1:
            st.info("**Top Performers**")
            for i, r in t50_f.head(3).iterrows(): st.write(f"🌟 **{r[inv_name_col]}**")
        with col2:
            st.warning("**Stock Attention**")
            crit = t50_f[t50_f['Total Stock'] < t50_f['Sold']].head(3)
            for i, r in crit.iterrows(): st.write(f"⚠️ **{r[inv_name_col]}**: Stock is critical vs sales.")

else:
    st.info("Vänligen ladda upp Försäljning CW, LW, LY och Lagerrapport i sidomenyn för att starta.")
