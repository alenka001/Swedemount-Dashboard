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
    /* Tighten Layout */
    .block-container { padding-top: 1rem; padding-bottom: 0rem; }
    [data-testid="stMetricValue"] { font-size: 24px !important; }
    [data-testid="stMetricDelta"] { font-size: 14px !important; }
    
    /* Table Styling */
    [data-testid="stDataFrame"] td, [data-testid="stDataFrame"] th { 
        padding: 1px 10px !important; 
        font-size: 13px !important; 
    }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { 
        height: 40px; 
        white-space: pre-wrap; 
        background-color: #f0f2f6; 
        border-radius: 5px 5px 0 0; 
        padding: 5px 20px;
    }
    .stTabs [aria-selected="true"] { background-color: #004a99 !important; color: white !important; }
    
    /* Metric Card Maturity */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        padding: 10px;
        border-radius: 8px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- UTILITIES ---
def clean_val(val, is_pct=False):
    if pd.isna(val) or val == '' or str(val).lower() == 'undefined': return 0.0
    s = str(val).strip().replace('€', '').replace('kr', '').replace('SEK', '')
    has_pct_sign = '%' in s
    s = s.replace('%', '').replace(' ', '')
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
f_inv = st.sidebar.file_uploader("4. Inventory", type="csv")
f_mkt = st.sidebar.file_uploader("5. Marketing Full", type="csv")
f_hybrid = st.sidebar.file_uploader("6. Z-Hybrid", type="csv")
f_mcw = st.sidebar.file_uploader("7. Market CW", type="csv")
f_mlw = st.sidebar.file_uploader("8. Market LW", type="csv")

# --- MAIN LOGIC ---
if all([f_cw, f_lw, f_ly, f_inv]):
    df_cw_raw = load_csv_robust(f_cw)
    df_lw_raw = load_csv_robust(f_lw)
    df_ly_raw = load_csv_robust(f_ly)
    df_inv_raw = load_csv_robust(f_inv)

    # Process Inventory - Aggregate by Variant for correct mapping
    inv_key = next((c for c in df_inv_raw.columns if 'zalando_article_variant' in c.lower()), 'zalando_article_variant')
    name_col = next((c for c in df_inv_raw.columns if 'article_name' in c.lower()), 'article_name')
    zfs_col = next((c for c in df_inv_raw.columns if 'zfs' in c.lower()), 'sellable_zfs_stock')
    pf_col = next((c for c in df_inv_raw.columns if 'pf' in c.lower()), 'sellable_pf_stock')
    
    df_inv_raw[zfs_col] = df_inv_raw[zfs_col].apply(clean_val)
    df_inv_raw[pf_col] = df_inv_raw[pf_col].apply(clean_val)
    inv_agg = df_inv_raw.groupby(inv_key).agg({name_col: 'first', zfs_col: 'sum', pf_col: 'sum'}).reset_index()
    inv_agg['Total Stock'] = inv_agg[zfs_col] + inv_agg[pf_col]

    # Process Sales
    def process_sales(df):
        df['NMV_EUR'] = df['NMV'].apply(clean_val)
        df['Sold'] = df[next((c for c in df.columns if 'sold' in c.lower()), 'Sold articles')].apply(clean_val)
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
    m2.metric("vs LW", f"{nmv_cw_sek:,.0f} kr", delta=f"{((nmv_cw_sek/nmv_lw_sek)-1):.1%}")
    m3.metric("vs LY", f"{nmv_ly_sek:,.0f} kr", delta=f"{((nmv_cw_sek/nmv_ly_sek)-1):.1%}")
    m4.metric("vs Budget", f"Gap", delta=f"{(nmv_cw_sek/weekly_budget_sek-1):.1%}")
    m5.metric("vs Prognos", f"Gap", delta=f"{(nmv_cw_sek/weekly_prognos_sek-1):.1%}")

    st.markdown("---")
    tabs = st.tabs(["📈 Health", "🏆 Top 50 Revenue", "❤️ Wishlist Top 50", "📣 Marketing", "🌍 Market Dev", "🔄 Hybrid", "📝 Analysis"])

    with tabs[1]: # Top 50 Revenue with Rankings
        st.subheader("🏆 Performance Ranking & Stock Alerts")
        
        cw_grp = df_cw.groupby('Article variant')[['NMV_EUR', 'Sold']].sum().reset_index()
        cw_grp['Rank'] = cw_grp['NMV_EUR'].rank(ascending=False, method='min')
        
        lw_grp = df_lw.groupby('Article variant')[['NMV_EUR']].sum().reset_index()
        lw_grp['Rank_LW'] = lw_grp['NMV_EUR'].rank(ascending=False, method='min')
        
        # Merge Rankings
        top50 = cw_grp.merge(lw_grp[['Article variant', 'Rank_LW']], on='Article variant', how='left')
        top50 = top50.merge(inv_agg, left_on='Article variant', right_on=inv_key, how='left').fillna(0)
        
        def get_trend(row):
            if row['Rank_LW'] == 0: return "🆕"
            if row['Rank'] < row['Rank_LW']: return "⬆️"
            if row['Rank'] > row['Rank_LW']: return "⬇️"
            return "➡️"
        
        top50['Status'] = top50.apply(get_trend, axis=1)
        top50 = top50.sort_values('Rank').head(50)
        
        # Display Logic
        disp_50 = top50[['Status', 'Rank', 'Article variant', name_col, 'NMV_EUR', 'Sold', zfs_col, pf_col]]
        disp_50 = disp_50.rename(columns={name_col: 'Article Name', zfs_col: 'Stock ZFS', pf_col: 'Stock PF', 'NMV_EUR': 'NMV €'})
        
        def highlight_stock(row):
            sold = row['Sold']
            styles = [''] * len(row)
            if row['Stock ZFS'] < sold and row['Stock ZFS'] > 0: styles[6] = 'background-color: #ff4b4b; color: white;'
            if row['Stock PF'] < sold and row['Stock PF'] > 0: styles[7] = 'background-color: #ff4b4b; color: white;'
            return styles

        st.dataframe(disp_50.style.format({
            'NMV €': '€{:,.0f}', 'Sold': '{:,.0f}', 'Stock ZFS': '{:,.0f}', 'Stock PF': '{:,.0f}', 'Rank': '{:.0f}'
        }).apply(highlight_stock, axis=1), hide_index=True, use_container_width=True)

    with tabs[2]: # Wishlist
        if f_mkt:
            st.subheader("❤️ Top 50 Added to Wishlist (Latest Week)")
            m_wish = load_csv_robust(f_mkt)
            m_wish.columns = [c.replace(' ', '') for c in m_wish.columns]
            latest_w = clean_val(m_wish['Week'].max())
            wish_df = m_wish[m_wish['Week'].apply(clean_val) == latest_w].groupby('ConfigSKU')['Addtowishlist'].sum().reset_index()
            wish_df['Addtowishlist'] = wish_df['Addtowishlist'].apply(clean_val)
            wish_top = wish_df.merge(inv_agg, left_on='ConfigSKU', right_on=inv_key, how='left').sort_values('Addtowishlist', ascending=False).head(50)
            st.dataframe(wish_top[['ConfigSKU', name_col, 'Addtowishlist', 'Total Stock', zfs_col, pf_col]].style.format(precision=0), hide_index=True, use_container_width=True)

    with tabs[3]: # Marketing WoW Summary
        if f_mkt:
            mkt = load_csv_robust(f_mkt)
            mkt.columns = [c.replace(' ', '') for c in mkt.columns]
            for c in ['Budgetspent', 'GMV', 'Addtowishlist', 'Clicks', 'Itemssold', 'Viewableadimpressions', 'PDPviews']:
                mkt[c] = mkt[c].apply(clean_val)
            
            # Period Filter
            y_list = sorted(mkt['Year'].apply(clean_val).unique(), reverse=True)
            w_list = sorted(mkt['Week'].apply(clean_val).unique(), reverse=True)
            col_a, col_b = st.columns(2)
            sel_w1 = col_a.selectbox("Current Week", w_list, index=0)
            sel_w2 = col_b.selectbox("Comparison Week", w_list, index=min(1, len(w_list)-1))

            p1 = mkt[mkt['Week'].apply(clean_val) == sel_w1]
            p2 = mkt[mkt['Week'].apply(clean_val) == sel_w2]

            def mkt_metrics(df, nmv_sek_val):
                s = df.sum(numeric_only=True)
                res = {}
                res['Spend'] = s['Budgetspent']
                res['GMV'] = s['GMV']
                res['ROAS'] = s['GMV'] / s['Budgetspent'] if s['Budgetspent'] > 0 else 0
                res['Impressions'] = s['Viewableadimpressions']
                res['PDP'] = s['PDPviews']
                res['CVR'] = s['Itemssold'] / s['Clicks'] if s['Clicks'] > 0 else 0
                res['COS'] = s['Budgetspent'] / s['GMV'] if s['GMV'] > 0 else 0
                res['Blended'] = s['Budgetspent'] / (nmv_sek_val / ex_rate) if nmv_sek_val > 0 else 0
                return res

            m1_vals = mkt_metrics(p1, nmv_cw_sek)
            m2_vals = mkt_metrics(p2, nmv_lw_sek)

            # High Level Row
            st.markdown("#### 📊 Executive Marketing Summary")
            r1, r2, r3, r4, r5, r6, r7 = st.columns(7)
            r1.metric("Spend", f"€{m1_vals['Spend']:,.0f}", delta=f"{(m1_vals['Spend']/m2_vals['Spend']-1):.1%}", delta_color="inverse")
            r2.metric("GMV", f"€{m1_vals['GMV']:,.0f}", delta=f"{(m1_vals['GMV']/m2_vals['GMV']-1):.1%}")
            r3.metric("ROAS", f"{m1_vals['ROAS']:.2f}x", delta=f"{(m1_vals['ROAS']-m2_vals['ROAS']):.2f}")
            r4.metric("PDP Views", f"{m1_vals['PDP']:,.0f}", delta=f"{(m1_vals['PDP']/m2_vals['PDP']-1):.1%}")
            r5.metric("CVR", f"{m1_vals['CVR']:.2%}", delta=f"{(m1_vals['CVR']-m2_vals['CVR']):.2%}")
            r6.metric("COS", f"{m1_vals['COS']:.1%}", delta=f"{(m1_vals['COS']-m2_vals['COS']):.1%}", delta_color="inverse")
            r7.metric("Blended COS", f"{m1_vals['Blended']:.1%}", delta=f"{(m1_vals['Blended']-m2_vals['Blended']):.1%}", delta_color="inverse")

            # Restore Campaign Table and Gender
            st.markdown("---")
            c_cw = p1.groupby('ZMSCampaign')[['Budgetspent', 'GMV']].sum()
            c_lw = p2.groupby('ZMSCampaign')[['Budgetspent', 'GMV']].sum()
            camp_tab = c_cw.join(c_lw, rsuffix='_LW').fillna(0)
            camp_tab['ROAS'] = camp_tab['GMV'] / camp_tab['Budgetspent'].replace(0,1)
            camp_tab['Trend'] = (camp_tab['ROAS'] / (camp_tab['GMV_LW']/camp_tab['Budgetspent_LW'].replace(0,1)).replace(0,1)) - 1
            st.write("**Campaign Performance**")
            st.dataframe(camp_tab.style.format({'Budgetspent': '€{:,.0f}', 'GMV': '€{:,.0f}', 'ROAS': '{:.2f}x', 'Trend': '{:+.1%}'}), use_container_width=True)

            if 'Gender' in mkt.columns:
                st.write("**Gender Performance (Current Week)**")
                st.dataframe(p1.groupby('Gender')[['Budgetspent', 'GMV']].sum().style.format(precision=0), use_container_width=True)

    with tabs[4]: # Market Development
        if f_mcw and f_mlw:
            mcw = load_csv_robust(f_mcw)
            mlw = load_csv_robust(f_mlw)
            for d in [mcw, mlw]:
                d['NMV_C'] = d['NMV'].apply(clean_val)
                d['Basket_C'] = d['Add to basket'].apply(lambda x: clean_val(x, is_pct=True))
                d['Conv_C'] = d['Conversion rate'].apply(lambda x: clean_val(x, is_pct=True))
                d['Sold_C'] = d['Sold articles'].apply(clean_val)
            
            mcw['Market Share'] = mcw['NMV_C'] / mcw['NMV_C'].sum()
            mcw['Dropout'] = (mcw['Basket_C'] - mcw['Conv_C']) / mcw['Basket_C'].replace(0,1)
            
            m_comp = mcw.merge(mlw[['Country', 'NMV_C']], on='Country', suffixes=('', '_LW'))
            m_comp['Growth'] = (m_comp['NMV_C'] / m_comp['NMV_C_LW']) - 1
            st.dataframe(m_comp[['Country', 'NMV_C', 'Market Share', 'Growth', 'Conv_C', 'Dropout']].style.format({
                'NMV_C': '€{:,.0f}', 'Market Share': '{:.1%}', 'Growth': '{:+.1%}', 'Conv_C': '{:.2%}', 'Dropout': '{:.1%}'
            }), hide_index=True, use_container_width=True)

    with tabs[6]: # Analysis & To-Dos
        st.subheader("📝 Strategic Summary")
        a1, a2 = st.columns(2)
        with a1:
            st.info("**Top Performance (Marketing)**")
            if f_mkt:
                best = camp_tab.sort_values('ROAS', ascending=False).head(3)
                for c, r in best.iterrows(): st.write(f"🌟 {c}: {r['ROAS']:.2f}x ROAS")
        with a2:
            st.warning("**Attention Required (Inventory)**")
            low_stk = top50[top50['Total Stock'] < top50['Sold']].head(5)
            for _, r in low_stk.iterrows(): st.write(f"⚠️ {r[name_col]}: Sold {r['Sold']:.0f} vs {r['Total Stock']:.0f} Stock")

        st.markdown("### 🚀 Weekly To-Do List")
        st.write("- [ ] **Replenishment:** Focus on the red-highlighted styles in the Top 50 Revenue tab.")
        if f_mkt and m1_vals['Blended'] > 0.15: st.write("- [ ] **Efficiency:** Blended COS is high. Trim budget from campaigns with ROAS < 2.0x.")
        st.write("- [ ] **Market Growth:** Review pricing in countries with negative growth in Market Dev tab.")

else:
    st.info("Upload Files 1-4 in the Sidebar to begin.")
