#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sqlite3
import threading
import time
import math
from datetime import datetime, date
from flask import Flask, jsonify, render_template, request, g, send_from_directory
import requests
import config

DB_FILE = 'raspihome.db'
app = Flask(__name__)
try:
    from sense_hat import SenseHat
    sense = SenseHat()
    sense.clear()
    print("✅ Sense HAT détecté.")
except (OSError, IOError, ImportError):
    print("⚠️ Sense HAT non détecté. Passage en mode simulation.")
    class SenseHat:
        def get_temperature(self): return 25.8
        def get_humidity(self): return 45.2
        def get_pressure(self): return 1012.5
        def clear(self): pass
    sense = SenseHat()

notified_today = set()
last_check_day = date.today()

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_FILE)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def is_summer():
    return 4 <= date.today().month <= 9

def calculate_noaa_heat_index(temperature_c, humidity_percent):
    T_f = (temperature_c * 9/5) + 32; RH = humidity_percent
    if T_f < 80.0: return temperature_c
    HI_f = -42.379 + 2.04901523*T_f + 10.14333127*RH - 0.22475541*T_f*RH - 6.83783e-3*T_f**2 - 5.481717e-2*RH**2 + 1.22874e-3*T_f**2*RH + 8.5282e-4*T_f*RH**2 - 1.99e-6*T_f**2*RH**2
    if RH < 13 and 80 < T_f < 112: HI_f -= ((13 - RH) / 4) * math.sqrt((17 - abs(T_f - 95.0)) / 17)
    if RH > 85 and 80 < T_f < 87: HI_f += ((RH - 85) / 10) * ((87 - T_f) / 5)
    return round((HI_f - 32) * 5/9, 2)

def send_telegram_notification(message):
    token = config.TELEGRAM_TOKEN
    chat_id = config.TELEGRAM_CHAT_ID
    if not all([token, chat_id]) or "VOTRE_" in token or "VOTRE_" in chat_id:
        print("CONFIG MANQUANTE : Notification Telegram non envoyée.")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': message, 'parse_mode': 'HTML'}
    try:
        requests.post(url, json=payload, timeout=10)
        print("✅ Notification Telegram envoyée.")
    except requests.exceptions.RequestException as e:
        print(f"❌ Erreur Notification Telegram : {e}")

def boucle_enregistrement_meteo():
    print("Lancement du thread d'enregistrement météo...")
    with app.app_context():
        while True:
            try:
                temp = round(sense.get_temperature(), 2); hum = round(sense.get_humidity(), 2); pres = round(sense.get_pressure(), 2)
                heat_idx = calculate_noaa_heat_index(temp, hum)
                db = sqlite3.connect(DB_FILE)
                db.execute("INSERT INTO sensor_readings (timestamp, temperature, humidity, pressure, heat_index) VALUES (?, ?, ?, ?, ?)",
                           (datetime.now(), temp, hum, pres, heat_idx))
                db.commit()
                db.close()
            except Exception as e:
                print(f"Erreur dans boucle_enregistrement_meteo: {e}")
            time.sleep(300)

def boucle_notifications_arrosage():
    global notified_today, last_check_day
    print("Lancement du thread de notification d'arrosage...")
    time.sleep(20)
    while True:
        try:
            if date.today() != last_check_day:
                notified_today.clear(); last_check_day = date.today()
                print("Réinitialisation des notifications quotidiennes.")
            with app.app_context():
                plants = get_db().execute("SELECT p.id, p.name, pr.summer_weeks, pr.winter_weeks, p.last_watered FROM plants p JOIN plant_rules pr ON p.type = pr.name").fetchall()
                plants_to_water = []
                for plant in plants:
                    last_watered = datetime.strptime(plant['last_watered'], '%Y-%m-%d').date()
                    days_since = (date.today() - last_watered).days
                    interval_weeks = plant['summer_weeks'] if is_summer() else plant['winter_weeks']
                    watering_interval_days = interval_weeks * 7
                    if days_since >= watering_interval_days and plant['id'] not in notified_today:
                        plants_to_water.append(plant['name']); notified_today.add(plant['id'])
                if plants_to_water:
                    message = "💧 <b>Alerte Arrosage RaspiHome</b> 💧\n\nLes plantes suivantes ont besoin d'eau :\n"
                    for name in plants_to_water: message += f"- {name}\n"
                    send_telegram_notification(message)
            time.sleep(4 * 3600)
        except Exception as e:
            print(f"Erreur dans boucle_notifications_arrosage: {e}"); time.sleep(600)

@app.route('/')
def index(): return render_template('index.html')

@app.route('/templates/<path:filename>')
def serve_template_files(filename): return send_from_directory('templates', filename)

def get_outdoor_weather():
    if not all([config.API_KEY, config.LATITUDE, config.LONGITUDE]) or "VOTRE_" in config.API_KEY:
        return None
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={config.LATITUDE}&lon={config.LONGITUDE}&appid={config.API_KEY}&units=metric&lang=fr"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        return {
            "temperature": data["main"]["temp"], "humidite": data["main"]["humidity"], "pression": data["main"]["pressure"],
            "heat_index": data["main"]["feels_like"], "description": data["weather"][0]["description"].capitalize(), "icon": data["weather"][0]["icon"]
        }
    except requests.exceptions.RequestException as e:
        print(f"Erreur API météo : {e}"); return None

@app.route('/alldata')
def get_all_data():
    outdoor_data = get_outdoor_weather()
    if outdoor_data: return jsonify(outdoor_data)
    temp = round(sense.get_temperature(), 2); hum = round(sense.get_humidity(), 2)
    return jsonify({
        'temperature': temp, 'humidite': hum, 'pression': round(sense.get_pressure(), 2),
        'heat_index': calculate_noaa_heat_index(temp, hum), 'description': "Données intérieures (Sense HAT)", 'icon': "04d"
    })

@app.route('/history')
def history():
    period = request.args.get('period', 'day')
    formats = {
        'day':   {'format': '%Y-%m-%d %H:00', 'interval': '1 DAY', 'label': '%H:%M'},
        'week':  {'format': '%Y-%m-%d', 'interval': '7 DAY', 'label': '%d/%m'},
        'month': {'format': '%Y-%m-%d', 'interval': '1 MONTH', 'label': '%d/%m'}
    }
    config = formats.get(period, formats['day'])
    query = f"""
        SELECT strftime('{config["label"]}', timestamp) as label,
            ROUND(AVG(temperature), 2) as temp, ROUND(AVG(humidity), 2) as hum
        FROM sensor_readings WHERE timestamp >= DATETIME('now', '-{config["interval"]}')
        GROUP BY strftime('{config["format"]}', timestamp) ORDER BY timestamp ASC;
    """
    rows = get_db().execute(query).fetchall()
    return jsonify({'datetime': [row['label'] for row in rows], 'temp': [row['temp'] for row in rows], 'hum': [row['hum'] for row in rows]})

@app.route('/plants')
def get_plant_statuses():
    plants = get_db().execute("SELECT p.id, p.name, p.type, p.last_watered, pr.summer_weeks, pr.winter_weeks FROM plants p JOIN plant_rules pr ON p.type = pr.name").fetchall()
    plant_list = []
    for plant in plants:
        plant_dict = dict(plant); last_watered = datetime.strptime(plant['last_watered'], '%Y-%m-%d').date()
        days_since = (date.today() - last_watered).days
        interval_weeks = plant['summer_weeks'] if is_summer() else plant['winter_weeks']
        watering_interval_days = interval_weeks * 7
        days_until = watering_interval_days - days_since
        plant_dict['is_due'] = days_until <= 0
        plant_dict['status'] = f"Dans {days_until} jours" if days_until > 0 else ("Aujourd'hui !" if days_until == 0 else "En retard")
        plant_list.append(plant_dict)
    return jsonify(plant_list)

@app.route('/watered/<int:plant_id>', methods=['POST'])
def watered_plant(plant_id):
    today_str = date.today().strftime('%Y-%m-%d'); db = get_db()
    db.execute("UPDATE plants SET last_watered = ? WHERE id = ?", (today_str, plant_id))
    db.execute("INSERT INTO watering_history (plant_id, watering_date) VALUES (?, ?)", (plant_id, today_str))
    db.commit(); return jsonify({'status': 'success'})

@app.route('/add_plant', methods=['POST'])
def add_plant():
    data = request.get_json(); db = get_db()
    cursor = db.execute("INSERT INTO plants (name, type, last_watered) VALUES (?, ?, ?)", (data['nom'].strip(), data['type'], date.today().strftime('%Y-%m-%d')))
    db.execute("INSERT INTO watering_history (plant_id, watering_date) VALUES (?, ?)", (cursor.lastrowid, date.today().strftime('%Y-%m-%d')))
    db.commit(); return jsonify({'status': 'success', 'message': 'Plante ajoutée !'})

@app.route('/delete_plant/<int:plant_id>', methods=['POST'])
def delete_plant(plant_id):
    db = get_db(); db.execute("DELETE FROM plants WHERE id = ?", (plant_id,)); db.commit()
    return jsonify({'status': 'success', 'message': 'Plante supprimée'})

@app.route('/edit_plant/<int:plant_id>', methods=['POST'])
def edit_plant(plant_id):
    data = request.get_json()
    db = get_db(); db.execute("UPDATE plants SET name = ?, type = ? WHERE id = ?", (data['name'], data['type'], plant_id)); db.commit()
    return jsonify({'status': 'success', 'message': 'Plante mise à jour !'})

@app.route('/plant_history/<int:plant_id>')
def get_plant_history(plant_id):
    history = get_db().execute("SELECT watering_date FROM watering_history WHERE plant_id = ? ORDER BY watering_date DESC", (plant_id,)).fetchall()
    return jsonify([row['watering_date'] for row in history])

# --- CORRECTION ICI ---
@app.route('/plant_types')
def get_plant_types(): # Suppression de (self)
    types = get_db().execute("SELECT name FROM plant_rules ORDER BY name").fetchall()
    return jsonify([row['name'] for row in types])

# --- CORRECTION ICI ---
@app.route('/plant_rules')
def get_plant_rules(): # Suppression de (self)
    rules = get_db().execute("SELECT name, summer_weeks, winter_weeks FROM plant_rules").fetchall()
    return jsonify({rule['name']: [rule['summer_weeks'], rule['winter_weeks']] for rule in rules})

# --- CORRECTION ICI ---
@app.route('/add_plant_type', methods=['POST'])
def add_plant_type(): # Suppression de (self)
    data = request.get_json(); db = get_db()
    db.execute("INSERT OR REPLACE INTO plant_rules (name, summer_weeks, winter_weeks) VALUES (?, ?, ?)",
                 (data['type_name'].lower().strip().replace(' ', '_'), int(data['summer_weeks']), int(data['winter_weeks'])))
    db.commit(); return jsonify({'status': 'success', 'message': f"Type sauvegardé !"})

# --- CORRECTION ICI ---
@app.route('/smart_recommendation')
def get_smart_recommendation(): # Suppression de (self)
    try:
        outdoor_weather = get_outdoor_weather()
        if outdoor_weather and outdoor_weather['temperature'] > 28:
            plants = get_db().execute("SELECT p.name, p.last_watered, pr.summer_weeks FROM plants p JOIN plant_rules pr ON p.type = pr.name").fetchall()
            for plant in plants:
                last_watered = datetime.strptime(plant['last_watered'], '%Y-%m-%d').date()
                if (date.today() - last_watered).days >= (plant['summer_weeks'] * 7) - 2:
                    return jsonify({"icon": "fa-temperature-high", "message": f"Forte chaleur aujourd'hui ! Pensez à vérifier la terre de votre <strong>{plant['name']}</strong>."})
        tip = get_db().execute("SELECT tip FROM tips WHERE category = 'general' ORDER BY RANDOM() LIMIT 1").fetchone()
        return jsonify({"icon": "fa-lightbulb", "message": tip['tip'] if tip else "Passez une excellente journée !"})
    except Exception:
        return jsonify({"icon": "fa-info-circle", "message": "Vérifiez vos plantes régulièrement."})

if __name__ == '__main__':
    threading.Thread(target=boucle_enregistrement_meteo, daemon=True).start()
    threading.Thread(target=boucle_notifications_arrosage, daemon=True).start()
    send_telegram_notification("✅ <b>RaspiHome Hub Démarré</b>\nLe système de surveillance est maintenant en ligne.")
    print("🚀 Lancement du serveur Flask sur http://0.0.0.0:5001")
    app.run(host='0.0.0.0', port=5000)
