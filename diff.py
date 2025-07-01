import os
import sys
import time
from datetime import datetime
import pandas as pd
from sklearn.ensemble import IsolationForest

# ─── CONFIG ────────────────────────────────────────────────────────────────────
# Path to your synthetic warm-up CSV (must contain columns: min, request_count)
TRAIN_FILE     = os.path.join(os.path.dirname(__file__), '..', 'simData', 'minute_counts_test.csv')  # unchanged

# Live sensor data directory
DATA_DIR       = os.path.join(os.path.dirname(__file__), '..', 'sensor_data')  # unchanged
# Next.js public folder
PUBLIC_DIR     = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'gritter-frontend', 'public')  # unchanged
COUNT_FILE     = os.path.join(PUBLIC_DIR, 'minute_counts.csv')  # unchanged
ANOM_FILE      = os.path.join(PUBLIC_DIR, 'minute_anomalies.csv')  # unchanged
LOG_FILE       = os.path.join(PUBLIC_DIR, 'anom.csv')  # unchanged

CHECK_INTERVAL = 10  # seconds between checks (unchanged)
MIN_HISTORY    = 5   # minutes of live history before detecting anomalies (unchanged)
# ────────────────────────────────────────────────────────────────────────────────

# Ensure the output directory exists
os.makedirs(PUBLIC_DIR, exist_ok=True)  # unchanged

# Initialize log file with header if not present
if not os.path.exists(LOG_FILE):  # unchanged
    pd.DataFrame(columns=['min', 'request_count', 'is_anomaly']).to_csv(LOG_FILE, index=False)  # unchanged

# Verify training file exists
if not os.path.exists(TRAIN_FILE):  # unchanged
    print(f"❌ Training file not found: {TRAIN_FILE}")  # unchanged
    sys.exit(1)  # unchanged

# ── WARM-UP TRAINING (run once) ───────────────────────────────────────────────
# >>> CHANGE: Warm-up training on synthetic data before live loop <<<
df_train = pd.read_csv(TRAIN_FILE, parse_dates=['min'])  # added for warm-up training
model    = IsolationForest(contamination=0.05, random_state=42)  # added for warm-up training
model.fit(df_train[['request_count']])  # added for warm-up training
print(f"✅ Warm-up training done on {len(df_train)} synthetic minutes")  # added for warm-up training
# ────────────────────────────────────────────────────────────────────────────────

processed_mins = set()  # track which minutes have been processed (unchanged)

while True:
    now = datetime.now()  # unchanged
    print(f"\n[+] Checking data at {now.isoformat(timespec='seconds')}")  # unchanged

    # ── 1) Load & filter live sensor CSVs ────────────────────────────────────────
    all_events = []  # unchanged
    for fname in os.listdir(DATA_DIR):  # unchanged
        if not fname.endswith('.csv'):  # unchanged
            continue  # unchanged
        path = os.path.join(DATA_DIR, fname)  # unchanged
        df   = pd.read_csv(path, parse_dates=['timestamp'])  # unchanged

        if 'timestamp.1' in df.columns:  # unchanged
            df = df.drop(columns=['timestamp.1'])  # unchanged

        if 'contact' in df.columns:  # unchanged
            df = df[df['contact'] == True]  # unchanged
        elif 'action' in df.columns:  # unchanged
            df = df[df['action'] == 'single']  # unchanged
        else:  # unchanged
            continue  # unchanged

        df['sensor'] = fname  # unchanged
        all_events.append(df[['timestamp', 'sensor']])  # unchanged

    if not all_events:  # unchanged
        print("⚠️ No live event files found—waiting...")  # unchanged
        time.sleep(CHECK_INTERVAL)  # unchanged
        continue  # unchanged

    # ── 2) Concatenate & group by minute ───────────────────────────────────────
    events = pd.concat(all_events, ignore_index=True)  # unchanged
    events['min'] = events['timestamp'].dt.floor('min')  # unchanged
    min_counts = (
        events.groupby('min')
              .size()
              .reset_index(name='request_count')
    )  # unchanged

    # >>> CHANGE: Restore previous anomaly flags <<<
    min_counts['is_anomaly'] = False  # added placeholder reset
    if os.path.exists(ANOM_FILE):  # added restoration logic
        prev = pd.read_csv(ANOM_FILE, parse_dates=['min'])  # added restoration logic
        min_counts = min_counts.merge(prev[['min','is_anomaly']], on='min', how='left', suffixes=('','_prev'))  # added restoration logic
        min_counts['is_anomaly'] = min_counts['is_anomaly_prev'].fillna(min_counts['is_anomaly'])  # added restoration logic
        min_counts.drop(columns=['is_anomaly_prev'], inplace=True)  # added restoration logic

    # ── 3) Write full time-series CSV for frontend ─────────────────────────────
    min_counts.to_csv(COUNT_FILE, index=False)  # unchanged

    # ── 4) Anomaly detection on the latest minute ──────────────────────────────
    if len(min_counts) >= MIN_HISTORY:  # unchanged
        last_min = min_counts['min'].max()  # unchanged
        if last_min not in processed_mins and last_min < now.replace(second=0, microsecond=0):  # unchanged
            test = min_counts[min_counts['min'] == last_min].copy()  # unchanged

            # >>> CHANGE: Exclude previous anomalies from retraining <<<
            live_train = min_counts[min_counts['is_anomaly'] == False].iloc[:-1]  # added exclusion logic
            model.fit(live_train[['request_count']])  # added retraining logic
            test['is_anomaly'] = model.predict(test[['request_count']]) == -1  # unchanged prediction

            # >>> CHANGE: Log every minute outcome <<<
            test[['min','request_count','is_anomaly']].to_csv(LOG_FILE, mode='a', header=False, index=False)  # added logging

            is_anom = test['is_anomaly'].iat[0]  # unchanged
            min_counts.loc[min_counts['min'] == last_min, 'is_anomaly'] = is_anom  # unchanged
            min_counts.to_csv(COUNT_FILE, index=False)  # unchanged

            if is_anom:  # unchanged
                print(f"⚠️ ANOMALY at {last_min}: {test['request_count'].iat[0]} events")  # unchanged
                write_header = not os.path.exists(ANOM_FILE)  # unchanged
                test[['min','request_count','is_anomaly']].to_csv(ANOM_FILE, mode='a', header=write_header, index=False)  # unchanged
            else:  # unchanged
                print(f"✅ Normal at {last_min}: {test['request_count'].iat[0]} events")  # unchanged

            processed_mins.add(last_min)  # unchanged
        else:  # unchanged
            print(f"[+] Minute {last_min} already processed or not complete")  # unchanged
    else:  # unchanged
        need = MIN_HISTORY - len(min_counts)  # unchanged
        print(f"ℹ️ Need {need} more minutes before detecting anomalies")  # unchanged

    time.sleep(CHECK_INTERVAL)  # unchanged
