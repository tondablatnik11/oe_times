import streamlit as st
import pandas as pd
import io

# --- KONFIGURACE ---
st.set_page_config(page_title="Logistics Analyzer", layout="wide")
st.title("📦 Logistický Analyzátor Zakázek")

# --- LOGIKA ---
PALLET_CARTONS = ['CARTON-16', 'CARTON-17', 'CARTON-18']

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

def classify_hu(row):
    mat = str(row['Packaging materials']).upper().strip()
    l = row['L_CM']
    w = row['W_CM']
    load_wt = row['Loading weight']

    is_pallet = False
    dim_match = ((abs(l - 120) <= 2 and abs(w - 80) <= 2) or (abs(l - 80) <= 2 and abs(w - 120) <= 2))
    if dim_match or mat in PALLET_CARTONS:
        is_pallet = True

    is_klt = False
    if (mat.startswith('8216') or 'KLT' in mat) and not is_pallet:
        is_klt = True

    is_carton = False
    if 'CARTON' in mat and not is_pallet and not is_klt:
        is_carton = True

    is_full = False
    try:
        if pd.notna(load_wt) and float(load_wt) > 0: is_full = True
    except: pass

    return pd.Series([is_pallet, is_klt, is_carton, is_full])

# --- GUI APLIKACE ---
st.write("Nahrajte exporty pro analýzu.")
col1, col2 = st.columns(2)
file_hu = col1.file_uploader("Soubor 1: OBALY (HU)", type=['csv', 'xlsx'])
file_items = col2.file_uploader("Soubor 2: MATERIÁLY (Items)", type=['csv', 'xlsx'])

if file_hu and file_items:
    try:
        # Načtení
        df_hu = pd.read_csv(file_hu) if file_hu.name.endswith('.csv') else pd.read_excel(file_hu)
        df_items = pd.read_csv(file_items) if file_items.name.endswith('.csv') else pd.read_excel(file_items)

        # Items logic
        if 'Dest.Storage Bin' in df_items.columns:
            df_items['Delivery_ID'] = df_items['Dest.Storage Bin'].astype(str).str.replace(r'\.0$', '', regex=True)
        else:
            st.error("Chyba: Soubor materiálů nemá sloupec 'Dest.Storage Bin'")
            st.stop()

        items_agg = df_items.groupby('Delivery_ID').agg({
            'Material': lambda x: ", ".join(x.unique().astype(str)),
            'Act.qty (dest)': 'sum'
        }).reset_index().rename(columns={'Material': 'Materiál', 'Act.qty (dest)': 'Počet kusů'})

        # HU logic
        if 'Generated delivery' in df_hu.columns:
            df_hu = df_hu[df_hu['Generated delivery'].notna()]
            df_hu['Delivery_ID'] = df_hu['Generated delivery'].astype(str).str.replace(r'\.0$', '', regex=True)
        else:
            st.error("Chyba: Soubor obalů nemá sloupec 'Generated delivery'")
            st.stop()
            
        df_hu['Weight_KG'] = df_hu.apply(normalize_weight, axis=1)
        df_hu['L_CM'] = df_hu.apply(lambda x: normalize_dim(x['Length'], x['Unit of Dimension']), axis=1)
        df_hu['W_CM'] = df_hu.apply(lambda x: normalize_dim(x['Width'], x['Unit of Dimension']), axis=1)
        df_hu[['Is_Pallet', 'Is_KLT', 'Is_Carton', 'Is_Full']] = df_hu.apply(classify_hu, axis=1)

        hu_agg = df_hu.groupby('Delivery_ID').apply(lambda x: pd.Series({
            'Počet palet': x['Is_Pallet'].sum(),
            'Počet KLT': x['Is_KLT'].sum(),
            'Počet plných KLT': x[x['Is_KLT'] & x['Is_Full']].shape[0],
            'Počet prázdných KLT': x[x['Is_KLT'] & (~x['Is_Full'])].shape[0],
            'Počet kartonů': x['Is_Carton'].sum(),
            'Váha (KG)': x['Weight_KG'].sum()
        })).reset_index()

        # Merge & Output
        final_df = pd.merge(items_agg, hu_agg, on='Delivery_ID', how='right').fillna(0)
        
        cols_int = ['Počet kusů', 'Počet palet', 'Počet KLT', 'Počet plných KLT', 'Počet prázdných KLT', 'Počet kartonů']
        for c in cols_int: final_df[c] = final_df[c].astype(int)
        final_df['Váha (KG)'] = final_df['Váha (KG)'].round(2)
        
        final_df.rename(columns={'Delivery_ID': 'Zakázka (Delivery)'}, inplace=True)
        final_df = final_df[['Zakázka (Delivery)', 'Materiál', 'Počet kusů', 'Počet palet', 'Počet KLT', 'Počet plných KLT', 'Počet prázdných KLT', 'Počet kartonů', 'Váha (KG)']]

        st.success("Hotovo!")
        st.dataframe(final_df, use_container_width=True)

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            final_df.to_excel(writer, index=False)
        
        st.download_button("📥 Stáhnout Excel", buffer.getvalue(), "report.xlsx", "application/vnd.ms-excel")

    except Exception as e:

        st.error(f"Chyba: {e}")
