import csv
import json
import os
import paho.mqtt.client as mqtt
from datetime import datetime
from sklearn.ensemble import IsolationForest
import schedule 
import time 
import threading 
import os 
from datetime import datetime, timedelta
import pandas as pd 




MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPICS = ["zigbee2mqtt/switch_1","zigbee2mqtt/door_1","zigbee2mqtt/door_2","zigbee2mqtt/door_3","zigbee2mqtt/door_4","zigbee2mqtt/temp_1"]

DATA_DIR = "sensor_data"
os.makedirs(DATA_DIR, exist_ok=True)

def topic_filename(topic):
    return topic.replace("/", "_") + ".csv" 

def does_csv_file_exists(filename, fieldnames):
    if not os.path.exists(filename):
        with open(filename, mode='w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=['timestamp', *fieldnames])
            writer.writeheader()

def append_to_csv(filename, data_dict, topic):
    data_dict['timestamp'] = datetime.now().isoformat()

    if not os.path.exists(filename):
        does_csv_file_exists(filename, list(data_dict.keys()))
        current_header = ['timestamp'] + list(data_dict.keys())

    else: 
        with open(filename, 'r', newline='') as f:
            reader = csv.reader(f)
            current_header = next(reader)

    new_fields = [key for key in data_dict if key not in current_header]
    if new_fields:
            updated_header = current_header + new_fields
            with open(filename, 'r', newline='')as f:
                rows = list(csv.DictReader(f))
            with open (filename, 'w', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=updated_header)
                writer.writeheader()
                for row in rows:
                    writer.writerow(row)
            current_header = updated_header

    with open(filename, 'a', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=current_header)
        writer.writerow(data_dict)

def detect_anomalies():
    for topic in MQTT_TOPICS:
        filename = topic_filename(topic)
        try: 
            df = pd.read_csv(filename, parse_dates=['timestamp'])
            now = datetime.now()
            one_hour_ago = now - timedelta(hours=1)
            recent_data = df[df['timestamp'] >= one_hour_ago.isoformat()]
            if recent_data.empty:
                print("no data from last hour")
                return 
           

            model = IsolationForest(contamination = 0.1, random_state = 42)
            recent_data['anomaly'] = model.fit_predict(recent_data[['value']])
            anomalies = recent_data[recent_data['anomaly'] == -1]
            print(f"[{now}] Detected {len(anomalies)} anomalies:\n{anomalies}")
        except Exception as e:
            print("Anomalie Detection failed: " + str(e) ) 


schedule.every().hour.at(":00").do(detect_anomalies)
def run_Schedule():
    while True:
        schedule.run_pending()
        time.sleep(1)

threading.Thread(target=run_Schedule, deamon=True).start()

def on_connect(client, userdata, flag, rc):
    print(f"Connected to result code{rc}")
    for topic in MQTT_TOPICS:
        client.subscribe(topic)
        print(f"Sub to Topic: {topic}")

def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode('utf-8')
        data = json.loads(payload)
        filename = topic_filename(msg.topic)
        append_to_csv(filename, data, msg.topic)
        print(f"[{msg.topic}]Got that mf Product{data}")

        print(dir(msg))
        print(msg.topic)
        print(msg.payload.decode("utf-8"))


    except Exception as e:
        print(f'bro got away and said: {e}')

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect(MQTT_BROKER, MQTT_PORT)
client.loop_forever()