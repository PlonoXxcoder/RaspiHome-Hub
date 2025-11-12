# RaspiHome Hub v1.5 : Météo, Jardinage, Tâches & Domotique Intelligente

<p align="center">
  <img src="https://assets.raspberrypi.com/static/5b1d6198ce585628ff74093aeae5cfbc/9ff6b/049d9e7a086cb233116999b3fd701e4cfae86d3a_sense-hat-plugged-in-1-1383x1080.webp" alt="Sense HAT" width="100"/>
</p>

**RaspiHome Hub** transforme votre Raspberry Pi en un serveur domotique complet. Cette version majeure intègre une station météo multi-sources (Sense HAT, ESP32, API web), un assistant de jardinage proactif, un gestionnaire de tâches ménagères et un moteur d'astuces contextuelles pour vous aider à gérer votre maison.

## Table des Matières

* [Fonctionnalités Clés](#fonctionnalités-clés)
* [Aperçu de l'Interface](#aperçu-de-linterface)
* [Architecture Technique v3.0](#architecture-technique-v30)
* [Prérequis](#prérequis)
* [Installation Facile](#installation-facile)
* [Guide d'Utilisation](#guide-dutilisation)
* [Structure du Projet](#structure-du-projet)
* [Personnalisation](#personnalisation)
* [Feuille de Route et Idées Futures](#feuille-de-route-et-idées-futures)
* [Licence](#licence)

---

## Fonctionnalités Clés

### Station Météo & Domotique Intelligente

* 📡 **Dashboard Météo Multi-Sources** : Affiche les données de 3 sources :
    * **Capteur Local** (Sense HAT sur le Pi).
    * **Capteur Distant** (ESP32 via WiFi, pour la salle de bain).
    * **API Météo Web** (OpenWeatherMap).
* 🔄 **Rafraîchissement à la Demande** : Le bouton "Rafraîchir" force une nouvelle lecture du Sense HAT et envoie un ordre de lecture à l'ESP32.
* 🧠 **Assistant Domotique Proactif** :
    * **Bandeau d'Alertes** : Affiche des alertes prioritaires pour le chauffage (si T° < 18°C le soir/weekend), les plantes à arroser et les tâches en retard.
    * **Astuces Contextuelles** : Affiche des conseils météo (ouverture des volets basée sur `astral`, alerte humidité SDB) dans un emplacement dédié.
* 📈 **Graphiques Interactifs Avancés** :
    * **Zoom et Panoramique** : Zoomez et déplacez-vous sur l'axe du temps.
    * **Plages de Temps Étendues** : Sélectionnez des périodes de 8h, 24h, 2 jours, 7 jours ou 30 jours.
    * **Zones Nuit/Jour** : Affiche des zones grisées pour les heures de nuit (basées sur `astral`).

### Gestion de la Maison

* 💧 **Assistant de Jardinage Proactif** :
    * **Suivi Visuel** : Une barre de progression colorée (vert/jaune/rouge) montre l'état du cycle d'arrosage pour chaque plante.
    * **Gestion Complète via l'Interface** : Ajoutez, modifiez et supprimez des plantes. Créez de nouveaux types de plantes (ex: "Plante tropicale") avec leurs propres règles d'arrosage été/hiver.
* 🧹 **Gestion des Tâches Ménagères (Nouveau v1.7)** :
    * **Suivi Visuel** : Affiche les tâches récurrentes (ex: "Nettoyer la litière") avec une barre de progression d'urgence.
    * **API Complète** : Ajoutez, complétez et supprimez des tâches directement depuis l'interface.
    * **Alertes** : Intégrées aux notifications Telegram et au bandeau d'alertes du tableau de bord.
* 🔔 **Notifications Telegram** : Envoie des rappels groupés pour les plantes à arroser et les tâches en retard.

### Interface & Fiabilité

* 🌗 **Thème Clair & Sombre** : Basculez entre deux thèmes. Le choix est mémorisé dans le `localStorage`.
* 🔐 **Authentification** : Une page de connexion protège l'accès au tableau de bord.
* 🧩 **Code JavaScript Modulaire** : Le frontend est divisé en `api.js`, `ui.js`, et `main.js` pour une meilleure maintenabilité.
* 🛠️ **Fiabilité des Données (Nouveau v1.5)** : Les affichages des capteurs distants et les astuces contextuelles lisent la **dernière valeur de la base de données** (`raspihome.db`) au lieu du cache, garantissant que les données sont toujours disponibles, même après un redémarrage du serveur.

### Protection Réseau (Optionnelle)

* ⛔ **Blocage des Publicités** : Possibilité d'installer AdGuard Home pour filtrer les publicités et traqueurs sur tout le réseau.

---

## Aperçu de l'Interface

L'interface V3 intègre les capteurs multiples, les plantes et les nouvelles astuces contextuelles.

| Thème Sombre | Thème Clair |
| :---: | :---: |
| ![Tableau de bord - Thème Sombre](assets/dashboard-dark-screenshot_V3.png) | ![Tableau de bord - Thème Clair](assets/dashboard-white-screenshot_V3.png) |
---

## Architecture Technique v3.0

1.  **Sources de Données** :
    * **Capteur Local (Sense HAT)** : Données intérieures du Pi.
    * **Capteur Distant (ESP32)** : Un ESP32 envoie ses données à la route `/esp32/data`.
    * **API OpenWeatherMap** : Données météo extérieures.
2.  **Script Python (`serveur_temp.py`)**:
    * **Serveur Web (Flask)** : Expose de multiples routes API (`/alldata`, `/plants`, `/tasks`, `/weather_tip`, etc.).
    * **Serveur de Commande** : Expose la route `/refresh/all` pour commander l'ESP32.
    * **Moteur d'Astuces** : Calcule les alertes (chauffage, plantes, tâches) et les astuces (volets, humidité SDB).
3.  **Stockage Centralisé (SQLite)** :
    * **`raspihome.db`** : Stocke tout : `user`, `plants`, `plant_rules`, `watering_history`, `sensor_readings` et la nouvelle table `tasks`.
4.  **Interface Utilisateur (Modulaire)** :
    * `index.html` : Structure la page avec la nouvelle barre de navigation.
    * `style.css` : Gère les thèmes clair/sombre et le style de la navigation "sticky".
    * Logique JS (`api.js`, `ui.js`, `main.js`).
    * **Chart.js** avec les plugins `zoom` et `annotation`.

---

## Prérequis

### Matériel

* Un Raspberry Pi (testé sur un modèle 1 B+)
* Une carte d'extension [Sense HAT](https://www.raspberrypi.com/products/sense-hat/)
* **(Optionnel) Un ESP32** (ou ESP8266) et un capteur (ex: DHT11/22).
* Une alimentation fiable et une carte microSD.

### Logiciel

* Python 3.x et Git.
* Un compte et une **clé d'API** [OpenWeatherMap](https://openweathermap.org/) (Gratuit, optionnel mais recommandé).
* Les bibliothèques Python (Flask, Requests, etc.).
* Les bibliothèques système `python3-sense-hat` et `python3-astral`.

---

## Installation Facile

1.  **Mettre à jour le système** :
    ```bash
    sudo apt update && sudo apt upgrade -y
    ```
2.  **Cloner ce dépôt** :
    ```bash
    git clone [https://github.com/PlonoXxcoder/RaspiHome-Hub.git](https://github.com/PlonoXxcoder/RaspiHome-Hub.git)
    cd RaspiHome-Hub
    ```
3.  **Installer les dépendances système et Python** :
    ```bash
    # Installer les dépendances système (Sense HAT, Astral, Requests)
    sudo apt-get install python3-sense-hat python3-astral python3-requests
    # Installer les autres dépendances (Flask, etc.)
    sudo pip3 install -r requirements.txt
    ```
4.  **Initialiser la base de données** :
    *Si c'est une nouvelle installation*, utilisez le script de setup :
    ```bash
    python3 database_setup.py
    ```
    *(Si vous mettez à jour une version existante, vous devrez peut-être ajouter la table `tasks` manuellement)*

5.  **Configurer** :
    Copiez `config.py.example` en `config.py` et ajoutez vos clés API, coordonnées et IP de l'ESP32.

---

## Guide d'Utilisation

### Démarrage du Serveur

Il est fortement recommandé d'utiliser le service `systemd` fourni.

1.  **Copier le fichier de service** :
    ```bash
    sudo cp raspihome.service /etc/systemd/system/raspihome.service
    ```
2.  **Mettre à jour le chemin dans le service** (si nécessaire) :
    * Éditez le fichier : `sudo nano /etc/systemd/system/raspihome.service`
    * Vérifiez que `WorkingDirectory` et `ExecStart` pointent vers le bon chemin.
3.  **Lancer et activer le service** :
    ```bash
    sudo systemctl daemon-reload
    sudo systemctl start raspihome.service
    sudo systemctl enable raspihome.service # Pour le lancer au démarrage
    ```
4.  **Accéder à l'interface** : `http://<VOTRE_ADRESSE_IP>:5000`
5.  **Voir les logs** : `journalctl -u raspihome.service -f`

---

## Structure du Projet

## Structure du Projet
```
RaspiHome-Hub/
├── templates/
│   ├── api.js
│   ├── ui.js
│   ├── main.js
│   ├── index.html
│   └── style.css
├── esp32_firmware/      
│   └── esp_client.ino   
├── assets/
├── config.py
├── database_setup.py
├── raspihome.service
├── requirements.txt
├── serveur_temp.py
└── README.md
```
---

---

## Personnalisation

* **Configuration Principale** : Éditez `config.py` pour vos clés API, coordonnées et jetons Telegram.
* **Seuils de Température** : Modifiez `TEMP_IDEAL_MIN` et `TEMP_IDEAL_MAX` dans `serveur_temp.py` pour ajuster les alertes de chauffage.
* **Règles d'Arrosage & Tâches** : N'éditez plus les fichiers ! Utilisez la section "Gestion" directement sur l'interface web pour ajouter/modifier vos plantes et tâches.

---

### Feuille de Route et Idées Futures

Ce projet évolue constamment. Voici ce qui a été fait et ce qui est à venir.

### 🚀 Historique Récent

-   **[✅] v1.1 - v1.4 : Fondation IoT & Jardinage**
    -   [X] Intégration capteur distant (ESP32).
    -   [X] Graphiques interactifs (Zoom, Pan, Seuils).
    -   [X] Barre de progression d'arrosage.
    -   [X] Notifications Telegram pour les plantes.
    -   [X] Déploiement via `systemd`.

-   **[✅] v1.5 : Gestion des Tâches Ménagères**
    -   [X] **Fondation Backend**: Création de la table `tasks` et des routes API CRUD.
    -   [X] **Interface de Suivi Visuel**: Ajout de "cartes de tâches" avec barre de progression d'urgence.
    -   [X] **Notifications Proactives**: Ajout des tâches en retard aux alertes Telegram.
    -   [X] **Intégration Intelligente**: Les tâches en retard sont prioritaires dans le bandeau d'alertes.
    -   [X] **Gestion Complète via l'UI**: Formulaire d'ajout et boutons de gestion sur l'interface.

-   **[✅] v1.6 - v1.7 : Améliorations UI & Fiabilité**
    -   [X] **Navigation Rapide** : Ajout d'une barre de navigation "sticky" pour accéder aux sections.
    -   [X] **Astuces Contextuelles** : Création d'une route `/weather_tip` et d'un emplacement UI dédié.
    -   [X] **Alertes Chauffage** : Le bandeau d'alerte principal prévient si T° < 18°C le soir.
    -   [X] **Plages de Graphique** : Ajout des options 8h, 2j, 7j, 30j.
    -   [X] **Fiabilité BDD** : Les routes `/esp32_latest` et `/weather_tip` lisent désormais la BDD pour garantir l'affichage des données après un redémarrage.

### 🚀 Prochaines Étapes (Feuille de Route)

-   [ ] **Alertes Météo Avancées** : Notifications Telegram pour seuils critiques (ex: "Alerte : Température intérieure trop élevée !").
-   [ ] **Page Historique Détaillée** : Créer une nouvelle page avec un sélecteur de dates (calendrier), un tableau de données triable et un bouton d'export CSV.
-   [ ] **Indicateurs Visuels** : Remplacer les pourcentages d'humidité par des jauges circulaires et ajouter des mini-graphiques "sparklines" dans les cartes météo.
-   [ ] **Contrôle Salle de Bain** : Objectif d'ajouter un capteur dans la SDB pour contrôler l'aération (Logique à affiner).

### 💡 Idées pour l'Avenir

* **Capteurs d'Humidité du Sol** : L'évolution logique. Utiliser des capteurs capacitifs pour baser l'arrosage sur le besoin réel.
* **Arrosage Automatique** : Connecter une pompe et un relais à l'ESP32 pour un arrosage 100% autonome.
* **Support Multi-Capteurs** : Permettre d'ajouter *plusieurs* capteurs ESP32 (ex: un par pièce) et de les afficher sur le dashboard.

---

## Licence

Ce projet est distribué sous la licence MIT.
