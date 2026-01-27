import streamlit as st
import pandas as pd
import io
import time

# --- 1. KONFIGURACE A STYL ---
st.set_page_config(
    page_title="Logistics Analyzer Pro",
    page_icon="📦",
    layout="wide"
)

# Vlastní CSS pro "vystajlování" aplikace
st.markdown("""
    <style>
    /* Hlavní pozadí a písmo */
    .main { background-color: #fdfdfd; }
    
    /* Úprava nadpisů */
    h1 { color: #1e3a8a; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; font-weight: 800; }
    h3 { color: #3b82f6; font-weight: 600; margin-bottom: 0.5rem; }

    /* Design tlačítek */
    .stButton>button {
        border-radius: 12px;
        background-color: #2563eb;
        color: white;
        font-weight: 600;
        border: none;
        transition: all 0.3s ease;
        padding: 0.6rem;
    }
    .stButton>button:hover {
        background-color: #1d4ed8;
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.2);
    }
    
    /* Vylepšení karet s metrikami */
    [data-testid="stMetricValue"] { font-size: 1.8rem; color: #1e3a8a; }
    
    /* Čistší Sidebar */
    section[data-testid="stSidebar"] { background-color: #f1f5f9; border-right: 1px solid #e2e8f0; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATABÁZE PRAVIDEL (Vše z v17) ---
PACKAGING_DESC = {
    '8216.00LP.04': 'PALLET OF WOOD 01', '8216.2032.01': 'GESTELL 2032 Mercedes',
    '9860000415900': 'EURO-PALETTE 0010 MAN', '8216.00KP.04': 'PALLET OF WOOD 02',
    '8216.3215.01': 'KLT 3215 DAIMLER', '9860000417900': 'ABDECKPLATTE EURO 0207 MAN',
    '8216.00LR.04': 'FRAME OF WOOD 21', '8216.4129.01': 'KLT 4129 ESD DAIMLER',
    '8216.0100.10': 'EPP-Behälter Radiofachgeräte', '8216.0782.04': 'SPACER OF SOLID BOARD 61',
    '8216.4314.01': 'KLT 4314 DAIMLER', '9860000422400': 'KLT 4329',
    '8216.4329.01': 'KLT 4329 DAIMLER', '9860000422000': 'KLT 4315',
    '8216.5009.01': 'EURO-PALETTE 5009 DAIMLER', '8216.6129.01': 'KLT 6129 ESD DAIMLER',
    '9860000421400': 'KLT 3215', '8216.1875.05': 'Palette RE MTCO MH 1875 SC',
    '8216.0010.03': 'EURO-PALETTE 0010 MAN', '8216.0474.05': 'KLT Plastic COO8 MH-0474 SCANI'
}

PALLET_WHITELIST = ['8216.00LP.04', '8216.00KP.04', '8216.2032.01', '8216.5009.01', '8216.1875.05', '8216.0010.03', '9860000415900', 'CARTON-16', 'CARTON-17', 'CARTON-18']
KLT_WHITELIST = ['8216.3215.01', '8216.4129.01', '8216.4314.01', '8216.4329.01', '8216.6129.01', '9860000422000', '9860000421400', '000198390A000']
LAYER_RULES = {'A2C3261731402': 4, '2801405007390': 4, 'A2C7771840190': 4, 'A3C1149850001': 4, 'A2C1482010032': 8, 'A3C1051900001': 6, 'A3C1223480001': 3, 'A3C1223490001': 3, 'A3C1149860001': 4}

# --- 3. FUNKCE ---
def clean_id(val):
    if pd.isna(val): return ""
    try: return str(int(float(val)))
    except: return str(val).strip()

def normalize_weight(row):
    try:
        w = float(row['Total Weight'])
        u = str(row['Unit of Weight']).upper().strip()
        return w / 1000.0 if u == 'G' else w
    except: return 0.0

def normalize_dim(val, unit):
    try:
        val = float(val)
        unit = str(unit).upper().strip()
        if unit == 'MM': return val / 10.0
        return val * 100.0 if unit == 'M' else val
    except: return 0.0

def classify_hu_row(row):
    mat = str(row['Packaging materials']).upper().strip()
    l, w = row['L_CM'], row['W_CM']
    if mat in KLT_WHITELIST: return pd.Series([False, True, False]) 
    if mat in PALLET_WHITELIST: return pd.Series([True, False, False])
    if 'CARTON' in mat: return pd.Series([False, False, True])
    is_pallet_dim = ((abs(l - 120) <= 2 and abs(w - 80) <= 2) or (abs(l - 80) <= 2 and abs(w - 120) <= 2))
    return pd.Series([is_pallet_dim, not is_pallet_dim, False])

# --- 4. SIDEBAR ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3063/3063822.png", width=80)
    st.title("Nastavení")
    st.markdown("---")
    
    st.subheader("📁 Vstupní data")
    file_hu = st.file_uploader("1. OBALY (Pack)", type=['csv', 'xlsx'], help="Export balících jednotek (Handling Units)")
    file_items = st.file_uploader("2. MATERIÁL (Pick)", type=['csv', 'xlsx'], help="Export položek ze skladu")
    
    st.markdown("---")
    st.subheader("🕒 Časový harmonogram")
    file_times = st.file_uploader("3. ČASY (Volitelné)", type=['csv', 'xlsx'], help="Soubor pro sjednocení časy + data")
    
    st.info(f"Verze: 18.1 Pro\nStatus: Online")

# --- 5. HLAVNÍ OBSAH ---
st.title("🚛 Logistics Analyzer Pro")
st.markdown("Sjednocení logistických reportů a časových plánů v reálném čase.")

if file_hu and file_items:
    try:
        # Tichý processing
        df_hu = pd.read_csv(file_hu) if file_hu.name.endswith('.csv') else pd.read_excel(file_hu)
        df_items = pd.read_csv(file_items) if file_items.name.endswith('.csv') else pd.read_excel(file_items)

        item_del_col = 'Dest.Storage Bin' if 'Dest.Storage Bin' in df_items.columns else 'Generated delivery'
        df_items['Delivery_ID'] = df_items[item_del_col].apply(clean_id)
        items_agg = df_items.groupby('Delivery_ID').agg({'Material': lambda x: x.iloc[0], 'Act.qty (dest)': 'sum'}).reset_index().rename(columns={'Material': 'Hlavní_Materiál', 'Act.qty (dest)': 'Počet kusů'})

        df_hu['Delivery_ID'] = df_hu['Generated delivery'].apply(clean_id)
        df_hu['Weight_KG'] = df_hu.apply(normalize_weight, axis=1)
        df_hu['L_CM'] = df_hu.apply(lambda x: normalize_dim(x['Length'], x['Unit of Dimension']), axis=1)
        df_hu['W_CM'] = df_hu.apply(lambda x: normalize_dim(x['Width'], x['Unit of Dimension']), axis=1)
        df_hu[['Is_Pallet', 'Is_KLT', 'Is_Carton']] = df_hu.apply(classify_hu_row, axis=1)

        def get_pack_details(group):
            counts = group['Packaging materials'].value_counts()
            return "; ".join([f"{str(c).strip()} ({n}x)" for c, n in counts.items()])

        pack_details = df_hu.groupby('Delivery_ID').apply(get_pack_details).reset_index(name='Packaging Details')
        hu_agg = df_hu.groupby('Delivery_ID').apply(lambda x: pd.Series({
            'Raw_Pallets': x['Is_Pallet'].sum(), 'Raw_KLTs': x['Is_KLT'].sum(), 'Raw_Cartons': x['Is_Carton'].sum(), 'Total_Weight': x['Weight_KG'].sum(),
            'Count_0780': (x['Packaging materials'].astype(str).str.strip() == '8216.0780.04').sum(),
            'Count_6428': (x['Packaging materials'].astype(str).str.strip() == '8216.6428.01').sum()
        }), include_groups=False).reset_index()

        final_df = pd.merge(items_agg, pd.merge(hu_agg, pack_details, on='Delivery_ID'), on='Delivery_ID', how='right').fillna(0)

        def apply_rules(row):
            full_klts = int(row['Raw_KLTs'])
            if row['Count_0780'] == 3 or row['Count_6428'] == 3: full_klts += 1
            l_size = LAYER_RULES.get(str(row['Hlavní_Materiál']), 1)
            empty = (l_size - (full_klts % l_size)) if (l_size > 1 and full_klts >= l_size and (full_klts % l_size) != 0) else 0
            return pd.Series([int(row['Raw_Pallets']), full_klts + empty, full_klts, empty])

        final_df[['Počet palet', 'Počet KLT', 'Počet plných KLT', 'Počet prázdných KLT']] = final_df.apply(apply_rules, axis=1)
        
        report_data = final_df[['Delivery_ID', 'Hlavní_Materiál', 'Počet kusů', 'Počet palet', 'Počet KLT', 'Počet plných KLT', 'Počet prázdných KLT', 'Raw_Cartons', 'Packaging Details', 'Total_Weight']].copy()
        report_data.columns = ['Zakázka', 'Material', 'Number of pieces', 'Number of pallets', 'Number of KLTs', 'Full KLTs', 'Empty KLTs', 'Number of cartons', 'Packaging Details', 'Weight (kg)']

        # --- MERGE LOGIKA ---
        if file_times:
            df_t = pd.read_csv(file_times) if file_times.name.endswith('.csv') else pd.read_excel(file_times)
            df_t['DN NUMBER (SAP)'] = df_t['DN NUMBER (SAP)'].apply(clean_id)
            cols_to_fill = ['Material', 'Number of pieces', 'Number of pallets', 'Number of KLTs', 'Full KLTs', 'Empty KLTs', 'Number of cartons', 'Weight (kg)', 'Packaging Details']
            output_df = pd.merge(df_t.drop(columns=[c for c in cols_to_fill if c in df_t.columns]), report_data, left_on='DN NUMBER (SAP)', right_on='Zakázka', how='left').drop(columns=['Zakázka'])
        else:
            output_df = report_data

        # --- VIZUÁLNÍ PANEL METRIK ---
        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("📦 Celkem zakázek", len(output_df))
        m2.metric("⚖️ Celková váha", f"{output_df['Weight (kg)'].sum():,.1f} kg")
        m3.metric("🏗️ Počet palet", int(output_df['Number of pallets'].sum()))
        m4.metric("🔧 Prázdné KLT", int(output_df['Empty KLTs'].sum()))

        # --- HLAVNÍ TABULKA ---
        st.subheader("🔍 Náhled výsledných dat")
        st.dataframe(
            output_df, 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "Weight (kg)": st.column_config.NumberColumn("Váha", format="%.2f kg"),
                "Number of pieces": st.column_config.NumberColumn("Kusy"),
                "Empty KLTs": st.column_config.NumberColumn("⚠️ Prázdné KLT")
            }
        )

        # --- EXPORT ---
        st.divider()
        col_down, _ = st.columns([1, 2])
        with col_down:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                output_df.to_excel(writer, index=False, sheet_name="Final_Report")
                # Auto-fit sloupců pro Excel
                worksheet = writer.sheets['Final_Report']
                for i, col in enumerate(output_df.columns):
                    column_len = max(output_df[col].astype(str).str.len().max(), len(col)) + 2
                    worksheet.set_column(i, i, column_len)
            
            st.download_button(
                label="📥 STÁHNOUT KOMPLETNÍ EXCEL REPORT",
                data=buffer.getvalue(),
                file_name=f"Logistics_Report_{time.strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.ms-excel"
            )

    except Exception as e:
        st.error(f"⚠️ Došlo k chybě při zpracování: {e}")
else:
    # Úvodní obrazovka, když nejsou data
    st.info("💡 Nahrajte soubory v levém menu pro zahájení analýzy.")
    st.image("https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?auto=format&fit=crop&q=80&w=1000", caption="Logistics Hub")
