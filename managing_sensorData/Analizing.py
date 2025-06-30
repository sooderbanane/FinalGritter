import os
import time
import pandas as pd
from sklearn.ensemble import IsolationForest
from datetime import datetime


# Hardcoded shit
DATA_DIR = 'sensor_data'
CHECK_INTERVAL = 60

checked_hours = set()  

while True: 
    print (f"\n[+] Checking data at {datetime.now()}")

    # Loads the data and prepares it 
    all_events = [] 
    for file in os.listdir(DATA_DIR):
        if file.endswith(".csv"):
            print(f"the file found is {file}")
            df = pd.read_csv(os.path.join(DATA_DIR, file), parse_dates=['timestamp'])
            df = df.drop(columns=['timestamp.1'])
            if 'contact' in df.columns: 
                df = df[df['contact'] == True]
            elif 'action' in df.columns:
                df = df
            else:
                continue
        df['sensor'] = file 
        all_events.append(df[['timestamp', 'sensor']])
    if not all_events:
        print('no events found. BRUHHHHHHH')
        time.sleep(CHECK_INTERVAL)
        continue 


    # makes it into hourly groups for later analyzing 
    events = pd.concat(all_events)
    events['hour'] = events['timestamp'].dt.floor('h')
    hourly_counts = events.groupby('hour').size().reset_index(name='request_count')


    # checks for duplicates
    last_hour = hourly_counts['hour'].max()

    if last_hour not in checked_hours and last_hour < datetime.now().replace(minute=0, second=0, microsecond=0):
        test_data = hourly_counts[hourly_counts['hour'] == last_hour]

        # Checking for amount of data for training
        if len(hourly_counts) < 5:
            print(f"Need more hours of data ({len(hourly_counts)}/5). Waiting for more...")
        # Setting testdata / traindata 
        else:
            train_data = hourly_counts.iloc[:-1]
            test_data = hourly_counts.iloc[-1:]

            # Actual testing 
            model = IsolationForest(contamination=0.05, random_state=42)
            model.fit(train_data[['request_count']])
            prediction = model.predict(test_data[['request_count']])


            if prediction[0] == -1:
                print(f"⚠️ ANOMALY: {test_data['request_count'].values[0]} requests in last hour")
            else:
                print(f"✅ Normal: {test_data['request_count'].values[0]} requests in last hour")

            #writing into extra file 
            with open ('anomalies.csv', 'a') as f :
                f.write(f"{datetime.now()}, ANOMALY, {test_data['request_count'].values[0]}\n")

            checked_hours.add(last_hour)

    time.sleep(CHECK_INTERVAL)
    