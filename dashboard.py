import streamlit as st
import pandas as pd
import warnings
import re

# Tysta tekniska varningar
warnings.filterwarnings('ignore', category=pd.errors.DtypeWarning)

# --- SET PAGE CONFIG ---
st.set_page_config(page_title="Weekly Strategic Dashboard", layout="wide", page_icon="📊")

# --- CSS FÖR EN PROFESSIONELL DESIGN ---
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
    .status-box {
        padding: 10px;
        border-radius: 5px;
        margin-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- ROBUST SIFFERRENSARE (FIXAR € 1 454,95 OCH 20 369) ---
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

st.sidebar.markdown("---")
st.sidebar.header("📂 Datauppladdning")
f_cw = st.sidebar.file_uploader("1. Försäljning CW", type="csv")
f_lw = st.sidebar.file_uploader("2. Försäljning LW", type="csv")
f_ly = st.sidebar.file_uploader("3. Försäljning LY", type="csv")
f_inv = st.sidebar.file_uploader("4. Lagerrapport", type="csv")
f_mkt = st.sidebar.file_uploader("5. Marknadsföring Full", type="csv")
f_hybrid = st.sidebar.file_uploader("6. Z-Hybrid", type="csv")
f_mcw = st.sidebar.file_uploader("7. Marknad CW (Land)", type="csv")
f_mlw = st.sidebar.file_uploader("8. Marknad LW (Land)", type="csv")

# --- HUVUDLOGIK ---
if all([f_cw, f_lw, f_ly, f_inv]):
    df_cw_raw = load_csv_robust(f_cw)
    df_lw_raw = load_csv_robust(f_lw)
    df_ly_raw = load_csv_robust(f_ly)
    df_inv_raw = load_csv_robust(f_inv)

    # 1. Bearbeta Lager
    inv_sku_col, inv_name_col = 'zalando_article_variant', 'article_name'
    zfs_col, pf_col = 'sellable_zfs_stock', 'sellable_pf_stock'
    df_inv_raw[inv_sku_col] = df_inv_raw[inv_sku_col].str.strip().str.upper()
    df_inv_raw[zfs_col] = df_inv_raw[zfs_col].apply(clean_val)
    df_inv_raw[pf_col] = df_inv_raw[pf_col].apply(clean_val)
    inv_map = df_inv_raw.groupby(inv_sku_col).agg({inv_name_col: 'first', zfs_col: 'sum', pf_col: 'sum'}).reset_index()
    inv_map['Total Stock'] = inv_map[zfs_col] + inv_map[pf_col]
    
    # 2. Bearbeta Försäljning
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

    df_cw, df_lw, df_ly = process_sales(df_cw_raw), process_sales(df_lw_raw), process_sales(df_ly_raw)
    nmv_cw_sek = df_cw['NMV_EUR'].sum() * ex_rate
    nmv_lw_sek = df_lw['NMV_EUR'].sum() * ex_rate
    nmv_ly_sek = df_ly['NMV_EUR'].sum() * ex_rate

    st.title("🚀 Weekly Strategic Marketplace Board")

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Current NMV", f"€{nmv_cw_sek/ex_rate:,.0f}")
    m2.metric("vs LW (SEK)", f"{nmv_cw_sek:,.0f} kr", delta=f"{((nmv_cw_sek/nmv_lw_sek)-1):.1%}")
    m3.metric("vs LY (SEK)", f"{nmv_ly_sek:,.0f} kr", delta=f"{((nmv_cw_sek/nmv_ly_sek)-1):.1%}")
    m4.metric("Budget Reach", f"{(nmv_cw_sek / weekly_budget_sek):.1%}", delta=f"Mål: {weekly_budget_sek:,.0f} kr")
    m5.metric("Prognos Reach", f"{(nmv_cw_sek / weekly_prognos_sek):.1%}", delta=f"Mål: {weekly_prognos_sek:,.0f} kr")

    st.markdown("---")
    tabs = st.tabs(["📈 Hälsa", "🏆 Topp 50 Omsättning", "❤️ Wishlist Topp 50", "📣 Marknadsföring", "🌍 Marknadsutveckling", "🔄 Z-Hybrid", "📝 Analys"])

    # Globala variabler för analys
    m_comp = None
    camp_tab = None
    p1 = None

    with tabs[0]: # Hälsa
        st.subheader("Business Health Tracker (YoY Growth)")
        c1, c2 = st.columns(2)
        for col, grp in zip([c1, c2], ['Brand', 'Article type']):
            cw_g = df_cw.groupby(grp)['NMV_EUR'].sum().reset_index().rename(columns={'NMV_EUR': 'CW_EUR'})
            ly_g = df_ly.groupby(grp)['NMV_EUR'].sum().reset_index().rename(columns={'NMV_EUR': 'LY_EUR'})
            h_m = cw_g.merge(ly_g, on=grp, how='left').fillna(0)
            h_m['Growth %'] = (h_m['CW_EUR'] - h_m['LY_EUR']) / h_m['LY_EUR'].replace(0, 1)
            h_m['Status'] = h_m['Growth %'].apply(lambda x: "🟢 Growth" if x > 0.05 else ("🔻 Decline" if x < -0.05 else "➖ Stable"))
            col.dataframe(h_m.sort_values('CW_EUR', ascending=False).style.format({"CW_EUR": "€{:,.0f}", "LY_EUR": "€{:,.0f}", "Growth %": "{:.1%}"}), hide_index=True, use_container_width=True)

    with tabs[1]: # Topp 50
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
        st.dataframe(disp[['Status', 'SKU', 'Article Name', 'NMV €', 'Sold', 'Stock ZFS', 'Stock PF']].style.format({'NMV €': '€{:,.0f}', 'Sold': '{:,.0f}', 'Stock ZFS': '{:,.0f}', 'Stock PF': '{:,.0f}'}), hide_index=True, use_container_width=True)

    with tabs[3]: # Marknadsföring
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

            # Summeringslogik... (samma som tidigare)
            s1, s2 = p1[m_cols].sum(), p2[m_cols].sum()
            ms1 = {'Spend': s1['Budgetspent'], 'GMV': s1['GMV'], 'ROAS': s1['GMV']/s1['Budgetspent'] if s1['Budgetspent']>0 else 0}
            ms2 = {'Spend': s2['Budgetspent'], 'GMV': s2['GMV'], 'ROAS': s2['GMV']/s2['Budgetspent'] if s2['Budgetspent']>0 else 0}

            r1, r2, r3 = st.columns(3)
            r1.metric("Ad Spend", f"€{ms1['Spend']:,.0f}", delta=f"{(ms1['Spend']/ms2['Spend']-1):.0%}" if ms2['Spend']>0 else None, delta_color="inverse")
            r2.metric("Total ROAS", f"{ms1['ROAS']:,.1f}x", delta=f"{(ms1['ROAS']-ms2['ROAS']):.1f}x")
            r3.metric("Impressions", f"{s1['Viewableadimpressions']:,.0f}")

            # Kampanjtabell för analys
            c_cw = p1.groupby('ZMSCampaign')[['Budgetspent', 'GMV']].sum()
            c_lw = p2.groupby('ZMSCampaign')[['Budgetspent', 'GMV']].sum()
            camp_tab = c_cw.join(c_lw, rsuffix='_LW', how='left').fillna(0).reset_index()
            camp_tab['ROAS CW'] = camp_tab['GMV'] / camp_tab['Budgetspent'].replace(0, 1)
            camp_tab['ROAS LW'] = camp_tab['GMV_LW'] / camp_tab['Budgetspent_LW'].replace(0, 1)
            camp_tab['Delta ROAS'] = camp_tab['ROAS CW'] - camp_tab['ROAS LW']
            st.dataframe(camp_tab[['ZMSCampaign', 'Budgetspent', 'GMV', 'ROAS CW', 'Delta ROAS']].style.format({'Budgetspent': '€{:,.0f}', 'GMV': '€{:,.0f}', 'ROAS CW': '{:,.1f}x', 'Delta ROAS': '{:+.1f}x'}), hide_index=True, use_container_width=True)

    with tabs[4]: # Marknadsutveckling
        if f_mcw and f_mlw:
            mcw, mlw = load_csv_robust(f_mcw), load_csv_robust(f_mlw)
            for d in [mcw, mlw]: d['NMV_C'] = d['NMV'].apply(clean_val)
            m_comp = mcw.merge(mlw[['Country', 'NMV_C']], on='Country', suffixes=('', '_LW'))
            m_comp['Growth'] = (m_comp['NMV_C'] / m_comp['NMV_C_LW'].replace(0, 1)) - 1
            st.dataframe(m_comp[['Country', 'NMV_C', 'Growth']].style.format({'NMV_C': '€{:,.0f}', 'Growth': '{:+.1%}'}), hide_index=True, use_container_width=True)

    with tabs[6]: # ANALYS (UPPDATERAD)
        st.subheader("📝 Weekly Focus Analysis & Deep Dive")
        
        # --- RAD 1: BÄSTA PERFORMANS ---
        st.markdown("### 🏆 Veckans Vinnare")
        v1, v2, v3 = st.columns(3)
        
        with v1: # Bästa Marknad
            if m_comp is not None:
                best_m = m_comp.sort_values('Growth', ascending=False).iloc[0]
                st.info(f"**Bästa Marknad (NMV %)**\n\n🌍 {best_m['Country']}\n\nÖkning: {best_m['Growth']:.1%}")
            else: st.write("Ladda upp marknadsdata")

        with v2: # Bästa Kampanj
            if camp_tab is not None:
                best_c = camp_tab.sort_values('Delta ROAS', ascending=False).iloc[0]
                st.info(f"**Bästa Kampanj (ROAS)**\n\n📣 {best_c['ZMSCampaign']}\n\nFörbättring: +{best_c['Delta ROAS']:.1f}x")
            else: st.write("Ladda upp kampanjdata")

        with v3: # Topp 5 Artiklar PDP
            if p1 is not None:
                st.info("**Topp 5 Artiklar (PDP Views)**")
                top_pdp = p1.groupby('ConfigSKU')['PDPviews'].sum().sort_values(ascending=False).head(5)
                for sku, val in top_pdp.items():
                    name = inv_map[inv_map[inv_sku_col] == sku][inv_name_col].values[0] if sku in inv_map[inv_sku_col].values else sku
                    st.write(f"👁️ {val:,.0f} - {name}")

        # --- RAD 2: UTMANINGAR ---
        st.markdown("### ⚠️ Veckans Utmaningar")
        u1, u2, u3 = st.columns(3)

        with u1: # Sämsta Marknad
            if m_comp is not None:
                worst_m = m_comp.sort_values('Growth', ascending=True).iloc[0]
                st.warning(f"**Utmanande Marknad (NMV %)**\n\n🌍 {worst_m['Country']}\n\nTapp: {worst_m['Growth']:.1%}")

        with u2: # Sämsta Kampanj
            if camp_tab is not None:
                worst_c = camp_tab.sort_values('Delta ROAS', ascending=True).iloc[0]
                st.warning(f"**Utmanande Kampanj (ROAS)**\n\n📣 {worst_c['ZMSCampaign']}\n\nTapp: {worst_c['Delta ROAS']:.1f}x")

        with u3: # Sämsta 5 Artiklar PDP
            if p1 is not None:
                st.warning("**Utmanande 5 Artiklar (Lägst PDP Views)**")
                low_pdp = p1[p1['PDPviews'] > 0].groupby('ConfigSKU')['PDPviews'].sum().sort_values(ascending=True).head(5)
                for sku, val in low_pdp.items():
                    name = inv_map[inv_map[inv_sku_col] == sku][inv_name_col].values[0] if sku in inv_map[inv_sku_col].values else sku
                    st.write(f"📉 {val:,.0f} - {name}")

        st.markdown("---")
        # Behåll de gamla varningarna också
        c_a1, c_a2 = st.columns(2)
        with c_a1:
            st.success("**Topp Omsättning (Total)**")
            for i, r in t50_f.head(3).iterrows(): st.write(f"💰 {r['NMV €']:,.0f} € - {r['Article Name']}")
        with c_a2:
            st.error("**Kritiskt Lagersaldo**")
            crit = t50_f[t50_f['Total Stock'] < t50_f['Sold']].head(3)
            for i, r in crit.iterrows(): st.write(f"🚨 {r['Article Name']} (Lager: {r['Total Stock']:.0f}st)")

else:
    st.info("Vänligen ladda upp Försäljning CW, LW, LY och Lagerrapport för att starta.")
