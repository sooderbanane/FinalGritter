import os
import time
from datetime import datetime
import pandas as pd
from sklearn.ensemble import IsolationForest

# ─── CONFIG ────────────────────────────────────────────────────────────────────
DATA_DIR = 'sensor_data'                # where your raw sensor CSVs live
PUBLIC_DIR = 'public'                   # Next.js serves files here
COUNT_FILE = os.path.join(PUBLIC_DIR, 'minute_counts.csv')
ANOM_FILE  = os.path.join(PUBLIC_DIR, 'minute_anomalies.csv')
CHECK_INTERVAL = 10                     # seconds between checks
MIN_HISTORY = 5                         # minutes of history before detecting
# ────────────────────────────────────────────────────────────────────────────────

checked_mins = set()

while True:
    now = datetime.now()
    print(f"\n[+] Checking data at {now.isoformat(timespec='seconds')}")

    # 1) CSV laden 
    all_events = [] # holt sich alle csv eventes 
    for fname in os.listdir(DATA_DIR):
        if not fname.endswith('.csv'):
            continue
        path = os.path.join(DATA_DIR, fname)
        df = pd.read_csv(path, parse_dates=['timestamp'])

        # unnoetige falsche value muss weg
        if 'timestamp.1' in df.columns:
            df = df.drop(columns=['timestamp.1'])

        # schaut nach richtiger reihe 
        if 'contact' in df.columns:
            df = df[df['contact'] == True]
        elif 'action' in df.columns:
            df = df[df['action'] == 'single']
        else:
            continue

        df['sensor'] = fname
        all_events.append(df[['timestamp', 'sensor']])

    if not all_events:
        print("⚠️  No event files found—waiting...")
        time.sleep(CHECK_INTERVAL)
        continue

    events = pd.concat(all_events, ignore_index=True)
    events['min'] = events['timestamp'].dt.floor('min')  # damals 'T' wurde modern mit min ersetzt
    min_counts = (
        events.groupby('min').size().reset_index(name='request_count')
    )

    min_counts['is_anomaly'] = False  # placeholder
    min_counts.to_csv(COUNT_FILE, index=False)

    if len(min_counts) >= MIN_HISTORY:
        last_min = min_counts['min'].max()
        if last_min not in checked_mins and last_min < now.replace(second=0, microsecond=0):
            train = min_counts.iloc[:-1]
            test  = min_counts.iloc[-1:].copy()

            # iso forrest trainieren damit er auf unsere vorgaben entspricht 
            model = IsolationForest(contamination=0.05, random_state=42)
            model.fit(train[['request_count']])

            # predicte die letzte min (eig stunde aber besser fuer demo zwecke)
            test['is_anomaly'] = model.predict(test[['request_count']]) == -1

            # update durch ganze 
            min_counts.loc[min_counts['min'] == last_min, 'is_anomaly'] = test.at[test.index[0], 'is_anomaly']
            min_counts.to_csv(COUNT_FILE, index=False)

            # append anomalous minute to anomalies CSV if it truly is one
            if test.at[test.index[0], 'is_anomaly']:
                print(f"⚠️ ANOMALY at {last_min}: {test.at[test.index[0], 'request_count']} events")
                # mach einen saftigen header wenns keinen hat 
                write_header = not os.path.exists(ANOM_FILE)
                test[['min', 'request_count', 'is_anomaly']].to_csv(
                    ANOM_FILE,
                    mode='a', # a = append mode
                    header=write_header, # mach einen header 
                    index=False
                )
            else:
                print(f"✅ Normal at {last_min}: {test.at[test.index[0], 'request_count']} events")

            checked_mins.add(last_min)
        else:
            print(f"[+] Minute {min_counts['min'].max()} already checked or still in progress")
    else:
        print(f"ℹ️  Need {MIN_HISTORY - len(min_counts)} more minutes of data before anomaly detection")

    time.sleep(CHECK_INTERVAL)
