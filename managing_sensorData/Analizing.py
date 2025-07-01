import os
import sys
import time
from datetime import datetime
import pandas as pd
from sklearn.ensemble import IsolationForest

# ─── CONFIG ────────────────────────────────────────────────────────────────────
TRAIN_FILE = os.path.join(os.path.dirname(__file__), '..', 'simData', 'minute_counts_test.csv')

# Pfad zur synthetischen CSV (anpassen basierend auf diesem Skript-Standort):

DATA_DIR       = os.path.join(os.path.dirname(__file__), '..', 'sensor_data')  # wo die Rohdaten liegen
# Next.js public-Ordner im Frontend-Projekt:
PUBLIC_DIR     = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'gritter-frontend', 'public')
COUNT_FILE     = os.path.join(PUBLIC_DIR, 'minute_counts.csv')
ANOM_FILE      = os.path.join(PUBLIC_DIR, 'minute_anomalies.csv')
LOG_FILE = os.path.join(PUBLIC_DIR, 'anom.csv')

CHECK_INTERVAL = 10  # Sekunden zwischen den Überprüfungen
MIN_HISTORY    = 5   # benötigte Minuten Historie vor dem Erkennen von Anomalien
# ────────────────────────────────────────────────────────────────────────────────


# Ausgabeordner sicherstellen
os.makedirs(PUBLIC_DIR, exist_ok=True)

# Initialisiere Minuten-Log
if not os.path.exists(LOG_FILE):
    pd.DataFrame(columns=['min', 'request_count', 'is_anomaly']).to_csv(LOG_FILE, index=False)

# Sicherstellen, dass die Trainingsdatei existiert
if not os.path.exists(TRAIN_FILE):
    print(f"❌ Trainingsdatei nicht gefunden: {TRAIN_FILE}")
    sys.exit(1)

# ── WARM-UP TRAINING (nur einmal) ────────────────────────────────────────────
# Trainiere IsolationForest auf synthetischen Daten
# >>> Änderung: Warm-up Training auf Testdaten <<<
df_train = pd.read_csv(TRAIN_FILE, parse_dates=['min'])
model    = IsolationForest(contamination=0.05, random_state=42)
model.fit(df_train[['request_count']])
print(f"✅ Warm-up Training abgeschlossen mit {len(df_train)} Test-Minuten")
# ────────────────────────────────────────────────────────────────────────────────

# Verfolgung bereits verarbeiteter Minuten
processed_mins = set()
# Zeitpunkt des Skriptstarts, um alte Daten zu ignorieren
script_start   = datetime.now().replace(second=0, microsecond=0)

while True:
    now = datetime.now()
    print(f"\n[+] Überprüfung um {now.isoformat(timespec='seconds')} (seit {script_start})")

    # ── 1) CSVs laden und filtern ──────────────────────────────────────────────
    all_events = []  # holt sich alle CSV-Events
    for fname in os.listdir(DATA_DIR):
        if not fname.endswith('.csv'):
            continue
        path = os.path.join(DATA_DIR, fname)
        df   = pd.read_csv(path, parse_dates=['timestamp'])

        # Entferne doppelte Zeitstempel-Spalte
        if 'timestamp.1' in df.columns:
            df = df.drop(columns=['timestamp.1'])

        # Filter: Türkontakte oder einzelne Button-Presses
        if 'contact' in df.columns:
            df = df[df['contact'] == True]  # nur True behalten
        elif 'action' in df.columns:
            df = df[df['action'] == 'single']  # nur "single" behalten
        else:
            continue

        df['sensor'] = fname  # Sensor-Dateiname taggen
        all_events.append(df[['timestamp', 'sensor']])

    # Wenn keine Events gefunden, warte
    if not all_events:
        print("⚠️ Keine Live-Events gefunden—warte...")
        time.sleep(CHECK_INTERVAL)
        continue

    # ── 2) Events zu DataFrame zusammenführen ─────────────────────────────────
    events = pd.concat(all_events, ignore_index=True)
    # >>> Änderung: Alte Events ausfiltern <<<
    events = events[events['timestamp'] >= script_start]
    events['min'] = events['timestamp'].dt.floor('min')  # auf Minute abrunden
    # nach Minute gruppieren und zählen
    min_counts = (
        events.groupby('min')
              .size()
              .reset_index(name='request_count')
    )
    # >>> Änderung: Alte Minuten ausfiltern <<<
    min_counts = min_counts[min_counts['min'] >= script_start]

    # Platzhalter-Flag für Anomalien, später wiederherstellen
    min_counts['is_anomaly'] = False
    if os.path.exists(ANOM_FILE):  # wiederherstellen historischer Flags
        prev = pd.read_csv(ANOM_FILE, parse_dates=['min'])
        min_counts = min_counts.merge(prev[['min','is_anomaly']], on='min', how='left', suffixes=('','_prev'))
        min_counts['is_anomaly'] = min_counts['is_anomaly_prev'].fillna(min_counts['is_anomaly'])
        min_counts.drop(columns=['is_anomaly_prev'], inplace=True)

    # ── 3) Schreibe volle Zeitreihe für Frontend ──────────────────────────────
    min_counts.to_csv(COUNT_FILE, index=False)

    # ── 4) Anomalieerkennung für letzte Minute ────────────────────────────────
    if len(min_counts) >= MIN_HISTORY:
        last_min = min_counts['min'].max()
        if last_min not in processed_mins and last_min < now.replace(second=0, microsecond=0):
            test = min_counts[min_counts['min'] == last_min].copy()  # nur letzte Minute

            # >>> Änderung: Alte Anomalien vom Training ausschließen <<<
            live_train = min_counts[min_counts['is_anomaly'] == False].iloc[:-1]
            model.fit(live_train[['request_count']])  # adaptives Nachtrainieren
            test['is_anomaly'] = model.predict(test[['request_count']]) == -1

            # >>> Änderung: Pro Minute protokollieren <<<
            test[['min','request_count','is_anomaly']].to_csv(LOG_FILE, mode='a', header=False, index=False)

            # Update Flags in Vollserie
            is_anom = test['is_anomaly'].iat[0]
            min_counts.loc[min_counts['min'] == last_min, 'is_anomaly'] = is_anom
            min_counts.to_csv(COUNT_FILE, index=False)

            # Nur echte Anomalien in eigene Datei
            if is_anom:
                print(f"⚠️ ANOMALIE um {last_min}: {test['request_count'].iat[0]} Events")
                write_header = not os.path.exists(ANOM_FILE)
                test[['min','request_count','is_anomaly']].to_csv(
                    ANOM_FILE, mode='a', header=write_header, index=False
                )
            else:
                print(f"✅ Normal um {last_min}: {test['request_count'].iat[0]} Events")

            processed_mins.add(last_min)
        else:
            print(f"[+] Minute {last_min} bereits verarbeitet oder noch nicht komplett")
    else:
        needed = MIN_HISTORY - len(min_counts)
        print(f"ℹ️ Brauche noch {needed} Minuten für Anomalieerkennung")

    # Warte bis nächster Check
    time.sleep(CHECK_INTERVAL)
