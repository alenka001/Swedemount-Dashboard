import streamlit as st
import pandas as pd
import warnings
import re

# Tysta tekniska varningar
warnings.filterwarnings('ignore', category=pd.errors.DtypeWarning)

# --- SET PAGE CONFIG ---
st.set_page_config(page_title="Weekly Strategic Dashboard", layout="wide", page_icon="📊")

# --- CSS FÖR PROFESSIONELL DESIGN (ÅTERSTÄLLD FRÅN MORGONEN) ---
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

# --- UTILITIES / DEN AGGRESSIVA SIFFER-TVÄTTEN ---
def clean_val(val, is_pct=False):
    if pd.isna(val) or val == '' or str(val).lower() == 'undefined': return 0.0
    s = str(val).strip().replace('€', '').replace('kr', '').replace('SEK', '')
    has_pct_sign = '%' in s
    s = re.sub(r'[\s\xa0]+', '', s) # Tar bort alla typer av mellanslag inkl hard spaces
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
f_mlw = st.sidebar.file_uploader("8. Market LY (Land)", type="csv")

# --- HUVUDLOGIK ---
if all([f_cw, f_lw, f_ly, f_inv]):
    df_cw_raw = load_csv_robust(f_cw)
    df_lw_raw = load_csv_robust(f_lw)
    df_ly_raw = load_csv_robust(f_ly)
    df_inv_raw = load_csv_robust(f_inv)

    # 1. Lager (Variant-nivå)
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
        df['join_key'] = df[sku_col].astype(str).str.strip().str.upper()
        df['Zalando article variant'] = df['join_key']
        if 'Article variant' not in df.columns:
        df['Article variant'] = df[next((c for c in df.columns if c.lower() == 'article variant'), sku_col)]
        return df

    df_cw, df_lw, df_ly = process_sales(df_cw_raw), process_sales(df_lw_raw), process_sales(df_ly_raw)
    nmv_cw_sek = df_cw['NMV_EUR'].sum() * ex_rate
    nmv_lw_sek = df_lw['NMV_EUR'].sum() * ex_rate
    nmv_ly_sek = df_ly['NMV_EUR'].sum() * ex_rate

    st.title("🚀 Weekly Strategic Marketplace Board")

    # ROW 1: EUR PERFORMANCE (ÅTERSTÄLLD)
    st.subheader("🇪🇺 Row 1: EUR Performance")
    e1, e2, e3 = st.columns(3)
    e1.metric("Current NMV", f"€{nmv_cw_sek/ex_rate:,.0f}")
    e2.metric("LW NMV", f"€{nmv_lw_sek/ex_rate:,.0f}", delta=f"{((nmv_cw_sek/nmv_lw_sek)-1):.1%} vs LW")
    e3.metric("LY NMV", f"€{nmv_ly_sek/ex_rate:,.0f}", delta=f"{((nmv_cw_sek/nmv_ly_sek)-1):.1%} vs LY")

    # ROW 2: SEK PERFORMANCE & TARGET GAPS (ÅTERSTÄLLD)
    st.subheader("🇸🇪 Row 2: SEK Performance & Target Gaps")
    s1, s2, s3, s4, s5 = st.columns(5)
    s1.metric("LW SEK", f"{nmv_lw_sek:,.0f} kr")
    s2.metric("LY SEK", f"{nmv_ly_sek:,.0f} kr")
    
    b_reach = (nmv_cw_sek / weekly_budget_sek)
    s3.metric("vs Budget", f"{weekly_budget_sek:,.0f} kr", delta=f"{b_reach:.1%} Reach")
    
    p_reach = (nmv_cw_sek / weekly_prognos_sek)
    s4.metric("vs Prognos", f"{weekly_prognos_sek:,.0f} kr", delta=f"{p_reach:.1%} Reach")
    s5.metric("Current Total", f"{nmv_cw_sek:,.0f} kr")

    st.markdown("---")
    tabs = st.tabs(["📈 Hälsa", "🏆 Top 50 Revenue", "❤️ Wishlist Top 50", "📣 Marknadsföring", "🌍 Marknadsutveckling", "🔄 Z-Hybrid", "📝 Analys"])

    # Hjälpvariabler för Analys-tab
    m_comp_analysis = None
    camp_tab_analysis = None
    p1_active_marketing = None

    with tabs[0]: # HÄLSA (GROWTH)
        st.subheader("Business Health Tracker: WoW & YoY Growth")
        total_nmv_cw = df_cw['NMV_EUR'].sum() # För att räkna ut andelen av totalen
        c1, c2 = st.columns(2)
        for col, grp in zip([c1, c2], ['Brand', 'Article type']):
            cw_g = df_cw.groupby(grp)['NMV_EUR'].sum().reset_index().rename(columns={'NMV_EUR': 'CW_EUR'})
            lw_g = df_lw.groupby(grp)['NMV_EUR'].sum().reset_index().rename(columns={'NMV_EUR': 'LW_EUR'})
            ly_g = df_ly.groupby(grp)['NMV_EUR'].sum().reset_index().rename(columns={'NMV_EUR': 'LY_EUR'})
            
            h_m = cw_g.merge(lw_g, on=grp, how='left').merge(ly_g, on=grp, how='left').fillna(0)
            
            # Beräkningar
            h_m['Andel %'] = h_m['CW_EUR'] / total_nmv_cw if total_nmv_cw > 0 else 0
            h_m['WoW %'] = (h_m['CW_EUR'] - h_m['LW_EUR']) / h_m['LW_EUR'].replace(0, 1)
            h_m['YoY %'] = (h_m['CW_EUR'] - h_m['LY_EUR']) / h_m['LY_EUR'].replace(0, 1)
            h_m['Status'] = h_m['YoY %'].apply(lambda x: "🟢 Growth" if x > 0.05 else ("🔻 Decline" if x < -0.05 else "➖ Stable"))
            
            col.write(f"**Summering per {grp}**")
            col.dataframe(h_m.sort_values('CW_EUR', ascending=False).style.format({
                "CW_EUR": "€{:,.0f}", "Andel %": "{:.1%}", "WoW %": "{:+.1%}", "YoY %": "{:+.1%}"
            }), hide_index=True, use_container_width=True) hide_index=True, use_container_width=True)

    with tabs[1]: # 🏆 Top 50 Revenue
        st.subheader("🏆 Top 50 Revenue Performance & Stock Alerts")
        
        # 1. Gruppera nuvarande vecka (CW)
        cw_top = df_cw.groupby(['join_key', 'Article variant'])[['NMV_EUR', 'Sold']].sum().reset_index()
        cw_top['Rank_CW'] = cw_top['NMV_EUR'].rank(ascending=False, method='min')
        
        # 2. Gruppera förra veckan (LW) - VIKTIGT: Använd 'join_key' här också
        lw_top = df_lw.groupby(['join_key'])[['NMV_EUR']].sum().reset_index()
        lw_top['Rank_LW'] = lw_top['NMV_EUR'].rank(ascending=False, method='min')
        
        # 3. Slå ihop CW och LW för att jämföra ranking (WoW)
        # VIKTIGT: Vi matchar 'join_key' mot 'join_key'
        t50 = cw_top.merge(lw_top[['join_key', 'Rank_LW']], on='join_key', how='left').fillna(0)
        
        # 4. Lägg till lagerinformation från din Inventory Map
        t50 = t50.merge(inv_map, left_on='join_key', right_on=inv_sku_col, how='left').fillna(0)
        
        # 5. Status-logik för pilar
        t50['Status'] = t50.apply(lambda r: "🆕" if r['Rank_LW'] == 0 else ("⬆️" if r['Rank_CW'] < r['Rank_LW'] else ("⬇️" if r['Rank_CW'] > r['Rank_LW'] else "➡️")), axis=1)
        
        t50_f = t50.sort_values('Rank_CW').head(50)
        
        # Byt namn på kolumner för snygg display
        disp = t50_f.rename(columns={
            'join_key': 'SKU', 
            inv_name_col: 'Article Name', 
            'NMV_EUR': 'NMV €', 
            zfs_col: 'Stock ZFS', 
            pf_col: 'Stock PF'
        })
        
        # Funktion för röd markering vid lågt lager
        def highlight_stock_alert(row):
            styles = [''] * len(row)
            sold_val = row['Sold']
            # Röd bakgrund om lagret är positivt men lägre än veckans försäljning
            if 0 < row['Stock ZFS'] < sold_val: 
                styles[row.index.get_loc('Stock ZFS')] = 'background-color: #ffcccc; color: #990000; font-weight: bold;'
            if 0 < row['Stock PF'] < sold_val: 
                styles[row.index.get_loc('Stock PF')] = 'background-color: #ffcccc; color: #990000; font-weight: bold;'
            return styles

        # Visa tabellen med formatering och tusentalsavgränsare
        st.dataframe(disp[['Status', 'SKU', 'Article Name', 'NMV €', 'Sold', 'Stock ZFS', 'Stock PF']].style.format({
            'NMV €': '€{:,.0f}', 
            'Sold': '{:,.0f}', 
            'Stock ZFS': '{:,.0f}', 
            'Stock PF': '{:,.0f}'
        }).apply(highlight_stock_alert, axis=1), hide_index=True, use_container_width=True)

    with tabs[2]: # WISHLIST TOP 50 (ÅTERSTÄLLD)
        if f_mkt:
            st.subheader("❤️ Top 50 Most Added to Wishlist (Latest Week)")
            m_wish = load_csv_robust(f_mkt)
            m_wish.columns = [c.replace(' ', '') for c in m_wish.columns]
            m_wish['W_Clean'] = m_wish['Week'].apply(clean_val)
            m_wish['Wish_Numeric'] = m_wish['Addtowishlist'].apply(clean_val)
            l_week = m_wish['W_Clean'].max()
            w_data = m_wish[m_wish['W_Clean'] == l_week].groupby('ConfigSKU')[['Wish_Numeric']].sum().reset_index()
            w_data['ConfigSKU'] = w_data['ConfigSKU'].str.strip().str.upper()
            w_merged = w_data.merge(inv_map, left_on='ConfigSKU', right_on=inv_sku_col, how='left').sort_values('Wish_Numeric', ascending=False).head(50)
            st.dataframe(w_merged[['ConfigSKU', inv_name_col, 'Wish_Numeric', 'Total Stock', zfs_col, pf_col]].style.format(precision=0), hide_index=True, use_container_width=True)

    with tabs[3]: # MARKNADSFÖRING (ÅTERSTÄLLD MED ALLA KPI:ER & DELTAS)
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
            sel_w1 = st.selectbox("Aktiv Vecka", w_list, index=0, key='mkt_active')
            sel_w2 = st.selectbox("Jämförelse Vecka", w_list, index=min(1, len(w_list)-1), key='mkt_compare')
            p1, p2 = mkt_df[mkt_df['W_Clean'] == sel_w1], mkt_df[mkt_df['W_Clean'] == sel_w2]
            p1_active_marketing = p1

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
            r2.metric("Total GMV", f"€{ms1['GMV']:,.0f}", delta=f"{(ms1['GMV']/ms2['GMV']-1):.0%}" if ms2['GMV']>0 else None)
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
            camp_tab_analysis = camp_tab

            def style_trends(row):
                styles = [''] * len(row)
                idx = row.index.get_loc('Delta ROAS')
                if row['Delta ROAS'] > 0: styles[idx] = 'color: #28a745; font-weight: bold'
                elif row['Delta ROAS'] < 0: styles[idx] = 'color: #dc3545; font-weight: bold'
                return styles

            st.dataframe(camp_tab[['ZMSCampaign', 'Budgetspent', 'GMV', 'ROAS CW', 'Delta ROAS']].style.format({
                'Budgetspent': '€{:,.0f}', 'GMV': '€{:,.0f}', 'ROAS CW': '{:,.1f}x', 'Delta ROAS': '{:+.1f}x'
            }).apply(style_trends, axis=1), hide_index=True, use_container_width=True)

    with tabs[4]: # MARKNADSUTVECKLING
        if f_mcw and f_mlw:
            st.subheader("🌍 Marknadsutveckling: WoW Performance & Share")
            mcw = load_csv_robust(f_mcw)
            mlw = load_csv_robust(f_mlw)
            
            for d in [mcw, mlw]: d['NMV_C'] = d['NMV'].apply(clean_val)
            
            total_m_nmv = mcw['NMV_C'].sum()
            mcw['Share %'] = mcw['NMV_C'] / total_m_nmv if total_m_nmv > 0 else 0
            
            # Merge för WoW jämförelse
            m_comp = mcw.merge(mlw[['Country', 'NMV_C']], on='Country', suffixes=('', '_LW'), how='left').fillna(0)
            m_comp['WoW Growth %'] = (m_comp['NMV_C'] - m_comp['NMV_C_LW']) / m_comp['NMV_C_LW'].replace(0, 1)
            
            st.dataframe(m_comp[['Country', 'NMV_C', 'Share %', 'WoW Growth %']].sort_values('NMV_C', ascending=False).style.format({
                'NMV_C': '€{:,.0f}', 'Share %': '{:.1%}', 'WoW Growth %': '{:+.1%}'
            }), hide_index=True, use_container_width=True)
        else:
            st.info("Ladda upp Market CW och Market LW för att se utveckling.")
    with tabs[5]: # Z-HYBRID (ÅTERSTÄLLD)
        if f_hybrid:
            st.subheader("🔄 Z-Hybrid Försäljningsandel")
            hy = load_csv_robust(f_hybrid)
            hy.columns = [c.strip() for c in hy.columns]
            v_col, d_col = 'Ordervärde ex.moms', 'Datum'
            if v_col in hy.columns:
                hy_c = hy[hy[d_col].str.lower() != 'total'].copy()
                hy_c['Sales_CW'] = hy_c[v_col].apply(clean_val)
                total_hy = hy_c['Sales_CW'].sum()
                share = (total_hy / nmv_cw_sek) if nmv_cw_sek > 0 else 0
                st.metric("Total Hybrid Sales (SEK)", f"{total_hy:,.0f} kr", f"{share:.1%} av totalen")
                st.dataframe(hy_c.groupby([d_col, 'Veckodag'])['Sales_CW'].sum().reset_index().style.format({"Sales_CW": "{:,.0f} kr"}), hide_index=True, use_container_width=True)

    with tabs[6]: # ANALYS (ÅTERSTÄLLD MED VINNARE/UTMANARE)
        st.subheader("📝 Weekly Strategic Focus")
        v1, v2, v3 = st.columns(3)
        with v1: # Bästa Marknad
            if m_comp_analysis is not None:
                best_m = m_comp_analysis.sort_values('Growth', ascending=False).iloc[0]
                st.success(f"**Bästa Marknad (Growth)**\n\n🌍 {best_m['Country']}\n\nÖkning: {best_m['Growth']:.1%}")
        with v2: # Bästa Kampanj
            if camp_tab_analysis is not None:
                best_c = camp_tab_analysis.sort_values('Delta ROAS', ascending=False).iloc[0]
                st.success(f"**Bästa Kampanj (ROAS)**\n\n📣 {best_c['ZMSCampaign']}\n\nFörbättring: +{best_c['Delta ROAS']:.1f}x")
        with v3: # Topp 5 PDP
            if p1_active_marketing is not None:
                st.success("**Topp 5 Artiklar (PDP Views)**")
                top_pdp = p1_active_marketing.groupby('ConfigSKU')['PDPviews'].sum().sort_values(ascending=False).head(5)
                for sku, val in top_pdp.items():
                    name = inv_map[inv_map[inv_sku_col] == sku][inv_name_col].values[0] if sku in inv_map[inv_sku_col].values else sku
                    st.write(f"👁️ {val:,.0f} - {name}")

        u1, u2, u3 = st.columns(3)
        with u1: # Sämsta Marknad
            if m_comp_analysis is not None:
                worst_m = m_comp_analysis.sort_values('Growth', ascending=True).iloc[0]
                st.error(f"**Utmanande Marknad**\n\n🌍 {worst_m['Country']}\n\nTapp: {worst_m['Growth']:.1%}")
        with u2: # Sämsta Kampanj
            if camp_tab_analysis is not None:
                worst_c = camp_tab_analysis.sort_values('Delta ROAS', ascending=True).iloc[0]
                st.error(f"**Utmanande Kampanj**\n\n📣 {worst_c['ZMSCampaign']}\n\nTapp: {worst_c['Delta ROAS']:.1f}x")
        with u3: # Sämsta 5 PDP
            if p1_active_marketing is not None:
                st.error("**Utmanande 5 Artiklar (Låga PDP)**")
                low_pdp = p1_active_marketing[p1_active_marketing['PDPviews'] > 0].groupby('ConfigSKU')['PDPviews'].sum().sort_values(ascending=True).head(5)
                for sku, val in low_pdp.items():
                    name = inv_map[inv_map[inv_sku_col] == sku][inv_name_col].values[0] if sku in inv_map[inv_sku_col].values else sku
                    st.write(f"📉 {val:,.0f} - {name}")

        st.markdown("---")
        c_a1, c_a2 = st.columns(2)
        with c_a1:
            st.info("**Topp 3 Omsättning (Total)**")
            for i, r in t50_f.head(3).iterrows(): st.write(f"💰 €{r['NMV_EUR']:,.0f} - {r[inv_name_col]}")
        with c_a2:
            st.error("**Lager-Attention**")
            crit = t50_f[t50_f['Total Stock'] < t50_f['Sold']].head(3)
            for i, r in crit.iterrows(): st.write(f"🚨 {r[inv_name_col]} (Lager: {r['Total Stock']:.0f}st)")

else:
    st.info("Vänligen ladda upp data i sidomenyn för att generera din dashboard.")
