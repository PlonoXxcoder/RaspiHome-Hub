# Moniteur de Plantes et de Pièce Raspberry Pi

Ce projet utilise un Raspberry Pi avec un Sense HAT pour surveiller les conditions environnementales (température, humidité, pression) à la fois pour les plantes et la pièce environnante, et fournir des alertes pour l'arrosage des plantes.

## Fonctionnalités

*   **Surveillance Environnementale:** Collecte les données de température, d'humidité et de pression à l'aide du Sense HAT pour les soins des plantes et les conditions de la pièce.
*   **Calcul de l'Indice de Chaleur:** Calcule l'indice de chaleur pour une représentation plus précise de la température ressentie.
*   **Enregistrement des Données:** Enregistre les données dans un fichier CSV (`data.csv`) pour une analyse historique.
*   **Alertes d'Arrosage des Plantes:** Surveille les calendriers d'arrosage des plantes en fonction du type de plante et fournit des alertes LED lorsque l'arrosage est nécessaire.
*   **Interface Web:** Fournit une interface web (en utilisant Flask) pour visualiser les données actuelles et les tendances historiques à la fois pour la pièce et les paramètres liés aux plantes.

## Prérequis

*   Raspberry Pi
*   Sense HAT
*   Python 3
*   Flask
*   Pandas
*   `pip install flask sense-hat pandas`
*   **ngrok:** Pour exposer le serveur Flask local sur Internet. [https://ngrok.com/](https://ngrok.com/)

## Installation

1.  **Cloner le dépôt:**
    ```bash
    git clone [URL du dépôt]
    ```

2.  **Naviguer vers le répertoire du projet:**
    ```bash
    cd raspberry-pi-plant-monitor
    ```

3.  **Installer les dépendances:**
    ```bash
    pip3 install flask sense-hat pandas
    ```

4.  **Télécharger et installer ngrok:** Suivez les instructions sur le site web de ngrok ([https://ngrok.com/download](https://ngrok.com/download)).

5.  **Exécuter l'application:**
    ```bash
    python3 serveur_temp.py
    ```

6.  **Exposer le serveur Flask avec ngrok:** Dans une *autre* fenêtre de terminal, exécutez :
    ```bash
    ngrok http 5000
    ```
    ngrok vous fournira une URL publique (par exemple, `https://xxxxxx.ngrok.io`).

7.  **Accéder à l'interface web:**
    Ouvrez votre navigateur web et accédez à l'URL ngrok fournie.

## Configuration

*   **`plants.json`:** Ce fichier stocke les informations sur vos plantes, y compris leur type et la date du dernier arrosage. Modifiez ce fichier pour ajouter ou modifier les données des plantes. Le format attendu est :

    ```json
    {
      "echeveria": {
        "nom": "Echeveria",
        "last_watered": "2024-01-01"
      },
      "sansevieria": {
        "nom": "Sansevieria",
        "last_watered": "2024-01-05"
      }
    }
    ```

*   **`PLANT_RULES` dans `serveur_temp.py`:** Ce dictionnaire définit les intervalles d'arrosage pour différents types de plantes. Ajustez ces valeurs si nécessaire.

## Licence

Ce projet est sous licence MIT - voir le fichier [LICENSE](LICENSE) pour plus de détails.

## Étapes Supplémentaires

*   **Créer un fichier `LICENSE`:** Créez un fichier nommé `LICENSE` à la racine du dépôt et collez le contenu de la licence MIT (voir ci-dessous).
*   **Configurer les données des plantes:** Remplissez le fichier `plants.json` avec les données de vos plantes.
*   **Tester minutieusement:** Testez l'application pour vous assurer qu'elle fonctionne correctement et que les alertes fonctionnent comme prévu.

## Développement Futur

*   **Plus de types de plantes:** Développez le dictionnaire `PLANT_RULES` pour inclure davantage de types de plantes et leurs besoins spécifiques en arrosage.
*   **Intégration de base de données:** Remplacez l'enregistrement des données CSV par une solution de base de données plus robuste (par exemple, SQLite, PostgreSQL).
*   **Graphiques:** Implémentez des graphiques dans l'interface web pour visualiser les données historiques.
*   **Accès à distance:** Explorez les options d'accès et de contrôle à distance du système (par exemple, en utilisant une plateforme cloud).
*   **Arrosage automatisé:** Intégrez-vous à une électrovanne pour automatiser le processus d'arrosage.
*   **Notifications:** Ajoutez des notifications par e-mail ou push pour les alertes d'arrosage.

## Contribution

Les contributions sont les bienvenues ! Veuillez forker le dépôt et soumettre une pull request.
