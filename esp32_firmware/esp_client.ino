#include <WiFi.h>
#include <WebServer.h>
#include <HTTPClient.h>
#include <ArduinoJson.h> // Pour formater les données
#include "DHT.h"         // Votre code de capteur
#include <vector>

// ------------------- À MODIFIER -------------------
const char* ssid = "Bbox-96952397-Plus";
const char* password = "4DzKZPWM9C4T5cCHvV";
const char* server_ip = "192.168.1.199"; // <-- L'ADRESSE IP DE VOTRE RASPBERRY PI
// ----------------------------------------------------

const char* server_endpoint = "/esp32/data"; 

// --- Configuration du capteur DHT ---
const int DHTPIN = 4;
#define DHTTYPE DHT11
DHT dht(DHTPIN, DHTTYPE);

// --- Serveur Web sur l'ESP32 ---
WebServer esp_server(80);

// Intervalle de mesure (5 minutes)
const long interval = 300000;
unsigned long previousMillis = 0;

struct SensorMeasurement { float temperature; float humidity; };
std::vector<SensorMeasurement> measurement_queue;
const int MAX_QUEUE_SIZE = 100;

/**
 * Fonction appelée quand le Pi envoie l'ordre /read_sensor
 */
void handleForceRead() {
  Serial.println(">>> Ordre de lecture manuel reçu du Pi !");
  esp_server.send(200, "text/plain", "OK, lecture forcée.");
  readAndProcessSensorData(); // On force une lecture immédiate
}

void setup() {
  Serial.begin(115200);
  dht.begin();
  
  connectToWiFi();

  // Configuration du serveur web de l'ESP32
  esp_server.on("/read_sensor", HTTP_GET, handleForceRead);
  esp_server.begin();
  Serial.println("Serveur web ESP32 démarré. En attente d'ordres sur /read_sensor");

  Serial.println("\n--- Démarrage du cycle de mesures ---");
  previousMillis = millis();
}

void loop() {
  // 1. Gérer les requêtes entrantes du Pi (pour le bouton "Rafraîchir")
  esp_server.handleClient();
  
  // 2. Vérifier la connexion WiFi
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi déconnecté. Tentative de reconnexion en arrière-plan...");
    WiFi.reconnect();
    delay(5000); // Attendre 5s avant de revérifier
    return; // On ne fait rien d'autre tant qu'il n'y a pas de WiFi
  }
  
  // 3. Si on est connecté et que la file d'attente n'est pas vide, on synchronise
  if (!measurement_queue.empty()) {
    Serial.printf("WiFi connecté ! Synchronisation de %d mesure(s) en attente...\n", measurement_queue.size());
    syncQueue();
  }
  
  // 4. Prendre une mesure toutes les 5 minutes
  unsigned long currentMillis = millis();
  if (currentMillis - previousMillis >= interval) {
    previousMillis = currentMillis;
    readAndProcessSensorData();
  }
}

void connectToWiFi() {
  Serial.print("Connexion à ");
  Serial.println(ssid);
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nConnecté au WiFi !");
  Serial.print("Adresse IP: ");
  Serial.println(WiFi.localIP());
}

void readAndProcessSensorData() {
  Serial.println("\n--------------------");
  Serial.print("Lecture du capteur... ");
  float h = dht.readHumidity();
  float t = dht.readTemperature();

  if (isnan(h) || isnan(t)) {
    Serial.println("Échec de la lecture du capteur !");
    return;
  }
  Serial.printf("Réussie: %.1f°C, %.1f%%\n", t, h);

  SensorMeasurement new_measurement = {t, h};

  if (sendDataToServer(new_measurement)) {
    Serial.println("-> Données envoyées avec succès.");
  } else {
    Serial.println("-> Échec de l'envoi. Mise en file d'attente.");
    if (measurement_queue.size() < MAX_QUEUE_SIZE) {
      measurement_queue.push_back(new_measurement);
      Serial.printf("   Taille de la file d'attente: %d\n", measurement_queue.size());
    } else {
      Serial.println("   ATTENTION: File d'attente pleine. Mesure perdue.");
    }
  }
}

bool sendDataToServer(SensorMeasurement measurement) {
  if (WiFi.status() != WL_CONNECTED) {
    return false;
  }
  
  bool success = false;
  HTTPClient http;
  String server_url = "http://" + String(server_ip) + ":5000" + String(server_endpoint);
  
  http.begin(server_url);
  http.addHeader("Content-Type", "application/json");
  
  StaticJsonDocument<100> jsonDoc;
  jsonDoc["temperature"] = measurement.temperature;
  jsonDoc["humidity"] = measurement.humidity;
  
  String jsonBuffer;
  serializeJson(jsonDoc, jsonBuffer);
  
  int httpResponseCode = http.POST(jsonBuffer);
  
  if (httpResponseCode == 200) {
    success = true;
  } else {
    Serial.printf("   Erreur d'envoi. Code de réponse du serveur: %d\n", httpResponseCode);
  }
  
  http.end();
  return success;
}

void syncQueue() {
  while (!measurement_queue.empty()) {
    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("Perte de connexion pendant la synchronisation. Arrêt.");
      return;
    }
    
    Serial.print("   Envoi de la mesure en cache... ");
    // On prend la plus ancienne mesure de la file
    SensorMeasurement measurement_to_send = measurement_queue.front();

    if (sendDataToServer(measurement_to_send)) {
      Serial.println("OK.");
      measurement_queue.erase(measurement_queue.begin()); // Si succès, on la supprime
      delay(500);
    } else {
      Serial.println("Échec. Réessai plus tard.");
      return;
    }
  }
  Serial.println("Synchronisation terminée !");
}
