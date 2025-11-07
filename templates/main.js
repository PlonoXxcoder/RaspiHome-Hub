/*
 * Fichier : templates/main.js
 * Rôle : Cerveau de l'application. Gère les appels API et coordonne l'UI.
 */
import * as api from './api.js';
import * as ui from './ui.js';

// --- FONCTIONS DE CHARGEMENT DES DONNÉES ---
async function loadWeatherData() { try { const data = await api.getWeatherData(); ui.displayWeatherData(data); } catch (e) { console.error("Erreur chargement météo:", e); } }
async function loadInteriorData() { try { const data = await api.getSenseHATData(); ui.displaySenseHATData(data); } catch (e) { console.error("Erreur chargement données intérieures:", e); } }
async function loadDistantData() { try { const data = await api.getESP32Data(); ui.displayESP32Data(data); } catch (e) { console.error("Erreur chargement données distantes:", e); } }
async function loadChart(period = 'day') { try { const [chartData, configData] = await Promise.all([api.getChartData(period), api.getConfigData()]); ui.createChart(chartData, configData); } catch (e) { console.error("Erreur chargement graphique:", e); } }
async function loadPlantData() { try { const [plants, types] = await Promise.all([api.getPlants(), api.getPlantTypes()]); ui.populatePlantTypes(types); ui.displayPlants(plants); } catch (e) { console.error("Erreur chargement plantes:", e); } }
async function loadSmartRecommendation() { try { const data = await api.getSmartRecommendation(); ui.displaySmartRecommendation(data); } catch (e) { console.error("Erreur chargement recommandation:", e); } }
async function loadRandomTip() { try { const data = await api.getRandomTip(); ui.displaySmartRecommendation(data); } catch (e) { console.error("Erreur chargement astuce aléatoire:", e); } }

// --- FONCTIONS DE GESTION DES ÉVÉNEMENTS ---
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
    document.getElementById('period-select').addEventListener('change', (e) => loadChart(e.target.value));
    
    // --- GESTION DE LA NOUVELLE MODALE D'AJOUT ---
    document.getElementById('show-add-plant-modal-btn').addEventListener('click', () => {
        ui.openAddPlantModal();
    });

    const typeSelect = document.getElementById('new-plant-type-select');
    const newTypeFields = document.getElementById('new-type-fields');
    const newTypeNameInput = document.getElementById('new-type-name');
    const newTypeSummerInput = document.getElementById('new-type-summer');
    const newTypeWinterInput = document.getElementById('new-type-winter');

    typeSelect.addEventListener('change', () => {
        const isNew = typeSelect.value === '--new--';
        newTypeFields.style.display = isNew ? 'block' : 'none';
        newTypeNameInput.required = isNew;
        newTypeSummerInput.required = isNew;
        newTypeWinterInput.required = isNew;
    });

    document.getElementById('add-plant-form-new').addEventListener('submit', async (e) => {
        e.preventDefault();
        const isNewType = typeSelect.value === '--new--';
        const plantData = {
            name: document.getElementById('new-plant-name').value,
            next_watering_date: document.getElementById('new-plant-next-watering').value,
            is_new_type: isNewType,
            type_name: isNewType ? newTypeNameInput.value : typeSelect.value,
            summer_weeks: newTypeSummerInput.value,
            winter_weeks: newTypeWinterInput.value
        };
        await api.addPlant(plantData);
        ui.closeModal();
        loadPlantData();
    });

    // --- GESTION DE LA MODALE DE MODIFICATION (EXISTANTE) ---
    document.getElementById('edit-plant-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const id = document.getElementById('edit-plant-id').value;
        const name = document.getElementById('edit-plant-name').value;
        const type_id = document.getElementById('edit-plant-type').value;
        await api.updatePlant(id, { name, type: type_id });
        ui.closeModal();
        loadPlantData();
    });

    // --- GESTION DES CLICS SUR LES CARTES DE PLANTES ---
    document.getElementById('plant-container').addEventListener('click', async (e) => {
        const button = e.target.closest('button.action-btn, button.water-button');
        if (!button) return;
        const plantId = button.dataset.plantId;
        if (!plantId) return;

        if (button.classList.contains('edit')) {
            const plantData = await api.getPlant(plantId);
            ui.openEditPlantModal(plantData);
        } else if (button.classList.contains('delete')) {
            if (confirm('Êtes-vous sûr de vouloir supprimer cette plante ?')) {
                await api.deletePlant(plantId);
                loadPlantData();
            }
        } else if (button.classList.contains('water-button')) {
            await api.waterPlant(plantId);
            loadPlantData();
            loadSmartRecommendation();
        }
    });
}

// --- INITIALISATION DE L'APPLICATION ---
async function initializeApp() {
    await Promise.all([
        loadSmartRecommendation(),
        loadWeatherData(),
        loadInteriorData(),
        loadDistantData(),
        loadPlantData(),
        loadChart('day')
    ]);
    setupEventListeners();
    setInterval(() => { loadInteriorData(); loadDistantData(); }, 60000);
    setInterval(() => {
        const currentIcon = document.getElementById('smart-recommendation-icon').className;
        if (!currentIcon.includes('fa-tint')) { loadRandomTip(); }
    }, 30000);
}

document.addEventListener('DOMContentLoaded', initializeApp);
