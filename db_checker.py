import sqlite3
import os

# --- CONFIGURATION ---
DB_FILE = "raspihome.db"

# Définition de la structure ATTENDUE par le nouveau serveur_temp.py
EXPECTED_STRUCTURE = {
    "PlantType": {
        "id": "INTEGER",
        "name": "VARCHAR",
        "summer_freq": "INTEGER",
        "winter_freq": "INTEGER",
    },
    "Plant": {
        "id": "INTEGER",
        "name": "VARCHAR",
        "last_watered": "DATETIME",
        "type_id": "INTEGER",
    },
    "SensorData": {
        "id": "INTEGER",
        "timestamp": "DATETIME",
        "source": "VARCHAR",
        "temperature": "FLOAT",
        "humidity": "FLOAT",
        "pressure": "FLOAT",
    }
}

# --- COULEURS POUR LE TERMINAL ---
class bcolors:
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def get_actual_structure(cursor):
    """Récupère la structure réelle de la base de données."""
    actual_structure = {}
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [table[0] for table in cursor.fetchall()]
    
    for table_name in tables:
        if table_name == 'sqlite_sequence': continue # Ignorer la table interne
        
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns_info = cursor.fetchall()
        actual_structure[table_name] = {info[1]: info[2] for info in columns_info}
        
    return actual_structure

def run_checks():
    """Lance les vérifications et affiche le rapport."""
    if not os.path.exists(DB_FILE):
        print(f"{bcolors.FAIL}ERREUR: Le fichier '{DB_FILE}' n'a pas été trouvé.{bcolors.ENDC}")
        return

    print(f"{bcolors.BOLD}--- Lancement du diagnostic de la base de données '{DB_FILE}' ---\n{bcolors.ENDC}")

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    actual_structure = get_actual_structure(cursor)
    
    # --- VÉRIFICATION 1: Comparaison des noms de tables ---
    print(f"{bcolors.BOLD}1. Vérification des noms de tables...{bcolors.ENDC}")
    actual_tables = set(actual_structure.keys())
    expected_tables = set(EXPECTED_STRUCTURE.keys())

    compatible_tables = actual_tables.intersection(expected_tables)
    incompatible_tables = actual_tables.difference(expected_tables)
    missing_tables = expected_tables.difference(actual_tables)

    if compatible_tables:
        print(f"{bcolors.OKGREEN}   [OK] Tables compatibles trouvées : {', '.join(compatible_tables)}{bcolors.ENDC}")
    if incompatible_tables:
        print(f"{bcolors.WARNING}   [ATTENTION] Tables anciennes/incompatibles trouvées : {', '.join(incompatible_tables)}{bcolors.ENDC}")
    if missing_tables:
        print(f"{bcolors.FAIL}   [ERREUR] Tables requises manquantes : {', '.join(missing_tables)}{bcolors.ENDC}")

    # --- VÉRIFICATION 2: Comparaison des colonnes ---
    print(f"\n{bcolors.BOLD}2. Vérification de la structure des colonnes...{bcolors.ENDC}")
    all_ok = True
    for table_name, expected_columns in EXPECTED_STRUCTURE.items():
        print(f"   - Analyse de la table '{table_name}':")
        if table_name not in actual_tables:
            print(f"     {bcolors.FAIL}[ERREUR] Table non trouvée.{bcolors.ENDC}")
            all_ok = False
            continue

        actual_columns = set(actual_structure[table_name].keys())
        expected_columns_set = set(expected_columns.keys())

        missing_cols = expected_columns_set.difference(actual_columns)
        extra_cols = actual_columns.difference(expected_columns_set)

        if not missing_cols:
            print(f"     {bcolors.OKGREEN}[OK] Toutes les colonnes requises sont présentes.{bcolors.ENDC}")
        else:
            print(f"     {bcolors.FAIL}[ERREUR] Colonnes requises manquantes : {', '.join(missing_cols)}{bcolors.ENDC}")
            all_ok = False
        
        if extra_cols:
            print(f"     {bcolors.WARNING}[INFO] Colonnes supplémentaires trouvées (ignorées) : {', '.join(extra_cols)}{bcolors.ENDC}")

    # --- RAPPORT FINAL ---
    print(f"\n{bcolors.BOLD}--- Rapport Final ---{bcolors.ENDC}")
    if all_ok and not missing_tables:
        print(f"{bcolors.OKGREEN}✅ DIAGNOSTIC RÉUSSI : La structure de votre base de données semble compatible avec le nouveau serveur.{bcolors.ENDC}")
    else:
        print(f"{bcolors.FAIL}❌ DIAGNOSTIC ÉCHOUÉ : La structure de votre base de données est INCOMPATIBLE avec le nouveau serveur.{bcolors.ENDC}")
        print("   Raison(s) : Des tables ou des colonnes requises sont manquantes.")
        print("\n   ACTION RECOMMANDÉE :")
        print("   1. Faites une sauvegarde de votre base de données actuelle : `cp raspihome.db raspihome.db.bak`")
        print("   2. Supprimez la base de données : `rm raspihome.db`")
        print("   3. Relancez `serveur_temp.py` pour qu'il crée une nouvelle base de données propre avec la bonne structure.")

    conn.close()

if __name__ == "__main__":
    run_checks()
