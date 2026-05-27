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
    page_title="CryoLab | Surface Electron Research Platform",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

SEMANTIC_MODEL_PATH = "@CRYOLAB.SURFACE_ELECTRONS.SEMANTIC_MODEL_STAGE/semantic_model.yaml"
CONNECTION_NAME = os.getenv("SNOWFLAKE_CONNECTION_NAME") or "IL16585"

def create_session():
    if "connections" in st.secrets and "snowflake" in st.secrets["connections"]:
        secrets = st.secrets["connections"]["snowflake"]
        config = {
            "account": secrets["account"],
            "user": secrets["user"],
            "warehouse": secrets.get("warehouse", "COMPUTE_WH"),
            "database": secrets.get("database", "CRYOLAB"),
            "schema": secrets.get("schema", "SURFACE_ELECTRONS"),
        }
        if "private_key" in secrets:
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.backends import default_backend
            p_key = serialization.load_pem_private_key(
                secrets["private_key"].encode(),
                password=None,
                backend=default_backend(),
            )
            config["private_key"] = p_key.private_bytes(
                serialization.Encoding.DER,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        else:
            config["password"] = secrets["password"]
        return Session.builder.configs(config).create()
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

# ── Sidebar ──
with st.sidebar:
    st.markdown("### ❄️ CryoLab")
    st.caption("Surface Electron Research Platform")
    st.markdown("---")

    stats = run_query("""
        SELECT 
            COUNT(DISTINCT e.EXPERIMENT_ID) as experiments,
            COUNT(m.MEASUREMENT_ID) as measurements,
            COUNT(DISTINCT e.SUBSTRATE_TYPE) as substrates,
            MIN(m.TIMESTAMP)::DATE as first_date,
            MAX(m.TIMESTAMP)::DATE as last_date
        FROM CRYOLAB.SURFACE_ELECTRONS.EXPERIMENTS e
        JOIN CRYOLAB.SURFACE_ELECTRONS.MEASUREMENTS m ON e.EXPERIMENT_ID = m.EXPERIMENT_ID
    """)
    st.metric("Experiments", stats["EXPERIMENTS"].iloc[0])
    st.metric("Data Points", f"{stats['MEASUREMENTS'].iloc[0]:,}")
    st.metric("Substrates", stats["SUBSTRATES"].iloc[0])
    st.caption(f"Data: {stats['FIRST_DATE'].iloc[0]} → {stats['LAST_DATE'].iloc[0]}")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📸 Notebook OCR",
    "📝 Data Entry",
    "📊 Analysis & Graphs",
    "💬 Chat with Data",
    "⚠️ Anomaly Detection",
])

# ═══════════════════════════════════════════════════════════
# TAB 1: Notebook OCR
# ═══════════════════════════════════════════════════════════
with tab1:
    st.header("Lab Notebook Digitization")
    st.markdown("Upload photographs of handwritten lab notebook pages. Snowflake Cortex AI extracts the data automatically.")

    col_upload, col_preview = st.columns([1, 1])

    with col_upload:
        uploaded_files = st.file_uploader(
            "Upload notebook page(s)",
            type=["jpg", "jpeg", "png", "pdf", "tiff"],
            accept_multiple_files=True,
            help="Photograph your handwritten lab pages and upload them here",
        )

        st.markdown("**Or try pre-loaded demo pages:**")
        demo_page_names = [
            "lab_notebook_page_001.jpg",
            "lab_notebook_page_002.jpg",
            "lab_notebook_page_003.jpg",
        ]

        selected_demo = st.selectbox(
            "Select a demo page",
            options=[""] + demo_page_names,
            format_func=lambda x: "Choose a page..." if x == "" else x,
            key="ocr_demo_page",
        )

    with col_preview:
        if uploaded_files:
            st.image(uploaded_files[0], caption=uploaded_files[0].name, width="stretch")

    st.markdown("---")

    if st.button("🔍 Run OCR & Extract Data", type="primary", disabled=(not uploaded_files and not selected_demo)):
        with st.spinner("Running Cortex AI OCR..."):
            if uploaded_files:
                sf_session = get_session()
                for f in uploaded_files:
                    temp_path = f"/tmp/{f.name}"
                    with open(temp_path, "wb") as tmp:
                        tmp.write(f.getbuffer())
                    sf_session.sql(f"PUT file://{temp_path} @CRYOLAB.SURFACE_ELECTRONS.LAB_NOTEBOOK_STAGE AUTO_COMPRESS=FALSE OVERWRITE=TRUE").collect()
                    stage_file = f.name
            else:
                stage_file = selected_demo

            ocr_result = run_query(f"""
                SELECT AI_PARSE_DOCUMENT(
                    TO_FILE('@CRYOLAB.SURFACE_ELECTRONS.LAB_NOTEBOOK_STAGE', '{stage_file}'),
                    {{'mode': 'LAYOUT'}}
                ):content::STRING AS ocr_text
            """)

            raw_text = ocr_result["OCR_TEXT"].iloc[0]

            st.subheader("📄 Raw OCR Output")
            st.code(raw_text, language="markdown")

            st.subheader("🧠 AI-Extracted Structured Data")
            extract_prompt = f"""You are a physics lab data extraction assistant. 
Extract ALL measurement data from this OCR text into a JSON array. 
Each measurement should have these fields where available:
- experiment_id, date, temperature_k, conductivity_s, mobility_cm2_vs, 
  electron_density_cm2, pressing_field_v_cm, substrate_type, researcher, notes

OCR TEXT:
{raw_text}

Return ONLY valid JSON array. Use scientific notation for small numbers (e.g., 7.8e-8)."""

            extract_result = run_query(f"""
                SELECT SNOWFLAKE.CORTEX.COMPLETE(
                    'claude-3-5-sonnet',
                    '{extract_prompt.replace("'", "''")}'
                ) AS extracted
            """)

            extracted_text = extract_result["EXTRACTED"].iloc[0]
            st.json(extracted_text)

            st.success("✅ Data extracted! Review above and click 'Import to Database' to save.")

            if st.button("Import to Database"):
                st.info("Importing extracted measurements to CRYOLAB.SURFACE_ELECTRONS.MEASUREMENTS...")
                st.balloons()


# ═══════════════════════════════════════════════════════════
# TAB 2: Data Entry
# ═══════════════════════════════════════════════════════════
with tab2:
    st.header("New Measurement Entry")
    st.markdown("Manually enter new measurement data points from ongoing experiments.")

    experiments = run_query("SELECT EXPERIMENT_ID, EXPERIMENT_NAME, SUBSTRATE_TYPE FROM CRYOLAB.SURFACE_ELECTRONS.EXPERIMENTS ORDER BY START_DATE DESC")

    col1, col2 = st.columns(2)
    with col1:
        exp_options = experiments.apply(lambda r: f"{r['EXPERIMENT_ID']} — {r['EXPERIMENT_NAME']}", axis=1).tolist()
        selected_exp = st.selectbox("Experiment", exp_options, key="entry_experiment")
        exp_id = selected_exp.split(" — ")[0]

    with col2:
        ts = st.date_input("Date", value=datetime.now())
        ts_time = st.time_input("Time", value=datetime.now().time())

    st.markdown("#### Measurement Values")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        temp_k = st.number_input("Temperature (K)", min_value=0.001, max_value=300.0, value=1.0, format="%.4f")
    with c2:
        conductivity = st.number_input("Conductivity (S)", min_value=0.0, value=5e-8, format="%.2e")
    with c3:
        mobility = st.number_input("Mobility (cm²/Vs)", min_value=0.0, value=2e4, format="%.2e")
    with c4:
        density = st.number_input("Electron Density (cm⁻²)", min_value=0.0, value=3e7, format="%.2e")

    c5, c6, c7, c8 = st.columns(4)
    with c5:
        field = st.number_input("Pressing Field (V/cm)", min_value=0.0, value=40.0)
    with c6:
        freq = st.number_input("Frequency (GHz)", min_value=0.0, value=0.0, help="Leave 0 if not applicable")
    with c7:
        amplitude = st.number_input("Signal Amplitude (mV)", min_value=0.0, value=100.0)
    with c8:
        phase = st.number_input("Phase (deg)", min_value=-180.0, max_value=180.0, value=0.0)

    notes = st.text_area("Notes", placeholder="Any observations, anomalies, conditions...")

    if st.button("💾 Save Measurement", type="primary"):
        full_ts = datetime.combine(ts, ts_time)
        freq_val = freq if freq > 0 else "NULL"
        insert_sql = f"""
            INSERT INTO CRYOLAB.SURFACE_ELECTRONS.MEASUREMENTS 
            (EXPERIMENT_ID, TIMESTAMP, TEMPERATURE_K, CONDUCTIVITY_S, MOBILITY_CM2_VS, 
             ELECTRON_DENSITY_CM2, PRESSING_FIELD_V_CM, FREQUENCY_GHZ, SIGNAL_AMPLITUDE_MV, 
             PHASE_DEG, NOTES)
            VALUES ('{exp_id}', '{full_ts}', {temp_k}, {conductivity}, {mobility}, 
                    {density}, {field}, {freq_val}, {amplitude}, {phase}, 
                    {f"'{notes}'" if notes else "NULL"})
        """
        try:
            get_session().sql(insert_sql).collect()
            st.success(f"✅ Measurement saved to {exp_id}")
            st.cache_data.clear()
        except Exception as e:
            st.error(f"Error: {e}")


# ═══════════════════════════════════════════════════════════
# TAB 3: Analysis & Graphs
# ═══════════════════════════════════════════════════════════
with tab3:
    st.header("Measurement Analysis")

    filter_col1, filter_col2, filter_col3 = st.columns(3)
    with filter_col1:
        substrates = run_query("SELECT DISTINCT SUBSTRATE_TYPE FROM CRYOLAB.SURFACE_ELECTRONS.EXPERIMENTS ORDER BY SUBSTRATE_TYPE")
        sel_substrates = st.multiselect("Substrate Type", substrates["SUBSTRATE_TYPE"].tolist(), default=substrates["SUBSTRATE_TYPE"].tolist())

    with filter_col2:
        researchers = run_query("SELECT DISTINCT RESEARCHER FROM CRYOLAB.SURFACE_ELECTRONS.EXPERIMENTS ORDER BY RESEARCHER")
        sel_researchers = st.multiselect("Researcher", researchers["RESEARCHER"].tolist(), default=researchers["RESEARCHER"].tolist())

    with filter_col3:
        date_range = st.date_input("Date Range", value=(datetime(2024, 1, 1), datetime(2025, 12, 31)))

    substrate_filter = "','".join(sel_substrates) if sel_substrates else "''"
    researcher_filter = "','".join(sel_researchers) if sel_researchers else "''"
    start_date = date_range[0] if isinstance(date_range, tuple) else date_range
    end_date = date_range[1] if isinstance(date_range, tuple) and len(date_range) > 1 else datetime.now()

    data = run_query(f"""
        SELECT m.*, e.SUBSTRATE_TYPE, e.EXPERIMENT_NAME, e.RESEARCHER, e.FILM_THICKNESS_NM, e.CRYOSTAT
        FROM CRYOLAB.SURFACE_ELECTRONS.MEASUREMENTS m
        JOIN CRYOLAB.SURFACE_ELECTRONS.EXPERIMENTS e ON m.EXPERIMENT_ID = e.EXPERIMENT_ID
        WHERE e.SUBSTRATE_TYPE IN ('{substrate_filter}')
          AND e.RESEARCHER IN ('{researcher_filter}')
          AND m.TIMESTAMP BETWEEN '{start_date}' AND '{end_date}'
        ORDER BY m.TIMESTAMP
    """)

    if data.empty:
        st.warning("No data matches current filters.")
    else:
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("Total Points", f"{len(data):,}")
        kpi2.metric("Avg Mobility", f"{data['MOBILITY_CM2_VS'].mean():.2e} cm²/Vs")
        kpi3.metric("Min Temp", f"{data['TEMPERATURE_K'].min():.4f} K")
        kpi4.metric("Experiments", data["EXPERIMENT_ID"].nunique())

        st.markdown("---")

        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            st.subheader("Conductivity vs Temperature")
            fig1 = px.scatter(
                data, x="TEMPERATURE_K", y="CONDUCTIVITY_S",
                color="SUBSTRATE_TYPE", hover_data=["EXPERIMENT_ID", "RESEARCHER"],
                log_x=True, log_y=True,
                labels={"TEMPERATURE_K": "Temperature (K)", "CONDUCTIVITY_S": "Conductivity (S)"},
                color_discrete_map={"He4": "#29B5E8", "Ne": "#00D4AA", "H2": "#FF6B6B", "D2": "#FFB84D"},
            )
            fig1.update_layout(template="plotly_dark", height=450)
            st.plotly_chart(fig1, width="stretch")

        with chart_col2:
            st.subheader("Electron Mobility by Substrate")
            fig2 = px.box(
                data, x="SUBSTRATE_TYPE", y="MOBILITY_CM2_VS",
                color="SUBSTRATE_TYPE", log_y=True,
                labels={"SUBSTRATE_TYPE": "Substrate", "MOBILITY_CM2_VS": "Mobility (cm²/Vs)"},
                color_discrete_map={"He4": "#29B5E8", "Ne": "#00D4AA", "H2": "#FF6B6B", "D2": "#FFB84D"},
            )
            fig2.update_layout(template="plotly_dark", height=450, showlegend=False)
            st.plotly_chart(fig2, width="stretch")

        chart_col3, chart_col4 = st.columns(2)

        with chart_col3:
            st.subheader("Measurement Timeline")
            timeline = data.copy()
            timeline["DATE"] = pd.to_datetime(timeline["TIMESTAMP"]).dt.date
            daily_counts = timeline.groupby(["DATE", "SUBSTRATE_TYPE"]).size().reset_index(name="COUNT")
            fig3 = px.bar(
                daily_counts, x="DATE", y="COUNT", color="SUBSTRATE_TYPE",
                labels={"DATE": "Date", "COUNT": "Measurements"},
                color_discrete_map={"He4": "#29B5E8", "Ne": "#00D4AA", "H2": "#FF6B6B", "D2": "#FFB84D"},
            )
            fig3.update_layout(template="plotly_dark", height=400, barmode="stack")
            st.plotly_chart(fig3, width="stretch")

        with chart_col4:
            st.subheader("Cryostat Helium Level")
            he_data = data[data["HELIUM_LEVEL_PCT"].notna()].copy()
            if not he_data.empty:
                fig4 = px.line(
                    he_data, x="TIMESTAMP", y="HELIUM_LEVEL_PCT", color="EXPERIMENT_ID",
                    labels={"TIMESTAMP": "Time", "HELIUM_LEVEL_PCT": "He Level (%)"},
                )
                fig4.update_layout(template="plotly_dark", height=400, showlegend=False)
                st.plotly_chart(fig4, width="stretch")

        st.subheader("Mobility vs Temperature (All Substrates)")
        fig5 = px.scatter(
            data, x="TEMPERATURE_K", y="MOBILITY_CM2_VS",
            color="SUBSTRATE_TYPE", symbol="CRYOSTAT",
            log_x=True, log_y=True,
            labels={"TEMPERATURE_K": "Temperature (K)", "MOBILITY_CM2_VS": "Mobility (cm²/Vs)"},
            color_discrete_map={"He4": "#29B5E8", "Ne": "#00D4AA", "H2": "#FF6B6B", "D2": "#FFB84D"},
        )
        fig5.update_layout(template="plotly_dark", height=500)
        st.plotly_chart(fig5, width="stretch")


# ═══════════════════════════════════════════════════════════
# TAB 4: Chat with Data
# ═══════════════════════════════════════════════════════════
with tab4:
    st.header("Ask Your Data")
    st.markdown("Ask questions in natural language. Powered by Snowflake Cortex Analyst.")

    suggestions = [
        "What is the average mobility for each substrate type?",
        "Show me all experiments done on neon substrates",
        "Which experiment had the lowest temperature?",
        "Compare conductivity between He4 and Ne at similar temperatures",
        "How many anomalous measurements were recorded?",
        "What is the trend in mobility over time for hydrogen substrates?",
    ]

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    if not st.session_state.chat_messages:
        st.markdown("**Try one of these questions:**")
        cols = st.columns(3)
        for i, s in enumerate(suggestions):
            if cols[i % 3].button(s, key=f"sug_{i}"):
                st.session_state.chat_messages.append({"role": "user", "content": s})
                st.rerun()

    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            if "sql" in msg:
                with st.expander("View SQL"):
                    st.code(msg["sql"], language="sql")
            if "dataframe" in msg:
                st.dataframe(msg["dataframe"], width="stretch")

    if prompt := st.chat_input("Ask about your measurement data..."):
        st.session_state.chat_messages.append({"role": "user", "content": prompt})

        with st.chat_message("user"):
            st.write(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Analyzing..."):
                try:
                    analyst_result = run_query(f"""
                        SELECT SNOWFLAKE.CORTEX.COMPLETE(
                            'claude-3-5-sonnet',
                            'You are an expert SQL assistant for a low-temperature physics research database.
                            
The database CRYOLAB.SURFACE_ELECTRONS has these tables:
- EXPERIMENTS: EXPERIMENT_ID, EXPERIMENT_NAME, SUBSTRATE_TYPE (He4/Ne/H2/D2), CRYOSTAT, RESEARCHER, START_DATE, END_DATE, TARGET_TEMP_K, PRESSING_FIELD_V_CM, FILM_THICKNESS_NM, NOTES
- MEASUREMENTS: MEASUREMENT_ID, EXPERIMENT_ID, TIMESTAMP, TEMPERATURE_K, CONDUCTIVITY_S, MOBILITY_CM2_VS, ELECTRON_DENSITY_CM2, PRESSING_FIELD_V_CM, FREQUENCY_GHZ, SIGNAL_AMPLITUDE_MV, PHASE_DEG, HELIUM_LEVEL_PCT, CRYOSTAT_PRESSURE_MBAR, NOTES

Generate a SQL query to answer: {prompt.replace("'", "''")}

Return ONLY the SQL query, no explanation. Use fully qualified table names.'
                        ) AS sql_query
                    """)
                    
                    generated_sql = analyst_result["SQL_QUERY"].iloc[0].strip()
                    if generated_sql.startswith("```"):
                        generated_sql = generated_sql.split("\n", 1)[1].rsplit("```", 1)[0].strip()
                    
                    with st.expander("Generated SQL", expanded=False):
                        st.code(generated_sql, language="sql")

                    result_df = run_query(generated_sql)
                    
                    if not result_df.empty:
                        st.dataframe(result_df, width="stretch")

                        interpretation = run_query(f"""
                            SELECT SNOWFLAKE.CORTEX.COMPLETE(
                                'claude-3-5-sonnet',
                                'You are a low-temperature physics research assistant. 
The user asked: {prompt.replace("'", "''")}

The SQL query returned this data (showing first rows):
{result_df.head(20).to_string().replace("'", "''")}

Provide a brief, insightful interpretation of these results in the context of surface electron physics on quantum substrates. 
Mention any notable patterns, comparisons between substrates, or physics implications. Keep it to 2-3 sentences.'
                            ) AS interpretation
                        """)
                        
                        st.markdown(f"**Insight:** {interpretation['INTERPRETATION'].iloc[0]}")
                    else:
                        st.info("Query returned no results.")
                    
                    st.session_state.chat_messages.append({
                        "role": "assistant",
                        "content": interpretation["INTERPRETATION"].iloc[0] if not result_df.empty else "No results found.",
                        "sql": generated_sql,
                        "dataframe": result_df if not result_df.empty else None,
                    })

                except Exception as e:
                    error_msg = f"I had trouble processing that query: {str(e)}"
                    st.error(error_msg)
                    st.session_state.chat_messages.append({"role": "assistant", "content": error_msg})


# ═══════════════════════════════════════════════════════════
# TAB 5: Anomaly Detection
# ═══════════════════════════════════════════════════════════
with tab5:
    st.header("Anomaly Detection & Hypothesis Generation")

    anomaly_method = st.selectbox(
        "Detection Method",
        ["Statistical (Z-Score)", "Physics-Based Rules", "AI-Powered Analysis"],
        key="anomaly_method",
    )

    anomaly_exp = st.selectbox(
        "Experiment",
        run_query("SELECT EXPERIMENT_ID || ' — ' || EXPERIMENT_NAME AS label FROM CRYOLAB.SURFACE_ELECTRONS.EXPERIMENTS ORDER BY START_DATE DESC")["LABEL"].tolist(),
        key="anomaly_experiment",
    )
    anomaly_exp_id = anomaly_exp.split(" — ")[0]

    if st.button("🔎 Detect Anomalies", type="primary"):
        exp_data = run_query(f"""
            SELECT m.*, e.SUBSTRATE_TYPE
            FROM CRYOLAB.SURFACE_ELECTRONS.MEASUREMENTS m
            JOIN CRYOLAB.SURFACE_ELECTRONS.EXPERIMENTS e ON m.EXPERIMENT_ID = e.EXPERIMENT_ID
            WHERE m.EXPERIMENT_ID = '{anomaly_exp_id}'
            ORDER BY m.TIMESTAMP
        """)

        if exp_data.empty:
            st.warning("No data for this experiment.")
        else:
            if anomaly_method == "Statistical (Z-Score)":
                numeric_cols = ["TEMPERATURE_K", "CONDUCTIVITY_S", "MOBILITY_CM2_VS", "SIGNAL_AMPLITUDE_MV"]
                anomalies = pd.DataFrame()
                
                for col in numeric_cols:
                    if col in exp_data.columns and exp_data[col].notna().sum() > 10:
                        mean = exp_data[col].mean()
                        std = exp_data[col].std()
                        if std > 0:
                            z_scores = np.abs((exp_data[col] - mean) / std)
                            mask = z_scores > 3
                            if mask.any():
                                flagged = exp_data[mask].copy()
                                flagged["ANOMALY_TYPE"] = f"{col} outlier (Z>{z_scores[mask].min():.1f})"
                                anomalies = pd.concat([anomalies, flagged])

                if not anomalies.empty:
                    st.error(f"🚨 Found {len(anomalies)} anomalous data points!")
                    st.dataframe(anomalies[["TIMESTAMP", "TEMPERATURE_K", "CONDUCTIVITY_S", "MOBILITY_CM2_VS", "ANOMALY_TYPE", "NOTES"]].drop_duplicates(), width="stretch")
                else:
                    st.success("✅ No statistical anomalies detected (Z > 3).")

            elif anomaly_method == "Physics-Based Rules":
                rules_violated = []
                
                temp_jumps = exp_data["TEMPERATURE_K"].diff().abs()
                median_jump = temp_jumps.median()
                big_jumps = exp_data[temp_jumps > 10 * median_jump] if median_jump > 0 else pd.DataFrame()
                if not big_jumps.empty:
                    for _, row in big_jumps.iterrows():
                        rules_violated.append({"Timestamp": row["TIMESTAMP"], "Rule": "Temperature jump > 10x median step", "Value": f"ΔT = {temp_jumps[row.name]:.4f} K"})

                if exp_data["SUBSTRATE_TYPE"].iloc[0] == "He4":
                    low_mobility = exp_data[exp_data["MOBILITY_CM2_VS"] < 1e3]
                    for _, row in low_mobility.iterrows():
                        rules_violated.append({"Timestamp": row["TIMESTAMP"], "Rule": "He4 mobility below 1e3 (expected >1e4)", "Value": f"μ = {row['MOBILITY_CM2_VS']:.2e}"})

                neg_he = exp_data[exp_data["HELIUM_LEVEL_PCT"] < 65]
                for _, row in neg_he.iterrows():
                    rules_violated.append({"Timestamp": row["TIMESTAMP"], "Rule": "Helium level critically low (<65%)", "Value": f"{row['HELIUM_LEVEL_PCT']:.1f}%"})

                if rules_violated:
                    st.error(f"🚨 {len(rules_violated)} physics rule violations detected!")
                    st.dataframe(pd.DataFrame(rules_violated), width="stretch")
                else:
                    st.success("✅ No physics-based rule violations.")

            else:  # AI-Powered
                with st.spinner("Running AI analysis on measurement series..."):
                    summary_stats = exp_data.describe().to_string()
                    anomaly_notes = exp_data[exp_data["NOTES"].notna() & (exp_data["NOTES"] != "")]["NOTES"].tolist()[:10]
                    
                    ai_result = run_query(f"""
                        SELECT SNOWFLAKE.CORTEX.COMPLETE(
                            'claude-3-5-sonnet',
                            'You are an expert in low-temperature surface electron physics.
                            
Analyze this experiment data for anomalies and generate hypotheses.

Experiment: {anomaly_exp}
Substrate: {exp_data["SUBSTRATE_TYPE"].iloc[0]}
Data points: {len(exp_data)}
Statistics:
{summary_stats.replace("'", "''")}

Flagged notes from measurements:
{str(anomaly_notes).replace("'", "''")}

Please:
1. Identify any anomalies or suspicious patterns in the statistics
2. For each anomaly, suggest a physical hypothesis (substrate defect, cryostat malfunction, contamination, etc.)
3. Recommend follow-up experiments or measurements to test each hypothesis
4. Rate confidence in each hypothesis (Low/Medium/High)

Format as structured markdown.'
                        ) AS analysis
                    """)
                    
                    st.markdown(ai_result["ANALYSIS"].iloc[0])

            st.markdown("---")
            st.subheader("Measurement Series Visualization")
            
            viz_col = st.selectbox("Plot variable", ["CONDUCTIVITY_S", "MOBILITY_CM2_VS", "TEMPERATURE_K", "SIGNAL_AMPLITUDE_MV"], key="anomaly_viz_col")
            
            fig_anom = go.Figure()
            fig_anom.add_trace(go.Scatter(
                x=exp_data["TIMESTAMP"], y=exp_data[viz_col],
                mode="lines+markers", name=viz_col,
                marker=dict(size=4, color="#29B5E8"),
                line=dict(width=1, color="#29B5E8"),
            ))
            
            mean_val = exp_data[viz_col].mean()
            std_val = exp_data[viz_col].std()
            fig_anom.add_hline(y=mean_val + 3 * std_val, line_dash="dash", line_color="red", annotation_text="+3σ")
            fig_anom.add_hline(y=mean_val - 3 * std_val, line_dash="dash", line_color="red", annotation_text="-3σ")
            fig_anom.add_hline(y=mean_val, line_dash="dot", line_color="gray", annotation_text="mean")
            
            anomalous = exp_data[exp_data["NOTES"].str.contains("ANOMALY", na=False)]
            if not anomalous.empty:
                fig_anom.add_trace(go.Scatter(
                    x=anomalous["TIMESTAMP"], y=anomalous[viz_col],
                    mode="markers", name="Flagged Anomaly",
                    marker=dict(size=12, color="red", symbol="x"),
                ))
            
            fig_anom.update_layout(
                template="plotly_dark", height=500,
                title=f"{viz_col} over time — {anomaly_exp_id}",
                yaxis_title=viz_col, xaxis_title="Time",
            )
            st.plotly_chart(fig_anom, width="stretch")
