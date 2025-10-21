# Fichier : database_setup.py
import sqlite3

DB_NAME = 'raspihome.db'
print(f"Initialisation de la base de données : {DB_NAME}")

try:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # --- Tables existantes pour les plantes (ajustez si nécessaire) ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS plants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            last_watered TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS plant_rules (
            name TEXT PRIMARY KEY,
            summer_weeks INTEGER NOT NULL,
            winter_weeks INTEGER NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            tip TEXT NOT NULL
        )
    ''')

    # --- NOUVELLE TABLE POUR LES DONNÉES DE CAPTEURS ---
    print("Création de la table 'sensor_readings' pour l'historique météo...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sensor_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME NOT NULL,
            temperature REAL NOT NULL,
            humidity REAL NOT NULL,
            pressure REAL NOT NULL,
            heat_index REAL NOT NULL
        )
    ''')

    # --- NOUVEL INDEX POUR ACCÉLÉRER LES REQUÊTES D'HISTORIQUE ---
    print("Création de l'index sur le timestamp...")
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON sensor_readings (timestamp)')

    conn.commit()
    print("Base de données et tables vérifiées/créées avec succès.")

except sqlite3.Error as e:
    print(f"Erreur lors de l'initialisation de la base de données : {e}")

finally:
    if conn:
        conn.close()
