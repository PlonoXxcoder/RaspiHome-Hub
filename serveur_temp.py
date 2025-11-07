import os
import threading
import time
import requests
import random
from datetime import datetime, timedelta, date
from flask import Flask, jsonify, request, render_template, send_from_directory, flash, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from threading import Lock
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# --- 1. IMPORTS ET CONFIGURATION ---
try:
    import config
except ImportError:
    print("❌ ERREUR: Le fichier config.py est manquant.")
    exit()

try:
    from astral.sun import sun
    from astral import LocationInfo
except ImportError:
    sun, LocationInfo = None, None
    print("⚠️ AVERTISSEMENT: 'astral' non installé. Les zones nuit/jour seront désactivées.")

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
# Utilisation de votre clé secrète
app.secret_key = 'jhfyipHTKLPJ35O5e6blRN285zbkpu9MocCKsdeu3ClNRoj68AfgEqOgMZ4n14LJO7774YQ5m0g3haNfLMfA7Q=='

# --- Configuration de Flask-Login ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

db = SQLAlchemy(app)

latest_sensor_data = {"weather": {}, "sensehat": {}, "esp32": {}}
data_lock = Lock()

TEMP_IDEAL_MIN = 18.0
TEMP_IDEAL_MAX = 25.0

# ======================= 2. MODÈLES DE BASE DE DONNÉES =======================
class PlantRule(db.Model): #
    __tablename__ = 'plant_rules'
    name = db.Column(db.Text, primary_key=True)
    summer_weeks = db.Column(db.Integer, nullable=False)
    winter_weeks = db.Column(db.Integer, nullable=False)

class Plant(db.Model): #
    __tablename__ = 'plants'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    type = db.Column(db.Text, db.ForeignKey('plant_rules.name'), nullable=False)
    last_watered = db.Column(db.Text, nullable=False, default=lambda: date.today().isoformat())
    plant_rule = db.relationship('PlantRule', backref=db.backref('plants', lazy=True))

class WateringHistory(db.Model): #
    __tablename__ = 'watering_history'
    id = db.Column(db.Integer, primary_key=True)
    plant_id = db.Column(db.Integer, db.ForeignKey('plants.id'), nullable=False)
    watering_date = db.Column(db.Date, nullable=False, default=date.today)

class SensorReading(db.Model): #
    __tablename__ = 'sensor_readings'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    source = db.Column(db.String(20))
    temperature = db.Column(db.Float)
    humidity = db.Column(db.Float)
    pressure = db.Column(db.Float)

class Tip(db.Model): #
    __tablename__ = 'tips'
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.Text)
    tip = db.Column(db.Text)

class User(UserMixin, db.Model): #
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)

# --- NOUVEAU MODÈLE V1.5 ---
class Task(db.Model):
    __tablename__ = 'tasks'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    frequency_days = db.Column(db.Integer, nullable=False, default=7)
    last_completed = db.Column(db.Date, nullable=False, default=date.today)
# -----------------------------

# --- CORRECTION ALERTE SQLALCHEMY V1.6 ---
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id)) # Remplace User.query.get()

# ======================= 3. FONCTIONS UTILITAIRES & THREADS =======================
def get_season(month): #
    return 'winter' if month in (11, 12, 1, 2, 3, 4) else 'summer'

def calculate_watering_info(plant): #
    last_watering_record = WateringHistory.query.filter_by(plant_id=plant.id).order_by(WateringHistory.watering_date.desc()).first()
    days_since_watered = (date.today() - last_watering_record.watering_date).days if last_watering_record else 999
    season = get_season(datetime.utcnow().month)
    frequency_weeks = plant.plant_rule.summer_weeks if plant.plant_rule else 2
    return {"days_since_watered": days_since_watered, "watering_frequency": frequency_weeks * 7}

# --- NOUVELLE FONCTION V1.5 ---
def calculate_task_info(task):
    days_since_completed = (date.today() - task.last_completed).days
    frequency = task.frequency_days
    # Calcule l'urgence : 100% = juste fait, 0% = à faire
    urgency_percentage = max(0, 100 - (days_since_completed / frequency) * 100)
    return {
        "days_since_completed": days_since_completed,
        "frequency_days": frequency,
        "urgency_percentage": urgency_percentage,
        "is_due": days_since_completed >= frequency
    }
# ------------------------------

def send_telegram_message(message): #
    for chat_id in getattr(config, 'TELEGRAM_CHAT_IDS', []):
        url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"
        payload = {'chat_id': chat_id, 'text': message, 'parse_mode': 'Markdown'}
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                print(f"✅ Notification Telegram envoyée à {chat_id}.")
            else:
                print(f"❌ Erreur Telegram pour {chat_id}: {response.text}")
        except Exception as e:
            print(f"❌ Impossible d'envoyer la notification Telegram à {chat_id} : {e}")

def weather_thread_func(): #
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

def sensehat_thread_func(): #
    while True:
        if sense:
            temp, humidity, pressure = sense.get_temperature(), sense.get_humidity(), sense.get_pressure()
            if temp > 0 and humidity > 0:
                cpu_temp_str = os.popen("vcgencmd measure_temp").readline()
                cpu_temp = float(cpu_temp_str.replace("temp=", "").replace("'C\n", ""))
                temp = temp - ((cpu_temp - temp) / 2.5)
            else:
                print(f"⚠️ Lecture aberrante du Sense HAT ignorée (Temp: {temp}, Hum: {humidity})")
                time.sleep(60); continue
        else:
            temp, humidity, pressure = 25.0, 45.0, 1012.0
        with data_lock:
            latest_sensor_data["sensehat"] = {"temperature": temp, "humidity": humidity, "pressure": pressure, "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        with app.app_context():
            db.session.add(SensorReading(source='sensehat', temperature=temp, humidity=humidity, pressure=pressure))
            db.session.commit()
        time.sleep(60)

# --- MIS À JOUR V1.5 ---
def notification_thread_func(): #
    time.sleep(60)
    while True:
        with app.app_context():
            # 1. Plantes
            plants_to_water = [p.name for p in Plant.query.all() if calculate_watering_info(p)["days_since_watered"] >= calculate_watering_info(p)["watering_frequency"]]
            if plants_to_water:
                send_telegram_message("💧 *Rappel d'arrosage !*\n- " + "\n- ".join(plants_to_water))
            
            # 2. Tâches
            overdue_tasks = [t.name for t in Task.query.all() if calculate_task_info(t)["is_due"]]
            if overdue_tasks:
                send_telegram_message("🧹 *Rappel de tâches !*\n- " + "\n- ".join(overdue_tasks))
                
        time.sleep(3600) # Vérifie toutes les heures
# -------------------------

def send_startup_notification(): #
    ngrok_url = None
    attempts, max_attempts = 0, 6
    while attempts < max_attempts and not ngrok_url:
        attempts += 1
        print(f"   Tentative {attempts}/{max_attempts} de récupération de l'URL Ngrok...")
        try:
            response = requests.get("http://127.0.0.1:4040/api/tunnels", timeout=2)
            if response.status_code == 200:
                for tunnel in response.json()['tunnels']:
                    if tunnel['proto'] == 'https': ngrok_url = tunnel['public_url']; break
        except requests.exceptions.ConnectionError: pass
        except Exception as e: print(f"   ❌ Erreur inattendue: {e}")
        if not ngrok_url: time.sleep(5)
    if ngrok_url: print(f"✅ URL Ngrok trouvée : {ngrok_url}")
    else: print("⚠️ AVERTISSEMENT: Le tunnel Ngrok n'a pas pu être contacté.")
    pi_ip = getattr(config, 'PI_IP', 'VOTRE_IP_LOCALE') 
    message = f"🚀 *Le serveur RaspiHome a démarré !*\n\n🏠 **Accès Local :** `http://{pi_ip}:5000`\n"
    message += f"🌍 **Accès Public :** {ngrok_url}" if ngrok_url else "⚠️ Le tunnel d'accès public (Ngrok) n'est pas disponible."
    send_telegram_message(message)

# ======================= 4. ROUTES D'AUTHENTIFICATION =======================
@app.route('/login', methods=['GET', 'POST']) #
def login():
    if current_user.is_authenticated:
        return redirect(url_for('serve_index'))
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and user.check_password(request.form.get('password')):
            login_user(user)
            return redirect(url_for('serve_index'))
        flash("Nom d'utilisateur ou mot de passe invalide.")
    return render_template('login.html')

@app.route('/logout') #
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ======================= 5. ROUTES DE L'APPLICATION (PROTÉGÉES) =======================
@app.route('/') #
@login_required
def serve_index():
    return render_template('index.html')

@app.route('/templates/<path:filename>') #
@login_required
def serve_template_files(filename):
    return send_from_directory('templates', filename)

@app.route('/favicon.ico') #
def favicon():
    return '', 204

@app.route('/weather') #
@login_required
def get_weather_data():
    with data_lock:
        return jsonify(latest_sensor_data.get("weather", {}))

@app.route('/sensehat_latest') #
@login_required
def get_sensehat_latest():
    with data_lock:
        return jsonify(latest_sensor_data.get("sensehat", {}))

@app.route('/esp32_latest') #
@login_required
def get_esp32_latest():
    with data_lock:
        return jsonify(latest_sensor_data.get("esp32", {}))

@app.route('/esp32/data', methods=['POST']) #
def receive_esp32_data(): # Pas de @login_required ici
    data = request.get_json()
    if not data or 'temperature' not in data or 'humidity' not in data:
        return jsonify({"error": "Données manquantes"}), 400
    with data_lock:
        latest_sensor_data["esp32"] = {"temperature": data['temperature'],"humidity": data['humidity'],"timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    with app.app_context():
        db.session.add(SensorReading(source='esp32', temperature=data['temperature'], humidity=data['humidity']))
        db.session.commit()
    return jsonify({"status": "success"}), 200

# --- MODIFIÉ V1.6 : Logique de période étendue ---
@app.route('/alldata', methods=['GET']) #
@login_required
def get_all_data():
    period = request.args.get('period', '24h') # Valeur par défaut : 24h
    
    # Logique pour définir le delta en fonction de la période
    if period == '8h':
        delta = timedelta(hours=8)
    elif period == '2d':
        delta = timedelta(days=2)
    elif period == '7d':
        delta = timedelta(days=7)
    elif period == '30d':
        delta = timedelta(days=30)
    else: # '24h' ou tout autre cas
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
# -------------------------------------------------

@app.route('/config_data') #
@login_required
def get_config_data():
    response_data = {"sunrise": None, "sunset": None, "temp_ideal_min": TEMP_IDEAL_MIN, "temp_ideal_max": TEMP_IDEAL_MAX}
    if LocationInfo and sun:
        try:
            city = LocationInfo("MyCity", "MyRegion", "Europe/Paris", config.LATITUDE, config.LONGITUDE)
            s = sun(city.observer, date=datetime.now())
            response_data["sunrise"], response_data["sunset"] = s['sunrise'].isoformat(), s['sunset'].isoformat()
        except Exception as e:
            print(f"⚠️ AVERTISSEMENT: Impossible de calculer les données astrales : {e}")
    return jsonify(response_data)

@app.route('/plants', methods=['GET', 'POST']) #
@login_required
def handle_plants():
    if request.method == 'GET':
        plants = Plant.query.all()
        plants_data = [ {"id": p.id, "name": p.name, "type_name": p.type, "type_id": p.type, **calculate_watering_info(p)} for p in plants]
        return jsonify(plants_data)
    
    if request.method == 'POST':
        data = request.get_json()
        if not data:
            return jsonify({"error": "Données invalides"}), 400

        # Logique pour gérer l'ajout d'un nouveau type EN MÊME TEMPS que la plante
        plant_type_name = data.get('type_name')
        if data.get('is_new_type') == True:
            if not plant_type_name or not data.get('summer_weeks') or not data.get('winter_weeks'):
                return jsonify({"error": "Données de nouveau type manquantes"}), 400
            
            existing_type = PlantRule.query.filter_by(name=plant_type_name).first()
            if not existing_type:
                new_rule = PlantRule(
                    name=plant_type_name,
                    summer_weeks=data['summer_weeks'],
                    winter_weeks=data['winter_weeks']
                )
                db.session.add(new_rule)
        
        # Ajout de la plante
        if not data.get('name') or not plant_type_name:
            return jsonify({"error": "Nom de plante ou type manquant"}), 400
            
        new_plant = Plant(name=data['name'], type=plant_type_name)
        db.session.add(new_plant)
        db.session.commit() # Commit de la plante et de la nouvelle règle (si applicable)

        # Gérer la date de prochain arrosage (transformée en "dernier arrosage")
        try:
            next_watering_date = date.fromisoformat(data.get('next_watering_date'))
            rule = PlantRule.query.get(plant_type_name)
            season = get_season(datetime.utcnow().month)
            frequency_weeks = rule.summer_weeks if season == 'summer' else rule.winter_weeks
            frequency_days = frequency_weeks * 7
            
            last_watered_date = next_watering_date - timedelta(days=frequency_days)
            
        except (TypeError, ValueError):
            last_watered_date = date.today()

        initial_watering = WateringHistory(plant_id=new_plant.id, watering_date=last_watered_date)
        db.session.add(initial_watering)
        db.session.commit()
        
        return jsonify({"message": "Plante ajoutée avec succès"}), 201


@app.route('/plant/<int:plant_id>', methods=['GET', 'PUT', 'DELETE']) #
@login_required
def handle_plant(plant_id):
    plant = Plant.query.get_or_404(plant_id)
    if request.method == 'GET':
        last_watering_record = WateringHistory.query.filter_by(plant_id=plant.id).order_by(WateringHistory.watering_date.desc()).first()
        last_watered_date = last_watering_record.watering_date.isoformat() if last_watering_record else date.today().isoformat()
        return jsonify({"id": plant.id, "name": plant.name, "type_id": plant.type, "last_watered_date": last_watered_date})
    if request.method == 'PUT':
        data = request.get_json()
        plant.name = data.get('name', plant.name)
        plant.type = data.get('type', plant.type)
        db.session.commit()
        return jsonify({"message": "Plante mise à jour avec succès"})
    if request.method == 'DELETE':
        WateringHistory.query.filter_by(plant_id=plant_id).delete()
        db.session.delete(plant)
        db.session.commit()
        return jsonify({"message": "Plante supprimée avec succès"})

@app.route('/plant/<int:plant_id>/water', methods=['POST']) #
@login_required
def water_plant(plant_id):
    new_watering = WateringHistory(plant_id=plant_id, watering_date=date.today())
    db.session.add(new_watering)
    db.session.commit()
    return jsonify({"message": "Arrosage enregistré"})

@app.route('/plant_types', methods=['GET', 'POST']) #
@login_required
def handle_plant_types():
    if request.method == 'GET':
        types = PlantRule.query.all()
        return jsonify([{"id": t.name, "name": t.name} for t in types])
    if request.method == 'POST':
        data = request.get_json()
        if not data or not data.get('name') or not data.get('summer_weeks') or not data.get('winter_weeks'):
            return jsonify({"error": "Données manquantes"}), 400
        existing_type = PlantRule.query.filter_by(name=data['name']).first()
        if existing_type:
            existing_type.summer_weeks = data['summer_weeks']
            existing_type.winter_weeks = data['winter_weeks']
        else:
            db.session.add(PlantRule(name=data['name'], summer_weeks=data['summer_weeks'], winter_weeks=data['winter_weeks']))
        db.session.commit()
        return jsonify({"message": "Type de plante sauvegardé"})

# --- NOUVELLES ROUTES TÂCHES V1.5 ---
@app.route('/tasks', methods=['GET'])
@login_required
def get_tasks():
    tasks = Task.query.all()
    tasks_data = []
    for task in tasks:
        tasks_data.append({
            "id": task.id,
            "name": task.name,
            **calculate_task_info(task)
        })
    # Trier pour afficher les tâches urgentes en premier
    tasks_data.sort(key=lambda x: x['urgency_percentage'])
    return jsonify(tasks_data)

@app.route('/tasks', methods=['POST'])
@login_required
def add_task():
    data = request.get_json()
    if not data or not data.get('name') or not data.get('frequency_days'):
        return jsonify({"error": "Données manquantes"}), 400
    
    new_task = Task(
        name=data['name'],
        frequency_days=int(data['frequency_days']),
        last_completed=date.today() # Par défaut, on considère qu'elle vient d'être faite
    )
    db.session.add(new_task)
    db.session.commit()
    return jsonify({"message": "Tâche ajoutée avec succès"}), 201

@app.route('/task/<int:task_id>/complete', methods=['POST'])
@login_required
def complete_task(task_id):
    task = Task.query.get_or_404(task_id)
    task.last_completed = date.today()
    db.session.commit()
    return jsonify({"message": "Tâche marquée comme terminée"})

@app.route('/task/<int:task_id>', methods=['DELETE'])
@login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    return jsonify({"message": "Tâche supprimée avec succès"})
# -----------------------------------

# --- MODIFIÉ V1.6 : Logique des astuces séparée ---
@app.route('/smart_recommendation', methods=['GET']) #
@login_required
def get_smart_recommendation():
    with app.app_context():
        now = datetime.now()
        day_of_week = now.weekday()
        current_hour = now.hour

        # Priorité 1 : Alerte Chauffage
        interior_temp = None
        with data_lock:
            interior_temp = latest_sensor_data.get("sensehat", {}).get("temperature")
        
        if interior_temp:
            is_evening_or_weekend = (current_hour >= 19) or (day_of_week >= 5)
            if interior_temp < TEMP_IDEAL_MIN and is_evening_or_weekend:
                message = f"Température intérieure basse ({interior_temp:.1f}°C). Pensez à allumer le chauffage."
                icon = "fa-solid fa-fire"
                return jsonify({"message": message, "icon": icon})

        # Priorité 2 : Plantes à arroser
        plants_to_water = [p.name for p in Plant.query.all() if calculate_watering_info(p)["days_since_watered"] >= calculate_watering_info(p)["watering_frequency"]]
        if plants_to_water:
            message, icon = f"Rappel : Il est temps d'arroser {', '.join(plants_to_water)} !", "fa-tint"
            return jsonify({"message": message, "icon": icon})

        # Priorité 3 : Tâches en retard
        overdue_tasks = [t.name for t in Task.query.all() if calculate_task_info(t)["is_due"]]
        if overdue_tasks:
            message, icon = f"Rappel : Tâches en retard : {', '.join(overdue_tasks)} !", "fa-broom"
            return jsonify({"message": message, "icon": icon})

        # Priorité 4 : Astuce aléatoire
        random_tip = Tip.query.order_by(func.random()).first()
        message = random_tip.tip if random_tip else "Pensez à vérifier vos plantes aujourd'hui."
        icon = "fa-lightbulb"
        return jsonify({"message": message, "icon": icon})
# ----------------------------------------------------

# --- NOUVELLE ROUTE V1.6 : Astuces Météo Contextuelles ---
@app.route('/weather_tip', methods=['GET'])
@login_required
def get_weather_tip():
    
    # Seuil d'humidité pour l'alerte
    HUMIDITY_ALERT_THRESHOLD = 75.0
    
    # On se concentre uniquement sur les données de l'ESP32
    with data_lock:
        esp32_data = latest_sensor_data.get("esp32", {})
        esp32_hum = esp32_data.get("humidity")
        esp32_temp = esp32_data.get("temperature")

    # Cas 1 : Données ESP32 non encore disponibles
    if not esp32_hum or not esp32_temp:
        message = "En attente des données du capteur salle de bain..."
        icon = "fa-solid fa-satellite-dish"
        return jsonify({"message": message, "icon": icon})

    # Cas 2 : Humidité élevée (Alerte)
    if esp32_hum > HUMIDITY_ALERT_THRESHOLD:
        message = f"L'humidité de la salle de bain est élevée ({esp32_hum:.0f}%). Pensez à aérer."
        icon = "fa-solid fa-wind"
        return jsonify({"message": message, "icon": icon})

    # Cas 3 : Humidité normale (Message de confirmation)
    message = f"Humidité SDB : {esp32_hum:.0f}%. Température : {esp32_temp:.1f}°C. Tout est normal."
    icon = "fa-solid fa-bath" # Icône de salle de bain
    return jsonify({"message": message, "icon": icon})
# ------------------------------------------------------
# --------------------------------------------------------

@app.route('/random_tip', methods=['GET']) #
@login_required
def get_random_tip():
    random_tip = Tip.query.order_by(func.random()).first()
    message = random_tip.tip if random_tip else "Pensez à vérifier vos plantes aujourd'hui."
    icon = "fa-lightbulb"
    return jsonify({"message": message, "icon": icon})

@app.route('/refresh/all', methods=['POST']) #
@login_required
def refresh_all_sensors():
    try:
        url = f"http://api.openweathermap.org/data/2.5/weather?lat={config.LATITUDE}&lon={config.LONGITUDE}&appid={config.API_KEY}&units=metric&lang=fr"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json(); print("🔄 Météo rafraîchie manuellement.")
            with data_lock: latest_sensor_data["weather"] = {"temperature": data['main']['temp'], "feels_like": data['main']['feels_like'], "humidity": data['main']['humidity'], "pressure": data['main']['pressure'], "description": data['weather'][0]['description'].capitalize(), "icon": data['weather'][0]['icon']}
    except Exception as e: print(f"❌ Erreur de rafraîchissement manuel de la météo: {e}")
    if sense:
        temp, hum, pres = sense.get_temperature(), sense.get_humidity(), sense.get_pressure()
        cpu_temp_str = os.popen("vcgencmd measure_temp").readline()
        cpu_temp = float(cpu_temp_str.replace("temp=", "").replace("'C\n", ""))
        temp_corr = temp - ((cpu_temp - temp) / 2.5)
        with data_lock: latest_sensor_data["sensehat"] = {"temperature": temp_corr, "humidity": hum, "pressure": pres, "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        print("🔄 Sense HAT rafraîchi manuellement.")
    try:
        esp32_url = f"http://{config.ESP32_IP}/read_sensor"
        response = requests.get(esp32_url, timeout=5)
        if response.status_code == 200: print("🔄 Ordre de lecture envoyé à l'ESP32.")
    except Exception as e: print(f"❌ Impossible de contacter l'ESP32 pour rafraîchissement: {e}")
    time.sleep(2)
    with data_lock:
        return jsonify(latest_sensor_data)

# ======================= 6. DÉMARRAGE =======================
if __name__ == '__main__':
    with app.app_context():
        # db.create_all() # Décommentez ceci UNE SEULE FOIS si vous ajoutez de nouvelles tables
        pass
    print("🚀 Lancement du thread d'enregistrement météo...")
    threading.Thread(target=weather_thread_func, daemon=True).start()
    print("🚀 Lancement du thread de lecture du Sense HAT...")
    threading.Thread(target=sensehat_thread_func, daemon=True).start()
    print("🚀 Lancement du thread de notification (Plantes & Tâches)...")
    threading.Thread(target=notification_thread_func, daemon=True).start()
    print("🚀 Lancement du thread de notification de démarrage...")
    threading.Thread(target=send_startup_notification, daemon=True).start()
    print("🚀 Lancement du serveur Flask sur http://0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)
