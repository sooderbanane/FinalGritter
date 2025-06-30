import os
import time
from datetime import datetime
import pandas as pd
from sklearn.ensemble import IsolationForest

# ─── CONFIG ────────────────────────────────────────────────────────────────────
USE_TEST       = True                        # ← toggle test mode on/off
TEST_FILE      = './training.csv'             # ← synthetic CSV you downloaded (ensure this path is correct)

DATA_DIR       = './sensor_data'             # where your raw sensor CSVs live (ensure folder exists)
PUBLIC_DIR     = '../frontend/gritter-frontend/public'  # Next.js static folder (ensure path from here)
COUNT_FILE     = os.path.join(PUBLIC_DIR, 'minute_counts.csv')
ANOM_FILE      = os.path.join(PUBLIC_DIR, 'minute_anomalies.csv')
CHECK_INTERVAL = 10                          # seconds between each loop iteration
MIN_HISTORY    = 5                           # number of minutes before anomaly detection starts
# ────────────────────────────────────────────────────────────────────────────────

# Ensure the output directory exists before writing
os.makedirs(PUBLIC_DIR, exist_ok=True)

# Keep track of which minutes have already been processed
generated_mins = set()

while True:
    now = datetime.now()
    print(f"\n[+] Checking data at {now.isoformat(timespec='seconds')}")

    # ── 1) Prepare minute_counts: load test CSV or aggregate raw data ────────
    if USE_TEST:
        # Load precomputed synthetic test data
        # TEST_FILE must contain columns: min, request_count, is_anomaly
        min_counts = pd.read_csv(TEST_FILE, parse_dates=['min'])
    else:
        #  CSV laden: load all sensor CSVs from DATA_DIR
        all_events = []  # collects events from each file
        for fname in os.listdir(DATA_DIR):
            if not fname.endswith('.csv'):
                continue
            path = os.path.join(DATA_DIR, fname)
            df = pd.read_csv(path, parse_dates=['timestamp'])

            # Remove duplicate Zigbee timestamp column if present
            if 'timestamp.1' in df.columns:
                df = df.drop(columns=['timestamp.1'])

            # Filter correct rows: door opens or single button presses
            if 'contact' in df.columns:
                df = df[df['contact'] == True]
            elif 'action' in df.columns:
                df = df[df['action'] == 'single']
            else:
                continue

            df['sensor'] = fname  # tag with sensor filename
            # Keep only timestamp and sensor for counting
            all_events.append(df[['timestamp', 'sensor']])

        # If no events found, wait and retry
        if not all_events:
            print("⚠️  No event files found—waiting...")
            time.sleep(CHECK_INTERVAL)
            continue

        # Merge all events into one DataFrame
        events = pd.concat(all_events, ignore_index=True)
        # Group by minute: floor timestamps to minute resolution
        events['min'] = events['timestamp'].dt.floor('min')
        # Count events per minute
        min_counts = (
            events.groupby('min')
                  .size()
                  .reset_index(name='request_count')
        )
        # Initialize anomaly flag to False for all rows
        min_counts['is_anomaly'] = False

    # ── 2) Write full time-series CSV for frontend ─────────────────────────
    # Overwrite minute_counts.csv so frontend sees fresh data
    min_counts.to_csv(COUNT_FILE, index=False)

    # ── 3) Run anomaly detection on the latest minute ───────────────────────
    if len(min_counts) >= MIN_HISTORY:
        last_min = min_counts['min'].max()
        # Only check each minute once, and only after it’s fully elapsed
        if last_min not in generated_mins and last_min < now.replace(second=0, microsecond=0):
            train = min_counts.iloc[:-1]          # all but newest minute
            test  = min_counts.iloc[-1:].copy()   # only newest minute

            # Train Isolation Forest on historical counts
            model = IsolationForest(contamination=0.05, random_state=42)
            model.fit(train[['request_count']])

            # Predict anomaly for the newest minute
            test['is_anomaly'] = model.predict(test[['request_count']]) == -1

            # Update full series with the anomaly flag
            is_anom = test.at[test.index[0], 'is_anomaly']
            min_counts.loc[min_counts['min'] == last_min, 'is_anomaly'] = is_anom
            min_counts.to_csv(COUNT_FILE, index=False)

            # Append only true anomalies to anomalies CSV
            if is_anom:
                print(f"⚠️ ANOMALY at {last_min}: {test.at[test.index[0], 'request_count']} events")
                write_header = not os.path.exists(ANOM_FILE)
                test[['min', 'request_count', 'is_anomaly']].to_csv(
                    ANOM_FILE,
                    mode='a',         # append mode
                    header=write_header,  # add header only if file is new
                    index=False
                )
            else:
                print(f"✅ Normal at {last_min}: {test.at[test.index[0], 'request_count']} events")

            generated_mins.add(last_min)
        else:
            print(f"[+] Minute {last_min} already processed or still in progress")
    else:
        needed = MIN_HISTORY - len(min_counts)
        print(f"ℹ️  Need {needed} more minutes before detecting anomalies")

    # Sleep until next check
    time.sleep(CHECK_INTERVAL)
