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
    [data-testid="stDataFrame"] td, [data-testid="stDataFrame"] th { padding: 1px 4px !important; }
    [data-testid="stDataFrame"] { font-weight: 500 !important; font-size: 13px !important; }
    [data-testid="stDataFrame"] th { background-color: #f0f2f6 !important; color: black !important; font-weight: bold !important; }
    .stMetric { background-color: #ffffff; padding: 10px; border-radius: 8px; border: 1px solid #f0f2f6; }
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
    
    # --- PRE-CLEAN PRIMARY SALES DATA ---
    # This block ensures 'Sold_Units' and rounded NMV exist for all calculations
    for df in [df_cw, df_lw, df_ly]:
        # Handle fuzzy matching for "Sold articles" column name
        src_sold_col = next((c for c in df.columns if 'sold articles' in c.lower()), None)
        
        df['NMV_EUR'] = df['NMV'].apply(clean_val)
        if src_sold_col:
            df['Sold_Units'] = df[src_sold_col].apply(clean_val)
        else:
            df['Sold_Units'] = 0.0
            
        df['NMV_SEK'] = df['NMV_EUR'] * ex_rate

    # Calculate Top-Level SEK Metrics
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

    # --- TAB 1: BRAND HEALTH ---
    with tab1:
        st.subheader("Health Tracker: YoY Growth (SEK)")
        c1, c2 = st.columns(2)
        for col, grp in zip([c1, c2], ['Brand', 'Article type']):
            cw_g = df_cw.groupby(grp)['NMV_SEK'].sum().reset_index().rename(columns={'NMV_SEK': 'CW_kr'})
            ly_g = df_ly.groupby(grp)['NMV_SEK'].sum().reset_index().rename(columns={'NMV_SEK': 'LY_kr'})
            m = cw_g.merge(ly_g, on=grp, how='left').fillna(0)
            
            # --- ROUNDING LOGIC (DATA) ---
            m['CW_kr'] = m['CW_kr'].round(0).astype(int)
            m['LY_kr'] = m['LY_kr'].round(0).astype(int)
            m['Growth %'] = (m['CW_kr'] - m['LY_kr']) / m['LY_kr'].replace(0, 1)
            
            m['Status'] = m['Growth %'].apply(lambda x: "🟢 Growth" if x > 0.05 else ("🔻 Decline" if x < -0.05 else "➖ Stable"))
            
            # --- ROUNDING LOGIC (DISPLAY) ---
            col.dataframe(
                m.sort_values('CW_kr', ascending=False), 
                column_config={
                    "CW_kr": st.column_config.NumberColumn("CW (kr)", format="%d kr"),
                    "LY_kr": st.column_config.NumberColumn("LY (kr)", format="%d kr"),
                    "Growth %": st.column_config.NumberColumn("Growth %", format="%.0f%%")
                },
                hide_index=True, 
                use_container_width=True
            )

    # --- TAB 2: ARTICLE PERFORMANCE & TRENDS (UPDATED AGGREGATION) ---
    with tab2:
        st.subheader("🏆 Top 50 Articles: Performance & Stock Alerts")
        
        # 1. Identify Inventory Columns
        inv_var_col = next((c for c in df_inv.columns if 'variant' in c.lower()), 'Article variant')
        name_col = 'article_name' if 'article_name' in df_inv.columns else \
                   next((c for c in df_inv.columns if any(k in c.lower() for k in ['article name', 'product title', 'title']) and 'partner' not in c.lower()), None)
        zfs_col = next((c for c in df_inv.columns if 'zfs' in c.lower()), None)
        pf_col = next((c for c in df_inv.columns if any(k in c.lower() for k in ['partner', 'pf']) and 'stock' in c.lower()), None)
        
        # --- NEW AGGREGATION LOGIC: SUM STOCK PER VARIANT ---
        # 1. Clean stock columns BEFORE grouping to ensure they are numeric
        if zfs_col: df_inv[zfs_col] = df_inv[zfs_col].apply(clean_val)
        if pf_col: df_inv[pf_col] = df_inv[pf_col].apply(clean_val)
        
        # 2. Group by Style/Variant and sum the stock across all sizes
        agg_dict = {}
        if name_col: agg_dict[name_col] = 'first' # Keep the descriptive name
        if zfs_col: agg_dict[zfs_col] = 'sum'     # Sum all ZFS rows (sizes)
        if pf_col: agg_dict[pf_col] = 'sum'       # Sum all PF rows (sizes)
        
        inv_map = df_inv.groupby(inv_var_col).agg(agg_dict).reset_index()
        
        # Force integer type for stock columns after summation
        if zfs_col: inv_map[zfs_col] = inv_map[zfs_col].astype(int)
        if pf_col: inv_map[pf_col] = inv_map[pf_col].astype(int)

        # 2. Aggregate Sales (Already correctly grouping in your script)
        target_cols = [c for c in ['NMV_EUR', 'Sold_Units'] if c in df_cw.columns]
        cw_art = df_cw.groupby('Article variant')[target_cols].sum().reset_index()
        
        if 'Sold_Units' not in cw_art.columns: cw_art['Sold_Units'] = 0
            
        lw_art = df_lw.groupby('Article variant')[['NMV_EUR']].sum().reset_index().rename(columns={'NMV_EUR': 'NMV_LW'})
        
        # 3. Merge & Status
        top = cw_art.merge(lw_art, on='Article variant', how='left').fillna(0)
        
        def get_status_icon(row):
            if row['NMV_LW'] == 0: return "🆕 New"
            return "🟢 Up" if row['NMV_EUR'] > row['NMV_LW'] else "🔴 Down"
        
        top['Status sales'] = top.apply(get_status_icon, axis=1)
        top = top.merge(inv_map, left_on='Article variant', right_on=inv_var_col, how='left')
        
        # Rename for output display
        rename_dict = {
            name_col: "Article Name",
            zfs_col: "Article Stock ZFS",
            pf_col: "Article Stock PF",
            "Sold_Units": "Article sold items",
            "NMV_EUR": "Article NMV €"
        }
        top = top.rename(columns={k: v for k, v in rename_dict.items() if k in top.columns})
        
        # Round values for clean presentation
        top['Article NMV €'] = top['Article NMV €'].round(0).astype(int)
        top['Article sold items'] = top['Article sold items'].round(0).astype(int)
        
        top = top.sort_values('Article NMV €', ascending=False).head(50)

        # 4. Display
        final_headers = ['Status sales', 'Article variant', 'Article Name', 'Article NMV €', 'Article sold items', 'Article Stock ZFS', 'Article Stock PF']
        existing_headers = [h for h in final_headers if h in top.columns]

        st.dataframe(
            top[existing_headers].style.apply(lambda x: [
                'background-color: #ffcccc' if (col in ['Article Stock ZFS', 'Article Stock PF'] and 0 < val < x['Article sold items']) else '' 
                for col, val in x.items()
            ], axis=1),
            column_config={
                "Article NMV €": st.column_config.NumberColumn("Article NMV €", format="€%d"),
                "Article sold items": st.column_config.NumberColumn("Article sold items", format="%d"),
                "Article Stock ZFS": st.column_config.NumberColumn("Article Stock ZFS", format="%d"),
                "Article Stock PF": st.column_config.NumberColumn("Article Stock PF", format="%d"),
            }, 
            hide_index=True, 
            use_container_width=True
        )
        
        st.caption("💡 Cells highlighted in red indicate style stock levels (sum of all sizes) lower than this week's sales.")

    with tab3:
        if f_mkt:
            mkt = load_csv_robust(f_mkt)
            mkt.columns = [c.replace(' ', '') for c in mkt.columns]
            
            # --- MAPPING & CLEANING ---
            m_cols = {'Spend': 'Budgetspent', 'GMV': 'GMV', 'Wish': 'Addtowishlist', 'Clicks': 'Clicks', 'Sold': 'Itemssold', 'Impressions': 'Impressions'}
            for k, v in m_cols.items():
                target_col = v if v in mkt.columns else next((c for c in mkt.columns if k.lower() in c.lower()), None)
                if target_col: mkt[k] = mkt[target_col].apply(clean_val)
                else: mkt[k] = 0.0
            
            mkt['ZMSCampaign'] = mkt['ZMSCampaign'] if 'ZMSCampaign' in mkt.columns else (mkt['Campaign'] if 'Campaign' in mkt.columns else "Unknown")
            mkt['ArticleSKU'] = mkt['ArticleSKU'] if 'ArticleSKU' in mkt.columns else (mkt['SKU'] if 'SKU' in mkt.columns else "Unknown")
            
            mkt['Week'] = mkt['Week'].apply(clean_val).astype(int)
            mkt['Year'] = mkt['Year'].apply(clean_val).astype(int) if 'Year' in mkt.columns else 2024
            
            weeks = sorted(mkt['Week'].unique())
            years = sorted(mkt['Year'].unique())
            
            if len(weeks) >= 2:
                cw_w, lw_w = weeks[-1], weeks[-2]
                llw_w = weeks[-3] if len(weeks) > 2 else None
                curr_yr = years[-1]
                last_yr = years[-2] if len(years) > 1 else None
                
                # Fetch total sales for Blended COS (Total NMV in EUR)
                total_sales_eur = (nmv_cw_sek / ex_rate) if 'nmv_cw_sek' in locals() else 0

                def get_mkt_stats(y, w):
                    subset = mkt[(mkt['Year'] == y) & (mkt['Week'] == w)]
                    s = subset[['Spend', 'GMV', 'Wish', 'Clicks', 'Sold', 'Impressions']].sum()
                    s['ROAS'] = s['GMV'] / s['Spend'] if s['Spend'] > 0 else 0
                    s['COS'] = s['Spend'] / s['GMV'] if s['GMV'] > 0 else 0
                    return s

                s_cw = get_mkt_stats(curr_yr, cw_w)
                s_lw = get_mkt_stats(curr_yr, lw_w)
                s_ly = get_mkt_stats(last_yr, cw_w) if last_yr else s_cw * 0
                
                blended_cos_cw = s_cw['Spend'] / total_sales_eur if total_sales_eur > 0 else 0
                
                def pct_change(c, p): return ((c/p)-1) if p > 0 else 0

                # --- TOP KPI SUMMARY ---
                st.subheader(f"Marketing Performance Week {cw_w}")
                
                # We use 6 columns now to include the new GMV summary
                mk1, mk2, mk3, mk4, mk5, mk6 = st.columns(6)
                
                # 1. Ad Spend
                mk1.metric("Ad Spend", f"€{s_cw['Spend']:,.0f}", 
                           delta=f"LW: {pct_change(s_cw['Spend'], s_lw['Spend']):.1%}")
                
                # 2. Total GMV (The new addition)
                mk2.metric("Total GMV", f"€{s_cw['GMV']:,.0f}", 
                           delta=f"LW: {pct_change(s_cw['GMV'], s_lw['GMV']):.1%}")
                
                # 3. ROAS
                mk3.metric("ROAS", f"{s_cw['ROAS']:.2f}x", 
                           delta=f"LW: {pct_change(s_cw['ROAS'], s_lw['ROAS']):.1%}")
                
                # 4. COS
                mk4.metric("COS", f"{s_cw['COS']:.1%}", 
                           delta=f"LW: {(s_cw['COS'] - s_lw['COS']):.1%}", delta_color="inverse")
                
                # 5. Blended COS
                mk5.metric("Blended COS", f"{blended_cos_cw:.1%}", help="Ad Spend / Total Marketplace NMV")
                
                # 6. Impressions
                mk6.metric("Impressions", f"{s_cw['Impressions']:,.0f}", 
                           delta=f"LY: {pct_change(s_cw['Impressions'], s_ly['Impressions']):.1%}")

                # --- TREND CHART ---
                st.markdown("---")
                trend_df = mkt[mkt['Year'] == curr_yr].groupby('Week').agg({'Spend':'sum', 'GMV':'sum'}).reset_index()
                trend_df['ROAS'] = trend_df['GMV'] / trend_df['Spend']
                
                fig = make_subplots(specs=[[{"secondary_y": True}]])
                fig.add_trace(go.Bar(x=trend_df['Week'], y=trend_df['Spend'], name="Spend", marker_color='#ff4b4b'), secondary_y=False)
                fig.add_trace(go.Bar(x=trend_df['Week'], y=trend_df['GMV'], name="GMV", marker_color='#0068c9', opacity=0.6), secondary_y=False)
                fig.add_trace(go.Scatter(x=trend_df['Week'], y=trend_df['ROAS'], name="ROAS", line=dict(color='#2ecc71', width=3)), secondary_y=True)
                fig.update_layout(title="Marketing Efficiency Trend", barmode='group', height=350, margin=dict(l=0,r=0,t=30,b=0))
                st.plotly_chart(fig, use_container_width=True)

                # --- CAMPAIGN PERFORMANCE ---
                st.markdown("---")
                st.subheader("📣 Campaign Analytics (WoW & YoY Compare)")
                
                def get_camp_data(y, w):
                    if w is None: return pd.DataFrame(columns=['Spend', 'GMV'])
                    return mkt[(mkt['Year']==y) & (mkt['Week']==w)].groupby('ZMSCampaign')[['Spend', 'GMV']].sum()

                c_cw = get_camp_data(curr_yr, cw_w)
                c_lw = get_camp_data(curr_yr, lw_w)
                c_llw = get_camp_data(curr_yr, llw_w)
                c_ly = get_camp_data(last_yr, cw_w)

                camp_final = c_cw.join(c_lw, rsuffix='_LW', how='left').join(c_llw, rsuffix='_LLW', how='left').join(c_ly, rsuffix='_LY', how='left').fillna(0)
                
                # Check for column existence
                for col_suffix in ['_LW', '_LLW', '_LY']:
                    if f'Spend{col_suffix}' not in camp_final.columns: camp_final[f'Spend{col_suffix}'] = 0.0
                    if f'GMV{col_suffix}' not in camp_final.columns: camp_final[f'GMV{col_suffix}'] = 0.0
                
                # Safe calculations using lambda instead of .replace on scalars
                camp_final['COS'] = camp_final.apply(lambda x: x['Spend'] / x['GMV'] if x['GMV'] != 0 else 0, axis=1)
                camp_final['Spend vs LLW %'] = (camp_final['Spend_LW'] - camp_final['Spend_LLW']) / camp_final['Spend_LLW'].apply(lambda x: x if x != 0 else 1)
                camp_final['Spend LW vs LY %'] = (camp_final['Spend_LW'] - camp_final['Spend_LY']) / camp_final['Spend_LY'].apply(lambda x: x if x != 0 else 1)
                camp_final['GMV vs LLW %'] = (camp_final['GMV_LW'] - camp_final['GMV_LLW']) / camp_final['GMV_LLW'].apply(lambda x: x if x != 0 else 1)
                
                camp_final['ROAS LW'] = camp_final.apply(lambda x: x['GMV_LW'] / x['Spend_LW'] if x['Spend_LW'] != 0 else 0, axis=1)
                
                # Fixed ROAS Trend logic
                def calc_roas_trend(row):
                    cur_roas = row['GMV'] / row['Spend'] if row['Spend'] != 0 else 0
                    prev_roas = row['GMV_LW'] / row['Spend_LW'] if row['Spend_LW'] != 0 else 0
                    return "🟢" if cur_roas >= prev_roas else "🔴"
                
                camp_final['ROAS Trend'] = camp_final.apply(calc_roas_trend, axis=1)

                st.dataframe(
                    camp_final.reset_index()[['ZMSCampaign', 'Spend', 'Spend vs LLW %', 'GMV', 'COS', 'ROAS LW', 'ROAS Trend']], 
                    column_config={
                        "Spend": st.column_config.NumberColumn("Spend CW (€)", format="€%d"),
                        "Spend vs LLW %": st.column_config.NumberColumn("vs LLW %", format="%.0f%%"),
                        "GMV": st.column_config.NumberColumn("GMV CW (€)", format="€%d"),
                        "COS": st.column_config.NumberColumn("COS %", format="%.1f%%"),
                        "ROAS LW": st.column_config.NumberColumn("ROAS LW", format="%.2fx")
                    }, hide_index=True, use_container_width=True)

                # --- ARTICLE ANALYTICS ---
                st.markdown("---")
                st.subheader("📦 Article SKU Performance (Current Week)")
                art_df = mkt[(mkt['Year']==curr_yr) & (mkt['Week']==cw_w)].groupby('ArticleSKU').agg({
                    'GMV': 'sum', 'Spend': 'sum', 'Clicks': 'sum', 'Sold': 'sum', 'Wish': 'sum'
                }).reset_index()
                
                # Rounding and Safe Division for Article Table
                art_df['Article NMV €'] = art_df['GMV'].round(0).astype(int)
                art_df['ROAS'] = art_df.apply(lambda x: x['GMV'] / x['Spend'] if x['Spend'] != 0 else 0, axis=1)
                art_df['COS'] = art_df.apply(lambda x: x['Spend'] / x['GMV'] if x['GMV'] != 0 else 0, axis=1)
                art_df['CVR'] = art_df.apply(lambda x: x['Sold'] / x['Clicks'] if x['Clicks'] != 0 else 0, axis=1)
                
                st.dataframe(
                    art_df[['ArticleSKU', 'ROAS', 'COS', 'Clicks', 'CVR', 'Wish']].sort_values('ROAS', ascending=False),
                    column_config={
                        "ROAS": st.column_config.NumberColumn("ROAS", format="%.2fx"),
                        "COS": st.column_config.NumberColumn("COS %", format="%.1f%%"),
                        "Clicks": st.column_config.NumberColumn("Clicks", format="%d"),
                        "CVR": st.column_config.NumberColumn("CVR", format="%.1%"),
                        "Wish": st.column_config.NumberColumn("Wishlists", format="%d")
                    }, hide_index=True, use_container_width=True)
            else:
                st.warning("Please upload a marketing file containing at least two weeks of data.")
        else:
            st.info("Upload Marketing CSV in the sidebar to view performance depth.")

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
    st.info("Awaiting file uploads 1-4 in the sidebar to generate board.")
