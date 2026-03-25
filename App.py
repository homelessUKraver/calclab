import streamlit as st
import pandas as pd
import scipy.stats as stats
import matplotlib.pyplot as plt
import io

st.set_page_config(page_title="GC-MS Kalibracja", layout="centered")
st.title("🧪 Kalkulator Kalibracji GC-MS / HPLC-MS")

# --- 1. Parametry ---
st.header("1. Parametry Roztworów")
col1, col2, col3 = st.columns(3)
with col1:
    stock_unit = st.text_input("Jednostka Stock", value="mg/L")
    C1_raw = st.number_input("Stężenie Stock", value=100.0)
with col2:
    target_unit = st.text_input("Jednostka Celu", value="ug/mL")
    c2_input = st.text_input("Stężenia (po przecinku)", value="0.1, 0.2, 0.3, 0.4, 0.5")
with col3:
    vol_unit = st.text_input("Jednostka Objętości", value="mL")
    V2 = st.number_input("Objętość Standardu", value=10.0)

# --- Konwersja i Matematyka ---
unit_factors = {'ug/ml': 1.0, 'mg/l': 1.0, 'ppm': 1.0, 'mg/ml': 1000.0, 'g/l': 1000.0, 'ug/l': 0.001, 'ng/ml': 0.001, 'ppb': 0.001}
multiplier = unit_factors.get(stock_unit.lower(), 1.0) / unit_factors.get(target_unit.lower(), 1.0)
C1 = C1_raw * multiplier

c2_list = [float(x.strip()) for x in c2_input.split(",") if x.strip()]
v1_list = [(c * V2) / C1 for c in c2_list]

# --- 2. Instrukcja Pipetowania ---
st.header("2. Instrukcja Pipetowania")
pipette_df = pd.DataFrame({
    f"Cel ({target_unit})": c2_list,
    f"Pobierz Stock ({vol_unit})": [round(v, 4) for v in v1_list],
    f"Dopełnij do ({vol_unit})": [V2] * len(c2_list)
})
st.table(pipette_df)

# --- 3. Wprowadzanie Pól Pików ---
st.header("3. Wprowadź Pokoje Pików (Peak Areas)")
st.write("Wpisz dane z maszyny w poniższą tabelę:")
entry_df = pd.DataFrame({f"Stężenie ({target_unit})": c2_list, "Peak Area": [0.0] * len(c2_list)})
edited_df = st.data_editor(entry_df, use_container_width=True)

# --- 4. Obliczenia i Wykres ---
if st.button("Oblicz Krzywą Kalibracyjną", type="primary"):
    peak_areas = edited_df["Peak Area"].tolist()
    
    # Zapobiega błędowi, jeśli ktoś kliknie przycisk, zanim wpisze dane
    if sum(peak_areas) == 0:
        st.error("Wprowadź wartości Peak Area większe niż 0!")
    else:
        slope, intercept, r_value, p_value, std_err = stats.linregress(c2_list, peak_areas)
        r_squared = r_value**2
        
        st.session_state['slope'] = slope
        st.session_state['intercept'] = intercept
        
        st.success(f"**Równanie:** $y = {slope:.4f}x + {intercept:.4f}$  |  **$R^2$:** {r_squared:.4f}")
        if r_squared < 0.99:
            st.warning("⚠️ Uwaga: Wartość $R^2$ jest poniżej 0.99!")

        # Wykres
        fig, ax = plt.subplots()
        ax.scatter(c2_list, peak_areas, color='red', label='Dane maszyny')
        ax.plot(c2_list, [slope*x + intercept for x in c2_list], color='blue', label='Linia trendu')
        ax.set_xlabel(f"Stężenie ({target_unit})")
        ax.set_ylabel("Peak Area")
        ax.legend()
        st.pyplot(fig)

# --- 5. Próbki Nieznane ---
st.header("4. Analiza Próbek Nieznanych")
unknown_area = st.number_input("Wpisz Peak Area dla nieznanej próbki:", value=0.0)

if unknown_area > 0 and 'slope' in st.session_state:
    slope = st.session_state['slope']
    intercept = st.session_state['intercept']
    unknown_conc = (unknown_area - intercept) / slope
    
    if unknown_conc < 0:
        st.error(f"Obliczone stężenie: **{unknown_conc:.4f} {target_unit}** (⚠️ Poniżej LOQ)")
    else:
        st.info(f"Obliczone stężenie: **{unknown_conc:.4f} {target_unit}**")

# --- 6. Pobieranie Raportu ---
st.header("5. Zapisz Raport")
csv_data = pipette_df.to_csv(index=False).encode('utf-8')
st.download_button(
    label="Pobierz tabelę pipetowania jako CSV",
    data=csv_data,
    file_name='instrukcja_pipetowania.csv',
    mime='text/csv',
)