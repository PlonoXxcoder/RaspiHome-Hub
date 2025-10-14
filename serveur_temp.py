#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sqlite3
from flask import Flask, jsonify, render_template, request, send_from_directory
from sense_hat import SenseHat
import threading
import time
import csv
from datetime import datetime, date
import pandas as pd
import os
import math
import random

app = Flask(__name__)
sense = SenseHat()
sense.clear()
DATA_FILE = 'data.csv'
DB_FILE = 'raspihome.db'

@app.route('/templates/<path:filename>')
def serve_template_files(filename):
    return send_from_directory('templates', filename)

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def is_summer():
    return 4 <= date.today().month <= 9

@app.route('/plants')
def get_plant_statuses():
    statuses = {}
    conn = get_db_connection()
    plants = conn.execute("SELECT p.id, p.name, p.type, p.last_watered, pr.summer_weeks, pr.winter_weeks FROM plants p JOIN plant_rules pr ON p.type = pr.name").fetchall()
    conn.close()
    for plant in plants:
        last_watered = datetime.strptime(plant['last_watered'], '%Y-%m-%d').date()
        days_since = (date.today() - last_watered).days
        interval_weeks = plant['summer_weeks'] if is_summer() else plant['winter_weeks']
        watering_interval_days = interval_weeks * 7
        days_until = watering_interval_days - days_since
        is_due = days_until <= 0
        status_text = f"Dans {days_until} jours" if days_until > 0 else ("Aujourd'hui !" if days_until == 0 else "En retard")
        statuses[plant['id']] = {'nom': plant['name'], 'type': plant['type'], 'status': status_text, 'is_due': is_due}
    return jsonify(statuses)

@app.route('/watered/<int:plant_id>', methods=['POST'])
def watered_plant(plant_id):
    conn = get_db_connection()
    conn.execute("UPDATE plants SET last_watered = ? WHERE id = ?", (date.today().strftime('%Y-%m-%d'), plant_id))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

@app.route('/add_plant', methods=['POST'])
def add_plant():
    data = request.get_json()
    conn = get_db_connection()
    conn.execute("INSERT INTO plants (name, type, last_watered) VALUES (?, ?, ?)",
                 (data['nom'].strip(), data['type'], date.today().strftime('%Y-%m-%d')))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success', 'message': 'Plante ajoutée !'})

@app.route('/delete_plant/<int:plant_id>', methods=['POST'])
def delete_plant(plant_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM plants WHERE id = ?", (plant_id,))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success', 'message': 'Plante supprimée'})

@app.route('/plant_rules')
def get_plant_rules():
    conn = get_db_connection()
    rules = conn.execute("SELECT * FROM plant_rules").fetchall()
    conn.close()
    return jsonify({rule['name']: [rule['summer_weeks'], rule['winter_weeks']] for rule in rules})

@app.route('/plant_types')
def get_plant_types():
    conn = get_db_connection()
    types = conn.execute("SELECT name FROM plant_rules ORDER BY name").fetchall()
    conn.close()
    return jsonify([row['name'] for row in types])

@app.route('/add_plant_type', methods=['POST'])
def add_plant_type():
    data = request.get_json()
    conn = get_db_connection()
    conn.execute("INSERT OR REPLACE INTO plant_rules (name, summer_weeks, winter_weeks) VALUES (?, ?, ?)",
                 (data['type_name'].lower().strip().replace(' ', '_'), int(data['summer_weeks']), int(data['winter_weeks'])))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success', 'message': f"Type sauvegardé !"})

@app.route('/tips')
def get_random_tip():
    conn = get_db_connection()
    tip = conn.execute("SELECT category, tip FROM tips ORDER BY RANDOM() LIMIT 1").fetchone()
    conn.close()
    return jsonify({'category': tip['category'].capitalize(), 'tip': tip['tip']}) if tip else jsonify({'category': 'Erreur', 'tip': 'Aucune astuce.'}), 404

@app.route('/tip_for_type/<plant_type>')
def get_tip_for_type(plant_type):
    conn = get_db_connection()
    tip = conn.execute("SELECT category, tip FROM tips WHERE category = ? OR category = 'general' ORDER BY RANDOM() LIMIT 1", (plant_type.lower(),)).fetchone()
    conn.close()
    return jsonify({'category': tip['category'].capitalize(), 'tip': tip['tip']}) if tip else get_random_tip()

def calculate_noaa_heat_index(temperature_c, humidity_percent):
    T_f = (temperature_c * 9/5) + 32
    RH = humidity_percent
    if T_f < 80.0:
        return temperature_c
    HI_f = -42.379 + 2.04901523*T_f + 10.14333127*RH - 0.22475541*T_f*RH - 6.83783e-3*T_f**2 - 5.481717e-2*RH**2 + 1.22874e-3*T_f**2*RH + 8.5282e-4*T_f*RH**2 - 1.99e-6*T_f**2*RH**2
    if RH < 13 and 80 < T_f < 112:
        HI_f -= ((13 - RH) / 4) * math.sqrt((17 - abs(T_f - 95.0)) / 17)
    if RH > 85 and 80 < T_f < 87:
        HI_f += ((RH - 85) / 10) * ((87 - T_f) / 5)
    return round((HI_f - 32) * 5/9, 2)

def boucle_enregistrement():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE,'w',newline='')as f:csv.writer(f).writerow(['datetime','temp','hum','pres','heat_index'])
    def record_data():
        now=datetime.now().strftime('%Y-%m-%d %H:%M:%S');temp=round(sense.get_temperature(),2);hum=round(sense.get_humidity(),2);pres=round(sense.get_pressure(),2)
        with open(DATA_FILE,'a',newline='')as f:csv.writer(f).writerow([n,t,h,p,calculate_noaa_heat_index(temp,hum)])
        print(f"Data saved at {now}")
    record_data()
    while True:time.sleep(300);record_data()

def boucle_gestion_alertes_led():
    while True: time.sleep(60)

@app.route('/')
def index(): return render_template('index.html')

@app.route('/alldata')
def get_all_data():
    t=round(sense.get_temperature(),2);h=round(sense.get_humidity(),2)
    return jsonify({'temperature':t,'humidite':h,'pression':round(sense.get_pressure(),2),'heat_index':calculate_noaa_heat_index(t,h)})

@app.route('/history')
def history():
    p=request.args.get('period','day');
    try:df=pd.read_csv(DATA_FILE)
    except(FileNotFoundError,pd.errors.EmptyDataError):return jsonify({'datetime':[],'temp':[],'hum':[],'pres':[],'heat_index':[]})
    df['datetime']=pd.to_datetime(df['datetime']);df.set_index('datetime',inplace=True);n=pd.Timestamp.now();d='%H:%M'
    df_filtered=df[df.index>n-pd.Timedelta(days=365)]
    if p=='hour':pr=df_filtered[df_filtered.index>n-pd.Timedelta(hours=1)]
    elif p=='12hours':df_temp=df_filtered[df_filtered.index>n-pd.Timedelta(hours=12)];pr=df_temp.resample('10T').mean().dropna()
    elif p=='day':df_temp=df_filtered[df_filtered.index>n-pd.Timedelta(days=1)];pr=df_temp.resample('15T').mean().dropna()
    elif p=='week':df_temp=df_filtered[df_filtered.index>n-pd.Timedelta(weeks=1)];pr=df_temp.resample('H').mean().dropna();d='%d/%m %Hh'
    elif p=='month':df_temp=df_filtered[df_filtered.index>n-pd.DateOffset(months=1)];pr=df_temp.resample('D').mean().dropna();d='%d/%m/%Y'
    elif p=='year':pr=df_filtered.resample('D').mean().dropna();d='%d/%m/%Y'
    else:df_temp=df_filtered[df_filtered.index>n-pd.Timedelta(days=1)];pr=df_temp.resample('15T').mean().dropna()
    pr.reset_index(inplace=True);return jsonify({'datetime':pr['datetime'].dt.strftime(d).tolist(),'temp':pr['temp'].round(2).tolist(),'hum':pr['hum'].round(2).tolist(),'pres':pr['pres'].round(2).tolist(),'heat_index':pr['heat_index'].round(2).tolist()})

if __name__ == '__main__':
    threading.Thread(target=boucle_enregistrement, daemon=True).start()
    threading.Thread(target=boucle_gestion_alertes_led, daemon=True).start()
    app.run(host='0.0.0.0', port=5000, debug=True)
