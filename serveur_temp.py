import os
import threading
import time
import requests
import random
from datetime import datetime, timedelta, date
from flask import Flask, jsonify, request, render_template, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from threading import Lock

# --- 1. IMPORTS ET CONFIGURATION ---
try:
    import config
except ImportError:
    print("❌ ERREUR: Le fichier config.py est manquant.")
    exit()

try:
    from sense_hat import SenseHat
    sense = SenseHat()
    print("✅ Sense HAT détecté.")
except (ImportError, OSError):
    sense = None
    print("⚠️ AVERTISSEMENT: Sense HAT non détecté.")

app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'raspihome.db')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

latest_sensor_data = {"weather": {}, "sensehat": {}, "esp32": {}}
data_lock = Lock()

# ======================= 2. MODÈLES DE BASE DE DONNÉES (Adaptés à votre structure) =======================
class PlantRule(db.Model):
    __tablename__ = 'plant_rules'
    name = db.Column(db.Text, primary_key=True)
    summer_weeks = db.Column(db.Integer, nullable=False)
    winter_weeks = db.Column(db.Integer, nullable=False)

class Plant(db.Model):
    __tablename__ = 'plants'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    type = db.Column(db.Text, db.ForeignKey('plant_rules.name'), nullable=False)
    plant_rule = db.relationship('PlantRule', backref=db.backref('plants', lazy=True))

class WateringHistory(db.Model):
    __tablename__ = 'watering_history'
    id = db.Column(db.Integer, primary_key=True)
    plant_id = db.Column(db.Integer, db.ForeignKey('plants.id'), nullable=False)
    watering_date = db.Column(db.Date, nullable=False, default=date.today)

class SensorReading(db.Model):
    __tablename__ = 'sensor_readings'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    source = db.Column(db.String(20))
    temperature = db.Column(db.Float)
    humidity = db.Column(db.Float)
    pressure = db.Column(db.Float)

class Tip(db.Model):
    __tablename__ = 'tips'
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.Text)
    tip = db.Column(db.Text)

# ======================= 3. FONCTIONS UTILITAIRES =======================
def get_season(month):
    return 'winter' if month in (11, 12, 1, 2, 3, 4) else 'summer'

def calculate_watering_info(plant):
    last_watering_record = WateringHistory.query.filter_by(plant_id=plant.id).order_by(WateringHistory.watering_date.desc()).first()
    if not last_watering_record:
        days_since_watered = 999
    else:
        days_since_watered = (date.today() - last_watering_record.watering_date).days
    season = get_season(datetime.utcnow().month)
    if plant.plant_rule:
        frequency_weeks = plant.plant_rule.summer_weeks if season == 'summer' else plant.plant_rule.winter_weeks
    else:
        frequency_weeks = 2 # Valeur par défaut si la règle n'est pas trouvée
    return {"days_since_watered": days_since_watered, "watering_frequency": frequency_weeks * 7}

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': config.TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'Markdown'}
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200: print("✅ Notification Telegram envoyée.")
        else: print(f"❌ Erreur Telegram: {response.text}")
    except Exception as e:
        print(f"❌ Impossible d'envoyer la notification Telegram : {e}")

# ======================= 4. THREADS D'ARRIÈRE-PLAN =======================
def weather_thread_func():
    while True:
        try:
            url = f"http://api.openweathermap.org/data/2.5/weather?lat={config.LATITUDE}&lon={config.LONGITUDE}&appid={config.API_KEY}&units=metric&lang=fr"
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                print(f"❌ Erreur API Météo: {response.json().get('message', 'Erreur inconnue')}")
                time.sleep(300); continue
            data = response.json()
            with data_lock:
                latest_sensor_data["weather"] = {"temperature": data['main']['temp'], "feels_like": data['main']['feels_like'], "humidity": data['main']['humidity'], "pressure": data['main']['pressure'], "description": data['weather'][0]['description'].capitalize(), "icon": data['weather'][0]['icon']}
            with app.app_context():
                db.session.add(SensorReading(source='weather', temperature=data['main']['temp'], humidity=data['main']['humidity'], pressure=data['main']['pressure']))
                db.session.commit()
        except Exception as e:
            print(f"❌ Exception dans le thread météo: {e}")
        time.sleep(900)

def sensehat_thread_func():
    while True:
        if sense:
            temp, humidity, pressure = sense.get_temperature(), sense.get_humidity(), sense.get_pressure()
            cpu_temp_str = os.popen("vcgencmd measure_temp").readline()
            cpu_temp = float(cpu_temp_str.replace("temp=", "").replace("'C\n", ""))
            temp = temp - ((cpu_temp - temp) / 2.5)
        else:
            temp, humidity, pressure = 25.0, 45.0, 1012.0
        with data_lock:
            latest_sensor_data["sensehat"] = {"temperature": temp, "humidity": humidity, "pressure": pressure, "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        with app.app_context():
            db.session.add(SensorReading(source='sensehat', temperature=temp, humidity=humidity, pressure=pressure))
            db.session.commit()
        time.sleep(60)

def notification_thread_func():
    time.sleep(60)
    while True:
        with app.app_context():
            plants_to_water = [p.name for p in Plant.query.all() if calculate_watering_info(p)["days_since_watered"] >= calculate_watering_info(p)["watering_frequency"]]
            if plants_to_water:
                send_telegram_message("💧 *Rappel d'arrosage !*\n- " + "\n- ".join(plants_to_water))
        time.sleep(3600)

# ======================= 5. ROUTES DE L'API FLASK =======================
@app.route('/')
def serve_index():
    return render_template('index.html')

@app.route('/templates/<path:filename>')
def serve_template_files(filename):
    return send_from_directory('templates', filename)

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/weather')
def get_weather_data():
    with data_lock: return jsonify(latest_sensor_data.get("weather", {}))

@app.route('/sensehat_latest')
def get_sensehat_latest():
    with data_lock: return jsonify(latest_sensor_data.get("sensehat", {}))

@app.route('/esp32_latest')
def get_esp32_latest():
    with data_lock: return jsonify(latest_sensor_data.get("esp32", {}))

@app.route('/esp32/data', methods=['POST'])
def receive_esp32_data():
    data = request.get_json()
    if not data or 'temperature' not in data or 'humidity' not in data:
        return jsonify({"error": "Données manquantes"}), 400
    with data_lock:
        latest_sensor_data["esp32"] = {"temperature": data['temperature'], "humidity": data['humidity'], "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    with app.app_context():
        db.session.add(SensorReading(source='esp32', temperature=data['temperature'], humidity=data['humidity']))
        db.session.commit()
    print(f"✅ Données reçues de l'ESP32: {data}")
    return jsonify({"status": "success"}), 200

@app.route('/alldata', methods=['GET'])
def get_all_data():
    period = request.args.get('period', 'day')
    if period == 'week':
        delta = timedelta(days=7)
    elif period == 'month':
        delta = timedelta(days=30)
    else:
        delta = timedelta(days=1)
    since = datetime.utcnow() - delta

    sensehat_readings = SensorReading.query.filter(SensorReading.source == 'sensehat', SensorReading.timestamp >= since).order_by(SensorReading.timestamp.asc()).all()
    esp32_readings = SensorReading.query.filter(SensorReading.source == 'esp32', SensorReading.timestamp >= since).order_by(SensorReading.timestamp.asc()).all()

    datasets = [
        {"label": "Temp. Intérieure (°C)", "data": [{"x": r.timestamp.isoformat(), "y": r.temperature} for r in sensehat_readings], "borderColor": "#ef476f", "fill": False, "yAxisID": "y_temp"},
        {"label": "Temp. SDB (°C)", "data": [{"x": r.timestamp.isoformat(), "y": r.temperature} for r in esp32_readings], "borderColor": "#fca311", "fill": False, "yAxisID": "y_temp"},
        {"label": "Hum. Intérieure (%)", "data": [{"x": r.timestamp.isoformat(), "y": r.humidity} for r in sensehat_readings], "borderColor": "#06d6a0", "fill": False, "yAxisID": "y_hum"},
        {"label": "Hum. SDB (%)", "data": [{"x": r.timestamp.isoformat(), "y": r.humidity} for r in esp32_readings], "borderColor": "#118ab2", "fill": False, "yAxisID": "y_hum"},
    ]
    return jsonify({"datasets": datasets})

@app.route('/plants', methods=['GET'])
def get_plants():
    plants = Plant.query.all()
    plants_data = []
    for p in plants:
        info = calculate_watering_info(p)
        plants_data.append({"id": p.id, "name": p.name, "type_name": p.type, "type_id": p.type, **info})
    return jsonify(plants_data)

@app.route('/plant_types', methods=['GET'])
def get_plant_types():
    types = PlantRule.query.all()
    return jsonify([{"id": t.name, "name": t.name} for t in types])

@app.route('/plant/<int:plant_id>/water', methods=['POST'])
def water_plant(plant_id):
    new_watering = WateringHistory(plant_id=plant_id, watering_date=date.today())
    db.session.add(new_watering)
    db.session.commit()
    return jsonify({"message": "Arrosage enregistré"})

@app.route('/smart_recommendation', methods=['GET'])
def get_smart_recommendation():
    with app.app_context():
        plants_to_water = [p.name for p in Plant.query.all() if calculate_watering_info(p)["days_since_watered"] >= calculate_watering_info(p)["watering_frequency"]]
        if plants_to_water:
            message = f"Rappel : Il est temps d'arroser {', '.join(plants_to_water)} !"
            icon = "fa-tint"
        else:
            random_tip = Tip.query.order_by(func.random()).first()
            message = random_tip.tip if random_tip else "Pensez à vérifier vos plantes aujourd'hui."
            icon = "fa-lightbulb"
    return jsonify({"message": message, "icon": icon})

@app.route('/random_tip', methods=['GET'])
def get_random_tip():
    random_tip = Tip.query.order_by(func.random()).first()
    message = random_tip.tip if random_tip else "Pensez à vérifier vos plantes aujourd'hui."
    icon = "fa-lightbulb"
    return jsonify({"message": message, "icon": icon})

@app.route('/refresh/all', methods=['POST'])
def refresh_all_sensors():
    try:
        url = f"http://api.openweathermap.org/data/2.5/weather?lat={config.LATITUDE}&lon={config.LONGITUDE}&appid={config.API_KEY}&units=metric&lang=fr"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            with data_lock:
                latest_sensor_data["weather"] = {"temperature": data['main']['temp'], "feels_like": data['main']['feels_like'], "humidity": data['main']['humidity'], "pressure": data['main']['pressure'], "description": data['weather'][0]['description'].capitalize(), "icon": data['weather'][0]['icon']}
            print("🔄 Météo rafraîchie manuellement.")
    except Exception as e:
        print(f"❌ Erreur de rafraîchissement manuel de la météo: {e}")
    if sense:
        temp, humidity, pressure = sense.get_temperature(), sense.get_humidity(), sense.get_pressure()
        cpu_temp_str = os.popen("vcgencmd measure_temp").readline()
        cpu_temp = float(cpu_temp_str.replace("temp=", "").replace("'C\n", ""))
        temp_corrected = temp - ((cpu_temp - temp) / 2.5)
        with data_lock:
            latest_sensor_data["sensehat"] = {"temperature": temp_corrected, "humidity": humidity, "pressure": pressure, "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        print("🔄 Sense HAT rafraîchi manuellement.")
    try:
        esp32_url = f"http://{config.ESP32_IP}/read_sensor"
        response = requests.get(esp32_url, timeout=5)
        if response.status_code == 200:
            print("🔄 Ordre de lecture envoyé à l'ESP32.")
    except Exception as e:
        print(f"❌ Impossible de contacter l'ESP32 pour rafraîchissement: {e}")
    time.sleep(2)
    with data_lock:
        return jsonify(latest_sensor_data)

# ======================= 6. DÉMARRAGE =======================
if __name__ == '__main__':
    # On ne lance PAS db.create_all() pour ne pas interférer avec la base existante.
    print("🚀 Lancement du thread d'enregistrement météo...")
    threading.Thread(target=weather_thread_func, daemon=True).start()
    print("🚀 Lancement du thread de lecture du Sense HAT...")
    threading.Thread(target=sensehat_thread_func, daemon=True).start()
    print("🚀 Lancement du thread de notification d'arrosage...")
    threading.Thread(target=notification_thread_func, daemon=True).start()
    print("🚀 Lancement du serveur Flask sur http://0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)
