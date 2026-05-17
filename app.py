import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from snowflake.snowpark import Session
import json
import os

st.set_page_config(
    page_title="CryoLab | Research Data Platform",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

CONNECTION_NAME = os.getenv("SNOWFLAKE_CONNECTION_NAME") or "IL16585"
COLOR_MAP = {
    "Gold (111)": "#FFD700",
    "Silver (111)": "#C0C0C0",
    "He4": "#29B5E8",
    "Ne": "#00D4AA",
    "H2": "#FF6B6B",
    "D2": "#FFB84D",
}

def create_session():
    try:
        secrets = st.secrets["connections"]["snowflake"]
        return Session.builder.configs({
            "account": secrets["account"],
            "user": secrets["user"],
            "password": secrets["password"],
            "warehouse": secrets.get("warehouse", "COMPUTE_WH"),
            "database": secrets.get("database", "CRYOLAB"),
            "schema": secrets.get("schema", "SURFACE_ELECTRONS"),
        }).create()
    except Exception:
        return Session.builder.config("connection_name", CONNECTION_NAME).create()

if "snowpark_session" not in st.session_state:
    st.session_state.snowpark_session = create_session()

def get_session():
    return st.session_state.snowpark_session

def run_query(sql):
    try:
        return get_session().sql(sql).to_pandas()
    except Exception as e:
        if "390114" in str(e) or "Authentication token has expired" in str(e):
            st.session_state.snowpark_session = create_session()
            return get_session().sql(sql).to_pandas()
        raise

with st.sidebar:
    st.markdown("### ❄️ CryoLab")
    st.caption("Uni Konstanz — Research Data Platform")
    st.markdown("---")

    lab_section = st.radio(
        "Experiment-Bereich",
        ["Argon-Film", "Oberflächenelektronen"],
        index=0,
        key="lab_section",
    )

    st.markdown("---")

    if lab_section == "Argon-Film":
        stats = run_query("""
            SELECT 
                COUNT(DISTINCT e.EXPERIMENT_ID) as experiments,
                COUNT(m.MEASUREMENT_ID) as measurements,
                MIN(m.TIMESTAMP)::DATE as first_date,
                MAX(m.TIMESTAMP)::DATE as last_date,
                SUM(CASE WHEN m.IS_ANOMALY THEN 1 ELSE 0 END) as anomalies
            FROM CRYOLAB.ARGON_FILM.EXPERIMENTS e
            JOIN CRYOLAB.ARGON_FILM.MEASUREMENTS m ON e.EXPERIMENT_ID = m.EXPERIMENT_ID
        """)
        intensity_count = run_query("SELECT COUNT(*) AS cnt FROM CRYOLAB.ARGON_FILM.INTENSITY_MEASUREMENTS")["CNT"].iloc[0]
        st.metric("Experimente", stats["EXPERIMENTS"].iloc[0])
        st.metric("Messpunkte", f"{stats['MEASUREMENTS'].iloc[0]:,}")
        st.metric("Intensitätsdaten", f"{intensity_count}")
        st.metric("Anomalien", stats["ANOMALIES"].iloc[0])
        st.caption(f"Daten: {stats['FIRST_DATE'].iloc[0]} → {stats['LAST_DATE'].iloc[0]}")
    else:
        try:
            stats = run_query("""
                SELECT 
                    COUNT(DISTINCT e.EXPERIMENT_ID) as experiments,
                    COUNT(m.MEASUREMENT_ID) as measurements,
                    COUNT(DISTINCT e.SUBSTRATE_TYPE) as substrates
                FROM CRYOLAB.SURFACE_ELECTRONS.EXPERIMENTS e
                JOIN CRYOLAB.SURFACE_ELECTRONS.MEASUREMENTS m ON e.EXPERIMENT_ID = m.EXPERIMENT_ID
            """)
            st.metric("Experimente", stats["EXPERIMENTS"].iloc[0])
            st.metric("Messpunkte", f"{stats['MEASUREMENTS'].iloc[0]:,}")
            st.metric("Substrate", stats["SUBSTRATES"].iloc[0])
        except:
            st.info("Keine Daten im Schema SURFACE_ELECTRONS.")

# ══════════════════════════════════════════════════════════════
# ARGON FILM SECTION
# ══════════════════════════════════════════════════════════════
if lab_section == "Argon-Film":
    st.title("Argon-Film Experiment")
    st.caption("Filmdicke als Funktion von Temperatur und Druck — Surface Plasmon Spectroscopy")

    tab_analysis, tab_intensity, tab_ocr, tab_anomaly, tab_model, tab_chat, tab_data = st.tabs([
        "📊 Analyse & Diagramme",
        "🔴 Reflektierte Intensität",
        "📸 Notebook OCR",
        "⚠️ Anomalie-Erkennung",
        "🧮 Modell-Fitting",
        "💬 Daten-Chat",
        "📋 Rohdaten",
    ])

    # ── TAB: Analysis ──
    with tab_analysis:
        st.header("Messanalyse")

        fc1, fc2 = st.columns(2)
        with fc1:
            experiments_df = run_query("SELECT EXPERIMENT_ID, EXPERIMENT_DATE, DESCRIPTION FROM CRYOLAB.ARGON_FILM.EXPERIMENTS ORDER BY EXPERIMENT_DATE")
            exp_options = experiments_df.apply(lambda r: f"{r['EXPERIMENT_ID']} — {r['DESCRIPTION'][:60]}", axis=1).tolist()
            sel_exps = st.multiselect("Experimente", exp_options, default=exp_options, key="analysis_exps")
        with fc2:
            substrate_options = run_query("SELECT DISTINCT SUBSTRATE_MATERIAL FROM CRYOLAB.ARGON_FILM.EXPERIMENTS")["SUBSTRATE_MATERIAL"].tolist()
            sel_substrates = st.multiselect("Substrat", substrate_options, default=substrate_options, key="analysis_substrates")

        sel_exp_ids = [s.split(" — ")[0] for s in sel_exps]
        exp_filter = "','".join(sel_exp_ids)
        sub_filter = "','".join(sel_substrates)

        data = run_query(f"""
            SELECT m.*, e.DESCRIPTION, e.SUBSTRATE_MATERIAL, e.EXPERIMENT_DATE
            FROM CRYOLAB.ARGON_FILM.MEASUREMENTS m
            JOIN CRYOLAB.ARGON_FILM.EXPERIMENTS e ON m.EXPERIMENT_ID = e.EXPERIMENT_ID
            WHERE m.EXPERIMENT_ID IN ('{exp_filter}')
              AND e.SUBSTRATE_MATERIAL IN ('{sub_filter}')
            ORDER BY m.TIMESTAMP
        """)

        if data.empty:
            st.warning("Keine Daten für aktuelle Filter.")
        else:
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Messpunkte", f"{len(data):,}")
            k2.metric("Ø Filmdicke", f"{data['FILM_THICKNESS_NM'].mean():.1f} nm")
            k3.metric("T-Bereich", f"{data['TEMPERATURE_K'].min():.1f} – {data['TEMPERATURE_K'].max():.1f} K")
            k4.metric("P-Bereich", f"{data['PRESSURE_MBAR'].min():.0f} – {data['PRESSURE_MBAR'].max():.0f} mbar")

            st.markdown("---")

            c1, c2 = st.columns(2)

            with c1:
                st.subheader("Filmdicke vs. Temperatur")
                fig1 = px.scatter(
                    data, x="TEMPERATURE_K", y="FILM_THICKNESS_NM",
                    color="EXPERIMENT_ID",
                    hover_data=["PRESSURE_MBAR", "TIMESTAMP"],
                    labels={"TEMPERATURE_K": "Temperatur (K)", "FILM_THICKNESS_NM": "Filmdicke (nm)"},
                )
                anomalies = data[data["IS_ANOMALY"] == True]
                if not anomalies.empty:
                    fig1.add_trace(go.Scatter(
                        x=anomalies["TEMPERATURE_K"], y=anomalies["FILM_THICKNESS_NM"],
                        mode="markers", name="Anomalie",
                        marker=dict(size=14, color="red", symbol="x", line=dict(width=2)),
                    ))
                fig1.update_layout(template="plotly_dark", height=450)
                st.plotly_chart(fig1, use_container_width=True)

            with c2:
                st.subheader("Filmdicke vs. Druck")
                fig2 = px.scatter(
                    data, x="PRESSURE_MBAR", y="FILM_THICKNESS_NM",
                    color="EXPERIMENT_ID",
                    hover_data=["TEMPERATURE_K", "TIMESTAMP"],
                    labels={"PRESSURE_MBAR": "Druck (mbar)", "FILM_THICKNESS_NM": "Filmdicke (nm)"},
                )
                if not anomalies.empty:
                    fig2.add_trace(go.Scatter(
                        x=anomalies["PRESSURE_MBAR"], y=anomalies["FILM_THICKNESS_NM"],
                        mode="markers", name="Anomalie",
                        marker=dict(size=14, color="red", symbol="x", line=dict(width=2)),
                    ))
                fig2.update_layout(template="plotly_dark", height=450)
                st.plotly_chart(fig2, use_container_width=True)

            c3, c4 = st.columns(2)

            with c3:
                st.subheader("3D: Filmdicke(T, P)")
                fig3 = px.scatter_3d(
                    data, x="TEMPERATURE_K", y="PRESSURE_MBAR", z="FILM_THICKNESS_NM",
                    color="EXPERIMENT_ID",
                    labels={"TEMPERATURE_K": "T (K)", "PRESSURE_MBAR": "P (mbar)", "FILM_THICKNESS_NM": "d (nm)"},
                )
                fig3.update_layout(template="plotly_dark", height=550)
                st.plotly_chart(fig3, use_container_width=True)

            with c4:
                st.subheader("Temperatur & Druck Zeitverlauf")
                sel_timeline_exp = st.selectbox(
                    "Experiment", sel_exp_ids, key="timeline_exp"
                )
                tl_data = data[data["EXPERIMENT_ID"] == sel_timeline_exp]
                fig4 = make_subplots(specs=[[{"secondary_y": True}]])
                fig4.add_trace(
                    go.Scatter(x=tl_data["TIMESTAMP"], y=tl_data["TEMPERATURE_K"],
                               name="Temperatur (K)", line=dict(color="#FF6B6B")),
                    secondary_y=False,
                )
                fig4.add_trace(
                    go.Scatter(x=tl_data["TIMESTAMP"], y=tl_data["PRESSURE_MBAR"],
                               name="Druck (mbar)", line=dict(color="#29B5E8")),
                    secondary_y=True,
                )
                fig4.update_layout(template="plotly_dark", height=450, title=sel_timeline_exp)
                fig4.update_yaxes(title_text="Temperatur (K)", secondary_y=False)
                fig4.update_yaxes(title_text="Druck (mbar)", secondary_y=True)
                st.plotly_chart(fig4, use_container_width=True)

            st.subheader("Korrelation T ↔ P ↔ Filmdicke")
            fig5 = px.scatter(
                data, x="TEMPERATURE_K", y="PRESSURE_MBAR",
                color="FILM_THICKNESS_NM", size="FILM_THICKNESS_NM",
                color_continuous_scale="Viridis",
                labels={"TEMPERATURE_K": "Temperatur (K)", "PRESSURE_MBAR": "Druck (mbar)",
                         "FILM_THICKNESS_NM": "Dicke (nm)"},
            )
            fig5.update_layout(template="plotly_dark", height=500)
            st.plotly_chart(fig5, use_container_width=True)

    # ── TAB: Reflected Intensity ──
    with tab_intensity:
        st.header("Reflektierte Intensität — Realmessung 27.07.2025")
        st.caption("Surface Plasmon Spectroscopy: Reflektierte Intensität und Temperatur vs. Zeit")

        try:
            intensity_data = run_query("""
                SELECT TIME_MIN, REFLECTED_INTENSITY, TEMPERATURE_K, TIMESTAMP, NOTES
                FROM CRYOLAB.ARGON_FILM.INTENSITY_MEASUREMENTS
                WHERE EXPERIMENT_ID = 'ARG-REAL-001'
                ORDER BY TIME_MIN
            """)
        except:
            intensity_data = pd.DataFrame()

        if intensity_data.empty:
            st.warning("Keine Intensitätsdaten vorhanden. Lade zuerst load_real_data.py aus.")
        else:
            ik1, ik2, ik3, ik4 = st.columns(4)
            ik1.metric("Messpunkte", len(intensity_data))
            ik2.metric("I-Bereich", f"{intensity_data['REFLECTED_INTENSITY'].min():.2f} – {intensity_data['REFLECTED_INTENSITY'].max():.2f}")
            ik3.metric("T-Bereich", f"{intensity_data['TEMPERATURE_K'].min():.0f} – {intensity_data['TEMPERATURE_K'].max():.0f} K")
            ik4.metric("Dauer", f"{intensity_data['TIME_MIN'].max():.0f} min")

            st.markdown("---")

            st.subheader("Intensität & Temperatur vs. Zeit")
            fig_it = make_subplots(specs=[[{"secondary_y": True}]])
            fig_it.add_trace(
                go.Scatter(
                    x=intensity_data["TIME_MIN"], y=intensity_data["REFLECTED_INTENSITY"],
                    name="Reflektierte Intensität", mode="lines+markers",
                    line=dict(color="#4169E1", width=2),
                    marker=dict(size=3),
                ),
                secondary_y=False,
            )
            fig_it.add_trace(
                go.Scatter(
                    x=intensity_data["TIME_MIN"], y=intensity_data["TEMPERATURE_K"],
                    name="Temperatur", mode="lines+markers",
                    line=dict(color="#FF69B4", width=2),
                    marker=dict(size=3),
                ),
                secondary_y=True,
            )

            labels = intensity_data[intensity_data["NOTES"].notna()]
            for _, row in labels.iterrows():
                fig_it.add_annotation(
                    x=row["TIME_MIN"], y=row["REFLECTED_INTENSITY"],
                    text=row["NOTES"].split(":")[0] if ":" in str(row["NOTES"]) else str(row["NOTES"])[:20],
                    showarrow=True, arrowhead=2, arrowsize=0.8,
                    font=dict(size=9, color="white"),
                    ax=0, ay=-30,
                )

            fig_it.update_layout(
                template="plotly_dark", height=500,
                xaxis_title="Zeit (min)",
                legend=dict(x=0.01, y=0.99),
            )
            fig_it.update_yaxes(title_text="Reflektierte Intensität (arb. u.)", secondary_y=False, range=[0, 1.1])
            fig_it.update_yaxes(title_text="Temperatur (K)", secondary_y=True, range=[80, 64], autorange=False)
            st.plotly_chart(fig_it, use_container_width=True)

            st.markdown("---")
            ic1, ic2 = st.columns(2)

            with ic1:
                st.subheader("Intensität vs. Temperatur")
                fig_ivt = go.Figure()

                panel1 = intensity_data[intensity_data["TIME_MIN"] <= 26]
                panel2 = intensity_data[intensity_data["TIME_MIN"] >= 34]

                fig_ivt.add_trace(go.Scatter(
                    x=panel1["TEMPERATURE_K"], y=panel1["REFLECTED_INTENSITY"],
                    mode="lines+markers", name="Messung 0–26 min",
                    marker=dict(size=5, color="#4169E1"),
                    line=dict(color="#4169E1", width=1.5),
                    text=[f"t={t:.1f} min" for t in panel1["TIME_MIN"]],
                ))
                fig_ivt.add_trace(go.Scatter(
                    x=panel2["TEMPERATURE_K"], y=panel2["REFLECTED_INTENSITY"],
                    mode="lines+markers", name="Messung 34–44 min",
                    marker=dict(size=5, color="#FF6B6B"),
                    line=dict(color="#FF6B6B", width=1.5),
                    text=[f"t={t:.1f} min" for t in panel2["TIME_MIN"]],
                ))

                fig_ivt.update_layout(
                    template="plotly_dark", height=450,
                    xaxis_title="Temperatur (K)",
                    yaxis_title="Reflektierte Intensität (arb. u.)",
                )
                st.plotly_chart(fig_ivt, use_container_width=True)

                st.markdown("""
                **Hysterese-Effekt**: Die Intensität folgt bei Abkühlung und Erwärmung 
                unterschiedlichen Pfaden — typisch für Argon-Filmwachstum und -desorption.
                """)

            with ic2:
                st.subheader("Intensität vs. dT/dt (Temperaturänderung)")

                dt_min = intensity_data["TIME_MIN"].diff()
                dT = intensity_data["TEMPERATURE_K"].diff()
                dT_dt = dT / dt_min

                plot_df = intensity_data.copy()
                plot_df["dT_dt"] = dT_dt
                plot_df = plot_df.dropna(subset=["dT_dt"])
                plot_df = plot_df[plot_df["dT_dt"].abs() < 50]

                p1_mask = plot_df["TIME_MIN"] <= 26
                p2_mask = plot_df["TIME_MIN"] >= 34

                fig_idt = go.Figure()
                fig_idt.add_trace(go.Scatter(
                    x=plot_df.loc[p1_mask, "dT_dt"], y=plot_df.loc[p1_mask, "REFLECTED_INTENSITY"],
                    mode="markers", name="0–26 min",
                    marker=dict(size=7, color="#4169E1", opacity=0.8),
                    text=[f"t={t:.1f} min, T={T:.1f} K" for t, T in zip(
                        plot_df.loc[p1_mask, "TIME_MIN"], plot_df.loc[p1_mask, "TEMPERATURE_K"])],
                ))
                fig_idt.add_trace(go.Scatter(
                    x=plot_df.loc[p2_mask, "dT_dt"], y=plot_df.loc[p2_mask, "REFLECTED_INTENSITY"],
                    mode="markers", name="34–44 min",
                    marker=dict(size=7, color="#FF6B6B", opacity=0.8),
                    text=[f"t={t:.1f} min, T={T:.1f} K" for t, T in zip(
                        plot_df.loc[p2_mask, "TIME_MIN"], plot_df.loc[p2_mask, "TEMPERATURE_K"])],
                ))
                fig_idt.add_vline(x=0, line_dash="dash", line_color="gray")
                fig_idt.update_layout(
                    template="plotly_dark", height=450,
                    xaxis_title="dT/dt (K/min)",
                    yaxis_title="Reflektierte Intensität (arb. u.)",
                )
                st.plotly_chart(fig_idt, use_container_width=True)

                st.markdown("""
                **dT/dt > 0**: Erwärmung (Ar desorbiert → Intensität steigt)  
                **dT/dt < 0**: Abkühlung (Ar kondensiert → Intensität sinkt)  
                **dT/dt ≈ 0**: Gleichgewicht (Film stabil)
                """)

            st.markdown("---")
            st.subheader("Phasendiagramm: I(T) mit Zeitfarbe")

            fig_phase = go.Figure()
            fig_phase.add_trace(go.Scatter(
                x=intensity_data["TEMPERATURE_K"],
                y=intensity_data["REFLECTED_INTENSITY"],
                mode="markers+lines",
                marker=dict(
                    size=8,
                    color=intensity_data["TIME_MIN"],
                    colorscale="Plasma",
                    colorbar=dict(title="Zeit (min)"),
                    showscale=True,
                ),
                line=dict(width=0.5, color="rgba(255,255,255,0.3)"),
                text=[f"t={t:.1f} min" for t in intensity_data["TIME_MIN"]],
                hovertemplate="T=%{x:.1f} K<br>I=%{y:.3f}<br>%{text}<extra></extra>",
            ))
            fig_phase.update_layout(
                template="plotly_dark", height=500,
                xaxis_title="Temperatur (K)",
                yaxis_title="Reflektierte Intensität (arb. u.)",
            )
            st.plotly_chart(fig_phase, use_container_width=True)

            st.markdown("""
            **Beschriftungen im Originaldiagramm:**
            - **1–5**: Punkte auf der Intensitätskurve (blau)
            - **A–E**: Punkte auf der Temperaturkurve (magenta)
            - **A→B**: Abkühlung von 65K auf 80K — Argon kondensiert, Film wächst, Intensität sinkt
            - **B→C**: Bei 80K wird aufgeheizt — rapide Desorption, Intensität springt auf ~0.9
            - **C→E**: Erneute Abkühlung — Film wächst wieder
            - **Punkt 5 (38 min)**: Zweiter Aufheiz-Zyklus — erneut kurzer Intensitätspeak
            """)

    # ── TAB: OCR ──
    with tab_ocr:
        st.header("Notizbuch-Digitalisierung")
        st.markdown("""
        Fotografiere die handschriftlichen Notizbuchseiten und lade sie hier hoch. 
        Snowflake Cortex AI extrahiert die Daten automatisch.
        
        **So funktioniert es:**
        1. Notizbuchseite abfotografieren (Handy reicht)
        2. Hier hochladen (Drag & Drop)
        3. KI liest Text und Tabellen
        4. Strukturierte Daten werden extrahiert (T, P, Filmdicke)
        5. Ein Klick importiert in die Datenbank
        """)

        if "ocr_raw_text" not in st.session_state:
            st.session_state.ocr_raw_text = None
        if "ocr_extracted_json" not in st.session_state:
            st.session_state.ocr_extracted_json = None
        if "ocr_filename" not in st.session_state:
            st.session_state.ocr_filename = None
        if "ocr_imported" not in st.session_state:
            st.session_state.ocr_imported = False

        uploaded_files = st.file_uploader(
            "Notizbuchseite(n) hochladen",
            type=["jpg", "jpeg", "png", "pdf", "tiff"],
            accept_multiple_files=True,
            help="Fotografiere handgeschriebene Laborseiten",
        )

        if uploaded_files:
            st.image(uploaded_files[0], caption=uploaded_files[0].name, width=400)

        if st.button("🔍 OCR starten & Daten extrahieren", type="primary", disabled=not uploaded_files):
            st.session_state.ocr_imported = False
            with st.spinner("Cortex AI OCR läuft..."):
                sf_session = get_session()
                for f in uploaded_files:
                    temp_path = f"/tmp/{f.name}"
                    with open(temp_path, "wb") as tmp:
                        tmp.write(f.getbuffer())
                    sf_session.sql(f"PUT file://{temp_path} @CRYOLAB.ARGON_FILM.LAB_NOTEBOOK_STAGE AUTO_COMPRESS=FALSE OVERWRITE=TRUE").collect()
                    stage_file = f.name

                ocr_result = run_query(f"""
                    SELECT AI_PARSE_DOCUMENT(
                        TO_FILE('@CRYOLAB.ARGON_FILM.LAB_NOTEBOOK_STAGE', '{stage_file}'),
                        {{'mode': 'LAYOUT'}}
                    ):content::STRING AS ocr_text
                """)

                raw_text = ocr_result["OCR_TEXT"].iloc[0]
                st.session_state.ocr_raw_text = raw_text
                st.session_state.ocr_filename = stage_file

                extract_prompt = f"""Du bist ein Physik-Labor-Datenextraktions-Assistent.
Extrahiere ALLE Messdaten aus diesem OCR-Text in ein JSON-Array.

Die Tabelle im Notizbuch kann unterschiedliche Spalten haben. Erkenne die Spaltenüberschriften und extrahiere die Werte korrekt.
Typische Spalten sind (erkenne anhand der Überschriften im Text):
- datum (Datum der Messung, z.B. "Daten vom 4.2.26")
- delta_r_deg (ΔR in Grad — Spaltenüberschrift "ΔR [°]" oder "ΔR")
- delta_t_min (Δt in Minuten — Spaltenüberschrift "Δt [min]" oder "Δt")
- dicke_d_nm (Filmdicke d in Nanometer — Spaltenüberschrift "Dicke d" oder "d")
- temperature_k (Temperatur in Kelvin, falls vorhanden)
- pressure_mbar (Druck in Millibar, falls vorhanden)
- notes (Bemerkungen)

WICHTIG: Jede Spaltenüberschrift im Notizbuch ist ein SEPARATES Feld!
- "ΔR [°]" = delta_r_deg (Änderung der Reflektivität in Grad)
- "Δt [min]" = delta_t_min (Zeitintervall in Minuten)
- "ΔR/Δt" = NICHT extrahieren, wird berechnet aus delta_r_deg / delta_t_min
- "Dicke d" = dicke_d_nm (Filmdicke in Nanometer)

Der Kontext: Argon-Film-Adsorption, Surface Plasmon Spectroscopy.

OCR TEXT:
{raw_text}

Gib NUR gültiges JSON-Array zurück, OHNE Markdown-Formatierung."""

                extract_result = run_query(f"""
                    SELECT SNOWFLAKE.CORTEX.COMPLETE(
                        'mistral-large2',
                        '{extract_prompt.replace("'", "''")}'
                    ) AS extracted
                """)

                st.session_state.ocr_extracted_json = extract_result["EXTRACTED"].iloc[0]

        if st.session_state.ocr_raw_text:
            st.subheader("📄 OCR-Rohtext")
            st.code(st.session_state.ocr_raw_text, language="markdown")

        if st.session_state.ocr_extracted_json:
            st.subheader("🧠 KI-extrahierte Messdaten")
            st.json(st.session_state.ocr_extracted_json)

            if st.session_state.ocr_imported:
                st.success("✅ Daten wurden erfolgreich in die Datenbank importiert!")
            else:
                st.success("✅ Daten extrahiert! Prüfe oben und klicke 'In Datenbank importieren'.")

                if st.button("💾 In Datenbank importieren", type="primary"):
                    with st.spinner("Importiere in Snowflake..."):
                        try:
                            extracted = st.session_state.ocr_extracted_json
                            if isinstance(extracted, str):
                                clean = extracted.strip()
                                while clean.startswith("```"):
                                    clean = clean.split("\n", 1)[-1]
                                clean = clean.replace("```", "").strip()
                                idx_start = clean.find("[")
                                idx_end = clean.rfind("]")
                                if idx_start != -1 and idx_end != -1:
                                    clean = clean[idx_start:idx_end + 1]
                                records = json.loads(clean)
                            else:
                                records = extracted

                            if not isinstance(records, list):
                                records = [records]

                            sf_session = get_session()

                            exp_id = f"OCR-{datetime.now().strftime('%m%d%H%M')}"

                            is_notebook_data = any(
                                rec.get("delta_r_deg") is not None or rec.get("delta_t_min") is not None or rec.get("dicke_d_nm") is not None
                                for rec in records
                            )

                            if is_notebook_data:
                                datum = records[0].get("datum", "") if records else ""
                                sf_session.sql(f"""
                                    INSERT INTO CRYOLAB.ARGON_FILM.EXPERIMENTS
                                    (EXPERIMENT_ID, EXPERIMENT_DATE, DESCRIPTION, TARGET_TEMP_MIN_K, TARGET_TEMP_MAX_K,
                                     SUBSTRATE_MATERIAL, MEASUREMENT_METHOD, NOTES)
                                    VALUES ('{exp_id}', CURRENT_DATE(),
                                     'OCR-Import aus {st.session_state.ocr_filename}',
                                     NULL, NULL, NULL, 'Notizbuch-Messung',
                                     'Automatisch per OCR + KI-Extraktion importiert — {datum}')
                                """).collect()

                                sf_session.sql(f"""
                                    INSERT INTO CRYOLAB.ARGON_FILM.OCR_EXTRACTS
                                    (FILENAME, RAW_OCR_TEXT, EXTRACTED_JSON, STATUS)
                                    SELECT '{st.session_state.ocr_filename}',
                                           '{st.session_state.ocr_raw_text.replace("'", "''")}',
                                           PARSE_JSON('{json.dumps(records).replace("'", "''")}'),
                                           'IMPORTED'
                                """).collect()

                                imported_count = 0
                                for rec in records:
                                    dr = rec.get("delta_r_deg")
                                    dt = rec.get("delta_t_min")
                                    dicke = rec.get("dicke_d_nm")
                                    notes = rec.get("notes", "")
                                    datum_val = rec.get("datum", datum)

                                    dr_val = f"{float(dr)}" if dr is not None else "NULL"
                                    dt_val = f"{float(dt)}" if dt is not None else "NULL"
                                    dicke_val = f"{float(dicke)}" if dicke is not None else "NULL"
                                    notes_val = str(notes).replace("'", "''") if notes else ""

                                    drdt_val = "NULL"
                                    if dr is not None and dt is not None:
                                        try:
                                            dt_f = float(dt)
                                            if dt_f != 0:
                                                drdt_val = f"{float(dr) / dt_f}"
                                        except:
                                            pass

                                    sf_session.sql(f"""
                                        INSERT INTO CRYOLAB.ARGON_FILM.NOTEBOOK_MEASUREMENTS
                                        (EXPERIMENT_ID, DATUM, DELTA_R_DEG, DELTA_T_MIN,
                                         DELTA_R_DELTA_T, DICKE_D_NM, NOTES)
                                        VALUES ('{exp_id}', '{datum_val}', {dr_val}, {dt_val},
                                                {drdt_val}, {dicke_val}, '{notes_val}')
                                    """).collect()
                                    imported_count += 1

                            else:
                                sf_session.sql(f"""
                                    INSERT INTO CRYOLAB.ARGON_FILM.EXPERIMENTS
                                    (EXPERIMENT_ID, EXPERIMENT_DATE, DESCRIPTION, TARGET_TEMP_MIN_K, TARGET_TEMP_MAX_K,
                                     SUBSTRATE_MATERIAL, MEASUREMENT_METHOD, NOTES)
                                    VALUES ('{exp_id}', CURRENT_DATE(),
                                     'OCR-Import aus {st.session_state.ocr_filename}',
                                     65.0, 77.0, 'Gold', 'Surface Plasmon Spectroscopy',
                                     'Automatisch per OCR + KI-Extraktion importiert')
                                """).collect()

                                sf_session.sql(f"""
                                    INSERT INTO CRYOLAB.ARGON_FILM.OCR_EXTRACTS
                                    (FILENAME, RAW_OCR_TEXT, EXTRACTED_JSON, STATUS)
                                    SELECT '{st.session_state.ocr_filename}',
                                           '{st.session_state.ocr_raw_text.replace("'", "''")}',
                                           PARSE_JSON('{json.dumps(records).replace("'", "''")}'),
                                           'IMPORTED'
                                """).collect()

                                imported_count = 0
                                prev_r = None
                                prev_ts = None

                                for rec in records:
                                    ts = rec.get("timestamp", datetime.now().isoformat())
                                    temp = rec.get("temperature_k")
                                    pres = rec.get("pressure_mbar")
                                    thick = rec.get("film_thickness_nm")
                                    refl = rec.get("reflected_intensity")
                                    notes = rec.get("notes", "")

                                    delta_r_dt = None
                                    if refl is not None and prev_r is not None:
                                        try:
                                            dr = float(refl) - float(prev_r)
                                            if prev_ts and ts:
                                                from dateutil import parser as dtparser
                                                try:
                                                    t1 = dtparser.parse(str(prev_ts))
                                                    t2 = dtparser.parse(str(ts))
                                                    dt_sec = (t2 - t1).total_seconds()
                                                    if dt_sec > 0:
                                                        delta_r_dt = dr / (dt_sec / 60.0)
                                                except:
                                                    delta_r_dt = dr
                                            else:
                                                delta_r_dt = dr
                                        except:
                                            pass

                                    if refl is not None:
                                        prev_r = refl
                                        prev_ts = ts

                                    temp_val = f"{float(temp)}" if temp is not None else "NULL"
                                    pres_val = f"{float(pres)}" if pres is not None else "NULL"
                                    thick_val = f"{float(thick)}" if thick is not None else "NULL"
                                    drdt_val = f"{float(delta_r_dt)}" if delta_r_dt is not None else "NULL"
                                    notes_val = str(notes).replace("'", "''") if notes else ""

                                    sf_session.sql(f"""
                                        INSERT INTO CRYOLAB.ARGON_FILM.OCR_MEASUREMENTS
                                        (EXPERIMENT_ID, TIMESTAMP, TEMPERATURE_K, PRESSURE_MBAR,
                                         FILM_THICKNESS_NM, DELTA_R_DELTA_T, NOTES)
                                        VALUES ('{exp_id}', '{ts}', {temp_val}, {pres_val},
                                                {thick_val}, {drdt_val}, '{notes_val}')
                                    """).collect()
                                    imported_count += 1

                            st.session_state.ocr_imported = True
                            st.balloons()
                            st.success(f"✅ {imported_count} Messpunkte als Experiment **{exp_id}** importiert!")
                            st.rerun()

                        except json.JSONDecodeError as e:
                            st.error(f"JSON-Parsing fehlgeschlagen: {e}")
                            st.info("Das KI-Ergebnis war kein gültiges JSON. Versuche es erneut mit einem besseren Bild.")
                        except Exception as e:
                            st.error(f"Import fehlgeschlagen: {e}")

    # ── TAB: Anomaly Detection ──
    with tab_anomaly:
        st.header("Anomalie-Erkennung")

        anomaly_method = st.selectbox(
            "Methode",
            ["Statistisch (Z-Score)", "Physik-basierte Regeln", "KI-Analyse"],
            key="argon_anomaly_method",
        )

        anomaly_exp_options = run_query(
            "SELECT EXPERIMENT_ID || ' — ' || DESCRIPTION AS label FROM CRYOLAB.ARGON_FILM.EXPERIMENTS ORDER BY EXPERIMENT_DATE DESC"
        )["LABEL"].tolist()
        anomaly_exp = st.selectbox("Experiment", anomaly_exp_options, key="argon_anomaly_exp")
        anomaly_exp_id = anomaly_exp.split(" — ")[0]

        if st.button("🔎 Anomalien suchen", type="primary"):
            exp_data = run_query(f"""
                SELECT m.*, e.SUBSTRATE_MATERIAL
                FROM CRYOLAB.ARGON_FILM.MEASUREMENTS m
                JOIN CRYOLAB.ARGON_FILM.EXPERIMENTS e ON m.EXPERIMENT_ID = e.EXPERIMENT_ID
                WHERE m.EXPERIMENT_ID = '{anomaly_exp_id}'
                ORDER BY m.TIMESTAMP
            """)

            if exp_data.empty:
                st.warning("Keine Daten.")
            else:
                if anomaly_method == "Statistisch (Z-Score)":
                    numeric_cols = ["TEMPERATURE_K", "PRESSURE_MBAR", "FILM_THICKNESS_NM"]
                    all_anomalies = pd.DataFrame()

                    for col in numeric_cols:
                        if exp_data[col].notna().sum() > 10:
                            mean = exp_data[col].mean()
                            std = exp_data[col].std()
                            if std > 0:
                                z_scores = np.abs((exp_data[col] - mean) / std)
                                mask = z_scores > 2.5
                                if mask.any():
                                    flagged = exp_data[mask].copy()
                                    flagged["ANOMALIE_TYP"] = f"{col} Ausreißer (Z>{z_scores[mask].min():.1f})"
                                    all_anomalies = pd.concat([all_anomalies, flagged])

                    if not all_anomalies.empty:
                        st.error(f"🚨 {len(all_anomalies)} anomale Messpunkte gefunden!")
                        st.dataframe(
                            all_anomalies[["TIMESTAMP", "TEMPERATURE_K", "PRESSURE_MBAR", "FILM_THICKNESS_NM", "ANOMALIE_TYP", "NOTES"]].drop_duplicates(),
                            use_container_width=True,
                        )
                    else:
                        st.success("✅ Keine statistischen Anomalien (Z > 2.5).")

                elif anomaly_method == "Physik-basierte Regeln":
                    rules = []

                    temp_jumps = exp_data["TEMPERATURE_K"].diff().abs()
                    median_jump = temp_jumps.median()
                    if median_jump > 0:
                        big = exp_data[temp_jumps > 10 * median_jump]
                        for _, row in big.iterrows():
                            rules.append({"Zeitstempel": row["TIMESTAMP"], "Regel": "Temperatursprung > 10x Median", "Wert": f"ΔT = {temp_jumps[row.name]:.3f} K"})

                    press_jumps = exp_data["PRESSURE_MBAR"].diff().abs()
                    median_pjump = press_jumps.median()
                    if median_pjump > 0:
                        big_p = exp_data[press_jumps > 10 * median_pjump]
                        for _, row in big_p.iterrows():
                            rules.append({"Zeitstempel": row["TIMESTAMP"], "Regel": "Drucksprung > 10x Median", "Wert": f"ΔP = {press_jumps[row.name]:.1f} mbar"})

                    neg_thick = exp_data[exp_data["FILM_THICKNESS_NM"] < 1.0]
                    for _, row in neg_thick.iterrows():
                        rules.append({"Zeitstempel": row["TIMESTAMP"], "Regel": "Filmdicke < 1 nm (unrealistisch dünn)", "Wert": f"d = {row['FILM_THICKNESS_NM']:.2f} nm"})

                    if rules:
                        st.error(f"🚨 {len(rules)} Regelverletzungen!")
                        st.dataframe(pd.DataFrame(rules), use_container_width=True)
                    else:
                        st.success("✅ Keine physik-basierten Regelverletzungen.")

                else:
                    with st.spinner("KI analysiert Messserie..."):
                        summary_stats = exp_data.describe().to_string()
                        ai_result = run_query(f"""
                            SELECT SNOWFLAKE.CORTEX.COMPLETE(
                                'mistral-large2',
                                'Du bist Experte für Tieftemperatur-Oberflächenphysik und Argon-Adsorption.

Analysiere diese Experimentdaten auf Anomalien und generiere Hypothesen.

Experiment: {anomaly_exp.replace("'", "''")}
Substrat: {exp_data["SUBSTRATE_MATERIAL"].iloc[0]}
Messpunkte: {len(exp_data)}
Methode: Surface Plasmon Spectroscopy
Statistik:
{summary_stats.replace("'", "''")}

Bitte:
1. Identifiziere Anomalien oder verdächtige Muster
2. Schlage für jede Anomalie eine physikalische Hypothese vor (Kondensation, Delamination, Heizerfehler, Leck, etc.)
3. Empfehle Folgeexperimente
4. Bewerte Konfidenz (Niedrig/Mittel/Hoch)

Antworte auf Deutsch in strukturiertem Markdown.'
                            ) AS analysis
                        """)
                        st.markdown(ai_result["ANALYSIS"].iloc[0])

                st.markdown("---")
                st.subheader("Messserie Visualisierung")

                viz_col = st.selectbox("Plot-Variable", ["FILM_THICKNESS_NM", "TEMPERATURE_K", "PRESSURE_MBAR"], key="argon_viz_col")

                fig_a = go.Figure()
                fig_a.add_trace(go.Scatter(
                    x=exp_data["TIMESTAMP"], y=exp_data[viz_col],
                    mode="lines+markers", name=viz_col,
                    marker=dict(size=4, color="#29B5E8"),
                    line=dict(width=1, color="#29B5E8"),
                ))

                mean_val = exp_data[viz_col].mean()
                std_val = exp_data[viz_col].std()
                fig_a.add_hline(y=mean_val + 3 * std_val, line_dash="dash", line_color="red", annotation_text="+3σ")
                fig_a.add_hline(y=mean_val - 3 * std_val, line_dash="dash", line_color="red", annotation_text="-3σ")
                fig_a.add_hline(y=mean_val, line_dash="dot", line_color="gray", annotation_text="Mittelwert")

                flagged = exp_data[exp_data["IS_ANOMALY"] == True]
                if not flagged.empty:
                    fig_a.add_trace(go.Scatter(
                        x=flagged["TIMESTAMP"], y=flagged[viz_col],
                        mode="markers", name="Anomalie",
                        marker=dict(size=12, color="red", symbol="x"),
                    ))

                fig_a.update_layout(template="plotly_dark", height=500, title=f"{viz_col} — {anomaly_exp_id}")
                st.plotly_chart(fig_a, use_container_width=True)

    # ── TAB: Model Fitting ──
    with tab_model:
        st.header("Modell-Fitting")
        st.markdown("""
        Physikalisches Modell für die Argon-Filmdicke:
        
        **d(T, P) = d₀ · exp(-α · (T - T_ref)) · (P / P_ref)^β**
        
        wobei:
        - d₀ = Referenz-Filmdicke bei T_ref, P_ref
        - α = Temperaturkoeffizient (Desorptionsrate)
        - β = Druckexponent (Adsorptionsisotherme)
        - T_ref = 70 K, P_ref = 500 mbar
        """)

        model_exp_options = run_query(
            "SELECT EXPERIMENT_ID || ' — ' || DESCRIPTION AS label FROM CRYOLAB.ARGON_FILM.EXPERIMENTS ORDER BY EXPERIMENT_DATE"
        )["LABEL"].tolist()

        model_sel = st.multiselect("Experimente für Fit", model_exp_options, default=model_exp_options[:3], key="model_exps")
        model_exp_ids = [s.split(" — ")[0] for s in model_sel]

        if model_exp_ids and st.button("🧮 Modell fitten", type="primary"):
            exp_filter_m = "','".join(model_exp_ids)
            fit_data = run_query(f"""
                SELECT m.TEMPERATURE_K, m.PRESSURE_MBAR, m.FILM_THICKNESS_NM, m.IS_ANOMALY, m.EXPERIMENT_ID
                FROM CRYOLAB.ARGON_FILM.MEASUREMENTS m
                WHERE m.EXPERIMENT_ID IN ('{exp_filter_m}')
                  AND m.IS_ANOMALY = FALSE
                ORDER BY m.TIMESTAMP
            """)

            if fit_data.empty:
                st.warning("Keine Daten.")
            else:
                T = fit_data["TEMPERATURE_K"].values
                P = fit_data["PRESSURE_MBAR"].values
                d_measured = fit_data["FILM_THICKNESS_NM"].values

                T_ref, P_ref = 70.0, 500.0

                from scipy.optimize import curve_fit

                def model_func(X, d0, alpha, beta):
                    T, P = X
                    return d0 * np.exp(-alpha * (T - T_ref)) * (P / P_ref) ** beta

                try:
                    popt, pcov = curve_fit(model_func, (T, P), d_measured, p0=[50.0, 0.15, 0.7], maxfev=10000)
                    d0_fit, alpha_fit, beta_fit = popt
                    perr = np.sqrt(np.diag(pcov))

                    d_predicted = model_func((T, P), *popt)
                    residuals = d_measured - d_predicted
                    r_squared = 1 - np.sum(residuals**2) / np.sum((d_measured - d_measured.mean())**2)

                    st.success("✅ Modell-Fit erfolgreich!")

                    p1, p2, p3, p4 = st.columns(4)
                    p1.metric("d₀", f"{d0_fit:.2f} ± {perr[0]:.2f} nm")
                    p2.metric("α", f"{alpha_fit:.4f} ± {perr[1]:.4f} K⁻¹")
                    p3.metric("β", f"{beta_fit:.3f} ± {perr[2]:.3f}")
                    p4.metric("R²", f"{r_squared:.4f}")

                    st.markdown("---")

                    mc1, mc2 = st.columns(2)

                    with mc1:
                        st.subheader("Messung vs. Modell")
                        fig_fit = go.Figure()
                        fig_fit.add_trace(go.Scatter(
                            x=d_measured, y=d_predicted, mode="markers",
                            name="Datenpunkte",
                            marker=dict(size=4, color="#29B5E8", opacity=0.6),
                        ))
                        d_range = [min(d_measured.min(), d_predicted.min()), max(d_measured.max(), d_predicted.max())]
                        fig_fit.add_trace(go.Scatter(
                            x=d_range, y=d_range, mode="lines",
                            name="Perfekter Fit", line=dict(color="white", dash="dash"),
                        ))
                        fig_fit.update_layout(
                            template="plotly_dark", height=450,
                            xaxis_title="Gemessen (nm)", yaxis_title="Modell (nm)",
                        )
                        st.plotly_chart(fig_fit, use_container_width=True)

                    with mc2:
                        st.subheader("Residuen-Verteilung")
                        fig_res = px.histogram(
                            x=residuals, nbins=40,
                            labels={"x": "Residuum (nm)", "count": "Häufigkeit"},
                        )
                        fig_res.update_layout(template="plotly_dark", height=450)
                        st.plotly_chart(fig_res, use_container_width=True)

                    st.subheader("Modell-Vorhersage: Filmdicke(T, P)")
                    T_grid = np.linspace(65, 77, 50)
                    P_grid = np.linspace(200, 1000, 50)
                    T_mesh, P_mesh = np.meshgrid(T_grid, P_grid)
                    d_mesh = model_func((T_mesh.ravel(), P_mesh.ravel()), *popt).reshape(T_mesh.shape)

                    fig_surf = go.Figure(data=[go.Surface(
                        x=T_grid, y=P_grid, z=d_mesh,
                        colorscale="Viridis",
                        colorbar=dict(title="d (nm)"),
                    )])
                    fig_surf.update_layout(
                        template="plotly_dark", height=600,
                        scene=dict(
                            xaxis_title="Temperatur (K)",
                            yaxis_title="Druck (mbar)",
                            zaxis_title="Filmdicke (nm)",
                        ),
                    )
                    st.plotly_chart(fig_surf, use_container_width=True)

                    st.markdown("#### Physikalische Interpretation")
                    st.markdown(f"""
                    - **α = {alpha_fit:.4f} K⁻¹**: Temperaturabhängigkeit der Desorption. 
                      Höhere α → Film verschwindet schneller bei Erwärmung.
                    - **β = {beta_fit:.3f}**: Druckexponent der Adsorptionsisotherme. 
                      β < 1 deutet auf BET-artige Multilayer-Adsorption hin.
                    - **d₀ = {d0_fit:.1f} nm**: Referenz-Filmdicke bei T={T_ref} K, P={P_ref} mbar.
                    - **R² = {r_squared:.4f}**: Das Modell erklärt {r_squared*100:.1f}% der Varianz.
                    """)

                except Exception as e:
                    st.error(f"Fit fehlgeschlagen: {e}")

    # ── TAB: Chat ──
    with tab_chat:
        st.header("Daten-Chat")
        st.markdown("Stelle Fragen auf Deutsch oder Englisch an deine Messdaten.")

        suggestions = [
            "Welches Experiment hat die dicksten Argon-Filme?",
            "Zeige alle Anomalien mit Zeitstempel",
            "Wie unterscheiden sich Gold- und Silbersubstrat?",
            "Was ist die durchschnittliche Filmdicke bei Drücken über 800 mbar?",
            "Gibt es einen Zusammenhang zwischen Temperatur und Filmdicke?",
        ]

        if "argon_chat_messages" not in st.session_state:
            st.session_state.argon_chat_messages = []

        if not st.session_state.argon_chat_messages:
            st.markdown("**Beispiel-Fragen:**")
            cols = st.columns(3)
            for i, s in enumerate(suggestions):
                if cols[i % 3].button(s, key=f"argon_sug_{i}"):
                    st.session_state.argon_chat_messages.append({"role": "user", "content": s})
                    st.rerun()

        for msg in st.session_state.argon_chat_messages:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
                if "sql" in msg:
                    with st.expander("SQL anzeigen"):
                        st.code(msg["sql"], language="sql")
                if "dataframe" in msg and msg["dataframe"] is not None:
                    st.dataframe(msg["dataframe"], use_container_width=True)

        if prompt := st.chat_input("Frage zu deinen Argon-Film-Daten..."):
            st.session_state.argon_chat_messages.append({"role": "user", "content": prompt})

            with st.chat_message("user"):
                st.write(prompt)

            with st.chat_message("assistant"):
                with st.spinner("Analysiere..."):
                    try:
                        sql_gen = run_query(f"""
                            SELECT SNOWFLAKE.CORTEX.COMPLETE(
                                'mistral-large2',
                                'Du bist ein SQL-Experte für eine Physik-Forschungsdatenbank.

Datenbank: CRYOLAB.ARGON_FILM
Tabellen:
- EXPERIMENTS: EXPERIMENT_ID, EXPERIMENT_DATE, DESCRIPTION, TARGET_TEMP_MIN_K, TARGET_TEMP_MAX_K, TARGET_PRESSURE_MIN_MBAR, TARGET_PRESSURE_MAX_MBAR, SUBSTRATE_MATERIAL, MEASUREMENT_METHOD, NOTES
- MEASUREMENTS: MEASUREMENT_ID, EXPERIMENT_ID, TIMESTAMP, TEMPERATURE_K, PRESSURE_MBAR, FILM_THICKNESS_NM, NOTES, IS_ANOMALY
- INTENSITY_MEASUREMENTS: MEASUREMENT_ID, EXPERIMENT_ID, TIMESTAMP, TIME_MIN, REFLECTED_INTENSITY, TEMPERATURE_K, NOTES (Realmessung 27.07.2025, ARG-REAL-001)

Kontext: Argon-Film-Adsorption, Surface Plasmon Spectroscopy. MEASUREMENTS enthält synthetische Filmdicke-Daten (T: 65-77 K, P: 200-1000 mbar). INTENSITY_MEASUREMENTS enthält echte reflektierte Intensität vs. Temperatur/Zeit.

Generiere eine SQL-Abfrage für: {prompt.replace("'", "''")}

Gib NUR die SQL-Abfrage zurück, keine Erklärung. Verwende voll qualifizierte Tabellennamen.'
                            ) AS sql_query
                        """)

                        generated_sql = sql_gen["SQL_QUERY"].iloc[0].strip()
                        if generated_sql.startswith("```"):
                            generated_sql = generated_sql.split("\n", 1)[1].rsplit("```", 1)[0].strip()

                        with st.expander("Generiertes SQL", expanded=False):
                            st.code(generated_sql, language="sql")

                        result_df = run_query(generated_sql)

                        if not result_df.empty:
                            st.dataframe(result_df, use_container_width=True)

                            interp = run_query(f"""
                                SELECT SNOWFLAKE.CORTEX.COMPLETE(
                                    'mistral-large2',
                                    'Du bist Physik-Forschungsassistent für Argon-Adsorption.
Frage: {prompt.replace("'", "''")}

Ergebnis (erste Zeilen):
{result_df.head(20).to_string().replace("'", "''")}

Gib eine kurze, physikalisch fundierte Interpretation (2-3 Sätze, auf Deutsch).'
                                ) AS interpretation
                            """)
                            st.markdown(f"**Interpretation:** {interp['INTERPRETATION'].iloc[0]}")
                        else:
                            st.info("Keine Ergebnisse.")

                        st.session_state.argon_chat_messages.append({
                            "role": "assistant",
                            "content": interp["INTERPRETATION"].iloc[0] if not result_df.empty else "Keine Ergebnisse.",
                            "sql": generated_sql,
                            "dataframe": result_df if not result_df.empty else None,
                        })

                    except Exception as e:
                        error_msg = f"Fehler bei der Verarbeitung: {str(e)}"
                        st.error(error_msg)
                        st.session_state.argon_chat_messages.append({"role": "assistant", "content": error_msg})

    # ── TAB: Raw Data ──
    with tab_data:
        st.header("Rohdaten")
        data_exp = st.selectbox(
            "Experiment",
            run_query("SELECT EXPERIMENT_ID || ' — ' || DESCRIPTION AS label FROM CRYOLAB.ARGON_FILM.EXPERIMENTS ORDER BY EXPERIMENT_DATE")["LABEL"].tolist(),
            key="raw_data_exp",
        )
        data_exp_id = data_exp.split(" — ")[0]

        raw = run_query(f"""
            SELECT m.MEASUREMENT_ID, m.TIMESTAMP, m.TEMPERATURE_K, m.PRESSURE_MBAR, 
                   m.FILM_THICKNESS_NM, m.IS_ANOMALY, m.NOTES
            FROM CRYOLAB.ARGON_FILM.MEASUREMENTS m
            WHERE m.EXPERIMENT_ID = '{data_exp_id}'
            ORDER BY m.TIMESTAMP
        """)

        if not raw.empty:
            st.dataframe(
                raw.style.apply(
                    lambda row: ["background-color: #4a1a1a" if row["IS_ANOMALY"] else "" for _ in row],
                    axis=1,
                ),
                use_container_width=True,
                height=500,
            )
        else:
            st.info("Keine Daten in MEASUREMENTS für dieses Experiment.")

        nb_raw = run_query(f"""
            SELECT MEASUREMENT_ID, DATUM, DELTA_R_DEG AS "ΔR [°]", DELTA_T_MIN AS "Δt [min]",
                   DELTA_R_DELTA_T AS "ΔR/Δt", DICKE_D_NM AS "Dicke d [nm]", NOTES
            FROM CRYOLAB.ARGON_FILM.NOTEBOOK_MEASUREMENTS
            WHERE EXPERIMENT_ID = '{data_exp_id}'
            ORDER BY MEASUREMENT_ID
        """)

        if not nb_raw.empty:
            st.subheader("Notizbuch-Messdaten")
            st.dataframe(nb_raw, use_container_width=True, height=400)

            st.subheader("Dicke d als Funktion von ΔR/Δt")
            import numpy as np
            import matplotlib.pyplot as plt
            import matplotlib
            matplotlib.use("Agg")
            fig_m, ax = plt.subplots(figsize=(8, 5))
            ax.scatter(nb_raw["ΔR/Δt"], nb_raw["Dicke d [nm]"],
                       s=80, c="royalblue", edgecolors="black", linewidths=1, zorder=5, label="Messdaten")
            x_fit = nb_raw["ΔR/Δt"].dropna().values
            y_fit = nb_raw["Dicke d [nm]"].dropna().values
            if len(x_fit) >= 3:
                from scipy.optimize import curve_fit
                def exp_func(x, a, b, c):
                    return a * np.exp(b * x) + c
                sort_idx = np.argsort(x_fit)
                x_s, y_s = x_fit[sort_idx], y_fit[sort_idx]
                try:
                    popt, _ = curve_fit(exp_func, x_s, y_s, p0=[1, 10, 15], maxfev=10000)
                    x_smooth = np.linspace(x_s.min(), x_s.max(), 200)
                    y_smooth = exp_func(x_smooth, *popt)
                    ax.plot(x_smooth, y_smooth, color="salmon", linewidth=2, zorder=4,
                            label=f"Fit: {popt[0]:.1f}·exp({popt[1]:.1f}·x) + {popt[2]:.1f}")
                except Exception:
                    pass
            ax.axhline(0, color="black", linewidth=1, zorder=3)
            ax.axvline(0, color="black", linewidth=1, zorder=3)
            ax.set_xlabel("ΔR/Δt (°/min)", fontsize=14, color="black")
            ax.set_ylabel("Dicke d (nm)", fontsize=14, color="black")
            ax.tick_params(colors="black", labelsize=12)
            ax.set_facecolor("white")
            fig_m.patch.set_facecolor("white")
            for spine in ax.spines.values():
                spine.set_edgecolor("black")
                spine.set_linewidth(1.5)
            ax.legend(fontsize=11, frameon=True, edgecolor="black", loc="upper left")
            ax.grid(True, color="lightgray", linewidth=0.5)
            plt.tight_layout()
            st.pyplot(fig_m)
            plt.close(fig_m)

            col_a, col_b = st.columns(2)
            with col_a:
                st.subheader("ΔR [°] vs. Δt [min]")
                fig_scatter = px.scatter(nb_raw, x="Δt [min]", y="ΔR [°]",
                                         labels={"Δt [min]": "Δt (min)", "ΔR [°]": "ΔR (°)"})
                fig_scatter.update_traces(marker=dict(size=10))
                fig_scatter.update_layout(template="plotly_dark")
                st.plotly_chart(fig_scatter, use_container_width=True)

            with col_b:
                st.subheader("ΔR/Δt (berechnete Änderungsrate)")
                fig_rate = px.scatter(nb_raw, x=nb_raw.index + 1, y="ΔR/Δt",
                                      labels={"x": "Messpunkt", "ΔR/Δt": "ΔR/Δt (°/min)"},
                                      color="ΔR/Δt", color_continuous_scale="RdBu", color_continuous_midpoint=0)
                fig_rate.update_traces(mode="lines+markers")
                fig_rate.update_layout(template="plotly_dark", showlegend=False)
                st.plotly_chart(fig_rate, use_container_width=True)

        display_raw = nb_raw if not nb_raw.empty else raw

        st.download_button(
            "📥 Als CSV herunterladen",
            display_raw.to_csv(index=False).encode("utf-8"),
            f"{data_exp_id}_measurements.csv",
            "text/csv",
        )


# ══════════════════════════════════════════════════════════════
# SURFACE ELECTRONS SECTION (legacy)
# ══════════════════════════════════════════════════════════════
elif lab_section == "Oberflächenelektronen":
    st.title("Oberflächenelektronen auf Quantensubstraten")
    st.caption("He⁴, Ne, H₂, D₂ — Leitfähigkeit, Mobilität, Elektronendichte")

    tab_se_analysis, tab_se_ocr, tab_se_anomaly, tab_se_chat = st.tabs([
        "📊 Analyse",
        "📸 OCR",
        "⚠️ Anomalien",
        "💬 Chat",
    ])

    with tab_se_analysis:
        st.header("Messanalyse — Oberflächenelektronen")

        filter_col1, filter_col2 = st.columns(2)
        with filter_col1:
            substrates = run_query("SELECT DISTINCT SUBSTRATE_TYPE FROM CRYOLAB.SURFACE_ELECTRONS.EXPERIMENTS ORDER BY SUBSTRATE_TYPE")
            sel_substrates_se = st.multiselect("Substrat", substrates["SUBSTRATE_TYPE"].tolist(), default=substrates["SUBSTRATE_TYPE"].tolist(), key="se_substrates")
        with filter_col2:
            researchers = run_query("SELECT DISTINCT RESEARCHER FROM CRYOLAB.SURFACE_ELECTRONS.EXPERIMENTS ORDER BY RESEARCHER")
            sel_researchers = st.multiselect("Forscher", researchers["RESEARCHER"].tolist(), default=researchers["RESEARCHER"].tolist(), key="se_researchers")

        sub_f = "','".join(sel_substrates_se) if sel_substrates_se else "''"
        res_f = "','".join(sel_researchers) if sel_researchers else "''"

        data_se = run_query(f"""
            SELECT m.*, e.SUBSTRATE_TYPE, e.EXPERIMENT_NAME, e.RESEARCHER, e.CRYOSTAT
            FROM CRYOLAB.SURFACE_ELECTRONS.MEASUREMENTS m
            JOIN CRYOLAB.SURFACE_ELECTRONS.EXPERIMENTS e ON m.EXPERIMENT_ID = e.EXPERIMENT_ID
            WHERE e.SUBSTRATE_TYPE IN ('{sub_f}')
              AND e.RESEARCHER IN ('{res_f}')
            ORDER BY m.TIMESTAMP
        """)

        if data_se.empty:
            st.warning("Keine Daten.")
        else:
            k1, k2, k3 = st.columns(3)
            k1.metric("Messpunkte", f"{len(data_se):,}")
            k2.metric("Ø Mobilität", f"{data_se['MOBILITY_CM2_VS'].mean():.2e} cm²/Vs")
            k3.metric("Experimente", data_se["EXPERIMENT_ID"].nunique())

            c1, c2 = st.columns(2)
            with c1:
                st.subheader("Leitfähigkeit vs. Temperatur")
                fig = px.scatter(
                    data_se, x="TEMPERATURE_K", y="CONDUCTIVITY_S",
                    color="SUBSTRATE_TYPE", log_x=True, log_y=True,
                    labels={"TEMPERATURE_K": "T (K)", "CONDUCTIVITY_S": "σ (S)"},
                    color_discrete_map=COLOR_MAP,
                )
                fig.update_layout(template="plotly_dark", height=450)
                st.plotly_chart(fig, use_container_width=True)

            with c2:
                st.subheader("Mobilität nach Substrat")
                fig = px.box(
                    data_se, x="SUBSTRATE_TYPE", y="MOBILITY_CM2_VS",
                    color="SUBSTRATE_TYPE", log_y=True,
                    labels={"SUBSTRATE_TYPE": "Substrat", "MOBILITY_CM2_VS": "μ (cm²/Vs)"},
                    color_discrete_map=COLOR_MAP,
                )
                fig.update_layout(template="plotly_dark", height=450, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

    with tab_se_ocr:
        st.header("Notizbuch OCR — Oberflächenelektronen")
        st.info("Gleiche Funktionalität wie im Argon-Film Tab. Upload hier für Oberflächenelektronen-Daten.")
        uploaded = st.file_uploader("Notizbuchseite hochladen", type=["jpg", "png", "pdf"], key="se_ocr_upload")
        if uploaded:
            st.image(uploaded, width=400)

    with tab_se_anomaly:
        st.header("Anomalie-Erkennung — Oberflächenelektronen")
        st.info("Wähle ein Experiment und eine Methode zur Anomalie-Erkennung.")
        ae_exp = st.selectbox(
            "Experiment",
            run_query("SELECT EXPERIMENT_ID || ' — ' || EXPERIMENT_NAME AS label FROM CRYOLAB.SURFACE_ELECTRONS.EXPERIMENTS ORDER BY START_DATE DESC")["LABEL"].tolist(),
            key="se_anomaly_exp",
        )

    with tab_se_chat:
        st.header("Daten-Chat — Oberflächenelektronen")
        st.info("Stelle Fragen zu den Oberflächenelektronen-Daten.")
        if prompt_se := st.chat_input("Frage zu Oberflächenelektronen..."):
            st.write(f"Frage: {prompt_se}")
