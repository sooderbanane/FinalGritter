import os
import sys
import time
from datetime import datetime
import pandas as pd

# ─── CONFIG ────────────────────────────────────────────────────────────────────
# Pfad zur synthetischen CSV (muss Spalten 'min' und 'request_count' enthalten)
TRAIN_FILE   = os.path.join(os.path.dirname(__file__), '..', 'simData', 'minute_counts_test.csv')
# Verzeichnis mit Rohdaten (Zigbee2MQTT CSVs)
DATA_DIR     = os.path.join(os.path.dirname(__file__), '..', 'sensor_data')
# Next.js public-Ordner für Ausgabe
PUBLIC_DIR   = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'gritter-frontend', 'public')
COUNT_FILE   = os.path.join(PUBLIC_DIR, 'minute_counts.csv')       # gesamte Zeitreihe
ANOM_FILE    = os.path.join(PUBLIC_DIR, 'minute_anomalies.csv')    # nur Anomalien
LOG_FILE     = os.path.join(PUBLIC_DIR, 'anom.csv')               # Pro-Minute-Log

CHECK_INTERVAL = 10  # Sekunden zwischen Schleifendurchläufen
# Multiplikator für Threshold (mean + thresh_mul * std)
thresh_mul     = 2.0  # anpassen nach Bedarf
# ────────────────────────────────────────────────────────────────────────────────

os.makedirs(PUBLIC_DIR, exist_ok=True)

# Initialisiere Log, falls nötig
if not os.path.exists(LOG_FILE):
    pd.DataFrame(columns=['min', 'request_count', 'is_anomaly']).to_csv(LOG_FILE, index=False)

# Sicherstellen, dass die Trainingsdatei existiert
if not os.path.exists(TRAIN_FILE):
    print(f"❌ Trainingsdatei nicht gefunden: {TRAIN_FILE}")
    sys.exit(1)

# ── WARM-UP DATEN LADEN (einmalig) ─────────────────────────────────────────────
df_train    = pd.read_csv(TRAIN_FILE, parse_dates=['min'])
mean_train  = df_train['request_count'].mean()
std_train   = df_train['request_count'].std()
threshold   = mean_train + thresh_mul * std_train
print(f"✅ Trainingsdaten geladen: mean={mean_train:.1f}, std={std_train:.1f}, mul={thresh_mul:.1f}, threshold={threshold:.1f}")
# ────────────────────────────────────────────────────────────────────────────────

processed_mins = set()
script_start   = datetime.now().replace(second=0, microsecond=0)

while True:
    now = datetime.now()
    print(f"\n[+] Überprüfung um {now.isoformat(timespec='seconds')} (seit {script_start})")

    # 1) CSVs laden und filtern
    all_events = []
    for fname in os.listdir(DATA_DIR):
        if not fname.endswith('.csv'):
            continue
        path = os.path.join(DATA_DIR, fname)
        df   = pd.read_csv(path, parse_dates=['timestamp'])
        if 'timestamp.1' in df.columns:
            df = df.drop(columns=['timestamp.1'])
        if 'contact' in df.columns:
            df = df[df['contact'] == True]
        elif 'action' in df.columns:
            df = df[df['action'] == 'single']
        else:
            continue
        df['sensor'] = fname
        all_events.append(df[['timestamp', 'sensor']])

    if not all_events:
        print("⚠️ Keine Live-Events gefunden — warte...")
        time.sleep(CHECK_INTERVAL)
        continue

    # 2) Zusammenfassen und Gruppieren nach Minute
    events = pd.concat(all_events, ignore_index=True)
    events = events[events['timestamp'] >= script_start]
    events['min'] = events['timestamp'].dt.floor('min')
    min_counts = (
        events.groupby('min')
              .size()
              .reset_index(name='request_count')
    )
    min_counts = min_counts[min_counts['min'] >= script_start]

    # Restore previous anomaly flags
    min_counts['is_anomaly'] = False
    if os.path.exists(ANOM_FILE):
        prev = pd.read_csv(ANOM_FILE, parse_dates=['min'])
        min_counts = min_counts.merge(prev[['min','is_anomaly']], on='min', how='left', suffixes=('','_prev'))
        min_counts['is_anomaly'] = min_counts['is_anomaly_prev'].fillna(min_counts['is_anomaly']).astype(bool)
        min_counts.drop(columns=['is_anomaly_prev'], inplace=True)

    # 3) Vollserie für das Frontend schreiben
    min_counts.to_csv(COUNT_FILE, index=False)

    # 4) Threshold-Erkennung für die letzte Minute
    last_min = min_counts['min'].max()
    if last_min not in processed_mins and last_min < now.replace(second=0, microsecond=0):
        cnt = min_counts.loc[min_counts['min'] == last_min, 'request_count'].iat[0]
        print(f"DEBUG: threshold={threshold:.1f}, count={cnt}")
        is_anom = cnt >= threshold

        # Log
        pd.DataFrame([{'min': last_min, 'request_count': cnt, 'is_anomaly': is_anom}]) \
            .to_csv(LOG_FILE, mode='a', header=False, index=False)

        # Update full series
        min_counts.loc[min_counts['min'] == last_min, 'is_anomaly'] = is_anom
        min_counts.to_csv(COUNT_FILE, index=False)

        if is_anom:
            print(f"⚠️ ANOMALIE um {last_min}: {cnt} Events > {threshold:.1f}")
            write_header = not os.path.exists(ANOM_FILE)
            pd.DataFrame([{'min': last_min, 'request_count': cnt, 'is_anomaly': True}]) \
                .to_csv(ANOM_FILE, mode='a', header=write_header, index=False)
        else:
            print(f"✅ Normal um {last_min}: {cnt} Events")

        processed_mins.add(last_min)
    else:
        print(f"[+] Minute {last_min} bereits verarbeitet oder noch nicht komplett")

    time.sleep(CHECK_INTERVAL)
