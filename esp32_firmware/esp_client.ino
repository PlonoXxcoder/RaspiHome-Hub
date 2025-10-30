#include <WiFi.h>
#include <WebServer.h>   // Pour écouter les ordres du Pi
#include <HTTPClient.h>  // Pour envoyer les données au Pi
#include <ArduinoJson.h> // Pour formater les données en JSON
#include "DHT.h"         // Pour le capteur DHT11

// ------------------- À MODIFIER -------------------
const char* ssid = "LE_NOM_DE_VOTRE_WIFI";
const char* password = "LE_MOT_DE_PASSE_DE_VOTRE_WIFI";

// Mettez l'adresse IP de votre Raspberry Pi 1
const char* server_ip = "192.168.1.XX"; 
// ----------------------------------------------------

// Endpoint (route) sur le Pi pour recevoir nos données
const char* server_endpoint = "/esp32/data"; 

// --- Configuration du capteur DHT ---
const int DHTPIN = 4;
#define DHTTYPE DHT11
DHT dht(DHTPIN, DHTTYPE);

// --- NOUVEAU : Serveur Web sur l'ESP32 ---
WebServer esp_server(80); // Le serveur écoutera sur le port 80 (HTTP standard)

// Intervalle d'envoi automatique (toujours 5 minutes)
const long interval = 300000;
unsigned long previousMillis = 0;

/**
 * Fonction appelée quand le Pi demande une lecture
 */
void handleReadSensor() {
  Serial.println(">>> Ordre de lecture reçu du Pi !");
  esp_server.send(200, "text/plain", "OK, Lecture declenchee"); // Répond au Pi
  readAndSendData(); // Lance la lecture et l'envoi
}

void setup() {
  Serial.begin(115200);
  dht.begin();

  connectToWiFi();

  // --- NOUVEAU : Configuration du serveur web ESP32 ---
  esp_server.on("/read_sensor", HTTP_GET, handleReadSensor); // Route pour déclencher la lecture
  esp_server.begin(); // Démarre le serveur web de l'ESP32
  Serial.println("Serveur web ESP32 démarré. En attente d'ordres sur /read_sensor");
  // ----------------------------------------------------

  Serial.println("\n----------------------------------------------------");
  Serial.println("Envoi de la première lecture (Test au démarrage)...");
  readAndSendData(); // Envoi initial
  Serial.println("----------------------------------------------------\n");

  previousMillis = millis();
}

void loop() {
  // --- NOUVEAU : Gérer les requêtes entrantes ---
  esp_server.handleClient();
  // ---------------------------------------------

  // Cycle d'envoi automatique toutes les 5 minutes (ne change pas)
  unsigned long currentMillis = millis();
  if (currentMillis - previousMillis >= interval) {
    previousMillis = currentMillis;
    Serial.println("\n----------------------------------------------------");
    Serial.println("Cycle automatique (5 min) atteint.");
    readAndSendData();
    Serial.println("----------------------------------------------------\n");
  }
}

void connectToWiFi() {
  Serial.print("Connexion à ");
  Serial.println(ssid);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nConnecté au WiFi !");
  Serial.print("Adresse IP de l'ESP32: ");
  Serial.println(WiFi.localIP()); // <-- Notez cette IP ! Le Pi doit la connaître.
}

// Lit le capteur ET envoie les données au Pi (ne change pas)
void readAndSendData() {
  Serial.print("Lecture du capteur DHT... ");
  float h = dht.readHumidity();
  float t = dht.readTemperature();

  if (isnan(h) || isnan(t)) {
    Serial.println("Échec !");
    return;
  }
  Serial.print("Réussie: ");
  Serial.print(t);
  Serial.print("°C, ");
  Serial.print(h);
  Serial.println("%");
  sendDataToServer(t, h);
}

// Envoie les données au Pi (ne change pas)
void sendDataToServer(float temp, float hum) {
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    char server_url[100];
    sprintf(server_url, "http://%s:5000%s", server_ip, server_endpoint);
    Serial.print("Envoi vers Pi: ");
    Serial.println(server_url);
    http.begin(server_url);
    http.addHeader("Content-Type", "application/json");
    StaticJsonDocument<100> jsonDoc;
    jsonDoc["temperature"] = temp;
    jsonDoc["humidity"] = hum;
    char jsonBuffer[100];
    serializeJson(jsonDoc, jsonBuffer);
    int httpResponseCode = http.POST(jsonBuffer);
    if (httpResponseCode > 0) {
      Serial.printf("Réponse du Pi: %d - %s\n", httpResponseCode, http.getString().c_str());
    } else {
      Serial.printf("Erreur envoi vers Pi: %d\n", httpResponseCode);
    }
    http.end();
  } else {
    Serial.println("ERREUR: Non connecté au WiFi pour envoyer au Pi.");
    connectToWiFi();
  }
}
