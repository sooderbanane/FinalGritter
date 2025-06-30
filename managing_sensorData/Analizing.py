import os
import time
import pandas as pd
from sklearn.ensemble import IsolationForest
from datetime import datetime


# Hardcoded shit
DATA_DIR = 'sensor_data'
CHECK_INTERVAL = 10

checked_mins = set()  

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
    events['min'] = events['timestamp'].dt.floor('h')
    minly_counts = events.groupby('min').size().reset_index(name='request_count')


    # checks for duplicates
    last_min = minly_counts['min'].max()

    if last_min not in checked_mins and last_min < datetime.now().replace(second=0, microsecond=0):
        test_data = minly_counts[minly_counts['min'] == last_min]

        # Checking for amount of data for training
        if len(minly_counts) < 5:
            print(f"Need more mins of data ({len(minly_counts)}/5). Waiting for more...")
        # Setting testdata / traindata 
        else:
            train_data = minly_counts.iloc[:-1]
            test_data = minly_counts.iloc[-1:]

            # Actual testing 
            model = IsolationForest(contamination=0.05, random_state=42)
            model.fit(train_data[['request_count']])
            prediction = model.predict(test_data[['request_count']])


            if prediction[0] == -1:
                print(f"⚠️ ANOMALY: {test_data['request_count'].values[0]} requests in last min")
            else:
                print(f"✅ Normal: {test_data['request_count'].values[0]} requests in last min")

            #writing into extra file 
            with open ('anomalies.csv', 'a') as f :
                f.write(f"{datetime.now()}, ANOMALY, {test_data['request_count'].values[0]}\n")

            checked_mins.add(last_min)

    time.sleep(CHECK_INTERVAL)
    