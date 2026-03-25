import streamlit as st
import pandas as pd
import scipy.stats as stats
import matplotlib.pyplot as plt
from datetime import datetime
import io

st.set_page_config(page_title="GC-MS Pełny Raport", layout="centered")
st.title("Kalkulator Stężeń")

# Inicjalizacja pamięci dla wyników próbek nieznanych (żeby nie znikały przy odświeżeniu)
if 'unknowns_results' not in st.session_state:
    st.session_state['unknowns_results'] = []

# --- 1. Parametry ---
st.header("1. Parametry")
col1, col2 = st.columns(2)
with col1:
    stock_unit = st.text_input("Jednostka koncentracji stock roztworu (np. mg/L)", value="mg/L")
    target_unit = st.text_input("Jednostka koncentracji standardów (np. ug/mL)", value="ug/mL")
    vol_unit = st.text_input("Jednostka objętości standardów (np. mL)", value="mL")
with col2:
    C1_raw = st.number_input(f"Stężenie stock rozwtworu ({stock_unit})", value=100.0)
    V2 = st.number_input(f"Objętość końcowa standardu ({vol_unit})", value=10.0)
    c2_input = st.text_input("Stężenia standardów (oddzielone przecinkiem)", value="0.1, 0.5, 1.0, 2.0, 5.0")

# --- Konwersja ---
unit_factors = {'ug/ml': 1.0, 'mg/l': 1.0, 'ppm': 1.0, 'mg/ml': 1000.0, 'g/l': 1000.0, 'ug/l': 0.001, 'ng/ml': 0.001, 'ppb': 0.001}
s_unit_clean = stock_unit.lower().replace(" ", "")
t_unit_clean = target_unit.lower().replace(" ", "")
multiplier = unit_factors.get(s_unit_clean, 1.0) / unit_factors.get(t_unit_clean, 1.0)
C1_converted = C1_raw * multiplier

c2_list = [float(x.strip()) for x in c2_input.split(",") if x.strip()]
v1_list = [(c * V2) / C1_converted for c in c2_list]

# --- 2. Instrukcja Pipetowania ---
st.header("2. Przygotowanie Standardów")
pipette_df = pd.DataFrame({
    f"Stężenie ({target_unit})": c2_list,
    f"Objętość Stock ({vol_unit})": [round(v, 4) for v in v1_list],
    f"Dopełnić do ({vol_unit})": [V2] * len(c2_list)
})
st.table(pipette_df)

# --- 3. Peak Areas ---
st.header("3. Dane z chromatografu")
entry_df = pd.DataFrame({f"Standard ({target_unit})": c2_list, "Peak Area": [0.0] * len(c2_list)})
edited_df = st.data_editor(entry_df, use_container_width=True)

slope, intercept, r_squared = 0, 0, 0

if st.button("Oblicz Krzywą i Statystyki", type="primary"):
    y = edited_df["Peak Area"].tolist()
    slope, intercept, r_value, p_value, std_err = stats.linregress(c2_list, y)
    r_squared = r_value**2
    
    st.session_state['slope'] = slope
    st.session_state['intercept'] = intercept
    st.session_state['r2'] = r_squared
    
    st.info(f"Równanie: y = {slope:.4f}x + {intercept:.4f} | R² = {r_squared:.4f}")
    
    fig, ax = plt.subplots()
    ax.scatter(c2_list, y, color='red')
    ax.plot(c2_list, [slope*x + intercept for x in c2_list], color='blue')
    st.pyplot(fig)

# --- 4. Próbki Nieznane ---
st.header("4. Analiza Próbek")
unk_area = st.number_input("Wpisz Area próbki nieznanej:", value=0.0)
if st.button("Dodaj wynik do raportu"):
    if 'slope' in st.session_state:
        res = (unk_area - st.session_state['intercept']) / st.session_state['slope']
        st.session_state['unknowns_results'].append({"Area": unk_area, "Wynik": res})
    else:
        st.error("Najpierw oblicz krzywą!")

if st.session_state['unknowns_results']:
    st.write("Ostatnie wyniki:")
    st.table(pd.DataFrame(st.session_state['unknowns_results']))

# --- 5. GENEROWANIE PEŁNEGO RAPORTU ---
st.header("5. Eksport Danych")

def generate_full_report():
    output = io.StringIO()
    # Używamy średnika jako separatora dla europejskiego Excela
    def format_n(n): return str(round(n, 4)).replace('.', ',')

    output.write("--- PARAMETRY BIEGU ---\n")
    output.write(f"Data;{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    output.write(f"Jednostka Stock;{stock_unit}\n")
    output.write(f"Jednostka Celu;{target_unit}\n")
    output.write(f"Stezenie Stock;{format_n(C1_raw)}\n\n")

    output.write("--- KRZYWA KALIBRACYJNA ---\n")
    output.write(f"Rownanie;y = {format_n(st.session_state.get('slope',0))}x + {format_n(st.session_state.get('intercept',0))}\n")
    output.write(f"R2;{format_n(st.session_state.get('r2',0))}\n\n")

    output.write("--- DANE STANDARDOW ---\n")
    output.write(f"Stezenie ({target_unit});Peak Area\n")
    y_values = edited_df["Peak Area"].tolist()
    for c, a in zip(c2_list, y_values):
        output.write(f"{format_n(c)};{format_n(a)}\n")
    output.write("\n")

    output.write("--- WYNIKI PROBEK ---\n")
    output.write("Area próbki;Wynik stężenia;Uwagi\n")
    for item in st.session_state['unknowns_results']:
        uwaga = "Poniżej LOQ" if item['Wynik'] < 0 else ""
        output.write(f"{format_n(item['Area'])};{format_n(item['Wynik'])};{uwaga}\n")
    
    return output.getvalue()

if st.session_state['unknowns_results'] or 'slope' in st.session_state:
    full_report = generate_full_report()
    st.download_button(
        label="📥 Pobierz pełny raport (CSV)",
        data=full_report,
        file_name=f"Raport_Laboratorium_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime='text/csv',
    )

if st.button("Wyczyść dane"):
    st.session_state['unknowns_results'] = []
    st.rerun()
