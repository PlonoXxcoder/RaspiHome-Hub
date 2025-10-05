#!/usr/bin/python3
# -*- coding: utf-8 -*-

from flask import Flask, jsonify, render_template, request
from sense_hat import SenseHat
import threading
import time
import csv
from datetime import datetime, date
import pandas as pd
import os
import math
import json
import unicodedata

# --- Initialisation ---
app = Flask(__name__)
sense = SenseHat()
sense.clear() # S'assure que l'écran est éteint au démarrage
DATA_FILE = 'data.csv'
PLANT_DATA_FILE = 'plants.json'

# --- Section Logique des Plantes ---
PLANT_RULES = {'echeveria': (2, 5), 'sansevieria': (1, 1), 'succulente': (2, 5)}
watering_alert_active = False
plant_to_water_alert_name = None
plant_to_water_alert_key = None

def normalize_text_for_led(text):
    nfkd_form = unicodedata.normalize('NFD', text)
    return u"".join([c for c in nfkd_form if not unicodedata.combining(c)])

def is_summer(): return 4 <= date.today().month <= 9
def load_plant_data():
    with open(PLANT_DATA_FILE, 'r') as f: return json.load(f)
def save_plant_data(data):
    with open(PLANT_DATA_FILE, 'w') as f: json.dump(data, f, indent=2)
def get_plant_statuses():
    data = load_plant_data(); statuses = {}; interval_idx = 0 if is_summer() else 1
    for key, plant in data.items():
        rules = PLANT_RULES[key]; last_watered = datetime.strptime(plant['last_watered'], '%Y-%m-%d').date()
        days_since = (date.today() - last_watered).days; watering_interval = rules[interval_idx] * 7
        days_until = watering_interval - days_since
        statuses[key] = {'nom': plant['nom'], 'status': f"Dans {days_until} jours" if days_until > 0 else "Aujourd'hui", 'is_due': days_until <= 0}
    return statuses
def confirm_watering(plant_key):
    global watering_alert_active, plant_to_water_alert_name, plant_to_water_alert_key
    data = load_plant_data()
    if plant_key in data:
        data[plant_key]['last_watered'] = date.today().strftime('%Y-%m-%d'); save_plant_data(data)
        if watering_alert_active and plant_key == plant_to_water_alert_key:
            watering_alert_active = False; plant_to_water_alert_name = None; plant_to_water_alert_key = None
        return True
    return False

def boucle_gestion_alertes_led():
    global watering_alert_active, plant_to_water_alert_name, plant_to_water_alert_key
    while True:
        current_hour = datetime.now().hour
        if not watering_alert_active and 18 <= current_hour < 21:
            statuses = get_plant_statuses()
            for key, status in statuses.items():
                if status['is_due']:
                    plant_to_water_alert_name = status['nom']
                    plant_to_water_alert_key = key
                    watering_alert_active = True
                    break
        if watering_alert_active:
            message = f"Arroser {plant_to_water_alert_name}!"
            message_pour_led = normalize_text_for_led(message)
            while watering_alert_active:
                sense.show_message(message_pour_led, scroll_speed=0.07, text_colour=(0, 150, 255))
                for event in sense.stick.get_events():
                    if event.action == "pressed":
                        confirm_watering(plant_to_water_alert_key)
                        break
                if not watering_alert_active:
                    break
            sense.clear()
        time.sleep(60)

def calculate_noaa_heat_index(temperature_c, humidity_percent):
    T_f = (temperature_c * 9/5) + 32; RH = humidity_percent
    if T_f < 80.0: return temperature_c
    HI_f = -42.379 + 2.04901523*T_f + 10.14333127*RH - 0.22475541*T_f*RH - 6.83783e-3*T_f**2 - 5.481717e-2*RH**2 + 1.22874e-3*T_f**2*RH + 8.5282e-4*T_f*RH**2 - 1.99e-6*T_f**2*RH**2
    if RH < 13 and 80 < T_f < 112: HI_f -= ((13 - RH) / 4) * math.sqrt((17 - abs(T_f - 95.0)) / 17)
    if RH > 85 and 80 < T_f < 87: HI_f += ((RH - 85) / 10) * ((87 - T_f) / 5)
    return round((HI_f - 32) * 5/9, 2)
def boucle_enregistrement():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'w', newline='') as f:
            csv.writer(f).writerow(['datetime', 'temp', 'hum', 'pres', 'heat_index'])
    while True:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S'); temp = round(sense.get_temperature(), 2); hum = round(sense.get_humidity(), 2); pres = round(sense.get_pressure(), 2); heat_index = calculate_noaa_heat_index(temp, hum)
        with open(DATA_FILE, 'a', newline='') as f:
            csv.writer(f).writerow([now, temp, hum, pres, heat_index])
        time.sleep(300)
@app.route('/')
def index(): return render_template('index.html')
@app.route('/alldata')
def get_all_data():
    temp = round(sense.get_temperature(), 2); hum = round(sense.get_humidity(), 2)
    return jsonify({'temperature': temp, 'humidite': hum, 'pression': round(sense.get_pressure(), 2), 'heat_index': calculate_noaa_heat_index(temp, hum)})
@app.route('/history')
def history():
    period = request.args.get('period', 'day')
    try: df = pd.read_csv(DATA_FILE)
    except (FileNotFoundError, pd.errors.EmptyDataError): return jsonify({'datetime':[], 'temp':[], 'hum':[], 'pres':[], 'heat_index':[]})
    df['datetime'] = pd.to_datetime(df['datetime']); df.set_index('datetime', inplace=True); now = pd.Timestamp.now()
    df_processed = df; date_format = '%H:%M'
    if period == 'hour': df_processed = df[df.index > now - pd.Timedelta(hours=1)]
    elif period == '12hours': df_processed = df[df.index > now - pd.Timedelta(hours=12)]
    elif period == 'day': df_processed = df[df.index > now - pd.Timedelta(days=1)]
    elif period == 'week': df_filtered = df[df.index > now - pd.Timedelta(weeks=1)]; df_processed = df_filtered.resample('H').mean().dropna(); date_format = '%d/%m %Hh'
    elif period == 'month': df_filtered = df[df.index > now - pd.DateOffset(months=1)]; df_processed = df_filtered.resample('D').mean().dropna(); date_format = '%d/%m/%Y'
    elif period == 'year': df_filtered = df[df.index > now - pd.DateOffset(years=1)]; df_processed = df_filtered.resample('D').mean().dropna(); date_format = '%d/%m/%Y'
    df_processed.reset_index(inplace=True)
    return jsonify({'datetime': df_processed['datetime'].dt.strftime(date_format).tolist(), 'temp': df_processed['temp'].tolist(), 'hum': df_processed['hum'].tolist(), 'pres': df_processed['pres'].tolist(), 'heat_index': df_processed['heat_index'].tolist()})
@app.route('/plants')
def get_plants(): return jsonify(get_plant_statuses())
@app.route('/watered/<plant_key>', methods=['POST'])
def watered_plant(plant_key):
    if confirm_watering(plant_key): return jsonify({'status': 'success'})
    return jsonify({'status': 'error'}), 404

# --- DÉMARRAGE DES THREADS (CORRIGÉ) ---
if __name__ == '__main__':
    threading.Thread(target=boucle_enregistrement, daemon=True).start()
    # On lance le thread qui gère les alertes LED
    threading.Thread(target=boucle_gestion_alertes_led, daemon=True).start()
    app.run(host='0.0.0.0', port=5000, debug=False)
