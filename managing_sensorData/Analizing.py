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

    # 1) Load & filter all sensor CSVs
    all_events = []
    for fname in os.listdir(DATA_DIR):
        if not fname.endswith('.csv'):
            continue
        path = os.path.join(DATA_DIR, fname)
        df = pd.read_csv(path, parse_dates=['timestamp'])

        # drop duplicate timestamp column if present
        if 'timestamp.1' in df.columns:
            df = df.drop(columns=['timestamp.1'])

        # filter rows: only door-open events or button-press events
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

    # 2) Concatenate and group by minute
    events = pd.concat(all_events, ignore_index=True)
    events['min'] = events['timestamp'].dt.floor('T')  # 'T' = minute
    min_counts = (
        events
        .groupby('min')
        .size()
        .reset_index(name='request_count')
    )

    # 3) Save the full minute_counts.csv (overwrites every run)
    min_counts['is_anomaly'] = False  # placeholder
    min_counts.to_csv(COUNT_FILE, index=False)

    # 4) Detect anomalies once we have enough history
    if len(min_counts) >= MIN_HISTORY:
        last_min = min_counts['min'].max()
        if last_min not in checked_mins and last_min < now.replace(second=0, microsecond=0):
            train = min_counts.iloc[:-1]
            test  = min_counts.iloc[-1:].copy()

            # train Isolation Forest
            model = IsolationForest(contamination=0.05, random_state=42)
            model.fit(train[['request_count']])

            # predict the last minute
            test['is_anomaly'] = model.predict(test[['request_count']]) == -1

            # update the full counts CSV with anomaly flag
            min_counts.loc[min_counts['min'] == last_min, 'is_anomaly'] = test.at[test.index[0], 'is_anomaly']
            min_counts.to_csv(COUNT_FILE, index=False)

            # append anomalous minute to anomalies CSV if it truly is one
            if test.at[test.index[0], 'is_anomaly']:
                print(f"⚠️ ANOMALY at {last_min}: {test.at[test.index[0], 'request_count']} events")
                # write header only if file doesn't exist
                write_header = not os.path.exists(ANOM_FILE)
                test[['min', 'request_count', 'is_anomaly']].to_csv(
                    ANOM_FILE,
                    mode='a',
                    header=write_header,
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
