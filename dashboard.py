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
    .block-container { padding-top: 3.5rem !important; padding-bottom: 0rem; }
    [data-testid="stMetricValue"] { font-size: 22px !important; font-weight: 700; }
    [data-testid="stMetricDelta"] { font-size: 13px !important; }
    [data-testid="stDataFrame"] td, [data-testid="stDataFrame"] th { 
        padding: 3px 8px !important; 
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
    if pd.isna(val) or val == '' or str(val).lower() == 'undefined': 
        return 0.0
    s = str(val).strip().replace('€', '').replace('kr', '').replace('SEK', '').replace('$', '').replace('€', '')
    has_pct_sign = '%' in s
    s = s.replace('%', '')  # Rensa bort procenttecknet innan float-konvertering
    s = re.sub(r'[\s\xa0]+', '', s)
    if not s: 
        return 0.0
    if ',' in s:
        if '.' in s: 
            s = s.replace('.', '') 
        s = s.replace(',', '.')
    try: 
        num = float(s)
        return num / 100.0 if (is_pct or has_pct_sign) else num
    except: 
        return 0.0

def load_csv_robust(file_path_or_buffer):
    if file_path_or_buffer is None: 
        return None
    if hasattr(file_path_or_buffer, 'seek'): 
        file_path_or_buffer.seek(0)
    try:
        content = file_path_or_buffer.read(8192).decode('utf-8', errors='ignore')
    except:
        file_path_or_buffer.seek(0)
        content = file_path_or_buffer.read(8192).decode('latin1', errors='ignore')
    if hasattr(file_path_or_buffer, 'seek'): 
        file_path_or_buffer.seek(0)
    
    skip = 2 if "Swedemount - SKU Report;;" in content else 0
    sep = ';' if content.count(';') > content.count(',') else ','
    for enc in ['utf-8', 'latin1', 'cp1252']:
        try:
            if hasattr(file_path_or_buffer, 'seek'): 
                file_path_or_buffer.seek(0)
            df = pd.read_csv(file_path_or_buffer, sep=sep, encoding=enc, skiprows=skip, low_memory=False, dtype=str)
            df.columns = [c.strip() for c in df.columns] 
            return df
        except: 
            continue
    return None

# Hjälpfunktion för att aggregera och beräkna volymviktad snittrabatt
def build_comparison_matrix(df_cw, df_lw, df_ly, dim_col, total_nmv_cw):
    def agg_dim(df):
        if dim_col not in df.columns:
            return pd.DataFrame(columns=[dim_col, 'NMV', 'Sold', 'Sold_Disc_Vol'])
        return df.groupby(dim_col).agg(
            NMV=('NMV_EUR', 'sum'),
            Sold=('Sold', 'sum'),
            Sold_Disc_Vol=('Sold_Disc_Vol', 'sum')
        ).reset_index()

    cw_g = agg_dim(df_cw).rename(columns={'NMV': 'CW_EUR', 'Sold': 'Sold_CW', 'Sold_Disc_Vol': 'Disc_Vol_CW'})
    lw_g = agg_dim(df_lw).rename(columns={'NMV': 'LW_EUR', 'Sold': 'Sold_LW', 'Sold_Disc_Vol': 'Disc_Vol_LW'})
    ly_g = agg_dim(df_ly).rename(columns={'NMV': 'LY_EUR', 'Sold': 'Sold_LY', 'Sold_Disc_Vol': 'Disc_Vol_LY'})

    res = cw_g.merge(lw_g, on=dim_col, how='outer').merge(ly_g, on=dim_col, how='outer').fillna(0.0)

    # Andel och tillväxt
    res['Andel %'] = res['CW_EUR'] / total_nmv_cw if total_nmv_cw > 0 else 0.0
    res['WoW %'] = (res['CW_EUR'] - res['LW_EUR']) / res['LW_EUR'].replace(0, 1)
    res['YoY %'] = (res['CW_EUR'] - res['LY_EUR']) / res['LY_EUR'].replace(0, 1)

    # Volymviktad genomsnittlig rabatt
    res['Avg Disc CW'] = (res['Disc_Vol_CW'] / res['Sold_CW'].replace(0, 1)).fillna(0.0)
    res['Avg Disc LW'] = (res['Disc_Vol_LW'] / res['Sold_LW'].replace(0, 1)).fillna(0.0)
    res['Avg Disc LY'] = (res['Disc_Vol_LY'] / res['Sold_LY'].replace(0, 1)).fillna(0.0)

    # Förändring i procentenheter
    res['Δ Disc WoW'] = res['Avg Disc CW'] - res['Avg Disc LW']
    res['Δ Disc YoY'] = res['Avg Disc CW'] - res['Avg Disc LY']

    return res

# --- SIDEBAR ---
st.sidebar.header("⚙️ Kontroller")
ex_rate = st.sidebar.number_input("Växelkurs (1€ = X SEK)", value=10.66)
weekly_budget_sek = st.sidebar.number_input("Budget (SEK)", value=4300000)
weekly_prognos_sek = st.sidebar.number_input("Prognos (SEK)", value=4500000)

st.sidebar.markdown("### 📁 Datafiler")
f_cw = st.sidebar.file_uploader("1. Försäljning CW (Breakdown Detailed)", type="csv")
f_lw = st.sidebar.file_uploader("2. Försäljning LW (Breakdown Detailed)", type="csv")
f_ly = st.sidebar.file_uploader("3. Försäljning LY (Breakdown Detailed)", type="csv")
f_inv = st.sidebar.file_uploader("4. Lagerrapport", type="csv")
f_mkt = st.sidebar.file_uploader("5. Marknadsföring Full", type="csv")
f_hybrid = st.sidebar.file_uploader("6. Z-Hybrid", type="csv")

# --- HUVUDLOGIK ---
if all([f_cw, f_lw, f_ly, f_inv]):
    camp_tab_global = None
    p1_active_mkt = None
    
    # 1. Ladda rådata
    with st.spinner("Läser in och aggregerar filer..."):
        df_cw_raw = load_csv_robust(f_cw)
        df_lw_raw = load_csv_robust(f_lw)
        df_ly_raw = load_csv_robust(f_ly)
        df_inv_raw = load_csv_robust(f_inv)

    # 2. Tvätta lagerfilen
    df_inv_raw.columns = [c.strip().lower().replace(' ', '_') for c in df_inv_raw.columns]
    inv_sku_col, inv_name_col = 'zalando_article_variant', 'article_name'
    zfs_col, pf_col = 'sellable_zfs_stock', 'sellable_pf_stock'
    reg_price_col, disc_price_col = 'regular_price', 'discounted_price'
    
    df_inv_raw[inv_sku_col] = df_inv_raw[inv_sku_col].astype(str).str.strip().str.upper()
    df_inv_raw[zfs_col] = df_inv_raw[zfs_col].apply(clean_val)
    df_inv_raw[pf_col] = df_inv_raw[pf_col].apply(clean_val)
    df_inv_raw[reg_price_col] = df_inv_raw[reg_price_col].apply(clean_val)
    df_inv_raw[disc_price_col] = df_inv_raw[disc_price_col].apply(clean_val)

    temp_disc_price = df_inv_raw[disc_price_col].where(df_inv_raw[disc_price_col] > 0, df_inv_raw[reg_price_col])
    df_inv_raw['DiscountRate'] = ((df_inv_raw[reg_price_col] - temp_disc_price) / df_inv_raw[reg_price_col].replace(0, 1)).clip(0, 1)

    # Priskonflikter i lager
    conflict_skus = df_inv_raw.groupby(inv_sku_col)[disc_price_col].nunique()
    conflict_skus = conflict_skus[conflict_skus > 1].index.tolist()
    
    if conflict_skus:
        conflict_report = df_inv_raw[df_inv_raw[inv_sku_col].isin(conflict_skus)].groupby(inv_sku_col).agg({
            inv_name_col: 'first',
            disc_price_col: lambda x: sorted(list(set(x))),
            zfs_col: 'sum',
            pf_col: 'sum'
        }).reset_index()
        conflict_report = conflict_report.rename(columns={
            inv_sku_col: 'Zalando article variant',
            inv_name_col: 'article_name',
            disc_price_col: 'Pris-varianter'
        })
        conflict_report['Antal Priser'] = conflict_report['Pris-varianter'].apply(len)
    else:
        conflict_report = pd.DataFrame()

    inv_map = df_inv_raw.groupby(inv_sku_col).agg({
        inv_name_col: 'first', 
        zfs_col: 'sum', 
        pf_col: 'sum',
        'DiscountRate': 'max'
    }).reset_index()
    inv_map['Total Stock'] = inv_map[zfs_col] + inv_map[pf_col]
    inv_map = inv_map[inv_map['Total Stock'] > 0]

    # --- 3. PROCESSING AV FÖRSÄLJNINGSFILER ---
    def process_sales(df):
        df.columns = [c.strip() for c in df.columns]
        
        nmv_col = next((c for c in df.columns if c.lower() == 'nmv'), 'NMV')
        sold_col = next((c for c in df.columns if 'sold articles' in c.lower()), 'Sold articles')
        disc_col = next((c for c in df.columns if 'sold discount rate' in c.lower()), None)
        
        df['NMV_EUR'] = df[nmv_col].apply(clean_val)
        df['Sold'] = df[sold_col].apply(clean_val)
        
        # Läser av kolumn P (Sold discount rate)
        if disc_col:
            df['Sold_Disc_Rate'] = df[disc_col].apply(clean_val)
        else:
            df['Sold_Disc_Rate'] = 0.0
            
        # Volymviktat underlag för aggregering
        df['Sold_Disc_Vol'] = df['Sold'] * df['Sold_Disc_Rate']
        
        # Dimensioner
        bc = next((c for c in df.columns if 'brand' in c.lower()), None)
        cat_c = next((c for c in df.columns if c.lower() == 'category'), None)
        tc = next((c for c in df.columns if 'article type' in c.lower() or 'commodity' in c.lower()), None)
        cntry_c = next((c for c in df.columns if 'country' in c.lower()), None)
        
        df['Brand'] = df[bc].fillna('Unknown') if bc else 'N/A'
        df['Category'] = df[cat_c].fillna('Unknown') if cat_c else 'N/A'
        df['Article type'] = df[tc].fillna('Unknown') if tc else 'N/A'
        df['Country'] = df[cntry_c].fillna('Unknown').astype(str).str.upper() if cntry_c else 'N/A'
        
        # Identifiera SKU
        sku_col = next((c for c in df.columns if 'zalando article variant' in c.lower()), None)
        if not sku_col:
            sku_col = next((c for c in df.columns if 'article variant' in c.lower() and 'country' not in c.lower()), df.columns[0])
            
        val = df[sku_col].astype(str).str.strip().str.upper()
        df['join_key'] = val
        df['Article variant'] = val
        
        return df

    df_cw = process_sales(df_cw_raw)
    df_lw = process_sales(df_lw_raw)
    df_ly = process_sales(df_ly_raw)

    # Totaler
    nmv_cw_sek = df_cw['NMV_EUR'].sum() * ex_rate
    nmv_lw_sek = df_lw['NMV_EUR'].sum() * ex_rate
    nmv_ly_sek = df_ly['NMV_EUR'].sum() * ex_rate
    total_nmv_cw = df_cw['NMV_EUR'].sum()

    # --- DASHBOARD HEADER ---
    st.title("🚀 Weekly Strategic Marketplace Board")
    
    nmv_lw_eur = nmv_lw_sek / ex_rate
    wow_growth = (nmv_cw_sek - nmv_lw_sek) / nmv_lw_sek if nmv_lw_sek > 0 else 0
    yoy_growth = (nmv_cw_sek - nmv_ly_sek) / nmv_ly_sek if nmv_ly_sek > 0 else 0
    vs_budget = (nmv_cw_sek / weekly_budget_sek) - 1 if weekly_budget_sek > 0 else 0
    vs_forecast = (nmv_cw_sek / weekly_prognos_sek) - 1 if weekly_prognos_sek > 0 else 0

    st.markdown("### 💰 Totals (Full Numbers)")
    v1, v2, v3, v4 = st.columns(4)
    v1.metric("Current Week (SEK)", f"{nmv_cw_sek:,.0f} kr")
    v2.metric("Last Week (SEK)", f"{nmv_lw_sek:,.0f} kr")
    v3.metric("Last Year (SEK)", f"{nmv_ly_sek:,.0f} kr")
    v4.metric("Last Week (€)", f"€{nmv_lw_eur:,.0f}")

    st.markdown("### 📈 Performance & Targets")
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("WoW Growth %", f"{wow_growth:+.1%}", delta=f"{wow_growth:.1%}")
    p2.metric("YoY Growth %", f"{yoy_growth:+.1%}", delta=f"{yoy_growth:.1%}")
    b_diff = (nmv_cw_sek - weekly_budget_sek)
    p3.metric("Vs Budget", f"{vs_budget:+.1%}", delta=f"{b_diff:,.0f} kr", delta_color="normal")
    f_diff = (nmv_cw_sek - weekly_prognos_sek)
    p4.metric("Vs Forecast", f"{vs_forecast:+.1%}", delta=f"{f_diff:,.0f} kr")

    st.markdown("---")

    # --- FLIKAR ---
    tabs = st.tabs([
        "📈 Hälsa & Kategori", 
        "🏆 Top 50 Revenue", 
        "❤️ Wishlist", 
        "📣 Marknadsföring", 
        "🌍 Marknad", 
        "🔄 Hybrid", 
        "📝 Analys", 
        "🔥 REA Manager"
    ])

    # 1. HÄLSA & KATEGORI
    with tabs[0]:
        st.subheader("Business Health Tracker: Kategori & Sold Discount")
        
        cat_matrix = build_comparison_matrix(df_cw, df_lw, df_ly, 'Category', total_nmv_cw)
        st.markdown("#### Summering per Kategori")
        st.dataframe(
            cat_matrix.sort_values('CW_EUR', ascending=False)[[
                'Category', 'CW_EUR', 'Andel %', 'WoW %', 'YoY %', 
                'Avg Disc CW', 'Avg Disc LW', 'Avg Disc LY', 'Δ Disc WoW', 'Δ Disc YoY'
            ]].style.format({
                "CW_EUR": "€{:,.0f}",
                "Andel %": "{:.1%}",
                "WoW %": "{:+.1%}",
                "YoY %": "{:+.1%}",
                "Avg Disc CW": "{:.1%}",
                "Avg Disc LW": "{:.1%}",
                "Avg Disc LY": "{:.1%}",
                "Δ Disc WoW": "{:+.1%}",
                "Δ Disc YoY": "{:+.1%}"
            }),
            hide_index=True,
            use_container_width=True
        )

        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### Brand Matrix")
            brand_m = build_comparison_matrix(df_cw, df_lw, df_ly, 'Brand', total_nmv_cw)
            st.dataframe(
                brand_m.sort_values('CW_EUR', ascending=False)[[
                    'Brand', 'CW_EUR', 'Andel %', 'WoW %', 'YoY %', 'Avg Disc CW', 'Δ Disc WoW'
                ]].style.format({
                    "CW_EUR": "€{:,.0f}",
                    "Andel %": "{:.1%}",
                    "WoW %": "{:+.1%}",
                    "YoY %": "{:+.1%}",
                    "Avg Disc CW": "{:.1%}",
                    "Δ Disc WoW": "{:+.1%}"
                }),
                hide_index=True,
                use_container_width=True
            )
            
        with c2:
            st.markdown("#### Article Type Matrix (Topp 20)")
            type_m = build_comparison_matrix(df_cw, df_lw, df_ly, 'Article type', total_nmv_cw)
            st.dataframe(
                type_m.sort_values('CW_EUR', ascending=False)[[
                    'Article type', 'CW_EUR', 'Andel %', 'WoW %', 'YoY %', 'Avg Disc CW', 'Δ Disc WoW'
                ]].head(20).style.format({
                    "CW_EUR": "€{:,.0f}",
                    "Andel %": "{:.1%}",
                    "WoW %": "{:+.1%}",
                    "YoY %": "{:+.1%}",
                    "Avg Disc CW": "{:.1%}",
                    "Δ Disc WoW": "{:+.1%}"
                }),
                hide_index=True,
                use_container_width=True
            )

    # 2. TOP 50 REVENUE
    with tabs[1]:
        st.subheader("🏆 Top 50 Revenue Performance & Sold Discounts")
        
        cw_sku = df_cw.groupby('join_key').agg(
            NMV_EUR=('NMV_EUR', 'sum'),
            Sold=('Sold', 'sum'),
            Sold_Disc_Vol=('Sold_Disc_Vol', 'sum')
        ).reset_index()
        cw_sku['Avg_Disc_CW'] = (cw_sku['Sold_Disc_Vol'] / cw_sku['Sold'].replace(0, 1)).fillna(0.0)
        cw_sku['Rank_CW'] = cw_sku['NMV_EUR'].rank(ascending=False, method='min')

        lw_sku = df_lw.groupby('join_key').agg(
            NMV_EUR_LW=('NMV_EUR', 'sum'),
            Sold_LW=('Sold', 'sum'),
            Sold_Disc_Vol_LW=('Sold_Disc_Vol', 'sum')
        ).reset_index()
        lw_sku['Avg_Disc_LW'] = (lw_sku['Sold_Disc_Vol_LW'] / lw_sku['Sold_LW'].replace(0, 1)).fillna(0.0)
        lw_sku['Rank_LW'] = lw_sku['NMV_EUR_LW'].rank(ascending=False, method='min')

        ly_sku = df_ly.groupby('join_key').agg(
            Sold_LY=('Sold', 'sum'),
            Sold_Disc_Vol_LY=('Sold_Disc_Vol', 'sum')
        ).reset_index()
        ly_sku['Avg_Disc_LY'] = (ly_sku['Sold_Disc_Vol_LY'] / ly_sku['Sold_LY'].replace(0, 1)).fillna(0.0)

        # Merge ihop SKU-data
        t50 = cw_sku.merge(lw_sku[['join_key', 'Rank_LW', 'Avg_Disc_LW', 'Sold_LW', 'Sold_Disc_Vol_LW']], on='join_key', how='left').fillna(0.0)
        t50 = t50.merge(ly_sku[['join_key', 'Avg_Disc_LY', 'Sold_LY', 'Sold_Disc_Vol_LY']], on='join_key', how='left').fillna(0.0)
        t50 = t50.merge(inv_map, left_on='join_key', right_on=inv_sku_col, how='left').fillna(0)
        t50 = t50.loc[:, ~t50.columns.duplicated()]

        t50['Status'] = t50.apply(lambda r: "🆕" if r['Rank_LW'] == 0 else ("⬆️" if r['Rank_CW'] < r['Rank_LW'] else ("⬇️" if r['Rank_CW'] > r['Rank_LW'] else "➡️")), axis=1)
        t50_f = t50.sort_values('Rank_CW').head(50).copy()

        # Sammanfattning för hela TOP 50 gruppen
        top50_sold_cw = t50_f['Sold'].sum()
        top50_disc_cw = (t50_f['Sold_Disc_Vol'].sum() / top50_sold_cw) if top50_sold_cw > 0 else 0.0
        
        top50_sold_lw = t50_f['Sold_LW'].sum()
        top50_disc_lw = (t50_f['Sold_Disc_Vol_LW'].sum() / top50_sold_lw) if top50_sold_lw > 0 else 0.0

        top50_sold_ly = t50_f['Sold_LY'].sum()
        top50_disc_ly = (t50_f['Sold_Disc_Vol_LY'].sum() / top50_sold_ly) if top50_sold_ly > 0 else 0.0

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Top 50 Total NMV", f"€{t50_f['NMV_EUR'].sum():,.0f}", f"{(t50_f['NMV_EUR'].sum()/total_nmv_cw):.1%} av totalen")
        m2.metric("Top 50 Snittrabatt CW", f"{top50_disc_cw:.1%}")
        m3.metric("Top 50 vs Föregående vecka", f"{top50_disc_lw:.1%}", delta=f"{(top50_disc_cw - top50_disc_lw):+.1%}", delta_color="inverse")
        m4.metric("Top 50 vs Föregående år", f"{top50_disc_ly:.1%}", delta=f"{(top50_disc_cw - top50_disc_ly):+.1%}", delta_color="inverse")

        st.markdown("---")

        disp50 = t50_f.rename(columns={
            'join_key': 'SKU', 
            inv_name_col: 'Article Name', 
            'NMV_EUR': 'NMV €', 
            zfs_col: 'Stock ZFS', 
            pf_col: 'Stock PF',
            'Avg_Disc_CW': 'Disc CW',
            'Avg_Disc_LW': 'Disc LW',
            'Avg_Disc_LY': 'Disc LY'
        })

        def highlight_stock_alert(row):
            styles = [''] * len(row)
            sold_val = row['Sold']
            if 0 < row['Stock ZFS'] < sold_val: 
                styles[row.index.get_loc('Stock ZFS')] = 'background-color: #ffcccc; color: #990000; font-weight: bold;'
            if 0 < row['Stock PF'] < sold_val: 
                styles[row.index.get_loc('Stock PF')] = 'background-color: #ffcccc; color: #990000; font-weight: bold;'
            return styles

        st.dataframe(
            disp50[['Status', 'SKU', 'Article Name', 'NMV €', 'Sold', 'Disc CW', 'Disc LW', 'Disc LY', 'Stock ZFS', 'Stock PF']].style.format({
                'NMV €': '€{:,.0f}', 
                'Sold': '{:,.0f}', 
                'Disc CW': '{:.1%}',
                'Disc LW': '{:.1%}',
                'Disc LY': '{:.1%}',
                'Stock ZFS': '{:,.0f}', 
                'Stock PF': '{:,.0f}'
            }).apply(highlight_stock_alert, axis=1), 
            hide_index=True, 
            use_container_width=True
        )

    # 3. WISHLIST
    with tabs[2]:
        if f_mkt:
            st.subheader("❤️ Top 50 Most Added to Wishlist")
            m_wish = load_csv_robust(f_mkt)
            m_wish.columns = [c.replace(' ', '') for c in m_wish.columns]
            m_wish['W_Clean'] = m_wish['Week'].apply(clean_val)
            m_wish['Wish_Numeric'] = m_wish['Addtowishlist'].apply(clean_val)
            l_week = m_wish['W_Clean'].max()
            w_data = m_wish[m_wish['W_Clean'] == l_week].groupby('ConfigSKU')[['Wish_Numeric']].sum().reset_index()
            w_data['ConfigSKU'] = w_data['ConfigSKU'].str.strip().str.upper()
            w_merged = w_data.merge(inv_map, left_on='ConfigSKU', right_on=inv_sku_col, how='left').sort_values('Wish_Numeric', ascending=False).head(50)
            st.dataframe(w_merged[['ConfigSKU', inv_name_col, 'Wish_Numeric', 'Total Stock', zfs_col, pf_col]].style.format(precision=0), hide_index=True, use_container_width=True)

    # 4. MARKNADSFÖRING
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
            sel_w1 = st.selectbox("Aktiv Vecka", w_list, index=0, key='mkt_w1')
            sel_w2 = st.selectbox("Jämförelse Vecka", w_list, index=min(1, len(w_list)-1), key='mkt_w2')
            p1, p2 = mkt_df[mkt_df['W_Clean'] == sel_w1], mkt_df[mkt_df['W_Clean'] == sel_w2]
            p1_active_mkt = p1

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
            camp_tab_global = camp_tab

            def style_trends(row):
                styles = [''] * len(row)
                idx = row.index.get_loc('Delta ROAS')
                if row['Delta ROAS'] > 0: styles[idx] = 'color: #28a745; font-weight: bold'
                elif row['Delta ROAS'] < 0: styles[idx] = 'color: #dc3545; font-weight: bold'
                return styles

            st.dataframe(camp_tab[['ZMSCampaign', 'Budgetspent', 'GMV', 'ROAS CW', 'Delta ROAS']].style.format({
                'Budgetspent': '€{:,.0f}', 'GMV': '€{:,.0f}', 'ROAS CW': '{:,.1f}x', 'Delta ROAS': '{:+.1f}x'
            }).apply(style_trends, axis=1), hide_index=True, use_container_width=True)

    # 5. MARKNAD
    with tabs[4]:
        st.subheader("🌍 Marknadsutveckling & Sold Discount per Land")
        m_comp = build_comparison_matrix(df_cw, df_lw, df_ly, 'Country', total_nmv_cw)
        m_comp_global = m_comp

        st.dataframe(
            m_comp.sort_values('CW_EUR', ascending=False)[[
                'Country', 'CW_EUR', 'Andel %', 'WoW %', 'YoY %', 
                'Avg Disc CW', 'Avg Disc LW', 'Avg Disc LY', 'Δ Disc WoW', 'Δ Disc YoY'
            ]].style.format({
                'CW_EUR': '€{:,.0f}', 
                'Andel %': '{:.1%}', 
                'WoW %': '{:+.1%}',
                'YoY %': '{:+.1%}',
                'Avg Disc CW': '{:.1%}',
                'Avg Disc LW': '{:.1%}',
                'Avg Disc LY': '{:.1%}',
                'Δ Disc WoW': '{:+.1%}',
                'Δ Disc YoY': '{:+.1%}'
            }), 
            hide_index=True, 
            use_container_width=True
        )

    # 6. Z-HYBRID
    with tabs[5]:
        if f_hybrid:
            st.subheader("🔄 Z-Hybrid Försäljning")
            hy = load_csv_robust(f_hybrid)
            hy.columns = [c.strip() for c in hy.columns]
            v_col, d_col = 'Ordervärde ex.moms', 'Datum'
            if v_col in hy.columns:
                hy_c = hy[hy[d_col].str.lower() != 'total'].copy()
                hy_c['Sales_CW'] = hy_c[v_col].apply(clean_val)
                total_hy = hy_c['Sales_CW'].sum()
                share = (total_hy / nmv_cw_sek) if nmv_cw_sek > 0 else 0
                st.metric("Total Hybrid", f"{total_hy:,.0f} kr", f"{share:.1%} av total sales")
                st.dataframe(hy_c.groupby([d_col, 'Veckodag'])['Sales_CW'].sum().reset_index().style.format({"Sales_CW": "{:,.0f} kr"}), hide_index=True, use_container_width=True)

    # 7. ANALYS
    with tabs[6]:
        st.subheader("📝 Weekly Strategic Focus")
        v1, v2, v3 = st.columns(3)
        with v1:
            if m_comp_global is not None and not m_comp_global.empty:
                bm = m_comp_global.sort_values('WoW %', ascending=False).iloc[0]
                st.success(f"**Bästa Marknad (WoW)**\n\n🌍 {bm['Country']} (+{bm['WoW %']:.1%})")
        with v2:
            if camp_tab_global is not None and not camp_tab_global.empty:
                bc = camp_tab_global.sort_values('Delta ROAS', ascending=False).iloc[0]
                st.success(f"**Bästa Kampanj (ROAS)**\n\n📣 {bc['ZMSCampaign']} (+{bc['Delta ROAS']:.1f}x)")
        with v3:
            if p1_active_mkt is not None and not p1_active_mkt.empty:
                st.success("**Topp 5 PDP Artiklar**")
                top_pdp = p1_active_mkt.groupby('ConfigSKU')['PDPviews'].sum().sort_values(ascending=False).head(5)
                for sku, val in top_pdp.items():
                    name = inv_map[inv_map[inv_sku_col] == sku][inv_name_col].values[0] if sku in inv_map[inv_sku_col].values else sku
                    st.write(f"👁️ {val:,.0f} - {name}")

        u1, u2, u3 = st.columns(3)
        with u1:
            if m_comp_global is not None and not m_comp_global.empty:
                wm = m_comp_global.sort_values('WoW %', ascending=True).iloc[0]
                st.error(f"**Utmanande Marknad**\n\n🌍 {wm['Country']} ({wm['WoW %']:.1%})")
        with u2:
            if camp_tab_global is not None and not camp_tab_global.empty:
                wc = camp_tab_global.sort_values('Delta ROAS', ascending=True).iloc[0]
                st.error(f"**Utmanande Kampanj**\n\n📣 {wc['ZMSCampaign']} ({wc['Delta ROAS']:.1f}x)")
        with u3:
            if p1_active_mkt is not None and not p1_active_mkt.empty:
                st.error("**Utmanande 5 PDP Artiklar**")
                low_pdp = p1_active_mkt[p1_active_mkt['PDPviews'] > 0].groupby('ConfigSKU')['PDPviews'].sum().sort_values(ascending=True).head(5)
                for sku, val in low_pdp.items():
                    name = inv_map[inv_map[inv_sku_col] == sku][inv_name_col].values[0] if sku in inv_map[inv_sku_col].values else sku
                    st.write(f"📉 {val:,.0f} - {name}")

        st.markdown("---")
        c_a1, c_a2 = st.columns(2)
        with c_a1:
            st.info("**Topp Omsättning**")
            for i, r in t50_f.head(3).iterrows(): 
                st.write(f"💰 €{r['NMV_EUR']:,.0f} - {r[inv_name_col]} (Snittrabatt: {r['Avg_Disc_CW']:.1%})")
        with c_a2:
            st.error("**Lager-Attention**")
            crit = t50_f[t50_f['Total Stock'] < t50_f['Sold']].head(3)
            for i, r in crit.iterrows(): 
                st.write(f"🚨 {r[inv_name_col]} (Lager: {r['Total Stock']:.0f}st | Sålt: {r['Sold']:.0f}st)")

    # 8. REA MANAGER
    with tabs[7]:
        st.subheader("🎯 REA Manager: Margin Recovery & Stock Health")
        
        rea_df = df_cw.groupby('join_key').agg(
            NMV_EUR=('NMV_EUR', 'sum'),
            Sold=('Sold', 'sum'),
            Sold_Disc_Vol=('Sold_Disc_Vol', 'sum')
        ).reset_index()
        rea_df['Avg_Sold_Disc'] = (rea_df['Sold_Disc_Vol'] / rea_df['Sold'].replace(0, 1)).fillna(0.0)

        rea_df = rea_df.merge(inv_map, left_on='join_key', right_on=inv_sku_col, how='inner')
        rea_df = rea_df.rename(columns={
            inv_sku_col: 'Zalando article variant',
            zfs_col: 'ZFS Stock'
        })
        rea_df = rea_df.loc[:, ~rea_df.columns.duplicated()]
        
        rea_df['Weeks Cover'] = rea_df['ZFS Stock'] / (rea_df['Sold'] + 0.1)
        
        money_on_table = rea_df[
            (rea_df['ZFS Stock'] > 50) & 
            (rea_df['DiscountRate'] > 0.15) & 
            (rea_df['Weeks Cover'] < 5)
        ].sort_values('Weeks Cover').copy()
        money_on_table['Strategi'] = "MARGINAL-BOOST"
        money_on_table['Rekommendation'] = "Säljer för snabbt. Sänk rabatten för att rädda marginal."

        stuck_stock = rea_df[
            (rea_df['ZFS Stock'] > 100) & 
            (rea_df['DiscountRate'] < 0.10) & 
            ((rea_df['Weeks Cover'] > 20) | (rea_df['Sold'] == 0))
        ].sort_values('ZFS Stock', ascending=False).copy()
        stuck_stock['Strategi'] = "STARTA REA"
        stuck_stock['Rekommendation'] = "Djupt fullprislager som står stilla. Aktivera en 15-20% introduktionsrea."

        deepen_promo = rea_df[
            (rea_df['ZFS Stock'] > 100) & 
            (rea_df['DiscountRate'] >= 0.10) & 
            (rea_df['Weeks Cover'] > 25)
        ].sort_values('ZFS Stock', ascending=False).copy()
        deepen_promo['Strategi'] = "ÖKA REAN (+5%)"
        deepen_promo['Rekommendation'] = "Befintlig rea ger inte tillräcklig effekt. Höj rabatten med ytterligare 5-10%."

        c1, c2, c3 = st.columns(3)
        with c1:
            st.error("📉 Money on the Table (Sänk rabatt)")
            st.caption("Volymartiklar (>50st) som säljer slut för snabbt.")
            st.dataframe(money_on_table[['Zalando article variant', 'DiscountRate', 'Avg_Sold_Disc', 'Weeks Cover', 'Sold', 'ZFS Stock']]
                         .style.format({'DiscountRate': '{:.1%}', 'Avg_Sold_Disc': '{:.1%}', 'Weeks Cover': '{:.1f} v', 'Sold': '{:,.0f}', 'ZFS Stock': '{:,.0f}'}), use_container_width=True, hide_index=True)

        with c2:
            st.warning("📦 Stuck in Warehouse (Starta rea)")
            st.caption("Stora fullprislager (>100st) som inte rör sig.")
            st.dataframe(stuck_stock[['Zalando article variant', 'DiscountRate', 'Avg_Sold_Disc', 'Weeks Cover', 'Sold', 'ZFS Stock']]
                         .style.format({'DiscountRate': '{:.1%}', 'Avg_Sold_Disc': '{:.1%}', 'Weeks Cover': '{:.1f} v', 'Sold': '{:,.0f}', 'ZFS Stock': '{:,.0f}'}), use_container_width=True, hide_index=True)

        with c3:
            st.info("🔥 Deepen Markdowns (Höj rean)")
            st.caption("Redan reade varor (>100st) där rean är för svag.")
            st.dataframe(deepen_promo[['Zalando article variant', 'DiscountRate', 'Avg_Sold_Disc', 'Weeks Cover', 'Sold', 'ZFS Stock']]
                         .style.format({'DiscountRate': '{:.1%}', 'Avg_Sold_Disc': '{:.1%}', 'Weeks Cover': '{:.1f} v', 'Sold': '{:,.0f}', 'ZFS Stock': '{:,.0f}'}), use_container_width=True, hide_index=True)

        # Priskonflikter
        st.markdown("---")
        st.subheader("⚠️ Priskonflikter (Dubbla priser på samma SKU)")
        st.write("Dessa produkter har två eller fler olika REA-priser aktiva samtidigt.")

        if not conflict_report.empty and 'Antal Priser' in conflict_report.columns:
            st.error(f"Hittade {len(conflict_report)} artiklar med priskonflikter!")
            st.dataframe(conflict_report[['Zalando article variant', 'article_name', 'Pris-varianter', 'Antal Priser']], use_container_width=True, hide_index=True)
            csv_conflict = conflict_report.to_csv(index=False).encode('utf-8-sig')
            st.download_button(label="📥 Ladda ner Rapport: Priskonflikter", data=csv_conflict, file_name='Zalando_Price_Conflicts.csv', mime='text/csv', key='btn_conflict_dl')
        else:
            st.success("Inga priskonflikter hittades. Alla SKU:er har enhetlig prissättning!")

        # Export Action Plan
        st.markdown("---")
        full_action_plan = pd.concat([money_on_table, stuck_stock, deepen_promo])
        if not full_action_plan.empty:
            export_df = full_action_plan[[
                'Zalando article variant', 
                'article_name', 
                'ZFS Stock', 
                'Sold', 
                'Weeks Cover', 
                'DiscountRate',
                'Avg_Sold_Disc',
                'Strategi', 
                'Rekommendation'
            ]].copy()
            export_df['DiscountRate'] = export_df['DiscountRate'].apply(lambda x: f"{x:.1%}")
            export_df['Avg_Sold_Disc'] = export_df['Avg_Sold_Disc'].apply(lambda x: f"{x:.1%}")
            csv = export_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 Ladda ner Strategisk Action Plan",
                data=csv,
                file_name='Zalando_Strategic_Action_Plan.csv',
                mime='text/csv',
                key='strategic_plan_v3'
            )
        else:
            st.write("Inga produkter matchar kriterierna för åtgärder just nu.")
else:
    st.info("Vänligen ladda upp data för att starta.")
