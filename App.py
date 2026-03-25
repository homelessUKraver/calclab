import streamlit as st
import pandas as pd
import scipy.stats as stats
import matplotlib.pyplot as plt

st.set_page_config(page_title="GC-MS Kalkulator", layout="centered")
st.title("🧪 Kalkulator Standardów")

# --- 1. JEDNOSTKI I PARAMETRY ---
st.header("1. Jednostki i Stężenia")
st.write("Wpisz parametry swojego roztworu (czysty układ z góry na dół):")

stock_unit = st.text_input("Jednostka roztworu Stock (np. mg/L):", value="mg/L")
target_unit = st.text_input("Jednostka docelowa Standardów (np. ug/mL):", value="ug/mL")
vol_unit = st.text_input("Jednostka Objętości (np. mL):", value="mL")

C1_raw = st.number_input(f"Stężenie roztworu Stock ({stock_unit}):", value=100.0)
V2 = st.number_input(f"Końcowa objętość w każdej fiolce ({vol_unit}):", value=10.0)
c2_input = st.text_input(f"Stężenia docelowe ({target_unit}), oddzielone przecinkiem:", value="0.1, 0.5, 1.0, 2.0")

# --- 2. WZORZEC WEWNĘTRZNY (CHECKBOX) ---
st.header("2. Wzorzec Wewnętrzny (IS)")
use_is = st.checkbox("Dodaj Wzorzec Wewnętrzny (Internal Standard) do fiolek")

is_vol = 0.0
if use_is:
    is_vol = st.number_input(f"Objętość IS dodawana do KAŻDEJ fiolki ({vol_unit}):", value=0.1)

# --- OBLICZENIA MATEMATYCZNE ROZCIEŃCZEŃ ---
unit_factors = {'ug/ml': 1.0, 'mg/l': 1.0, 'ppm': 1.0, 'mg/ml': 1000.0, 'g/l': 1000.0, 'ug/l': 0.001, 'ng/ml': 0.001, 'ppb': 0.001}
s_clean = stock_unit.lower().replace(" ", "")
t_clean = target_unit.lower().replace(" ", "")
multiplier = unit_factors.get(s_clean, 1.0) / unit_factors.get(t_clean, 1.0)

C1_converted = C1_raw * multiplier
c2_list = [float(x.strip()) for x in c2_input.split(",") if x.strip()]
v1_list = [(c * V2) / C1_converted for c in c2_list]

# --- 3. TABELA PIPETOWANIA ---
st.header("3. Instrukcja Pipetowania")

# Budowanie tabeli zależnie od tego, czy używamy IS
pipette_data = {
    f"Stężenie ({target_unit})": c2_list,
    f"Pobierz Stock ({vol_unit})": [round(v, 4) for v in v1_list]
}

if use_is:
    pipette_data[f"Pobierz IS ({vol_unit})"] = [is_vol] * len(c2_list)
    # Obliczenie ile rozpuszczalnika dodać (Całkowita objętość - Stock - IS)
    rozpuszczalnik = [round(V2 - v - is_vol, 4) for v in v1_list]
    pipette_data[f"Dodaj Rozpuszczalnik ({vol_unit})"] = rozpuszczalnik
else:
    pipette_data[f"Dopełnij rozpuszczalnikiem do ({vol_unit})"] = [V2] * len(c2_list)

st.table(pd.DataFrame(pipette_data))

# --- 4. WYBÓR DANYCH MS (RADIO) ---
st.header("4. Dane z Chromatografu")
ms_radio = st.radio(
    "Wybierz metodę kalibracji:",
    ["Tylko Peak Area (Krzywa Standardowa)", "Peak Area + IS Area (Krzywa ze Stosunku Pól / Ratio)"]
)

# Generowanie odpowiedniej tabelki w zależności od wyboru Radio
if ms_radio == "Tylko Peak Area (Krzywa Standardowa)":
    entry_df = pd.DataFrame({
        f"Stężenie ({target_unit})": c2_list, 
        "Peak Area": [0.0] * len(c2_list)
    })
else:
    entry_df = pd.DataFrame({
        f"Stężenie ({target_unit})": c2_list, 
        "Peak Area (Standard)": [0.0] * len(c2_list),
        "Peak Area (IS)": [0.0] * len(c2_list)
    })

edited_df = st.data_editor(entry_df, use_container_width=True)

if st.button("Oblicz Równanie"):
    if ms_radio == "Tylko Peak Area (Krzywa Standardowa)":
        y_values = edited_df["Peak Area"].tolist()
    else:
        std_areas = edited_df["Peak Area (Standard)"].tolist()
        is_areas = edited_df["Peak Area (IS)"].tolist()
        # Zabezpieczenie przed błędem, jeśli ktoś wpisze "0" jako IS Area
        y_values = [s / i if i > 0 else 0 for s, i in zip(std_areas, is_areas)]
        
    if sum(y_values) == 0:
        st.error("Wprowadź wartości Peak Area do tabeli wyżej!")
    else:
        slope, intercept, r_value, p_value, std_err = stats.linregress(c2_list, y_values)
        r2 = r_value**2
        
        st.success(f"Równanie: y = {slope:.4f}x + {intercept:.4f} | R-kwadrat: {r2:.4f}")
        
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.scatter(c2_list, y_values, color='red')
        ax.plot(c2_list, [slope*x + intercept for x in c2_list], color='blue')
        ax.set_xlabel(f"Stężenie ({target_unit})")
        if ms_radio == "Tylko Peak Area (Krzywa Standardowa)":
            ax.set_ylabel("Peak Area")
        else:
            ax.set_ylabel("Ratio (Standard Area / IS Area)")
        st.pyplot(fig)
