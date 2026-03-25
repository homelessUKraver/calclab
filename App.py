import streamlit as st
import pandas as pd
import scipy.stats as stats
import matplotlib.pyplot as plt
from datetime import datetime
import io

st.set_page_config(page_title="GC-MS Pełny Raport", layout="centered")
st.title("Kalkulator Stężeń")

# Inicjalizacja pamięci
if 'unknowns_results' not in st.session_state:
    st.session_state['unknowns_results'] = []
# Zmienna przechowująca informację, czy ostatnia krzywa była liczona z użyciem IS
if 'curve_has_is' not in st.session_state:
    st.session_state['curve_has_is'] = False

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

st.markdown("### Wzorzec Wewnętrzny (Internal Standard)")
use_is = st.checkbox("Dodaj Wzorzec Wewnętrzny (IS)")
if use_is:
    col_is1, col_is2 = st.columns(2)
    with col_is1:
        is_vol = st.number_input("Objętość IS dodawana do fiolki", value=10.0)
    with col_is2:
        is_unit = st.text_input("Jednostka objętości IS (np. uL)", value="uL")
else:
    is_vol = 0.0
    is_unit = ""

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
pipette_dict = {
    f"Stężenie ({target_unit})": c2_list,
    f"Objętość Stock ({vol_unit})": [round(v, 4) for v in v1_list]
}
if use_is:
    pipette_dict[f"Dodaj IS ({is_unit})"] = [is_vol] * len(c2_list)

pipette_dict[f"Dopełnić do ({vol_unit})"] = [V2] * len(c2_list)

pipette_df = pd.DataFrame(pipette_dict)
st.table(pipette_df)

# --- 3. Peak Areas ---
st.header("3. Dane z chromatografu")
if use_is:
    entry_df = pd.DataFrame({
        f"Standard ({target_unit})": c2_list, 
        "Peak Area (Standard)": [0.0] * len(c2_list),
        "Peak Area (IS)": [0.0] * len(c2_list)
    })
else:
    entry_df = pd.DataFrame({
        f"Standard ({target_unit})": c2_list, 
        "Peak Area": [0.0] * len(c2_list)
    })

edited_df = st.data_editor(entry_df, use_container_width=True)

if st.button("Oblicz Krzywą i Statystyki", type="primary"):
    if use_is:
        std_areas = edited_df["Peak Area (Standard)"].tolist()
        is_areas = edited_df["Peak Area (IS)"].tolist()
        # Wyliczanie stosunku (Ratio). Zabezpieczenie przed dzieleniem przez zero.
        y_vals = [s / i if i > 0 else 0 for s, i in zip(std_areas, is_areas)]
        
        st.session_state['std_areas_data'] = std_areas
        st.session_state['is_areas_data'] = is_areas
        st.session_state['ratios_data'] = y_vals
    else:
        y_vals = edited_df["Peak Area"].tolist()
        st.session_state['y_vals_data'] = y_vals

    slope, intercept, r_value, p_value, std_err = stats.linregress(c2_list, y_vals)
    r_squared = r_value**2
    
    st.session_state['slope'] = slope
    st.session_state['intercept'] = intercept
    st.session_state['r2'] = r_squared
    st.session_state['curve_has_is'] = use_is # Zapisujemy, czy krzywa ma IS, żeby próbki wiedziały jak się liczyć
    
    st.info(f"Równanie: y = {slope:.4f}x + {intercept:.4f} | R² = {r_squared:.4f}")
    
    fig, ax = plt.subplots()
    ax.scatter(c2_list, y_vals, color='red')
    ax.plot(c2_list, [slope*x + intercept for x in c2_list], color='blue')
    ax.set_xlabel(f"Stężenie ({target_unit})")
    ax.set_ylabel("Ratio (Standard/IS)" if use_is else "Peak Area")
    st.pyplot(fig)

# --- 4. Próbki Nieznane ---
st.header("4. Analiza Próbek")
curve_is_active = st.session_state.get('curve_has_is', False)

if curve_is_active:
    col_u1, col_u2 = st.columns(2)
    with col_u1:
        unk_area = st.number_input("Wpisz Peak Area próbki:", value=0.0)
    with col_u2:
        unk_is_area = st.number_input("Wpisz Peak Area IS w próbce:", value=0.0)
else:
    unk_area = st.number_input("Wpisz Area próbki nieznanej:", value=0.0)
    unk_is_area = 0.0

if st.button("Dodaj wynik do raportu"):
    if 'slope' in st.session_state:
        if curve_is_active:
            if unk_is_area > 0:
                y_for_calc = unk_area / unk_is_area
            else:
                y_for_calc = 0
                st.error("Błąd: Area IS musi być większe od 0!")
        else:
            y_for_calc = unk_area

        if not (curve_is_active and unk_is_area == 0):
            res = (y_for_calc - st.session_state['intercept']) / st.session_state['slope']
            
            if curve_is_active:
                st.session_state['unknowns_results'].append({
                    "Area (Próbka)": unk_area, 
                    "Area (IS)": unk_is_area,
                    "Ratio": y_for_calc,
                    "Wynik stężenia": res
                })
            else:
                st.session_state['unknowns_results'].append({
                    "Area": unk_area, 
                    "Wynik stężenia": res
                })
    else:
        st.error("Najpierw oblicz krzywą!")

if st.session_state['unknowns_results']:
    st.write("Ostatnie wyniki:")
    st.table(pd.DataFrame(st.session_state['unknowns_results']))

# --- 5. GENEROWANIE PEŁNEGO RAPORTU ---
st.header("5. Eksport Danych")

def generate_full_report():
    output = io.StringIO()
    def format_n(n): return str(round(n, 4)).replace('.', ',')

    output.write("--- PARAMETRY BIEGU ---\n")
    output.write(f"Data;{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    output.write(f"Jednostka Stock;{stock_unit}\n")
    output.write(f"Jednostka Celu;{target_unit}\n")
    output.write(f"Stezenie Stock;{format_n(C1_raw)}\n")
    if st.session_state.get('curve_has_is', False):
        output.write(f"Uzyto Wzorca Wewnetrznego (IS);TAK\n")
        output.write(f"Wielkosc dodatku IS;{format_n(is_vol)} {is_unit}\n")
    else:
        output.write("Uzyto Wzorca Wewnetrznego (IS);NIE\n")
    output.write("\n")

    output.write("--- KRZYWA KALIBRACYJNA ---\n")
    output.write(f"Rownanie;y = {format_n(st.session_state.get('slope',0))}x + {format_n(st.session_state.get('intercept',0))}\n")
    output.write(f"R2;{format_n(st.session_state.get('r2',0))}\n\n")

    output.write("--- DANE STANDARDOW ---\n")
    if st.session_state.get('curve_has_is', False):
        output.write(f"Stezenie ({target_unit});Peak Area (Standard);Peak Area (IS);Ratio\n")
        s_areas = st.session_state.get('std_areas_data', [])
        i_areas = st.session_state.get('is_areas_data', [])
        ratios = st.session_state.get('ratios_data', [])
        for c, s, i, r in zip(c2_list, s_areas, i_areas, ratios):
            output.write(f"{format_n(c)};{format_n(s)};{format_n(i)};{format_n(r)}\n")
    else:
        output.write(f"Stezenie ({target_unit});Peak Area\n")
        y_values = st.session_state.get('y_vals_data', [])
        for c, a in zip(c2_list, y_values):
            output.write(f"{format_n(c)};{format_n(a)}\n")
    output.write("\n")

    output.write("--- WYNIKI PROBEK ---\n")
    if st.session_state.get('curve_has_is', False):
        output.write("Area (Probka);Area (IS);Ratio;Wynik stezenia;Uwagi\n")
        for item in st.session_state['unknowns_results']:
            uwaga = "Ponizej LOQ" if item['Wynik stężenia'] < 0 else ""
            output.write(f"{format_n(item['Area (Próbka)'])};{format_n(item['Area (IS)'])};{format_n(item['Ratio'])};{format_n(item['Wynik stężenia'])};{uwaga}\n")
    else:
        output.write("Area probki;Wynik stezenia;Uwagi\n")
        for item in st.session_state['unknowns_results']:
            uwaga = "Ponizej LOQ" if item['Wynik stężenia'] < 0 else ""
            output.write(f"{format_n(item['Area'])};{format_n(item['Wynik stężenia'])};{uwaga}\n")
    
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
    if 'slope' in st.session_state:
        del st.session_state['slope']
    st.rerun()
