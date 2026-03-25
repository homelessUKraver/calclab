import streamlit as st
import pandas as pd
import scipy.stats as stats
import matplotlib.pyplot as plt
from datetime import datetime
import io
import numpy as np

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="GC-MS Master Pro", layout="wide")
st.title("🧪 System GC-MS: Pełna Analiza (Quant & Qual + IS)")

# --- INICJALIZACJA PAMIĘCI (Session State) ---
if 'results_log' not in st.session_state:
    st.session_state['results_log'] = []
if 'curve_data' not in st.session_state:
    st.session_state['curve_data'] = {'ready': False, 'avg_is_cal': 1.0, 'slope': 0, 'intercept': 0, 'r2': 0}

# --- PASEK BOCZNY (USTAWIENIA) ---
st.sidebar.header("🛡️ Ustawienia IS")
use_is = st.sidebar.checkbox("Użyj Standardu Wewnętrznego (IS)", value=True)
is_recovery_limit = st.sidebar.slider("Minimalny odzysk IS (%)", 20, 100, 50, help="Poniżej tego progu program oflaguje błąd.")

st.sidebar.divider()
st.sidebar.header("⚙️ Parametry Jakościowe (MS)")
expected_rt = st.sidebar.number_input("Oczekiwany Czas Retencji (RT)", value=5.20, format="%.2f")
rt_tolerance = st.sidebar.number_input("Tolerancja RT (+/- min)", value=0.05, format="%.2f")
nist_min = st.sidebar.slider("Min. NIST Match Score", 0, 1000, 800)

st.sidebar.subheader("Weryfikacja Jonów")
exp_ratio_q1 = st.sidebar.number_input("Oczekiwany Ratio Q1/Quant (%)", value=50.0)
ratio_tolerance = st.sidebar.number_input("Tolerancja Ratio (+/- %)", value=20.0)

# --- SEGMENT 1: KALIBRACJA ILOŚCIOWA ---
st.header("1️⃣ Kalibracja Ilościowa")
c_col1, c_col2 = st.columns([1, 2])

with c_col1:
    target_unit = st.text_input("Jednostka stężenia (x)", value="ug/mL")
    c2_input = st.text_input("Stężenia standardów (po przecinku)", value="0.1, 0.5, 1.0, 5.0")
    c2_list = [float(x.strip()) for x in c2_input.split(",") if x.strip()]

with c_col2:
    st.write("Wprowadź pola pików (Area) dla krzywej wzorcowej:")
    if use_is:
        cal_data = pd.DataFrame({
            "Stężenie x": c2_list, 
            "Area Analitu": [0.0] * len(c2_list), 
            "Area IS": [10000.0] * len(c2_list)
        })
    else:
        cal_data = pd.DataFrame({
            "Stężenie x": c2_list, 
            "Area Analitu": [0.0] * len(c2_list)
        })
    
    edited_cal_df = st.data_editor(cal_data, use_container_width=True, key="cal_editor")

if st.button("Wylicz Krzywą Kalibracyjną", type="primary"):
    x = edited_cal_df["Stężenie x"].tolist()
    if sum(edited_cal_df["Area Analitu"]) == 0:
        st.error("Wprowadź wartości Area Analitu większe od 0!")
    else:
        if use_is:
            avg_is_cal = edited_cal_df["Area IS"].mean()
            y = (edited_cal_df["Area Analitu"] / edited_cal_df["Area IS"]).tolist()
            y_label = "Response Ratio (Analit/IS)"
        else:
            avg_is_cal = 1.0
            y = edited_cal_df["Area Analitu"].tolist()
            y_label = "Peak Area (y)"

        slope, intercept, r_val, p, err = stats.linregress(x, y)
        st.session_state['curve_data'] = {
            'slope': slope, 'intercept': intercept, 'r2': r_val**2, 
            'ready': True, 'x': x, 'y': y, 'y_label': y_label,
            'avg_is_cal': avg_is_cal, 'cal_df': edited_cal_df
        }
        st.success(f"Krzywa wyliczona poprawnie! R² = {r_val**2:.4f}")

# Wyświetlanie wykresu
if st.session_state['curve_data']['ready']:
    fig, ax = plt.subplots(figsize=(8, 3))
    ax.scatter(st.session_state['curve_data']['x'], st.session_state['curve_data']['y'], color='red', zorder=5)
    line_x = np.linspace(min(st.session_state['curve_data']['x']), max(st.session_state['curve_data']['x']), 100)
    line_y = st.session_state['curve_data']['slope'] * line_x + st.session_state['curve_data']['intercept']
    ax.plot(line_x, line_y, color='blue', alpha=0.6)
    ax.set_xlabel(f"Stężenie [{target_unit}]")
    ax.set_ylabel(st.session_state['curve_data']['y_label'])
    ax.grid(True, linestyle='--', alpha=0.6)
    st.pyplot(fig)

# --- SEGMENT 2: ANALIZA PRÓBEK (NIEZNANYCH) ---
st.divider()
st.header("2️⃣ Analiza Próbek i Weryfikacja (Qualitative)")
if st.session_state['curve_data']['ready']:
    with st.expander("📝 Panel wprowadzania danych z chromatogramu", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            u_name = st.text_input("Nazwa Próbki", value=f"Próbka {len(st.session_state['results_log'])+1}")
            u_area = st.number_input("Area Analitu (Quantifier)", value=0.0)
            u_is = st.number_input("Area IS", value=st.session_state['curve_data']['avg_is_cal']) if use_is else 1.0
        with col2:
            u_rt = st.number_input("Zmierzony RT", value=0.0, format="%.2f")
            u_nist = st.number_input("NIST Match Score", value=0, min_value=0, max_value=1000)
        with col3:
            u_q1 = st.number_input("Area Jonu Q1 (Qualifier)", value=0.0)

        if st.button("Dodaj Wynik do Tabeli"):
            # Obliczenia ilościowe
            y_val = (u_area / u_is) if use_is else u_area
            conc = (y_val - st.session_state['curve_data']['intercept']) / st.session_state['curve_data']['slope']
            
            # Weryfikacja jakościowa i IS
            recovery = (u_is / st.session_state['curve_data']['avg_is_cal']) * 100 if use_is else 100.0
            is_ok = recovery >= is_recovery_limit
            
            rt_ok = abs(u_rt - expected_rt) <= rt_tolerance
            nist_ok = u_nist >= nist_min
            
            q1_ratio = (u_q1 / u_area * 100) if u_area > 0 else 0
            q1_ok = abs(q1_ratio - exp_ratio_q1) <= (exp_ratio_q1 * ratio_tolerance / 100)
            
            # Budowa statusu
            uwagi = []
            if not is_ok: uwagi.append("SŁABY IS")
            if not rt_ok: uwagi.append("ZŁE RT")
            if not nist_ok: uwagi.append("NISKI NIST")
            if not q1_ok: uwagi.append("ZŁE RATIO Q1")
            if conc < 0: uwagi.append("PONIŻEJ LOQ")
            
            final_status = "ZATWIERDZONO" if len(uwagi) == 0 else "BŁĄD"
            uwagi_str = " | ".join(uwagi) if uwagi else "OK"
            
            st.session_state['results_log'].append({
                "Nazwa": u_name,
                f"Stężenie [{target_unit}]": round(conc, 4),
                "IS Recovery %": round(recovery, 1) if use_is else "-",
                "RT": u_rt,
                "Q1 Ratio %": round(q1_ratio, 1),
                "NIST": u_nist,
                "Status": final_status,
                "Uwagi": uwagi_str
            })

# Wyświetlanie tabeli wyników
if st.session_state['results_log']:
    df_res = pd.DataFrame(st.session_state['results_log'])
    
    # Kolorowanie statusów
    def color_status(val):
        color = 'green' if val == "ZATWIERDZONO" else 'red'
        return f'color: {color}; font-weight: bold'

    st.subheader("📊 Wyniki Końcowe Serii")
    # Zabezpieczenie przed błędem w nowszych wersjach pandas (użycie map zamiast applymap)
    st.dataframe(df_res.style.map(color_status, subset=['Status']))

# --- SEGMENT 3: EKSPORT DO CSV ---
st.divider()
def format_eur(val):
    return str(val).replace('.', ',')

def generate_csv_full():
    output = io.StringIO()
    output.write("--- RAPORT GC-MS: QUANT & QUAL ---\n")
    output.write(f"Data wygenerowania;{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    output.write(f"Tryb Standardu Wewnetrznego (IS);{'WLACZONY' if use_is else 'WYLACZONY'}\n\n")
    
    output.write("--- PARAMETRY KRZYWEJ ---\n")
    output.write(f"Rownanie;y = {format_eur(round(st.session_state['curve_data']['slope'], 5))}x + {format_eur(round(st.session_state['curve_data']['intercept'], 5))}\n")
    output.write(f"R-kwadrat (R2);{format_eur(round(st.session_state['curve_data']['r2'], 5))}\n")
    if use_is:
        output.write(f"Srednie Area IS (100%);{format_eur(round(st.session_state['curve_data']['avg_is_cal'], 2))}\n")
    output.write("\n")
    
    output.write("--- WYNIKI PROBEK NIEZNANYCH ---\n")
    if st.session_state['results_log']:
        df_export = pd.DataFrame(st.session_state['results_log'])
        # Konwersja wszystkich liczb na format z przecinkiem dla Excela
        for col in df_export.select_dtypes(include=['float', 'float64']):
            df_export[col] = df_export[col].apply(format_eur)
        
        output.write(df_export.to_csv(index=False, sep=';'))
    else:
        output.write("Brak wprowadzonych probek.\n")
        
    return output.getvalue()

if st.session_state['results_log']:
    st.download_button(
        label="📥 Pobierz Pełny Certyfikat Analizy (CSV do Excela)", 
        data=generate_csv_full(), 
        file_name=f"GCMS_Raport_{datetime.now().strftime('%Y%m%d_%H%M')}.csv", 
        mime="text/csv",
        type="primary"
    )

if st.button("Wyczyść wszystkie dane (Nowa Seria)"):
    st.session_state['results_log'] = []
    st.session_state['curve_data'] = {'ready': False, 'avg_is_cal': 1.0, 'slope': 0, 'intercept': 0, 'r2': 0}
    st.rerun()
