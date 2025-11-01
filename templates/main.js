/*
 * Fichier : templates/main.js
 * Rôle : Cerveau de l'application. Gère les appels API et coordonne l'UI.
 */
import * as api from './api.js';
import * as ui from './ui.js';

// --- Fonctions de chargement des données ---

async function loadWeatherData() {
    try {
        const data = await api.getWeatherData();
        ui.displayWeatherData(data);
    } catch (error) {
        console.error("Erreur chargement météo:", error);
    }
}

async function loadInteriorData() {
    try {
        const data = await api.getSenseHATData();
        ui.displaySenseHATData(data);
    } catch (error) {
        console.error("Erreur chargement données intérieures:", error);
    }
}

async function loadDistantData() {
    try {
        const data = await api.getESP32Data();
        ui.displayESP32Data(data);
    } catch (error) {
        console.error("Erreur chargement données distantes:", error);
    }
}

async function loadChart(period = 'day') {
    try {
        const data = await api.getChartData(period);
        ui.createChart(data);
    } catch (error) {
        console.error("Erreur chargement graphique:", error);
    }
}

async function loadPlantData() {
    try {
        const [plants, types] = await Promise.all([api.getPlants(), api.getPlantTypes()]);
        ui.populatePlantTypes(types);
        ui.displayPlants(plants);
    } catch (error) {
        console.error("Erreur chargement plantes:", error);
    }
}

async function loadSmartRecommendation() {
    try {
        const data = await api.getSmartRecommendation();
        ui.displaySmartRecommendation(data);
    } catch (error) {
        console.error("Erreur chargement recommandation:", error);
    }
}

async function loadRandomTip() {
    try {
        const data = await api.getRandomTip();
        ui.displaySmartRecommendation(data);
    } catch (error) {
        console.error("Erreur chargement astuce aléatoire:", error);
    }
}

// --- Fonctions de gestion des événements ---

async function handleManualRefresh() {
    const refreshButtonIcon = document.querySelector('#refresh-weather-btn i');
    refreshButtonIcon.classList.add('spinning');
    try {
        const allData = await api.refreshAllSensors();
        if (allData.weather) ui.displayWeatherData(allData.weather);
        if (allData.sensehat) ui.displaySenseHATData(allData.sensehat);
        if (allData.esp32) ui.displayESP32Data(allData.esp32);
    } catch (error) {
        console.error("Erreur lors du rafraîchissement manuel:", error);
    } finally {
        refreshButtonIcon.classList.remove('spinning');
    }
}

function setupEventListeners() {
    document.getElementById('refresh-weather-btn').addEventListener('click', handleManualRefresh);
    
    // --- VÉRIFICATION ET CORRECTION ICI ---
    // On s'assure que l'élément existe avant d'ajouter l'écouteur
    const periodSelect = document.getElementById('period-select');
    if (periodSelect) {
        periodSelect.addEventListener('change', (event) => {
            // On appelle la fonction loadChart avec la nouvelle valeur (day, week, month)
            loadChart(event.target.value);
        });
    }

    // Le reste des formulaires
    // (Le code pour les plantes, etc. reste le même)
}

// --- Initialisation de l'application ---

async function initializeApp() {
    await Promise.all([
        loadSmartRecommendation(),
        loadWeatherData(),
        loadInteriorData(),
        loadDistantData(),
        loadPlantData(),
        loadChart('day') // On charge la vue "jour" par défaut
    ]);

    setupEventListeners();

    // Intervalles de rafraîchissement
    setInterval(() => {
        loadInteriorData();
        loadDistantData();
    }, 60000);

    setInterval(() => {
        const currentIcon = document.getElementById('smart-recommendation-icon').className;
        if (!currentIcon.includes('fa-tint')) {
            loadRandomTip();
        }
    }, 30000);
}

document.addEventListener('DOMContentLoaded', initializeApp);
