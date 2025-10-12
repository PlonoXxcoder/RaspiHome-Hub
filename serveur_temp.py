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
sense.clear()
DATA_FILE = 'data.csv'
PLANT_DATA_FILE = 'plants.json'
PLANT_RULES_FILE = 'plant_rules.json' # Fichier devient l'unique source de vérité

# --- Section Logique des Plantes ---

def load_plant_rules():
    """
    Charge les règles depuis plant_rules.json.
    Si le fichier n'existe pas, le crée avec des valeurs par défaut.
    """
    if not os.path.exists(PLANT_RULES_FILE):
        print(f"Le fichier {PLANT_RULES_FILE} n'existe pas. Création avec les règles par défaut.")
        default_rules = {
            'echeveria': [2, 5],
            'sansevieria': [1, 1],
            'succulente': [2, 5],
            'ficus': [1, 2],
            'pothos': [1, 3]
        }
        with open(PLANT_RULES_FILE, 'w') as f:
            json.dump(default_rules, f, indent=2)
        return default_rules
    else:
        try:
            with open(PLANT_RULES_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            print(f"ERREUR : Impossible de lire {PLANT_RULES_FILE}. Le fichier est peut-être corrompu.")
            return {}

PLANT_RULES = load_plant_rules()

def normalize_text_for_led(text):
    nfkd_form = unicodedata.normalize('NFD', text)
    return u"".join([c for c in nfkd_form if not unicodedata.combining(c)])

def is_summer():
    return 4 <= date.today().month <= 9

def save_plant_data(data):
    with open(PLANT_DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def load_plant_data():
    if not os.path.exists(PLANT_DATA_FILE):
        save_plant_data({})
        return {}
    with open(PLANT_DATA_FILE, 'r') as f:
        return json.load(f)

def get_plant_statuses():
    data = load_plant_data()
    statuses = {}
    interval_idx = 0 if is_summer() else 1
    current_rules = PLANT_RULES.copy()
    for key in data.keys():
        if key not in current_rules:
            base_type = key.split('_')[0]
            if base_type in current_rules:
                current_rules[key] = current_rules[base_type]
    for key, plant in data.items():
        if key in current_rules:
            rules = current_rules[key]
            last_watered = datetime.strptime(plant['last_watered'], '%Y-%m-%d').date()
            days_since = (date.today() - last_watered).days
            watering_interval = rules[interval_idx] * 7
            days_until = watering_interval - days_since
            status_text = f"Dans {days_until} jours" if days_until > 0 else ("Aujourd'hui !" if days_until == 0 else "En retard")
            statuses[key] = {'nom': plant['nom'], 'status': status_text, 'is_due': days_until <= 0}
    return statuses

def confirm_watering(plant_key):
    data = load_plant_data()
    if plant_key in data:
        data[plant_key]['last_watered'] = date.today().strftime('%Y-%m-%d')
        save_plant_data(data)
        return True
    return False

# --- Section Logique Météo ---
def calculate_noaa_heat_index(temperature_c, humidity_percent):
    T_f=(temperature_c*9/5)+32;RH=humidity_percent;
    if T_f<80.0:return temperature_c
    HI_f=-42.379+2.04901523*T_f+10.14333127*RH-0.22475541*T_f*RH-6.83783e-3*T_f**2-5.481717e-2*RH**2+1.22874e-3*T_f**2*RH+8.5282e-4*T_f*RH**2-1.99e-6*T_f**2*RH**2
    if RH<13 and 80<T_f<112:HI_f-=((13-RH)/4)*math.sqrt((17-abs(T_f-95.0))/17)
    if RH>85 and 80<T_f<87:HI_f+=((RH-85)/10)*((87-T_f)/5)
    return round((HI_f-32)*5/9,2)

def boucle_enregistrement():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE,'w',newline='')as f:csv.writer(f).writerow(['datetime','temp','hum','pres','heat_index'])
    def record_data():
        now=datetime.now().strftime('%Y-%m-%d %H:%M:%S');temp=round(sense.get_temperature(),2);hum=round(sense.get_humidity(),2);pres=round(sense.get_pressure(),2)
        with open(DATA_FILE,'a',newline='')as f:csv.writer(f).writerow([now,temp,hum,pres,calculate_noaa_heat_index(temp,hum)])
        print(f"Data saved at {now}")
    record_data()
    while True:time.sleep(300);record_data()

def boucle_gestion_alertes_led():
    while True: time.sleep(60)

# --- Section Routes Flask (API) ---
@app.route('/')
def index(): return render_template('index.html')

@app.route('/alldata')
def get_all_data():
    temp=round(sense.get_temperature(),2);hum=round(sense.get_humidity(),2)
    return jsonify({'temperature':temp,'humidite':hum,'pression':round(sense.get_pressure(),2),'heat_index':calculate_noaa_heat_index(temp,hum)})

@app.route('/history')
def history():
    period=request.args.get('period','day');
    try:df=pd.read_csv(DATA_FILE)
    except(FileNotFoundError,pd.errors.EmptyDataError):return jsonify({'datetime':[],'temp':[],'hum':[],'pres':[],'heat_index':[]})
    df['datetime']=pd.to_datetime(df['datetime']);df.set_index('datetime',inplace=True);now=pd.Timestamp.now();date_format='%H:%M'
    if period=='hour':df_processed=df[df.index>now-pd.Timedelta(hours=1)]
    elif period=='12hours':df_processed=df[df.index>now-pd.Timedelta(hours=12)]
    elif period=='day':df_processed=df[df.index>now-pd.Timedelta(days=1)]
    elif period=='week':df_filtered=df[df.index>now-pd.Timedelta(weeks=1)];df_processed=df_filtered.resample('H').mean().dropna();date_format='%d/%m %Hh'
    elif period=='month':df_filtered=df[df.index>now-pd.DateOffset(months=1)];df_processed=df_filtered.resample('D').mean().dropna();date_format='%d/%m/%Y'
    elif period=='year':df_filtered=df[df.index>now-pd.DateOffset(years=1)];df_processed=df_filtered.resample('D').mean().dropna();date_format='%d/%m/%Y'
    else:df_processed=df[df.index>now-pd.Timedelta(days=1)]
    df_processed.reset_index(inplace=True);return jsonify({'datetime':df_processed['datetime'].dt.strftime(date_format).tolist(),'temp':df_processed['temp'].round(2).tolist(),'hum':df_processed['hum'].round(2).tolist(),'pres':df_processed['pres'].round(2).tolist(),'heat_index':df_processed['heat_index'].round(2).tolist()})

@app.route('/plants')
def get_plants(): return jsonify(get_plant_statuses())

@app.route('/watered/<plant_key>', methods=['POST'])
def watered_plant(plant_key):
    if confirm_watering(plant_key): return jsonify({'status':'success'})
    return jsonify({'status':'error','message':'Plant not found'}),404

@app.route('/add_plant', methods=['POST'])
def add_plant():
    data=request.get_json();
    if not data or'nom'not in data or'type'not in data:return jsonify({'status':'error','message':'Invalid data'}),400
    plant_nom=data['nom'].strip();plant_type=data['type'];
    if not plant_nom:return jsonify({'status':'error','message':'Name cannot be empty.'}),400
    if plant_type not in PLANT_RULES:return jsonify({'status':'error','message':'Unknown type'}),400
    plant_key=f"{plant_type}_{normalize_text_for_led(plant_nom).lower().replace(' ','_')}_{int(time.time())}";all_plants=load_plant_data();all_plants[plant_key]={"nom":plant_nom,"last_watered":date.today().strftime('%Y-%m-%d')};save_plant_data(all_plants);return jsonify({'status':'success','message':'Plant added!'})

@app.route('/plant_types')
def get_plant_types():
    return jsonify(sorted(PLANT_RULES.keys()))

@app.route('/plant_rules')
def get_plant_rules():
    return jsonify(PLANT_RULES)

@app.route('/add_plant_type', methods=['POST'])
def add_plant_type():
    global PLANT_RULES
    data = request.get_json()
    if not data or not all(k in data for k in ['type_name', 'summer_weeks', 'winter_weeks']):
        return jsonify({'status': 'error', 'message': 'Données manquantes.'}), 400
    
    type_name = data['type_name'].lower().strip().replace(' ', '_')
    if not type_name:
        return jsonify({'status': 'error', 'message': 'Le nom du type est requis.'}), 400
        
    try:
        summer_weeks = int(data['summer_weeks']); winter_weeks = int(data['winter_weeks'])
    except (ValueError, TypeError):
        return jsonify({'status': 'error', 'message': 'Les intervalles doivent être des nombres.'}), 400

    current_rules = load_plant_rules()
    current_rules[type_name] = [summer_weeks, winter_weeks]
    
    with open(PLANT_RULES_FILE, 'w') as f:
        json.dump(current_rules, f, indent=2)
        
    PLANT_RULES = current_rules
    return jsonify({'status': 'success', 'message': f'Type "{type_name}" sauvegardé !'})

# --- Démarrage ---
if __name__ == '__main__':
    threading.Thread(target=boucle_enregistrement, daemon=True).start()
    threading.Thread(target=boucle_gestion_alertes_led, daemon=True).start()
    app.run(host='0.0.0.0', port=5000, debug=True)
