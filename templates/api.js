/*
 * Fichier : templates/api.js
 * Rôle : Gère toutes les communications avec le serveur Flask (backend).
 */

/**
 * Une fonction utilitaire pour gérer les appels fetch, vérifier les erreurs et parser le JSON.
 * @param {string} url L'URL de l'API à appeler.
 * @param {object} options Les options de la requête fetch (méthode, headers, body, etc.).
 * @returns {Promise<any>} La réponse JSON du serveur.
 */
async function fetchJSON(url, options = {}) {
    try {
        const response = await fetch(url, options);
        if (!response.ok) {
            throw new Error(`Erreur HTTP ${response.status}: ${response.statusText}`);
        }
        if (response.status === 204) { // No Content
            return {};
        }
        return await response.json();
    } catch (error) {
        console.error(`Erreur lors de l'appel à ${url}:`, error);
        throw error;
    }
}

// --- Fonctions d'obtention des données (GET) ---

export function getWeatherData() {
    return fetchJSON('/weather');
}

export function getSenseHATData() {
    return fetchJSON('/sensehat_latest');
}

export function getESP32Data() {
    return fetchJSON('/esp32_latest');
}

export function getChartData(period = 'day') {
    return fetchJSON(`/alldata?period=${period}`);
}

export function getPlants() {
    return fetchJSON('/plants');
}

export function getPlantTypes() {
    return fetchJSON('/plant_types');
}

export function getSmartRecommendation() {
    return fetchJSON('/smart_recommendation');
}

export function getRandomTip() {
    return fetchJSON('/random_tip');
}

export function getPlant(id) {
    return fetchJSON(`/plant/${id}`);
}

// --- Fonctions de modification des données (POST, PUT, DELETE) ---

export function addPlant(data) {
    return fetchJSON('/plants', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });
}

export function managePlantType(data) {
    return fetchJSON('/plant_types', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });
}

export function updatePlant(id, data) {
    return fetchJSON(`/plant/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });
}

export function deletePlant(id) {
    return fetchJSON(`/plant/${id}`, {
        method: 'DELETE'
    });
}

export function waterPlant(id) {
    return fetchJSON(`/plant/${id}/water`, {
        method: 'POST'
    });
}

export function refreshAllSensors() {
    return fetchJSON('/refresh/all', { method: 'POST' });
}
