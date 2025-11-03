#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include "DHT.h"
#include <vector> // Pour utiliser la file d'attente (vector)

// ------------------- À MODIFIER -------------------
const char* ssid = "LE_NOM_DE_VOTRE_WIFI";
const char* password = "LE_MOT_DE_PASSE_DE_VOTRE_WIFI";
const char* server_ip = "192.168.1.199"; // L'IP de votre Raspberry Pi
// ----------------------------------------------------

const char* server_endpoint = "/esp32/data"; 

// --- Configuration du capteur DHT ---
const int DHTPIN = 4;
#define DHTTYPE DHT11
DHT dht(DHTPIN, DHTTYPE);

// Intervalle de mesure (toutes les 5 minutes)
const long interval = 300000; // 5 * 60 * 1000
unsigned long previousMillis = 0;

// --- NOUVEAU : Structure pour stocker une mesure ---
struct SensorMeasurement {
  float temperature;
  float humidity;
};

// --- NOUVEAU : La file d'attente pour les mesures en cache ---
std::vector<SensorMeasurement> measurement_queue;
const int MAX_QUEUE_SIZE = 100; // Stocke jusqu'à 100 mesures en cas de déconnexion

void setup() {
  Serial.begin(115200);
  dht.begin();
  
  connectToWiFi();

  // On attend un peu que tout se stabilise avant la première lecture
  delay(2000); 
  Serial.println("\n--- Démarrage du cycle de mesures ---");
  previousMillis = millis();
}

void loop() {
  // 1. On vérifie la connexion WiFi à chaque boucle
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi déconnecté. Tentative de reconnexion...");
    connectToWiFi();
  } else {
    // Si on est connecté ET qu'il y a des données en attente, on les envoie
    if (!measurement_queue.empty()) {
      Serial.printf("WiFi reconnecté ! Synchronisation de %d mesure(s) en attente...\n", measurement_queue.size());
      syncQueue();
    }
  }
  
  // 2. On prend une mesure toutes les 5 minutes
  unsigned long currentMillis = millis();
  if (currentMillis - previousMillis >= interval) {
    previousMillis = currentMillis;
    readAndProcessSensorData();
  }

  delay(1000); // Petite pause pour ne pas surcharger le CPU
}

void connectToWiFi() {
  Serial.print("Connexion à ");
  Serial.println(ssid);
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  int attempt = 0;
  while (WiFi.status() != WL_CONNECTED && attempt < 20) { // On essaie pendant 10 secondes
    delay(500);
    Serial.print(".");
    attempt++;
  }
  
  if(WiFi.status() == WL_CONNECTED) {
    Serial.println("\nConnecté au WiFi !");
    Serial.print("Adresse IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\nÉchec de la connexion WiFi. Réessai plus tard.");
  }
}

// Lit le capteur et décide quoi faire des données
void readAndProcessSensorData() {
  Serial.println("\n--------------------");
  Serial.print("Lecture du capteur... ");
  float h = dht.readHumidity();
  float t = dht.readTemperature();

  if (isnan(h) || isnan(t)) {
    Serial.println("Échec !");
    return;
  }
  Serial.printf("Réussie: %.1f°C, %.1f%%\n", t, h);

  // On crée un objet pour cette mesure
  SensorMeasurement new_measurement = {t, h};

  // On essaie d'envoyer la nouvelle mesure immédiatement
  if (sendDataToServer(new_measurement)) {
    Serial.println("-> Données envoyées avec succès au serveur.");
  } else {
    Serial.println("-> Échec de l'envoi. Mise en file d'attente.");
    // Si l'envoi échoue, on ajoute la mesure à la file d'attente
    if (measurement_queue.size() < MAX_QUEUE_SIZE) {
      measurement_queue.push_back(new_measurement);
      Serial.printf("   Taille de la file d'attente: %d\n", measurement_queue.size());
    } else {
      Serial.println("   ATTENTION: La file d'attente est pleine. La mesure est perdue.");
    }
  }
}

// Tente d'envoyer UNE mesure au serveur. Retourne true si succès, false si échec.
bool sendDataToServer(SensorMeasurement measurement) {
  if (WiFi.status() != WL_CONNECTED) {
    return false; // Pas de WiFi, échec immédiat
  }
  
  bool success = false;
  HTTPClient http;
  char server_url[100];
  sprintf(server_url, "http://%s:5000%s", server_ip, server_endpoint);
  
  http.begin(server_url);
  http.addHeader("Content-Type", "application/json");
  
  StaticJsonDocument<100> jsonDoc;
  jsonDoc["temperature"] = measurement.temperature;
  jsonDoc["humidity"] = measurement.humidity;
  
  char jsonBuffer[100];
  serializeJson(jsonDoc, jsonBuffer);
  
  int httpResponseCode = http.POST(jsonBuffer);
  
  if (httpResponseCode == 200) {
    success = true;
  } else {
    Serial.printf("   Erreur d'envoi. Code de réponse: %d\n", httpResponseCode);
  }
  
  http.end();
  return success;
}

// Fonction pour vider la file d'attente
void syncQueue() {
  // On utilise un itérateur pour parcourir et supprimer en même temps
  for (auto it = measurement_queue.begin(); it != measurement_queue.end(); ) {
    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("Perte de connexion pendant la synchronisation. Arrêt.");
      return; // On arrête tout si le WiFi se coupe pendant la synchro
    }
    
    Serial.print("   Envoi de la mesure en cache... ");
    if (sendDataToServer(*it)) {
      Serial.println("OK.");
      it = measurement_queue.erase(it); // Si succès, on supprime l'élément de la file
      delay(500); // Petite pause pour ne pas saturer le serveur
    } else {
      Serial.println("Échec. Réessai plus tard.");
      return; // Si l'envoi échoue, on arrête et on réessaiera plus tard
    }
  }
  Serial.println("Synchronisation terminée !");
}
