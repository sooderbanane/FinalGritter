import os
import sys
import time
from datetime import datetime
import pandas as pd
from sklearn.ensemble import IsolationForest

# ─── CONFIG ────────────────────────────────────────────────────────────────────
USE_TEST       = True  # toggle test mode on/off (wenn True, lade die Testdaten)
# Pfad zur synthetischen CSV (anpassen basierend auf diesem Skript-Standort):
TEST_FILE = os.path.join(os.path.dirname(__file__), '..', 'simData', 'minute_counts_test.csv')  # sicherstellen, dass diese Datei existiert

DATA_DIR       = os.path.join(os.path.dirname(__file__), '..', 'sensor_data')  # wo die Rohdaten liegen
# Next.js public-Ordner im Frontend-Projekt:
PUBLIC_DIR     = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'gritter-frontend', 'public')
COUNT_FILE     = os.path.join(PUBLIC_DIR, 'minute_counts.csv')
ANOM_FILE      = os.path.join(PUBLIC_DIR, 'minute_anomalies.csv')
CHECK_INTERVAL = 10  # Sekunden zwischen den Überprüfungen
MIN_HISTORY    = 5   # benötigte Minuten Historie vor dem Erkennen von Anomalien
# ────────────────────────────────────────────────────────────────────────────────

# Stelle sicher, dass der Ausgabeordner existiert
os.makedirs(PUBLIC_DIR, exist_ok=True)

# Verifiziere, dass die Testdatei existiert, wenn USE_TEST aktiviert ist
if USE_TEST and not os.path.exists(TEST_FILE):
    print(f"❌ Test file not found: {TEST_FILE}")
    sys.exit(1)

processed_mins = set()  # verfolgt, welche Minuten bereits verarbeitet wurden

while True:
    now = datetime.now()
    print(f"\n[+] Checking data at {now.isoformat(timespec='seconds')}")

    # ── 1) Vorbereitung der minute_counts ───────────────────────────────────
    if USE_TEST:
        # Lade vorkomputierte synthetische Daten für Tests
        # TEST_FILE muss die Spalten: min, request_count, is_anomaly enthalten
        min_counts = pd.read_csv(TEST_FILE, parse_dates=['min'])
    else:
        #  CSV laden und filtern
        all_events = []  # holt sich alle csv events
        for fname in os.listdir(DATA_DIR):
            if not fname.endswith('.csv'):
                continue
            path = os.path.join(DATA_DIR, fname)
            df = pd.read_csv(path, parse_dates=['timestamp'])

            # unnötige falsche Spalte entfernen
            if 'timestamp.1' in df.columns:
                df = df.drop(columns=['timestamp.1'])

            # Filter: Tür-Öffnungen oder einzelne Button-Presses
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
            print("⚠️ No event files found—waiting...")
            time.sleep(CHECK_INTERVAL)
            continue

        # Alle Events zu einem DataFrame zusammenfassen
        events = pd.concat(all_events, ignore_index=True)
        events['min'] = events['timestamp'].dt.floor('min')  # auf Minute abrunden
        # nach Minute gruppieren und zählen
        min_counts = (
            events.groupby('min')
                  .size()
                  .reset_index(name='request_count')
        )
        min_counts['is_anomaly'] = False  # Platzhalter: noch kein Anomalie-Flag gesetzt

    # ── 2) Schreibe die Vollserie für das Frontend ─────────────────────────
    min_counts.to_csv(COUNT_FILE, index=False)  # überschreibe minute_counts.csv

    # ── 3) Erkenne Anomalien in der letzten Minute ─────────────────────────
    if len(min_counts) >= MIN_HISTORY:
        last_min = min_counts['min'].max()
        # nur einmal pro Minute und nur, wenn die Minute vorbei ist
        if last_min not in processed_mins and last_min < now.replace(second=0, microsecond=0):
            train = min_counts.iloc[:-1]         # alle bis auf die letzte Minute
            test  = min_counts.iloc[-1:].copy()  # nur die letzte Minute

            # IsolationForest trainieren
            model = IsolationForest(contamination=0.05, random_state=42)
            model.fit(train[['request_count']])

            # Anomalie-Vorhersage für die letzte Minute
            test['is_anomaly'] = model.predict(test[['request_count']]) == -1

            # Vollserie updaten mit dem Flag
            is_anom = test.at[test.index[0], 'is_anomaly']
            min_counts.loc[min_counts['min'] == last_min, 'is_anomaly'] = is_anom
            min_counts.to_csv(COUNT_FILE, index=False)

            # falls Anomalie, in separate Datei anhängen
            if is_anom:
                print(f"⚠️ ANOMALY at {last_min}: {test.at[test.index[0], 'request_count']} events")
                write_header = not os.path.exists(ANOM_FILE)  # nur einmal Header schreiben
                test[['min','request_count','is_anomaly']].to_csv(
                    ANOM_FILE,
                    mode='a',
                    header=write_header,
                    index=False
                )
            else:
                print(f"✅ Normal at {last_min}: {test.at[test.index[0], 'request_count']} events")

            processed_mins.add(last_min)
        else:
            print(f"[+] Minute {last_min} already processed or not complete")
    else:
        needed = MIN_HISTORY - len(min_counts)
        print(f"ℹ️ Need {needed} more minutes before detecting anomalies")

    # Sleep bis zum nächsten Check
    time.sleep(CHECK_INTERVAL)
