#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sqlite3
import threading
import time
import math
from datetime import datetime, date
from flask import Flask, jsonify, render_template, request, g, send_from_directory
from sense_hat import SenseHat

# --- Configuration ---
DB_FILE = 'raspihome.db'
app = Flask(__name__)
# Met en place une simulation du SenseHat si le script n'est pas sur un Raspberry Pi
try:
    sense = SenseHat()
    sense.clear()
except (OSError, IOError):
    print("Sense HAT non détecté. Passage en mode simulation.")
    class SenseHat:
        def get_temperature(self): return 25.8
        def get_humidity(self): return 45.2
        def get_pressure(self): return 1012.5
        def clear(self): pass
    sense = SenseHat()


# --- Gestion de la connexion à la base de données ---
def get_db():
    """Ouvre une connexion à la DB pour la requête en cours."""
    if 'db' not in g:
        g.db = sqlite3.connect(DB_FILE)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exception):
    """Ferme la connexion à la DB à la fin de la requête."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


# --- Fonctions Utilitaires ---
def is_summer():
    """Détermine si la date actuelle correspond à la période estivale."""
    return 4 <= date.today().month <= 9

def calculate_noaa_heat_index(temperature_c, humidity_percent):
    """Calcule l'indice de chaleur ressenti selon la formule de la NOAA."""
    T_f = (temperature_c * 9/5) + 32
    RH = humidity_percent
    if T_f < 80.0: return temperature_c
    HI_f = -42.379 + 2.04901523*T_f + 10.14333127*RH - 0.22475541*T_f*RH - 6.83783e-3*T_f**2 - 5.481717e-2*RH**2 + 1.22874e-3*T_f**2*RH + 8.5282e-4*T_f*RH**2 - 1.99e-6*T_f**2*RH**2
    if RH < 13 and 80 < T_f < 112: HI_f -= ((13 - RH) / 4) * math.sqrt((17 - abs(T_f - 95.0)) / 17)
    if RH > 85 and 80 < T_f < 87: HI_f += ((RH - 85) / 10) * ((87 - T_f) / 5)
    return round((HI_f - 32) * 5/9, 2)


# --- Tâches de fond ---
def boucle_enregistrement():
    """Thread qui enregistre les données du Sense HAT dans la DB toutes les 5 minutes."""
    print("Lancement du thread d'enregistrement des données...")
    with app.app_context():
        while True:
            try:
                temp = round(sense.get_temperature(), 2)
                hum = round(sense.get_humidity(), 2)
                pres = round(sense.get_pressure(), 2)
                heat_idx = calculate_noaa_heat_index(temp, hum)
                
                db = sqlite3.connect(DB_FILE)
                cursor = db.cursor()
                cursor.execute(
                    """INSERT INTO sensor_readings 
                       (timestamp, temperature, humidity, pressure, heat_index) 
                       VALUES (?, ?, ?, ?, ?)""",
                    (datetime.now(), temp, hum, pres, heat_idx)
                )
                db.commit()
                db.close()
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Données météo enregistrées.")
            except Exception as e:
                print(f"Erreur dans boucle_enregistrement: {e}")
            time.sleep(300)

def boucle_gestion_alertes_led():
    """(Placeholder) Gère les alertes sur la matrice LED."""
    while True: time.sleep(60)


# --- Routes principales ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/templates/<path:filename>')
def serve_template_files(filename):
    return send_from_directory('templates', filename)

@app.route('/alldata')
def get_all_data():
    """Renvoie les dernières données météo lues en temps réel."""
    temp = round(sense.get_temperature(), 2)
    hum = round(sense.get_humidity(), 2)
    return jsonify({
        'temperature': temp,
        'humidite': hum,
        'pression': round(sense.get_pressure(), 2),
        'heat_index': calculate_noaa_heat_index(temp, hum)
    })

@app.route('/history')
def history():
    """Renvoie l'historique agrégé pour les graphiques."""
    period = request.args.get('period', 'day')
    formats = {
        'hour':    {'format': '%Y-%m-%d %H:%M', 'interval': '1 HOUR', 'label': '%H:%M'},
        '12hours': {'format': '%Y-%m-%d %H:%M', 'interval': '12 HOUR','label': '%H:%M'},
        'day':     {'format': '%Y-%m-%d %H:00', 'interval': '1 DAY',  'label': '%H:%M'},
        'week':    {'format': '%Y-%m-%d', 'interval': '7 DAY',  'label': '%d/%m'},
        'month':   {'format': '%Y-%m-%d', 'interval': '1 MONTH','label': '%d/%m'},
        'year':    {'format': '%Y-%m', 'interval': '1 YEAR', 'label': '%m/%Y'}
    }
    config = formats.get(period, formats['day'])
    query = f"""
        SELECT strftime('{config["label"]}', timestamp) as label,
            ROUND(AVG(temperature), 2) as temp, ROUND(AVG(humidity), 2) as hum,
            ROUND(AVG(pressure), 2) as pres, ROUND(AVG(heat_index), 2) as heat_index
        FROM sensor_readings WHERE timestamp >= DATETIME('now', '-{config["interval"]}')
        GROUP BY strftime('{config["format"]}', timestamp) ORDER BY timestamp ASC;
    """
    try:
        rows = get_db().execute(query).fetchall()
        return jsonify({
            'datetime': [row['label'] for row in rows], 'temp': [row['temp'] for row in rows],
            'hum': [row['hum'] for row in rows], 'pres': [row['pres'] for row in rows],
            'heat_index': [row['heat_index'] for row in rows]
        })
    except Exception as e:
        print(f"Erreur dans /history: {e}")
        return jsonify({"error": str(e)}), 500


# --- ROUTES POUR LES PLANTES ---

@app.route('/plants')
def get_plant_statuses():
    """Récupère la liste des plantes avec leur statut d'arrosage."""
    plants_query = "SELECT p.id, p.name, p.type, p.last_watered, pr.summer_weeks, pr.winter_weeks FROM plants p JOIN plant_rules pr ON p.type = pr.name"
    plants = get_db().execute(plants_query).fetchall()
    plant_list = []
    for plant in plants:
        plant_dict = dict(plant)
        last_watered = datetime.strptime(plant['last_watered'], '%Y-%m-%d').date()
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
    """Marque une plante comme arrosée et enregistre l'événement."""
    today_str = date.today().strftime('%Y-%m-%d')
    db = get_db()
    db.execute("UPDATE plants SET last_watered = ? WHERE id = ?", (today_str, plant_id))
    db.execute("INSERT INTO watering_history (plant_id, watering_date) VALUES (?, ?)", (plant_id, today_str))
    db.commit()
    return jsonify({'status': 'success'})

@app.route('/add_plant', methods=['POST'])
def add_plant():
    """Ajoute une nouvelle plante."""
    data = request.get_json()
    db = get_db()
    cursor = db.execute("INSERT INTO plants (name, type, last_watered) VALUES (?, ?, ?)",
                 (data['nom'].strip(), data['type'], date.today().strftime('%Y-%m-%d')))
    # Ajoute aussi un premier enregistrement dans l'historique
    db.execute("INSERT INTO watering_history (plant_id, watering_date) VALUES (?, ?)",
                 (cursor.lastrowid, date.today().strftime('%Y-%m-%d')))
    db.commit()
    return jsonify({'status': 'success', 'message': 'Plante ajoutée !'})

@app.route('/delete_plant/<int:plant_id>', methods=['POST'])
def delete_plant(plant_id):
    """Supprime une plante (et son historique grâce à 'ON DELETE CASCADE')."""
    db = get_db()
    db.execute("DELETE FROM plants WHERE id = ?", (plant_id,))
    db.commit()
    return jsonify({'status': 'success', 'message': 'Plante supprimée'})

# --- NOUVELLE ROUTE : Éditer une plante ---
@app.route('/edit_plant/<int:plant_id>', methods=['POST'])
def edit_plant(plant_id):
    """Met à jour le nom et le type d'une plante."""
    data = request.get_json()
    if not data or 'name' not in data or 'type' not in data:
        return jsonify({'status': 'error', 'message': 'Données manquantes'}), 400
    
    db = get_db()
    db.execute("UPDATE plants SET name = ?, type = ? WHERE id = ?", (data['name'], data['type'], plant_id))
    db.commit()
    return jsonify({'status': 'success', 'message': 'Plante mise à jour !'})

# --- NOUVELLE ROUTE : Obtenir l'historique d'arrosage d'une plante ---
@app.route('/plant_history/<int:plant_id>')
def get_plant_history(plant_id):
    """Récupère toutes les dates d'arrosage pour une plante."""
    history = get_db().execute(
        "SELECT watering_date FROM watering_history WHERE plant_id = ? ORDER BY watering_date DESC",
        (plant_id,)
    ).fetchall()
    return jsonify([row['watering_date'] for row in history])


# --- ROUTES POUR LES TYPES DE PLANTES ET RÈGLES ---

@app.route('/plant_types')
def get_plant_types():
    """Récupère la liste des noms de types de plantes."""
    types = get_db().execute("SELECT name FROM plant_rules ORDER BY name").fetchall()
    return jsonify([row['name'] for row in types])

@app.route('/plant_rules')
def get_plant_rules():
    """Récupère les règles d'arrosage pour chaque type."""
    rules = get_db().execute("SELECT name, summer_weeks, winter_weeks FROM plant_rules").fetchall()
    return jsonify({rule['name']: [rule['summer_weeks'], rule['winter_weeks']] for rule in rules})

@app.route('/add_plant_type', methods=['POST'])
def add_plant_type():
    """Crée ou modifie un type de plante."""
    data = request.get_json()
    db = get_db()
    db.execute("INSERT OR REPLACE INTO plant_rules (name, summer_weeks, winter_weeks) VALUES (?, ?, ?)",
                 (data['type_name'].lower().strip().replace(' ', '_'), int(data['summer_weeks']), int(data['winter_weeks'])))
    db.commit()
    return jsonify({'status': 'success', 'message': f"Type sauvegardé !"})


# --- ROUTES POUR LES ASTUCES ET RECOMMANDATIONS ---

@app.route('/tips')
def get_random_tip():
    """Renvoie une astuce aléatoire."""
    tip = get_db().execute("SELECT category, tip FROM tips ORDER BY RANDOM() LIMIT 1").fetchone()
    return jsonify({'category': tip['category'].capitalize(), 'tip': tip['tip']}) if tip else jsonify({'tip': 'Aucune astuce.'}), 404

@app.route('/tip_for_type/<plant_type>')
def get_tip_for_type(plant_type):
    """Renvoie une astuce pour un type de plante ou une astuce générale."""
    tip = get_db().execute("SELECT category, tip FROM tips WHERE category = ? OR category = 'general' ORDER BY RANDOM() LIMIT 1", (plant_type.lower(),)).fetchone()
    if not tip: return get_random_tip()
    return jsonify({'category': tip['category'].capitalize(), 'tip': tip['tip']})

# --- NOUVELLE ROUTE : Recommandation intelligente ---
@app.route('/smart_recommendation')
def get_smart_recommendation():
    """Génère une recommandation basée sur la météo ou une astuce générale."""
    try:
        temp = round(sense.get_temperature(), 2)
        
        if temp > 28:
            # Cherche une plante qui doit être arrosée dans les 2 prochains jours
            plants = get_db().execute("SELECT p.name, p.last_watered, pr.summer_weeks FROM plants p JOIN plant_rules pr ON p.type = pr.name").fetchall()
            for plant in plants:
                last_watered = datetime.strptime(plant['last_watered'], '%Y-%m-%d').date()
                days_since = (date.today() - last_watered).days
                interval_days = (plant['summer_weeks'] * 7)
                if days_since >= interval_days - 2: # Arrosage prévu dans 2 jours ou moins
                    return jsonify({
                        "icon": "fa-temperature-high",
                        "message": f"Forte chaleur aujourd'hui ! Pensez à vérifier la terre de votre <strong>{plant['name']}</strong>, elle pourrait avoir soif plus tôt que prévu."
                    })

        # Si aucune condition n'est remplie, renvoyer une astuce générale
        tip = get_db().execute("SELECT tip FROM tips WHERE category = 'general' ORDER BY RANDOM() LIMIT 1").fetchone()
        return jsonify({
            "icon": "fa-lightbulb",
            "message": tip['tip'] if tip else "Passez une excellente journée !"
        })
    except Exception as e:
        print(f"Erreur dans /smart_recommendation: {e}")
        return jsonify({"icon": "fa-info-circle", "message": "Vérifiez vos plantes régulièrement pour vous assurer qu'elles vont bien."})


# --- Démarrage de l'application ---
if __name__ == '__main__':
    # Démarrage des threads pour les tâches de fond
    threading.Thread(target=boucle_enregistrement, daemon=True).start()
    threading.Thread(target=boucle_gestion_alertes_led, daemon=True).start()
    # Lancement du serveur Flask
    app.run(host='0.0.0.0', port=5001)
