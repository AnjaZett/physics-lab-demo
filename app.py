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
import uuid

st.set_page_config(
    page_title="CryoLab | Surface Electron Research Platform",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ═══════════════════════════════════════════════════════════
# CUSTOM CSS — Lab Aesthetic
# ═══════════════════════════════════════════════════════════
def inject_custom_css():
    st.markdown("""
    <style>
    /* Grid-paper background for main content */
    [data-testid="stMain"] {
        background-image: 
            linear-gradient(rgba(41, 181, 232, 0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(41, 181, 232, 0.03) 1px, transparent 1px);
        background-size: 40px 40px;
    }
    
    /* Monospace font for all metric values */
    [data-testid="stMetricValue"] {
        font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace !important;
    }
    
    /* Styled dataframes */
    [data-testid="stDataFrame"] {
        font-family: 'JetBrains Mono', 'Fira Code', monospace;
        font-size: 0.85rem;
    }
    
    /* Thinner dividers */
    hr {
        border: none;
        border-top: 1px solid rgba(41, 181, 232, 0.2) !important;
        margin: 1rem 0;
    }
    
    /* KPI Card styling */
    .kpi-card {
        background: linear-gradient(135deg, #1B2332 0%, #0E1117 100%);
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        border-left: 4px solid;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .kpi-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(41, 181, 232, 0.15);
    }
    .kpi-value {
        font-family: 'JetBrains Mono', 'Fira Code', monospace;
        font-size: 1.8rem;
        font-weight: 700;
        margin: 0.3rem 0;
    }
    .kpi-label {
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #8899AA;
    }
    .kpi-subtitle {
        font-size: 0.75rem;
        color: #667788;
        margin-top: 0.2rem;
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0a0f1a 0%, #0E1117 100%);
    }
    .sidebar-sparkline {
        margin: 0.5rem 0;
    }
    .status-badge {
        display: inline-block;
        padding: 0.2rem 0.6rem;
        border-radius: 12px;
        font-size: 0.7rem;
        font-weight: 600;
        letter-spacing: 0.03em;
    }
    .status-green { background: rgba(0, 212, 170, 0.15); color: #00D4AA; }
    .status-yellow { background: rgba(255, 184, 77, 0.15); color: #FFB84D; }
    .status-red { background: rgba(255, 107, 107, 0.15); color: #FF6B6B; }
    
    /* Anomaly alert banner */
    .anomaly-banner {
        background: linear-gradient(90deg, rgba(255, 107, 107, 0.08), rgba(255, 184, 77, 0.05));
        border: 1px solid rgba(255, 107, 107, 0.3);
        border-radius: 8px;
        padding: 0.8rem 1.2rem;
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
        gap: 0.8rem;
    }
    
    /* Better tab styling */
    [data-testid="stTabs"] [data-baseweb="tab"] {
        font-weight: 500;
        letter-spacing: 0.02em;
    }
    
    /* OCR History card */
    .ocr-history-item {
        background: #1B2332;
        border-radius: 8px;
        padding: 0.8rem 1rem;
        margin-bottom: 0.5rem;
        border-left: 3px solid #29B5E8;
    }
    
    /* Button hover glow */
    [data-testid="stButton"] button[kind="primary"]:hover {
        box-shadow: 0 0 15px rgba(41, 181, 232, 0.3);
    }
    </style>
    """, unsafe_allow_html=True)

inject_custom_css()

# ═══════════════════════════════════════════════════════════
# CONNECTION & SESSION
# ═══════════════════════════════════════════════════════════
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
        elif "password" in secrets:
            config["password"] = secrets["password"]
        elif "authenticator" in secrets:
            # externalbrowser or other authenticator — fall through to connection_name
            return Session.builder.config("connection_name", CONNECTION_NAME).create()
        else:
            return Session.builder.config("connection_name", CONNECTION_NAME).create()
        return Session.builder.configs(config).create()
    return Session.builder.config("connection_name", CONNECTION_NAME).create()

if "snowpark_session" not in st.session_state:
    st.session_state.snowpark_session = create_session()

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())[:8]

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

# ═══════════════════════════════════════════════════════════
# HELPER: KPI Card
# ═══════════════════════════════════════════════════════════
def kpi_card(icon, label, value, subtitle="", color="#29B5E8"):
    st.markdown(f"""
    <div class="kpi-card" style="border-left-color: {color};">
        <div class="kpi-label">{icon} {label}</div>
        <div class="kpi-value" style="color: {color};">{value}</div>
        <div class="kpi-subtitle">{subtitle}</div>
    </div>
    """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════
# SIDEBAR — Modernized
# ═══════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("""
    <div style="text-align:center; padding: 0.5rem 0 1rem 0;">
        <span style="font-size: 2.2rem;">❄️</span>
        <h2 style="margin: 0.2rem 0 0 0; font-weight: 700; letter-spacing: -0.02em;">CryoLab</h2>
        <span style="font-size: 0.75rem; color: #8899AA; letter-spacing: 0.05em;">SURFACE ELECTRON RESEARCH</span>
    </div>
    """, unsafe_allow_html=True)
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

    col_s1, col_s2 = st.columns(2)
    col_s1.metric("Experiments", stats["EXPERIMENTS"].iloc[0])
    col_s2.metric("Substrates", stats["SUBSTRATES"].iloc[0])
    st.metric("Total Data Points", f"{stats['MEASUREMENTS'].iloc[0]:,}")

    # Sparkline — last 30 days activity
    sparkline_data = run_query("""
        SELECT TIMESTAMP::DATE AS day, COUNT(*) AS cnt
        FROM CRYOLAB.SURFACE_ELECTRONS.MEASUREMENTS
        WHERE TIMESTAMP >= DATEADD(DAY, -30, CURRENT_TIMESTAMP())
        GROUP BY day ORDER BY day
    """)
    if not sparkline_data.empty:
        fig_spark = go.Figure(go.Scatter(
            x=sparkline_data["DAY"], y=sparkline_data["CNT"],
            mode="lines", fill="tozeroy",
            line=dict(color="#29B5E8", width=1.5),
            fillcolor="rgba(41, 181, 232, 0.1)",
        ))
        fig_spark.update_layout(
            height=60, margin=dict(l=0, r=0, t=0, b=0),
            xaxis=dict(visible=False), yaxis=dict(visible=False),
            template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_spark, use_container_width=True, config={"displayModeBar": False})
        st.caption("Activity (last 30 days)")

    # Status badge
    last_measurement = run_query("SELECT MAX(TIMESTAMP) AS last_ts FROM CRYOLAB.SURFACE_ELECTRONS.MEASUREMENTS")
    if not last_measurement.empty and last_measurement["LAST_TS"].iloc[0] is not None:
        last_ts = pd.to_datetime(last_measurement["LAST_TS"].iloc[0])
        days_ago = (datetime.now() - last_ts).days
        if days_ago <= 3:
            badge_class, badge_text = "status-green", f"Active — last measurement {days_ago}d ago"
        elif days_ago <= 14:
            badge_class, badge_text = "status-yellow", f"Idle — last measurement {days_ago}d ago"
        else:
            badge_class, badge_text = "status-red", f"Inactive — last measurement {days_ago}d ago"
        st.markdown(f'<span class="status-badge {badge_class}">{badge_text}</span>', unsafe_allow_html=True)

    st.markdown("---")
    st.caption(f"Data: {stats['FIRST_DATE'].iloc[0]} → {stats['LAST_DATE'].iloc[0]}")


# ═══════════════════════════════════════════════════════════
# ANOMALY ALERT BANNER (proactive check)
# ═══════════════════════════════════════════════════════════
try:
    recent_anomalies = run_query("""
        SELECT COUNT(*) AS cnt
        FROM CRYOLAB.SURFACE_ELECTRONS.MEASUREMENTS
        WHERE TIMESTAMP >= DATEADD(DAY, -1, CURRENT_TIMESTAMP())
          AND NOTES LIKE '%ANOMALY%'
    """)
    anomaly_count = recent_anomalies["CNT"].iloc[0] if not recent_anomalies.empty else 0
    if anomaly_count > 0:
        st.markdown(f"""
        <div class="anomaly-banner">
            <span style="font-size: 1.3rem;">⚠️</span>
            <div>
                <strong>{anomaly_count} anomalous measurement{'s' if anomaly_count > 1 else ''}</strong> detected in the last 24 hours.
                <span style="color: #8899AA;">Check the Anomaly Detection tab for details.</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
except Exception:
    pass


# ═══════════════════════════════════════════════════════════
# TABS
# ═══════════════════════════════════════════════════════════
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📸 Notebook OCR",
    "📝 Data Entry",
    "📊 Analysis & Graphs",
    "💬 Chat with Data",
    "⚠️ Anomaly Detection",
])


# ═══════════════════════════════════════════════════════════
# TAB 1: Notebook OCR (with real import + data editor + history)
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
            st.image(uploaded_files[0], caption=uploaded_files[0].name, use_container_width=True)

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
            st.session_state["ocr_raw_text"] = raw_text
            st.session_state["ocr_filename"] = stage_file

            st.subheader("📄 Raw OCR Output")
            with st.expander("Show raw text", expanded=False):
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
                    'mistral-large2',
                    '{extract_prompt.replace("'", "''")}'
                ) AS extracted
            """)

            extracted_text = extract_result["EXTRACTED"].iloc[0]

            # Parse JSON and store in session state
            try:
                # Handle markdown code fences
                clean_json = extracted_text.strip()
                if clean_json.startswith("```"):
                    clean_json = clean_json.split("\n", 1)[1].rsplit("```", 1)[0].strip()
                parsed_data = json.loads(clean_json)
                st.session_state["ocr_extracted_data"] = parsed_data
                st.session_state["ocr_stage_file"] = stage_file
            except json.JSONDecodeError:
                st.error("Could not parse AI output as JSON. Raw output shown below.")
                st.code(extracted_text)
                st.session_state["ocr_extracted_data"] = None

    # Data Editor for validation before import
    if "ocr_extracted_data" in st.session_state and st.session_state["ocr_extracted_data"]:
        st.subheader("✏️ Review & Edit Extracted Data")
        st.caption("Correct any OCR errors before importing. Delete rows you don't want to import.")

        edit_df = pd.DataFrame(st.session_state["ocr_extracted_data"])
        edited_df = st.data_editor(
            edit_df,
            num_rows="dynamic",
            use_container_width=True,
            key="ocr_data_editor",
        )

        col_import, col_clear = st.columns([1, 4])
        with col_import:
            if st.button("💾 Import to Database", type="primary"):
                imported = 0
                errors = 0
                for _, row in edited_df.iterrows():
                    try:
                        exp_id = row.get("experiment_id", "UNKNOWN")
                        date_val = row.get("date", datetime.now().strftime("%Y-%m-%d"))
                        temp = row.get("temperature_k", "NULL")
                        cond = row.get("conductivity_s", "NULL")
                        mob = row.get("mobility_cm2_vs", "NULL")
                        dens = row.get("electron_density_cm2", "NULL")
                        field = row.get("pressing_field_v_cm", "NULL")
                        notes_val = str(row.get("notes", "")).replace("'", "''")

                        # Convert NaN/None to NULL
                        temp = "NULL" if pd.isna(temp) else temp
                        cond = "NULL" if pd.isna(cond) else cond
                        mob = "NULL" if pd.isna(mob) else mob
                        dens = "NULL" if pd.isna(dens) else dens
                        field = "NULL" if pd.isna(field) else field

                        insert_sql = f"""
                            INSERT INTO CRYOLAB.SURFACE_ELECTRONS.MEASUREMENTS 
                            (EXPERIMENT_ID, TIMESTAMP, TEMPERATURE_K, CONDUCTIVITY_S, 
                             MOBILITY_CM2_VS, ELECTRON_DENSITY_CM2, PRESSING_FIELD_V_CM, NOTES)
                            VALUES ('{exp_id}', 
                                    COALESCE(TRY_TO_TIMESTAMP_NTZ('{date_val}'), TRY_TO_TIMESTAMP_NTZ('{date_val}', 'DD MON YYYY'), TRY_TO_TIMESTAMP_NTZ('{date_val}', 'D MON YYYY'), TRY_TO_TIMESTAMP_NTZ('{date_val}', 'MON DD, YYYY'), TRY_TO_TIMESTAMP_NTZ('{date_val}', 'YYYY/MM/DD'), CURRENT_TIMESTAMP()),
                                    {temp}, {cond}, 
                                    {mob}, {dens}, {field}, 
                                    '{notes_val}')
                        """
                        get_session().sql(insert_sql).collect()
                        imported += 1
                    except Exception as e:
                        errors += 1
                        st.warning(f"Row error: {e}")

                # Save OCR extract metadata
                try:
                    raw_text = st.session_state.get("ocr_raw_text", "")
                    filename = st.session_state.get("ocr_filename", "unknown")
                    json_str = json.dumps(st.session_state["ocr_extracted_data"]).replace("'", "''")
                    get_session().sql(f"""
                        INSERT INTO CRYOLAB.SURFACE_ELECTRONS.OCR_EXTRACTS
                        (FILE_NAME, UPLOAD_TIMESTAMP, RAW_OCR_TEXT, PARSED_DATA, STATUS)
                        VALUES ('{filename}', CURRENT_TIMESTAMP(), 
                                '{raw_text.replace("'", "''")}',
                                PARSE_JSON('{json_str}'),
                                'imported')
                    """).collect()
                except Exception:
                    pass

                if imported > 0:
                    st.success(f"✅ Successfully imported {imported} measurements!")
                    if errors > 0:
                        st.warning(f"⚠️ {errors} rows had errors.")
                    # Clear state
                    del st.session_state["ocr_extracted_data"]
                    st.balloons()
                else:
                    st.error("No rows could be imported.")

        with col_clear:
            if st.button("🗑️ Clear", help="Discard extracted data"):
                if "ocr_extracted_data" in st.session_state:
                    del st.session_state["ocr_extracted_data"]
                st.rerun()

    # OCR Upload History
    st.markdown("---")
    with st.expander("📋 Upload History", expanded=False):
        history = run_query("""
            SELECT FILE_NAME, UPLOAD_TIMESTAMP, STATUS,
                   ARRAY_SIZE(PARSED_DATA) AS rows_extracted
            FROM CRYOLAB.SURFACE_ELECTRONS.OCR_EXTRACTS
            ORDER BY UPLOAD_TIMESTAMP DESC
            LIMIT 20
        """)
        if not history.empty:
            st.dataframe(history, use_container_width=True, hide_index=True)
        else:
            st.info("No previous OCR uploads found.")


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
# TAB 3: Analysis & Graphs (with Export + Comparison)
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
        # Export toolbar
        export_col1, export_col2, export_col3 = st.columns([1, 1, 6])
        with export_col1:
            csv_data = data.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Export CSV",
                data=csv_data,
                file_name=f"cryolab_export_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )
        with export_col2:
            # Excel export
            try:
                import io
                excel_buffer = io.BytesIO()
                data.to_excel(excel_buffer, index=False, engine="openpyxl")
                excel_buffer.seek(0)
                st.download_button(
                    "📥 Export Excel",
                    data=excel_buffer,
                    file_name=f"cryolab_export_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            except ImportError:
                pass  # openpyxl not available

        # KPI Cards
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        with kpi1:
            kpi_card("📊", "Total Points", f"{len(data):,}",
                     f"from {data['EXPERIMENT_ID'].nunique()} experiments", "#29B5E8")
        with kpi2:
            kpi_card("⚡", "Avg Mobility", f"{data['MOBILITY_CM2_VS'].mean():.2e}",
                     "cm²/Vs across all substrates", "#00D4AA")
        with kpi3:
            kpi_card("🌡️", "Min Temperature", f"{data['TEMPERATURE_K'].min():.4f} K",
                     f"Max: {data['TEMPERATURE_K'].max():.2f} K", "#FF6B6B")
        with kpi4:
            kpi_card("🧪", "Substrates", f"{data['SUBSTRATE_TYPE'].nunique()}",
                     ", ".join(data['SUBSTRATE_TYPE'].unique()), "#FFB84D")

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
            st.plotly_chart(fig1, use_container_width=True)

        with chart_col2:
            st.subheader("Electron Mobility by Substrate")
            fig2 = px.box(
                data, x="SUBSTRATE_TYPE", y="MOBILITY_CM2_VS",
                color="SUBSTRATE_TYPE", log_y=True,
                labels={"SUBSTRATE_TYPE": "Substrate", "MOBILITY_CM2_VS": "Mobility (cm²/Vs)"},
                color_discrete_map={"He4": "#29B5E8", "Ne": "#00D4AA", "H2": "#FF6B6B", "D2": "#FFB84D"},
            )
            fig2.update_layout(template="plotly_dark", height=450, showlegend=False)
            st.plotly_chart(fig2, use_container_width=True)

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
            st.plotly_chart(fig3, use_container_width=True)

        with chart_col4:
            st.subheader("Cryostat Helium Level")
            he_data = data[data["HELIUM_LEVEL_PCT"].notna()].copy()
            if not he_data.empty:
                fig4 = px.line(
                    he_data, x="TIMESTAMP", y="HELIUM_LEVEL_PCT", color="EXPERIMENT_ID",
                    labels={"TIMESTAMP": "Time", "HELIUM_LEVEL_PCT": "He Level (%)"},
                )
                fig4.update_layout(template="plotly_dark", height=400, showlegend=False)
                st.plotly_chart(fig4, use_container_width=True)

        st.subheader("Mobility vs Temperature (All Substrates)")
        fig5 = px.scatter(
            data, x="TEMPERATURE_K", y="MOBILITY_CM2_VS",
            color="SUBSTRATE_TYPE", symbol="CRYOSTAT",
            log_x=True, log_y=True,
            labels={"TEMPERATURE_K": "Temperature (K)", "MOBILITY_CM2_VS": "Mobility (cm²/Vs)"},
            color_discrete_map={"He4": "#29B5E8", "Ne": "#00D4AA", "H2": "#FF6B6B", "D2": "#FFB84D"},
        )
        fig5.update_layout(template="plotly_dark", height=500)
        st.plotly_chart(fig5, use_container_width=True)

        # ── Experiment Comparison ──
        st.markdown("---")
        st.subheader("🔬 Experiment Comparison")
        st.caption("Select experiments to overlay their measurements in a single chart.")

        all_experiments = data[["EXPERIMENT_ID", "EXPERIMENT_NAME"]].drop_duplicates()
        exp_labels = all_experiments.apply(lambda r: f"{r['EXPERIMENT_ID']} — {r['EXPERIMENT_NAME']}", axis=1).tolist()

        compare_exps = st.multiselect(
            "Select experiments to compare",
            exp_labels,
            default=exp_labels[:2] if len(exp_labels) >= 2 else exp_labels,
            key="compare_experiments",
        )

        compare_y = st.selectbox(
            "Y-axis variable",
            ["CONDUCTIVITY_S", "MOBILITY_CM2_VS", "TEMPERATURE_K", "ELECTRON_DENSITY_CM2", "SIGNAL_AMPLITUDE_MV"],
            key="compare_y_var",
        )

        if compare_exps:
            compare_ids = [e.split(" — ")[0] for e in compare_exps]
            compare_data = data[data["EXPERIMENT_ID"].isin(compare_ids)].copy()
            # Normalize time to start=0 for fair comparison
            compare_data["TIME_OFFSET_H"] = compare_data.groupby("EXPERIMENT_ID")["TIMESTAMP"].transform(
                lambda x: (pd.to_datetime(x) - pd.to_datetime(x).min()).dt.total_seconds() / 3600
            )

            fig_compare = px.line(
                compare_data, x="TIME_OFFSET_H", y=compare_y,
                color="EXPERIMENT_ID", markers=True,
                labels={"TIME_OFFSET_H": "Time from start (hours)", compare_y: compare_y},
                color_discrete_sequence=["#29B5E8", "#00D4AA", "#FF6B6B", "#FFB84D", "#A78BFA"],
            )
            fig_compare.update_layout(template="plotly_dark", height=450)
            st.plotly_chart(fig_compare, use_container_width=True)


# ═══════════════════════════════════════════════════════════
# TAB 4: Chat with Data (with persistence)
# ═══════════════════════════════════════════════════════════
with tab4:
    st.header("Ask Your Data")
    st.markdown("Ask questions in natural language. Powered by Snowflake Cortex Analyst.")

    # Ensure chat history table exists
    try:
        get_session().sql("""
            CREATE TABLE IF NOT EXISTS CRYOLAB.SURFACE_ELECTRONS.CHAT_HISTORY (
                MESSAGE_ID NUMBER AUTOINCREMENT,
                SESSION_ID TEXT,
                ROLE TEXT,
                CONTENT TEXT,
                SQL_QUERY TEXT,
                CREATED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
            )
        """).collect()
    except Exception:
        pass

    suggestions = [
        "What is the average mobility for each substrate type?",
        "Show me all experiments done on neon substrates",
        "Which experiment had the lowest temperature?",
        "Compare conductivity between He4 and Ne at similar temperatures",
        "How many anomalous measurements were recorded?",
        "What is the trend in mobility over time for hydrogen substrates?",
    ]

    # Load persisted chat history
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
        try:
            saved_msgs = run_query(f"""
                SELECT ROLE, CONTENT, SQL_QUERY 
                FROM CRYOLAB.SURFACE_ELECTRONS.CHAT_HISTORY
                WHERE SESSION_ID = '{st.session_state.session_id}'
                ORDER BY CREATED_AT
                LIMIT 50
            """)
            if not saved_msgs.empty:
                for _, row in saved_msgs.iterrows():
                    msg = {"role": row["ROLE"], "content": row["CONTENT"]}
                    if row["SQL_QUERY"]:
                        msg["sql"] = row["SQL_QUERY"]
                    st.session_state.chat_messages.append(msg)
        except Exception:
            pass

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
                st.dataframe(msg["dataframe"], use_container_width=True)

    if prompt := st.chat_input("Ask about your measurement data..."):
        st.session_state.chat_messages.append({"role": "user", "content": prompt})

        # Persist user message
        try:
            get_session().sql(f"""
                INSERT INTO CRYOLAB.SURFACE_ELECTRONS.CHAT_HISTORY (SESSION_ID, ROLE, CONTENT)
                VALUES ('{st.session_state.session_id}', 'user', '{prompt.replace("'", "''")}')
            """).collect()
        except Exception:
            pass

        with st.chat_message("user"):
            st.write(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Analyzing..."):
                try:
                    analyst_result = run_query(f"""
                        SELECT SNOWFLAKE.CORTEX.COMPLETE(
                            'mistral-large2',
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
                        st.dataframe(result_df, use_container_width=True)

                        interpretation = run_query(f"""
                            SELECT SNOWFLAKE.CORTEX.COMPLETE(
                                'mistral-large2',
                                'You are a low-temperature physics research assistant. 
The user asked: {prompt.replace("'", "''")}

The SQL query returned this data (showing first rows):
{result_df.head(20).to_string().replace("'", "''")}

Provide a brief, insightful interpretation of these results in the context of surface electron physics on quantum substrates. 
Mention any notable patterns, comparisons between substrates, or physics implications. Keep it to 2-3 sentences.'
                            ) AS interpretation
                        """)
                        
                        response_text = interpretation['INTERPRETATION'].iloc[0]
                        st.markdown(f"**Insight:** {response_text}")
                    else:
                        response_text = "Query returned no results."
                        st.info(response_text)
                    
                    st.session_state.chat_messages.append({
                        "role": "assistant",
                        "content": response_text,
                        "sql": generated_sql,
                        "dataframe": result_df if not result_df.empty else None,
                    })

                    # Persist assistant message
                    try:
                        get_session().sql(f"""
                            INSERT INTO CRYOLAB.SURFACE_ELECTRONS.CHAT_HISTORY (SESSION_ID, ROLE, CONTENT, SQL_QUERY)
                            VALUES ('{st.session_state.session_id}', 'assistant', 
                                    '{response_text.replace("'", "''")}', '{generated_sql.replace("'", "''")}')
                        """).collect()
                    except Exception:
                        pass

                except Exception as e:
                    error_msg = f"I had trouble processing that query: {str(e)}"
                    st.error(error_msg)
                    st.session_state.chat_messages.append({"role": "assistant", "content": error_msg})

    # Clear chat button
    if st.session_state.chat_messages:
        if st.button("🗑️ Clear Chat History", key="clear_chat"):
            st.session_state.chat_messages = []
            try:
                get_session().sql(f"""
                    DELETE FROM CRYOLAB.SURFACE_ELECTRONS.CHAT_HISTORY
                    WHERE SESSION_ID = '{st.session_state.session_id}'
                """).collect()
            except Exception:
                pass
            st.rerun()


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
                    st.dataframe(anomalies[["TIMESTAMP", "TEMPERATURE_K", "CONDUCTIVITY_S", "MOBILITY_CM2_VS", "ANOMALY_TYPE", "NOTES"]].drop_duplicates(), use_container_width=True)
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
                    st.dataframe(pd.DataFrame(rules_violated), use_container_width=True)
                else:
                    st.success("✅ No physics-based rule violations.")

            else:  # AI-Powered
                with st.spinner("Running AI analysis on measurement series..."):
                    summary_stats = exp_data.describe().to_string()
                    anomaly_notes = exp_data[exp_data["NOTES"].notna() & (exp_data["NOTES"] != "")]["NOTES"].tolist()[:10]
                    
                    ai_result = run_query(f"""
                        SELECT SNOWFLAKE.CORTEX.COMPLETE(
                            'mistral-large2',
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
            st.plotly_chart(fig_anom, use_container_width=True)
