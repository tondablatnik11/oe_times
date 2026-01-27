import streamlit as st
import pandas as pd
import io
import time

# --- 1. KONFIGURACE ---
st.set_page_config(
    page_title="Logistics Analyzer Final v18",
    page_icon="🚛",
    layout="wide"
)

# --- 2. CSS ---
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { 
        width: 100%; 
        border-radius: 8px; 
        height: 3.5em; 
        background-color: #2e7bcf; 
        color: white; 
        font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. DATABÁZE PRAVIDEL (V3.17 - Kompletní seznam) ---

PACKAGING_DESC = {
    '8216.00LP.04': 'PALLET OF WOOD 01',
    '8216.2032.01': 'GESTELL 2032 Mercedes',
    '9860000415900': 'EURO-PALETTE 0010 MAN',
    '8216.00KP.04': 'PALLET OF WOOD 02',
    '8216.3215.01': 'KLT 3215 DAIMLER',
    '9860000417900': 'ABDECKPLATTE EURO 0207 MAN',
    '8216.00LR.04': 'FRAME OF WOOD 21',
    '8216.4129.01': 'KLT 4129 ESD DAIMLER',
    '8216.0100.10': 'EPP-Behälter Radiofachgeräte',
    '8216.0782.04': 'SPACER OF SOLID BOARD 61',
    '8216.4314.01': 'KLT 4314 DAIMLER',
    '9860000422400': 'KLT 4329',
    '8216.0783.04': 'SPACER OF SOLID BOARD 62',
    '8216.4329.01': 'KLT 4329 DAIMLER',
    '9860000422000': 'KLT 4315',
    '8216.00LD.04': 'LID OF PLYWOOD 71',
    '8216.5009.01': 'EURO-PALETTE 5009 DAIMLER',
    '9860000419300': 'DECKEL D41-ESD FUER KLT4129',
    '8216.00KD.04': 'LID OF PLYWOOD 72',
    '8216.5010.01': 'STAHL PALETTE 5010 DAIMLER',
    '8216.0003.10': 'LID OF PLASTIC 91',
    '8216.6129.01': 'KLT 6129 ESD DAIMLER',
    '9860000421400': 'KLT 3215',
    '8216.0092.04': 'LID OF PLASTIC 92',
    '8216.6428.01': 'KLT 6428 DAIMLER',
    '9860000423300': 'KLT 6428',
    '8216.6429.01': 'Behaelter DAG 6429 KLT',
    '9860000416100': 'RUNGENPALETTE 0036 MAN',
    '8216.9040.01': 'ABDECKPLATTE GROß 9040 DAIMLER',
    '9860000415300': 'POOL GITTERPALETTE 0002',
    '8216.0750.04': 'KIT OF BOX OF PLASTIC 750',
    '9860000126500': 'Abdeckplatte RE DTH 209040 PP',
    '9860001175000': 'Halbe Box blau 09.84019-0100',
    '8216.0780.04': 'KIT OF BOX OF PLASTIC 780',
    '9860000876100': 'Gitterbox DTH 202032',
    '9860001178000': 'ESD KLT 0523',
    '9860001205300': 'Palette RE DTH 205010 Stahl 4W',
    '9860001195800': 'EPP 09.84019-1339',
    '8216.9041.01': 'Abdeckplatte RE DAG 9041 EURO',
    '9860001530500': '0589 Deckel für KLT 4315',
    '8216.9094.01': 'DECKEL 9094 FÜR KLT 6129 DAIML',
    '9860001530600': '0569 Deckel für KLT 3215',
    '8216.9093.01': 'DECKEL ZU KLT 4129',
    '8216.0474.05': 'KLT Plastic COO8 MH-0474 SCANI',
    '8216.2035.01': 'GESTELL 2035 DAIMLER',
    '000198390A000': 'BEHAELTER KLT 6147 BLAU  594 X',
    '8216.4328.01': 'KLT 4328 DAIMLER',
    '9860001254000': 'Verp.-Set RE OEM Scania MH-0500',
    '8216.5003.01': 'HOLZ PALETTE 5003 DAIMLER',
    '8216.1875.05': 'Palette RE MTCO MH 1875 SC',
    '8216.1874.05': 'H-PALETTE MH-1874 SCANIA',
    '8216.0505.05': 'EPP MH-0505 SCANIA',
    '8216.0010.03': 'EURO-PALETTE 0010 MAN'
}

PALLET_WHITELIST = [
    '8216.00LP.04', '8216.00KP.04', 
    '8216.2032.01', '8216.2035.01', 
    '8216.5009.01', '8216.5010.01', 
    '8216.1874.05', '8216.1875.05', 
    '8216.0010.03', '9860000415900', 
    'CARTON-16', 'CARTON-17', 'CARTON-18'
]

KLT_WHITELIST = [
    '8216.3215.01', '8216.4129.01', '8216.4314.01', 
    '8216.4329.01', '8216.4328.01', '8216.6129.01', 
    '8216.0100.10', '8216.0505.05', 
    '000198390A000', '9860001393000', 
    '9860000422000', '9860001178000', 
    '9860000417900', '9860000419300', '9800004218000',
    '8216.0780.04', '8216.6428.01', 
    '8216.00LR.04', '8216.00LD.04'
]

LAYER_RULES = {
    'A2C3261731402': 4,
    '2801405007390': 4,
    'A2C7771840190': 4,
    'A3C0000550002': 4,
    'A3C1149850001': 4,
    'A2C1482010032': 8, 
    'A3C1051900001': 6,
    'A3C1223480001': 3,
    'A3C1223490001': 3,
    'A3C1149860001': 4,
}

# --- 4. FUNKCE ---
def clean_id(val):
    if pd.isna(val): return ""
    try: return str(int(float(val)))
    except: return str(val).strip()

def normalize_weight(row):
    try:
        w = float(row['Total Weight'])
        u = str(row['Unit of Weight']).upper().strip()
        if u == 'G': return w / 1000.0
        return w
    except: return 0.0

def normalize_dim(val, unit):
    try:
        val = float(val)
        unit = str(unit).upper().strip()
        if unit == 'MM': return val / 10.0
        elif unit == 'M': return val * 100.0
        return val
    except: return 0.0

def classify_hu_row(row):
    mat = str(row['Packaging materials']).upper().strip()
    l = row['L_CM']
    w = row['W_CM']
    
    if mat in KLT_WHITELIST: return pd.Series([False, True, False]) 
    if mat in PALLET_WHITELIST: return pd.Series([True, False, False])
    if 'CARTON' in mat: return pd.Series([False, False, True])

    is_pallet_dim = ((abs(l - 120) <= 2 and abs(w - 80) <= 2) or 
                     (abs(l - 80) <= 2 and abs(w - 120) <= 2) or
                     (abs(l - 120) <= 2 and abs(w - 100) <= 2))
    
    if is_pallet_dim and not mat.startswith('8216'):
        return pd.Series([True, False, False])

    return pd.Series([False, True, False]) 

# --- 5. UI ---
with st.sidebar:
    st.title("Menu")
    st.success("Verze: 18.0 (Final Merge)")
    file_hu = st.file_uploader("📂 1. OBALY (Pack)", type=['csv', 'xlsx'])
    file_items = st.file_uploader("📂 2. MATERIÁL (Pick)", type=['csv', 'xlsx'])
    file_times = st.file_uploader("📂 3. ČASY (K sjednocení)", type=['csv', 'xlsx'])

st.title("📦 Logistický Analyzátor")

if file_hu and file_items:
    try:
        # LOAD
        df_hu = pd.read_csv(file_hu) if file_hu.name.endswith('.csv') else pd.read_excel(file_hu)
        df_items = pd.read_csv(file_items) if file_items.name.endswith('.csv') else pd.read_excel(file_items)

        # PREP
        item_del_col = 'Dest.Storage Bin' if 'Dest.Storage Bin' in df_items.columns else 'Generated delivery'
        df_items['Delivery_ID'] = df_items[item_del_col].apply(clean_id)
        df_items['Material'] = df_items['Material'].astype(str)

        items_agg = df_items.groupby('Delivery_ID').agg({
            'Material': lambda x: x.mode()[0] if not x.mode().empty else x.iloc[0],
            'Act.qty (dest)': 'sum'
        }).reset_index().rename(columns={'Material': 'Hlavní_Materiál', 'Act.qty (dest)': 'Počet kusů'})

        hu_del_col = 'Generated delivery'
        df_hu = df_hu[df_hu[hu_del_col].notna()]
        df_hu['Delivery_ID'] = df_hu[hu_del_col].apply(clean_id)
        df_hu['Weight_KG'] = df_hu.apply(normalize_weight, axis=1)
        df_hu['L_CM'] = df_hu.apply(lambda x: normalize_dim(x['Length'], x['Unit of Dimension']), axis=1)
        df_hu['W_CM'] = df_hu.apply(lambda x: normalize_dim(x['Width'], x['Unit of Dimension']), axis=1)

        # Klasifikace
        df_hu[['Is_Pallet', 'Is_KLT', 'Is_Carton']] = df_hu.apply(classify_hu_row, axis=1)

        # --- DETAIL OBALŮ ---
        def get_pack_details(group):
            counts = group['Packaging materials'].value_counts()
            details = []
            for code, count in counts.items():
                code = str(code).strip()
                desc = PACKAGING_DESC.get(code, "")
                if desc:
                    details.append(f"{code} - {desc} ({count}x)")
                else:
                    details.append(f"{code} ({count}x)")
            return "; ".join(details)

        pack_details = df_hu.groupby('Delivery_ID').apply(get_pack_details).reset_index(name='Packaging Details')

        # AGGREGATION
        hu_agg = df_hu.groupby('Delivery_ID').apply(lambda x: pd.Series({
            'Raw_Pallets': x['Is_Pallet'].sum(),
            'Raw_KLTs': x['Is_KLT'].sum(),
            'Raw_Cartons': x['Is_Carton'].sum(),
            'Total_Weight': x['Weight_KG'].sum(),
            'Count_0780': (x['Packaging materials'].astype(str).str.strip() == '8216.0780.04').sum(),
            'Count_6428': (x['Packaging materials'].astype(str).str.strip() == '8216.6428.01').sum()
        }), include_groups=False).reset_index()

        # Join Details
        hu_agg = pd.merge(hu_agg, pack_details, on='Delivery_ID', how='left')

        # MERGE do základní tabulky
        final_df = pd.merge(items_agg, hu_agg, on='Delivery_ID', how='right').fillna(0)

        def apply_business_rules(row):
            mat = str(row['Hlavní_Materiál'])
            full_klts = int(row['Raw_KLTs'])
            pallets = int(row['Raw_Pallets'])
            empty_klts = 0
            
            if row['Count_0780'] == 3: full_klts += 1
            if row['Count_6428'] == 3: full_klts += 1

            layer_size = LAYER_RULES.get(mat, 1)
            if layer_size > 1 and full_klts >= layer_size: 
                remainder = full_klts % layer_size
                if remainder != 0:
                    empty_klts = layer_size - remainder
            
            total_klts = full_klts + empty_klts
            return pd.Series([pallets, total_klts, full_klts, empty_klts])

        final_df[['Počet palet', 'Počet KLT', 'Počet plných KLT', 'Počet prázdných KLT']] = final_df.apply(apply_business_rules, axis=1)
        final_df['Počet kartonů'] = final_df['Raw_Cartons']

        # Příprava dat pro merge s časy
        report_data = final_df[['Delivery_ID', 'Hlavní_Materiál', 'Počet kusů', 
                'Počet palet', 'Počet KLT', 'Počet plných KLT', 
                'Počet prázdných KLT', 'Počet kartonů', 'Packaging Details', 'Total_Weight']].copy()
        
        report_data.columns = ['Zakázka', 'Material', 'Number of pieces', 'Number of pallets', 'Number of KLTs', 'Full KLTs', 'Empty KLTs', 'Number of cartons', 'Packaging Details', 'Weight (kg)']

        # --- NOVÝ KROK: MERGE S ČASY ---
        if file_times:
            df_t = pd.read_csv(file_times) if file_times.name.endswith('.csv') else pd.read_excel(file_times)
            df_t['DN NUMBER (SAP)'] = df_t['DN NUMBER (SAP)'].apply(clean_id)
            
            # Vyčištění souboru s časy od starých (prázdných) sloupců, které chceme doplnit
            cols_to_fill = ['Material', 'Number of pieces', 'Number of pallets', 'Number of KLTs', 'Full KLTs', 'Empty KLTs', 'Number of cartons', 'Weight (kg)', 'Packaging Details']
            df_t_clean = df_t.drop(columns=[c for c in cols_to_fill if c in df_t.columns])

            # Spojení tabulek
            output_df = pd.merge(df_t_clean, report_data, left_on='DN NUMBER (SAP)', right_on='Zakázka', how='left').drop(columns=['Zakázka'])
            st.success("✅ Časy byly úspěšně propojeny s daty z reportu.")
        else:
            output_df = report_data

        # DISPLAY
        st.dataframe(output_df, use_container_width=True, hide_index=True)

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            output_df.to_excel(writer, index=False, sheet_name="Final_Report")
            worksheet = writer.sheets['Final_Report']
            for i, col in enumerate(output_df.columns):
                worksheet.set_column(i, i, 20)
        
        st.download_button("📥 STÁHNOUT FINÁLNÍ REPORT", buffer.getvalue(), "logistics_final_v18.xlsx")

    except Exception as e:
        st.error(f"Chyba: {e}")
