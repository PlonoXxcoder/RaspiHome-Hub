import os
import threading
import time
import requests
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, send_from_directory, render_template
from flask_sqlalchemy import SQLAlchemy
from threading import Lock

try:
    import config
except ImportError:
    print("❌ ERREUR: Le fichier config.py est manquant ou contient des erreurs.")
    exit()

# ======================= CONFIGURATION FINALE =======================

# En déclarant Flask comme ceci, il va AUTOMATIQUEMENT chercher :
# - Les templates HTML (comme index.html) dans un dossier nommé "templates"
# - Les fichiers statiques (CSS, JS) dans un dossier nommé "static"
app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///raspweatherplant.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- Variables globales ---
latest_sensor_data = {"weather": {}, "sensehat": {}, "esp32": {}}
data_lock = Lock()

# ======================= MODÈLES DE BASE DE DONNÉES =======================
# (Reste identique)
class PlantType(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    summer_freq = db.Column(db.Integer, nullable=False)
    winter_freq = db.Column(db.Integer, nullable=False)

class Plant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    last_watered = db.Column(db.DateTime, default=datetime.utcnow)
    type_id = db.Column(db.Integer, db.ForeignKey('plant_type.id'), nullable=False)
    plant_type = db.relationship('PlantType', backref=db.backref('plants', lazy=True))

class SensorData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    source = db.Column(db.String(20), nullable=False)
    temperature = db.Column(db.Float)
    humidity = db.Column(db.Float)
    pressure = db.Column(db.Float)

# ======================= FONCTIONS UTILITAIRES =======================
# (Reste identique)
def get_season(month):
    if month in (11, 12, 1, 2, 3, 4): return 'winter'
    return 'summer'

def calculate_watering_info(plant):
    days_since_watered = (datetime.utcnow() - plant.last_watered).days
    season = get_season(datetime.utcnow().month)
    frequency = plant.plant_type.summer_freq if season == 'summer' else plant.plant_type.winter_freq
    return {"days_since_watered": days_since_watered, "watering_frequency": frequency}

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': config.TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'Markdown'}
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200: print("✅ Notification Telegram envoyée.")
        else: print(f"❌ Erreur Telegram: {response.text}")
    except Exception as e: print(f"❌ Impossible d'envoyer la notification Telegram : {e}")

# ======================= THREADS D'ARRIÈRE-PLAN =======================
# (Reste identique)
def weather_thread_func():
    while True:
        try:
            url = (f"http://api.openweathermap.org/data/2.5/weather?"
                   f"lat={config.LATITUDE}&lon={config.LONGITUDE}"
                   f"&appid={config.API_KEY}&units=metric&lang=fr")
            
            response = requests.get(url)
            if response.status_code != 200:
                error_message = response.json().get('message', 'Erreur inconnue')
                print(f"❌ Erreur API Météo: {error_message}")
                time.sleep(300)
                continue
            
            data = response.json()
            with data_lock:
                latest_sensor_data["weather"] = {
                    "temperature": data['main']['temp'], "feels_like": data['main']['feels_like'],
                    "humidity": data['main']['humidity'], "pressure": data['main']['pressure'],
                    "description": data['weather'][0]['description'].capitalize(), "icon": data['weather'][0]['icon'],
                }
            with app.app_context():
                db.session.add(SensorData(source='weather', temperature=data['main']['temp'], humidity=data['main']['humidity'], pressure=data['main']['pressure']))
                db.session.commit()
            print("🌦️ Données météo enregistrées.")
        except Exception as e:
            print(f"❌ Exception dans le thread météo: {e}")
        time.sleep(900)

def notification_thread_func():
    time.sleep(60)
    while True:
        with app.app_context():
            plants_to_water = [p.name for p in Plant.query.all() if calculate_watering_info(p)["days_since_watered"] >= calculate_watering_info(p)["watering_frequency"]]
            if plants_to_water:
                send_telegram_message("💧 *Rappel d'arrosage !*\n- " + "\n- ".join(plants_to_water))
        time.sleep(3600)

# ======================= ROUTES DE L'API FLASK =======================

@app.route('/')
def serve_index():
    # Flask cherche maintenant index.html dans le dossier "templates" par défaut
    return render_template('index.html')

# Puisque vos fichiers CSS/JS sont aussi dans "templates", cette route est nécessaire
@app.route('/templates/<path:filename>')
def serve_template_files(filename):
    return send_from_directory('templates', filename)

# (Les autres routes ne changent pas)
@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/weather', methods=['GET'])
def get_weather_data():
    with data_lock: return jsonify(latest_sensor_data["weather"])

@app.route('/alldata', methods=['GET'])
def get_all_data():
    period = request.args.get('period', 'day')
    delta = timedelta(days={'day': 1, 'week': 7, 'month': 30}.get(period, 1))
    since = datetime.utcnow() - delta
    query = SensorData.query.filter(SensorData.timestamp >= since).order_by(SensorData.timestamp.asc()).all()
    labels = [d.timestamp.strftime('%d/%m %H:%M') for d in query]
    datasets = [{"label": "Température Météo (°C)", "data": [d.temperature for d in query if d.source == 'weather'], "borderColor": "#168AAD", "fill": False}]
    return jsonify({"labels": labels, "datasets": datasets})
    
@app.route('/smart_recommendation', methods=['GET'])
def get_smart_recommendation():
    return jsonify({"message": "Pensez à aérer la pièce si l'humidité intérieure est élevée.", "icon": "fa-lightbulb"})

@app.route('/esp32/data', methods=['POST'])
def receive_esp32_data():
    data = request.get_json()
    if not data or 'temperature' not in data or 'humidity' not in data:
        return jsonify({"error": "Données manquantes"}), 400
    with data_lock:
        latest_sensor_data["esp32"] = {"temperature": data['temperature'],"humidity": data['humidity'],"timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    print(f"✅ Données reçues de l'ESP32 : Temp={data['temperature']}°C, Hum={data['humidity']}%")
    return jsonify({"status": "success"}), 200

# (Les routes pour les plantes ne changent pas)
@app.route('/plants', methods=['GET', 'POST'])
def handle_plants():
    if request.method == 'GET':
        plants = Plant.query.all()
        return jsonify([{"id": p.id, "name": p.name, "type_name": p.plant_type.name, "type_id": p.type_id, "last_watered_date": p.last_watered.strftime('%Y-%m-%d'), **calculate_watering_info(p)} for p in plants])
    if request.method == 'POST':
        data = request.get_json()
        db.session.add(Plant(name=data['name'], type_id=data['type_id']))
        db.session.commit()
        return jsonify({"message": "Plante ajoutée"}), 201

@app.route('/plant/<int:plant_id>', methods=['GET', 'PUT', 'DELETE'])
def handle_plant(plant_id):
    plant = Plant.query.get_or_404(plant_id)
    if request.method == 'GET':
        return jsonify({"id": plant.id, "name": plant.name, "type_id": plant.type_id, "last_watered_date": plant.last_watered.strftime('%Y-%m-%d')})
    if request.method == 'PUT':
        data = request.get_json()
        plant.name, plant.type_id = data.get('name', plant.name), data.get('type_id', plant.type_id)
        if 'last_watered' in data: plant.last_watered = datetime.strptime(data['last_watered'], '%Y-%m-%d')
        db.session.commit()
        return jsonify({"message": "Plante mise à jour"})
    if request.method == 'DELETE':
        db.session.delete(plant), db.session.commit()
        return jsonify({"message": "Plante supprimée"})

@app.route('/plant/<int:plant_id>/water', methods=['POST'])
def water_plant(plant_id):
    plant = Plant.query.get_or_404(plant_id)
    plant.last_watered = datetime.utcnow()
    db.session.commit()
    return jsonify({"message": f"{plant.name} a été arrosée"})

@app.route('/plant_types', methods=['GET', 'POST'])
def handle_plant_types():
    if request.method == 'GET':
        return jsonify([{"id": t.id, "name": t.name} for t in PlantType.query.all()])
    if request.method == 'POST':
        data = request.get_json()
        summer_days, winter_days = int(data.get('summer_freq', 1)) * 7, int(data.get('winter_freq', 1)) * 7
        existing_type = PlantType.query.filter_by(name=data['name']).first()
        if existing_type:
            existing_type.summer_freq, existing_type.winter_freq = summer_days, winter_days
        else:
            db.session.add(PlantType(name=data['name'], summer_freq=summer_days, winter_freq=winter_days))
        db.session.commit()
        return jsonify({"message": "Type de plante sauvegardé"}), 201

# ======================= DÉMARRAGE DE L'APPLICATION =======================

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    print("🚀 Lancement du thread d'enregistrement météo...")
    threading.Thread(target=weather_thread_func, daemon=True).start()
    print("🚀 Lancement du thread de notification d'arrosage...")
    threading.Thread(target=notification_thread_func, daemon=True).start()
    print("🚀 Lancement du serveur Flask sur http://0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)
