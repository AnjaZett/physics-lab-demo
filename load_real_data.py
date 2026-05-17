import os
import numpy as np
import snowflake.connector
from datetime import datetime, timedelta

conn = snowflake.connector.connect(
    connection_name=os.getenv("SNOWFLAKE_CONNECTION_NAME") or "IL16585"
)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS CRYOLAB.ARGON_FILM.INTENSITY_MEASUREMENTS (
    MEASUREMENT_ID INT AUTOINCREMENT PRIMARY KEY,
    EXPERIMENT_ID VARCHAR(20) NOT NULL,
    TIMESTAMP TIMESTAMP_NTZ NOT NULL,
    TIME_MIN FLOAT NOT NULL,
    REFLECTED_INTENSITY FLOAT,
    TEMPERATURE_K FLOAT,
    NOTES VARCHAR(500),
    CREATED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
)
""")

cur.execute("""
INSERT INTO CRYOLAB.ARGON_FILM.EXPERIMENTS
(EXPERIMENT_ID, EXPERIMENT_DATE, DESCRIPTION, TARGET_TEMP_MIN_K, TARGET_TEMP_MAX_K,
 SUBSTRATE_MATERIAL, MEASUREMENT_METHOD, NOTES)
VALUES ('ARG-REAL-001', '2025-07-27',
 'Real measurement: Reflected intensity and temperature during Ar film growth/desorption cycle',
 65.0, 80.0, 'Gold', 'Surface Plasmon Spectroscopy',
 'Digitized from oscilloscope recording 27.07.2025 16:10-16:52. Points 1-5 and A-E marked. Two panels: 0-26 min and 34-44 min.')
""")

# Digitized data from the diagram (Slide 10, high-res image)
# Left panel: t=0..26 min, Right panel: t=34..44 min
# Blue line = reflected intensity (left Y: 0..1.0 arb.u.)
# Magenta line = temperature (right Y: 65..80 K, inverted: top=65, bottom=80)
#
# Key features visible in the diagram:
# Point 1 (t~2min): intensity peak ~0.88, T~65K (stable)
# Point 2 (t~5min): intensity starts to plateau ~0.85, T~65K
# Point A (t~5min): T starts dropping rapidly from 65K toward 80K
# Between A and B: T drops from ~65 to ~80K, intensity slowly decreases from ~0.85 to ~0.65
# Point B (t~12min): T at ~80K (bottom), intensity ~0.65
# Point 3 (t~16min): intensity at ~0.08, T still ~80K then jumps up
# Point C (t~17min): T jumps up sharply from ~80K to ~65K, intensity ~0.9
# Point 4 (t~17.5min): intensity ~0.48
# Point D (t~22min): intensity ~0.50, T~70K
# Point E (t~25min): intensity ~0.15, T~78K
# Right panel (t=34..44):
# Point 5 (t~38min): intensity ~0.30, T jumps from ~78K to ~65K
# Then intensity drops to ~0.15, T ~78K

# Careful point-by-point digitization from the graph
# Time(min), Intensity(arb.u.), Temperature(K)
data_points = [
    # Left panel: initial state and cooling
    (0.0, 0.55, 65.0),
    (0.5, 0.70, 65.0),
    (1.0, 0.82, 65.0),
    (1.5, 0.87, 65.0),   # near point 1
    (2.0, 0.88, 65.0),   # point 1 - intensity peak
    (2.5, 0.87, 65.0),
    (3.0, 0.86, 65.0),
    (3.5, 0.85, 65.0),
    (4.0, 0.85, 65.0),
    (4.5, 0.85, 65.0),
    (5.0, 0.85, 65.0),   # point 2
    # Point A: temperature starts to drop (cool down = T rises from 65 to 80K)
    (5.5, 0.84, 66.0),   # point A area
    (6.0, 0.82, 68.0),
    (6.5, 0.80, 70.0),
    (7.0, 0.78, 72.0),
    (7.5, 0.76, 74.0),
    (8.0, 0.74, 75.5),
    (8.5, 0.72, 77.0),
    (9.0, 0.70, 78.0),
    (9.5, 0.68, 79.0),
    (10.0, 0.66, 79.5),
    (10.5, 0.64, 80.0),  # T near bottom
    (11.0, 0.62, 80.0),
    (11.5, 0.60, 80.0),
    (12.0, 0.58, 80.0),  # near point B
    (12.5, 0.55, 80.0),
    (13.0, 0.50, 80.0),
    (13.5, 0.45, 80.0),
    (14.0, 0.35, 80.0),
    (14.5, 0.25, 80.0),
    (15.0, 0.15, 80.0),
    (15.5, 0.10, 80.0),
    (16.0, 0.08, 80.0),  # point 3 area - intensity minimum
    # Rapid warm-up: T jumps from 80K back toward 65K
    (16.2, 0.07, 79.0),
    (16.4, 0.06, 77.0),
    (16.6, 0.05, 74.0),
    (16.8, 0.10, 70.0),
    (17.0, 0.50, 66.0),  # point C area - T shoots up, intensity rises
    (17.2, 0.80, 65.5),
    (17.5, 0.90, 65.0),  # point C peak
    (18.0, 0.88, 65.0),  # point 4 area
    (18.5, 0.70, 66.0),
    (19.0, 0.62, 67.0),
    (19.5, 0.58, 68.0),
    (20.0, 0.55, 69.0),
    (20.5, 0.53, 69.5),  # point D area
    (21.0, 0.52, 70.0),
    (21.5, 0.50, 70.0),
    (22.0, 0.50, 70.0),  # point D
    (22.5, 0.48, 71.0),
    (23.0, 0.45, 73.0),
    (23.5, 0.40, 74.5),
    (24.0, 0.35, 76.0),  # approaching E
    (24.5, 0.25, 77.5),
    (25.0, 0.18, 78.0),  # point E
    (25.5, 0.15, 78.5),
    (26.0, 0.12, 79.0),

    # Right panel (gap from 26 to 34 min — no data visible)
    (34.0, 0.30, 78.0),
    (34.5, 0.28, 78.0),
    (35.0, 0.25, 78.0),
    (35.5, 0.23, 78.0),
    (36.0, 0.22, 78.0),
    (36.5, 0.20, 77.5),
    (37.0, 0.20, 76.0),
    (37.5, 0.22, 73.0),
    (38.0, 0.30, 68.0),  # point 5 area - T jumps up
    (38.2, 0.35, 66.0),
    (38.5, 0.88, 65.0),  # point 5 - brief peak
    (39.0, 0.85, 65.5),
    (39.5, 0.30, 70.0),
    (40.0, 0.22, 75.0),
    (40.5, 0.18, 77.0),
    (41.0, 0.16, 78.0),
    (41.5, 0.15, 78.5),
    (42.0, 0.14, 79.0),
    (42.5, 0.13, 79.0),
    (43.0, 0.12, 79.0),
    (44.0, 0.12, 79.0),
]

base_time = datetime(2025, 7, 27, 16, 10, 0)

notes_map = {
    2.0: "Point 1: intensity peak during initial Ar condensation",
    5.0: "Point 2: steady state before cooldown; Point A: T ramp starts",
    12.0: "Point B: T reached ~80K, film thickening continues",
    16.0: "Point 3: intensity minimum, thick Ar film",
    17.5: "Point C: rapid warm-up, Ar desorption, intensity peak",
    18.0: "Point 4: post-desorption",
    22.0: "Point D: slow re-cooling, partial film regrowth",
    25.0: "Point E: T dropping again, film thickening",
    38.5: "Point 5: second warm-up cycle, brief intensity peak",
}

values_list = []
for t_min, intensity, temp_k in data_points:
    ts = base_time + timedelta(minutes=t_min)
    note = notes_map.get(t_min, None)
    note_sql = f"'{note}'" if note else "NULL"
    values_list.append(
        f"('ARG-REAL-001', '{ts.strftime('%Y-%m-%d %H:%M:%S')}', {t_min}, {intensity}, {temp_k}, {note_sql})"
    )

sql = f"""
    INSERT INTO CRYOLAB.ARGON_FILM.INTENSITY_MEASUREMENTS
    (EXPERIMENT_ID, TIMESTAMP, TIME_MIN, REFLECTED_INTENSITY, TEMPERATURE_K, NOTES)
    VALUES {', '.join(values_list)}
"""
cur.execute(sql)

cur.execute("SELECT COUNT(*) FROM CRYOLAB.ARGON_FILM.INTENSITY_MEASUREMENTS")
count = cur.fetchone()[0]
print(f"Inserted {count} digitized data points")

cur.execute("""
    SELECT ROUND(MIN(TIME_MIN),1) as t_min, ROUND(MAX(TIME_MIN),1) as t_max,
           ROUND(MIN(REFLECTED_INTENSITY),2) as I_min, ROUND(MAX(REFLECTED_INTENSITY),2) as I_max,
           ROUND(MIN(TEMPERATURE_K),1) as T_min, ROUND(MAX(TEMPERATURE_K),1) as T_max
    FROM CRYOLAB.ARGON_FILM.INTENSITY_MEASUREMENTS
""")
row = cur.fetchone()
print(f"Time: {row[0]}-{row[1]} min | Intensity: {row[2]}-{row[3]} arb.u. | Temp: {row[4]}-{row[5]} K")

cur.close()
conn.close()
