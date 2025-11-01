import sqlite3
import os

# --- CONFIGURATION ---
# Le nom de votre fichier de base de données.
# Assurez-vous que ce script est dans le même dossier que votre base de données.
DB_FILE = "raspihome.db"

def clear_screen():
    """Efface le terminal pour une meilleure lisibilité."""
    os.system('cls' if os.name == 'nt' else 'clear')

def print_table(headers, rows):
    """
    Affiche une liste de lignes de manière formatée avec des en-têtes.
    """
    if not rows:
        print("\n-> La table est vide.")
        return

    # Calculer la largeur maximale pour chaque colonne
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            cell_str = str(cell)
            if len(cell_str) > col_widths[i]:
                col_widths[i] = len(cell_str)

    # Créer les chaînes de formatage pour les en-têtes et les séparateurs
    header_str = " | ".join(h.ljust(w) for h, w in zip(headers, col_widths))
    separator_str = "-+-".join("-" * w for w in col_widths)

    print("\n" + header_str)
    print(separator_str)

    # Afficher chaque ligne
    for row in rows:
        row_str = " | ".join(str(cell).ljust(w) for cell, w in zip(row, col_widths))
        print(row_str)

def get_tables(cursor):
    """Récupère et retourne la liste des tables de la base de données."""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    return [table[0] for table in cursor.fetchall()]

def view_table_schema(cursor, table_name):
    """Affiche la structure (colonnes) d'une table."""
    print(f"\n--- Structure de la table '{table_name}' ---")
    cursor.execute(f"PRAGMA table_info({table_name});")
    rows = cursor.fetchall()
    headers = ["ID", "Nom_Colonne", "Type", "Non_Nul", "Val_Defaut", "Clé_Primaire"]
    print_table(headers, rows)

def view_table_content(cursor, table_name):
    """Affiche le contenu (les 100 dernières lignes) d'une table."""
    print(f"\n--- Contenu de la table '{table_name}' (100 dernières lignes) ---")
    cursor.execute(f"PRAGMA table_info({table_name});")
    headers = [info[1] for info in cursor.fetchall()]
    
    cursor.execute(f"SELECT * FROM {table_name} ORDER BY id DESC LIMIT 100;")
    rows = cursor.fetchall()
    print_table(headers, rows)

def main():
    """Fonction principale du programme."""
    if not os.path.exists(DB_FILE):
        print(f"ERREUR: Le fichier de base de données '{DB_FILE}' n'a pas été trouvé.")
        print("Assurez-vous de lancer ce script dans le même dossier.")
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    while True:
        clear_screen()
        print("========== Explorateur de Base de Données SQLite ==========")
        
        tables = get_tables(cursor)
        if not tables:
            print("Aucune table trouvée dans la base de données.")
            break
            
        print("\nTables disponibles:")
        for table in tables:
            print(f"- {table}")
        
        print("\n---------------------------------------------------------")
        choice = input("Entrez le nom de la table à inspecter (ou 'q' pour quitter): ").strip()

        if choice.lower() == 'q':
            break
        
        if choice in tables:
            view_table_schema(cursor, choice)
            view_table_content(cursor, choice)
        else:
            print(f"\nERREUR: La table '{choice}' n'existe pas.")

        input("\nAppuyez sur Entrée pour revenir au menu...")

    conn.close()
    print("\nAu revoir !")


if __name__ == "__main__":
    main()
