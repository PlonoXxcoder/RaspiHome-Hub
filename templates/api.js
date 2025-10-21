/**
 * Ce module centralise toutes les communications avec l'API du serveur.
 * Il exporte des fonctions claires pour chaque action, cachant la complexité
 * des appels `fetch` et de la gestion des erreurs réseau.
 */

// --- FONCTIONS DE BASE (NON EXPORTÉES) ---

/**
 * Fonction générique pour effectuer des requêtes GET.
 * @param {string} url - L'URL de l'API à appeler.
 * @returns {Promise<any>} La réponse JSON du serveur.
 */
async function fetchData(url) {
    try {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`Erreur HTTP ! Statut: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error(`Erreur lors de la récupération des données depuis ${url}:`, error);
        throw error;
    }
}

/**
 * Fonction générique pour effectuer des requêtes POST.
 * @param {string} url - L'URL de l'API à appeler.
 * @param {object} data - Les données JavaScript à envoyer dans le corps de la requête.
 * @returns {Promise<any>} La réponse JSON du serveur.
 */
async function postData(url, data) {
    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data),
        });
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.message || `Erreur HTTP ! Statut: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error(`Erreur lors de l'envoi de données vers ${url}:`, error);
        throw error;
    }
}


// --- FONCTIONS D'API SPÉCIFIQUES (EXPORTÉES) ---

// -- Données Météo --
export const fetchCurrentData = () => fetchData('/alldata');
export const fetchHistory = (period) => fetchData(`/history?period=${period}`);

// -- Gestion des Plantes --
export const fetchPlants = () => fetchData('/plants');
export const addPlant = (plantData) => postData('/add_plant', { nom: plantData.name, type: plantData.type });
export const deletePlant = (plantId) => postData(`/delete_plant/${plantId}`, {});
export const savePlantEdit = (plantId, plantData) => postData(`/edit_plant/${plantId}`, plantData);

// -- Arrosage --
export const markAsWatered = (plantId) => postData(`/watered/${plantId}`, {});
export const fetchWateringHistory = (plantId) => fetchData(`/plant_history/${plantId}`);

// -- Types de Plantes --
export const fetchPlantTypes = () => fetchData('/plant_types');
export const fetchPlantRules = () => fetchData('/plant_rules');
export const savePlantType = (typeData) => postData('/add_plant_type', typeData);

// -- Astuces et Recommandations --
export const fetchSmartRecommendation = () => fetchData('/smart_recommendation');
export const fetchTipForType = (plantType) => fetchData(`/tip_for_type/${plantType}`);
