import os
import numpy as np
import snowflake.connector
from datetime import datetime, timedelta

conn = snowflake.connector.connect(
    connection_name=os.getenv("SNOWFLAKE_CONNECTION_NAME") or "IL16585"
)
cur = conn.cursor()

np.random.seed(42)

experiments = [
    ("ARG-2025-001", "2025-01-15 09:00:00", 65.0, 72.0, 200, 600, 1.0),
    ("ARG-2025-002", "2025-02-03 10:00:00", 66.0, 74.0, 400, 900, 1.0),
    ("ARG-2025-003", "2025-03-12 08:30:00", 65.0, 77.0, 250, 800, 1.0),
    ("ARG-2025-004", "2025-04-08 14:00:00", 66.0, 70.0, 300, 700, 1.0),
    ("ARG-2025-005", "2025-05-20 09:00:00", 65.0, 73.0, 250, 650, 0.85),
    ("ARG-2025-006", "2025-06-14 07:00:00", 67.0, 69.0, 450, 550, 1.0),
    ("ARG-2025-007", "2025-08-02 11:00:00", 67.0, 75.0, 200, 1000, 1.0),
    ("ARG-2025-008", "2025-09-18 13:00:00", 65.0, 77.0, 300, 900, 1.0),
    ("ARG-2025-009", "2025-10-30 09:30:00", 65.0, 72.0, 200, 600, 1.0),
    ("ARG-2025-010", "2025-12-05 08:00:00", 65.0, 77.0, 200, 1000, 1.0),
]

def argon_film_thickness(T, P, substrate_factor=1.0):
    T_ref = 70.0
    P_ref = 500.0
    d_ref = 50.0
    temp_effect = np.exp(-0.15 * (T - T_ref))
    pressure_effect = (P / P_ref) ** 0.7
    thickness = d_ref * temp_effect * pressure_effect * substrate_factor
    return thickness

all_rows = []

for exp_id, start_str, t_min, t_max, p_min, p_max, sub_factor in experiments:
    start_time = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
    n_points = 100

    if exp_id == "ARG-2025-006":
        temps = 68.0 + np.random.normal(0, 0.15, n_points)
        pressures = 500 + np.random.normal(0, 10, n_points)
    elif exp_id == "ARG-2025-008":
        temps = np.linspace(t_max, t_min, n_points)
        pressures = p_max - (p_max - p_min) * ((t_max - temps) / (t_max - t_min)) ** 0.8
    elif exp_id == "ARG-2025-004":
        temps = np.linspace(t_min, t_max, n_points)
        pressures = p_min + (p_max - p_min) * ((temps - t_min) / (t_max - t_min))
    else:
        temps = np.linspace(t_min, t_max, n_points)
        pressures = p_min + (p_max - p_min) * ((temps - t_min) / (t_max - t_min)) ** 1.2

    temps += np.random.normal(0, 0.05, n_points)
    pressures += np.random.normal(0, 2.0, n_points)
    pressures = np.clip(pressures, 50, 1200)

    thicknesses = argon_film_thickness(temps, pressures, sub_factor)
    thicknesses += np.random.normal(0, 0.5, n_points)
    thicknesses = np.clip(thicknesses, 0.5, 500)

    anomaly_indices = set()
    notes_map = {}

    if exp_id == "ARG-2025-003":
        for idx in [23, 24, 25]:
            anomaly_indices.add(idx)
            thicknesses[idx] *= 2.5
            notes_map[idx] = "ANOMALY: sudden thickness spike, possible condensation burst"

    if exp_id == "ARG-2025-007":
        for idx in [67, 68, 69, 70]:
            anomaly_indices.add(idx)
            thicknesses[idx] *= 0.1
            notes_map[idx] = "ANOMALY: thickness drop to near-zero, possible film delamination"

    if exp_id == "ARG-2025-010":
        for idx in [45, 46]:
            anomaly_indices.add(idx)
            temps[idx] += 5.0
            notes_map[idx] = "ANOMALY: temperature excursion, heater malfunction suspected"
        for idx in [80, 81, 82]:
            anomaly_indices.add(idx)
            pressures[idx] *= 1.8
            thicknesses[idx] = argon_film_thickness(temps[idx], pressures[idx], sub_factor) * 1.5
            notes_map[idx] = "ANOMALY: pressure spike, possible leak"

    for i in range(n_points):
        ts = start_time + timedelta(minutes=i * 5)
        is_anomaly = i in anomaly_indices
        note = notes_map.get(i, None)
        all_rows.append((
            exp_id,
            ts.strftime("%Y-%m-%d %H:%M:%S"),
            round(float(temps[i]), 3),
            round(float(pressures[i]), 1),
            round(float(thicknesses[i]), 2),
            note,
            is_anomaly,
        ))

batch_size = 100
for start in range(0, len(all_rows), batch_size):
    batch = all_rows[start:start + batch_size]
    values_list = []
    for row in batch:
        exp_id, ts, temp, pres, thick, note, is_anom = row
        note_sql = f"'{note}'" if note else "NULL"
        values_list.append(
            f"('{exp_id}', '{ts}', {temp}, {pres}, {thick}, {note_sql}, {is_anom})"
        )
    sql = f"""
        INSERT INTO CRYOLAB.ARGON_FILM.MEASUREMENTS
        (EXPERIMENT_ID, TIMESTAMP, TEMPERATURE_K, PRESSURE_MBAR, FILM_THICKNESS_NM, NOTES, IS_ANOMALY)
        VALUES {', '.join(values_list)}
    """
    cur.execute(sql)

cur.execute("SELECT COUNT(*) FROM CRYOLAB.ARGON_FILM.MEASUREMENTS")
count = cur.fetchone()[0]
print(f"Inserted {count} measurements across 10 experiments")

cur.execute("""
    SELECT EXPERIMENT_ID, COUNT(*) as cnt, 
           ROUND(MIN(TEMPERATURE_K),1) as t_min, ROUND(MAX(TEMPERATURE_K),1) as t_max,
           ROUND(MIN(PRESSURE_MBAR),0) as p_min, ROUND(MAX(PRESSURE_MBAR),0) as p_max,
           ROUND(MIN(FILM_THICKNESS_NM),1) as d_min, ROUND(MAX(FILM_THICKNESS_NM),1) as d_max,
           SUM(CASE WHEN IS_ANOMALY THEN 1 ELSE 0 END) as anomalies
    FROM CRYOLAB.ARGON_FILM.MEASUREMENTS 
    GROUP BY EXPERIMENT_ID ORDER BY EXPERIMENT_ID
""")
print("\nExperiment Summary:")
print(f"{'Experiment':<16} {'N':>4} {'T_min':>6} {'T_max':>6} {'P_min':>6} {'P_max':>6} {'d_min':>6} {'d_max':>7} {'Anom':>5}")
for row in cur.fetchall():
    print(f"{row[0]:<16} {row[1]:>4} {row[2]:>6.1f} {row[3]:>6.1f} {row[4]:>6.0f} {row[5]:>6.0f} {row[6]:>6.1f} {row[7]:>7.1f} {row[8]:>5}")

cur.close()
conn.close()
