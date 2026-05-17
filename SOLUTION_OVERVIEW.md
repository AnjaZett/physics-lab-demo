# CryoLab: AI-Powered Research Data Platform
## Surface Electrons on Quantum Substrates — Solution Overview

---

## The Problem

You have **years of handwritten lab notebooks** containing measurement data from cryogenic surface electron experiments. This data is:
- Scattered across paper notebooks, hard to search
- At risk of loss or degradation  
- Impossible to cross-reference or analyze at scale
- Not available for AI-assisted pattern discovery

New measurements are still recorded manually, with no systematic digital pipeline.

---

## The Solution: Snowflake as Your Research Data Cloud

### Architecture

```
┌─────────────────────┐     ┌──────────────────────┐     ┌────────────────────┐
│  HANDWRITTEN NOTES  │     │   NEW MEASUREMENTS   │     │   INSTRUMENT FEEDS │
│  (photographs)      │     │   (manual entry)     │     │   (future: direct) │
└────────┬────────────┘     └──────────┬───────────┘     └────────┬───────────┘
         │                             │                          │
         ▼                             ▼                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        SNOWFLAKE AI DATA CLOUD                             │
│                                                                             │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │ CORTEX OCR  │  │  STRUCTURED  │  │ CORTEX AI    │  │ CORTEX        │  │
│  │ AI_PARSE_   │  │  TABLES      │  │ ANALYST      │  │ ANOMALY       │  │
│  │ DOCUMENT    │──│  Experiments │──│ Natural      │  │ DETECTION     │  │
│  │             │  │  Measurements│  │ Language SQL │  │ + HYPOTHESIS  │  │
│  └─────────────┘  └──────────────┘  └──────────────┘  └────────────────┘  │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    STREAMLIT INTERACTIVE APP                        │   │
│  │  📸 OCR Upload │ 📝 Data Entry │ 📊 Analysis │ 💬 Chat │ ⚠️ Anomaly│   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Capabilities

### 1. Lab Notebook Digitization (OCR)
- **Photograph** your handwritten notebook pages with a phone camera
- **Upload** to the platform (drag & drop)
- **Cortex AI** automatically reads handwritten text, tables, and scientific notation
- **AI extraction** converts OCR text into structured data (temperature, conductivity, mobility...)
- **One-click import** into the research database

**Technology:** Snowflake `AI_PARSE_DOCUMENT` (LAYOUT mode) + `AI_COMPLETE` for structured extraction

### 2. Digital Data Entry
- Web form for entering new measurements directly
- Linked to experiment metadata (substrate, cryostat, researcher)
- Input validation and scientific notation support
- Immediate availability for analysis

### 3. Interactive Analysis & Visualization
- **Conductivity vs Temperature** scatter plots (log-log) across substrates
- **Mobility comparison** box plots (He⁴ vs Ne vs H₂ vs D₂)
- **Time series** of any measurement variable
- **Cryostat monitoring** (helium level, vacuum pressure)
- **Trend analysis** with regression fits
- Filters by substrate, researcher, date range, experiment

### 4. Natural Language Data Queries ("Chat with Your Data")
- Ask questions in plain English: *"What was the average mobility for neon experiments last year?"*
- AI generates SQL, executes it, and provides physics-aware interpretation
- Full history of questions and answers
- See the generated SQL for transparency

**Technology:** Snowflake Cortex `AI_COMPLETE` with schema-aware SQL generation

### 5. Anomaly Detection & Hypothesis Generation
Three methods:
- **Statistical (Z-Score):** Flags data points >3σ from the mean
- **Physics-Based Rules:** Domain-specific checks (e.g., He4 mobility bounds, temperature jump limits, helium level thresholds)
- **AI-Powered:** LLM analyzes entire measurement series, identifies anomalies, generates physical hypotheses (substrate defects, cryostat malfunction, contamination), rates confidence, and recommends follow-up experiments

---

## Data Model

| Table | Purpose | Records |
|-------|---------|---------|
| `EXPERIMENTS` | Experiment metadata (substrate, cryostat, researcher, conditions) | 16 |
| `MEASUREMENTS` | Individual data points (T, σ, μ, n_e, E⊥, frequency, signal...) | ~5,000 |
| `OCR_EXTRACTS` | Raw OCR text from digitized notebook pages | growing |

**Substrates covered:** He⁴ (superfluid helium), Ne (solid neon), H₂ (solid hydrogen), D₂ (solid deuterium)

**Time span:** January 2024 – November 2025 (2 years of experiments)

---

## Why Snowflake?

| Feature | Benefit for Research |
|---------|---------------------|
| **Built-in AI (Cortex)** | OCR, natural language queries, anomaly detection — no separate ML infrastructure |
| **SQL + Python** | Familiar tools, no vendor lock-in |
| **Secure & governed** | RBAC, encryption, audit trail for research data compliance |
| **Elastic compute** | Scale up for heavy analysis, scale down when idle — pay per second |
| **Data sharing** | Securely share datasets with collaborators at other institutions |
| **Streamlit apps** | Build interactive dashboards directly on the data platform |
| **Time travel** | Recover accidentally modified data up to 90 days back |

---

## Future Roadmap

1. **Direct instrument integration** — Connect cryostat sensors (Lakeshore, Bluefors) via MQTT/API → Snowflake streaming
2. **Automated alerts** — Real-time anomaly detection during experiments (Snowflake Tasks + email/Slack)
3. **ML models** — Train predictive models for optimal film growth parameters (Snowflake ML)
4. **Publication figures** — Generate publication-quality plots directly from the platform
5. **Multi-lab collaboration** — Share data securely across research groups via Snowflake Data Sharing

---

## Demo Contents

- **3 sample lab notebook pages** (simulated handwritten) ready for OCR
- **16 experiments** across 4 substrate types
- **~5,000 measurement data points** with realistic physics
- **Injected anomalies** for detection demo (conductivity spikes, temperature excursions, mobility drops)
- **Semantic model** for natural language querying
- **Interactive Streamlit app** with 5 functional tabs

---

*Built on Snowflake AI Data Cloud. All data processing stays within the platform — no data movement, no external APIs, full governance.*
