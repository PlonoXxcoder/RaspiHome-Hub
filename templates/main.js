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
async function loadChart(period = '24h') { try { const [chartData, configData] = await Promise.all([api.getChartData(period), api.getConfigData()]); ui.createChart(chartData, configData); } catch (e) { console.error("Erreur chargement graphique:", e); } }
async function loadPlantData() { try { const [plants, types] = await Promise.all([api.getPlants(), api.getPlantTypes()]); ui.populatePlantTypes(types); ui.displayPlants(plants); } catch (e) { console.error("Erreur chargement plantes:", e); } }
async function loadSmartRecommendation() { try { const data = await api.getSmartRecommendation(); ui.displaySmartRecommendation(data); } catch (e) { console.error("Erreur chargement recommandation:", e); } }
async function loadRandomTip() { try { const data = await api.getRandomTip(); ui.displaySmartRecommendation(data); } catch (e) { console.error("Erreur chargement astuce aléatoire:", e); } }

/**
 * NOUVEAU V1.5
 * Charge les données des tâches et demande à l'UI de les afficher.
 */
async function loadTaskData() {
    try {
        const tasks = await api.getTasks();
        ui.displayTasks(tasks);
    } catch (e) {
        console.error("Erreur chargement tâches:", e);
    }
}

/**
 * NOUVEAU V1.6
 * Charge l'astuce météo contextuelle.
 */
async function loadWeatherTip() {
    try {
        const data = await api.getWeatherTip();
        ui.displayWeatherTip(data);
    } catch (e) {
        console.error("Erreur chargement astuce météo:", e);
    }
}


// --- FONCTIONS DE GESTION DES ÉVÉNEMENTS ---

/**
 * MODIFIÉ V1.7
 * Gère le rafraîchissement manuel.
 * Force les capteurs à écrire en BDD, puis recharge les données côté client.
 */
async function handleManualRefresh() {
    const refreshButtonIcon = document.querySelector('#refresh-weather-btn i');
    refreshButtonIcon.classList.add('spinning');
    try {
        // 1. Demande au serveur de forcer la lecture des capteurs (qui écrivent en BDD)
        await api.refreshAllSensors();
        
        // 2. Attend 2 secondes (laissé dans serveur_temp.py) que l'ESP32 réponde
        
        // 3. Recharge toutes les données côté client (météo, capteurs BDD, astuces BDD)
        // Note : le 'await' n'est pas nécessaire ici car on veut que tout se charge en parallèle
        loadWeatherData();
        loadInteriorData();
        loadDistantData();  // Recharge depuis /esp32_latest (qui lit la BDD)
        loadWeatherTip();   // Recharge l'astuce SDB depuis la BDD
        loadSmartRecommendation(); // Met à jour l'alerte chauffage
        
    } catch (error) {
        console.error("Erreur lors du rafraîchissement manuel:", error);
    } finally {
        // S'assure que l'icône arrête de tourner même si le rafraîchissement de l'ESP échoue
        setTimeout(() => refreshButtonIcon.classList.remove('spinning'), 500);
    }
}

function setupEventListeners() {
    document.getElementById('refresh-weather-btn').addEventListener('click', handleManualRefresh);
    document.getElementById('period-select').addEventListener('change', (e) => loadChart(e.target.value));
    
    // --- GESTION MODALE AJOUT PLANTE (Logique existante) ---
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

    // --- GESTION MODALE MODIFICATION PLANTE (Logique existante) ---
    document.getElementById('edit-plant-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const id = document.getElementById('edit-plant-id').value;
        const name = document.getElementById('edit-plant-name').value;
        const type_id = document.getElementById('edit-plant-type').value;
        await api.updatePlant(id, { name, type: type_id });
        ui.closeModal();
        loadPlantData();
    });

    // --- GESTION CLICS CARTES PLANTES (Logique existante) ---
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

    // --- NOUVEAU : GESTION FORMULAIRE AJOUT TÂCHE V1.5 ---
    document.getElementById('add-task-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const nameInput = document.getElementById('new-task-name');
        const freqInput = document.getElementById('new-task-frequency');
        
        const taskData = {
            name: nameInput.value,
            frequency_days: parseInt(freqInput.value, 10)
        };

        try {
            await api.addTask(taskData);
            nameInput.value = '';
            freqInput.value = '';
            loadTaskData(); // Recharger les tâches
            loadSmartRecommendation(); // Mettre à jour l'astuce
        } catch (error) {
            console.error("Erreur lors de l'ajout de la tâche:", error);
            alert("Impossible d'ajouter la tâche.");
        }
    });

    // --- NOUVEAU : GESTION CLICS CARTES TÂCHES V1.5 ---
    document.getElementById('task-container').addEventListener('click', async (e) => {
        const button = e.target.closest('button.complete-task-button, button.delete-task');
        if (!button) return;

        const taskId = button.dataset.taskId;
        if (!taskId) return;

        if (button.classList.contains('complete-task-button')) {
            try {
                await api.completeTask(taskId);
                loadTaskData(); // Recharger les tâches
                loadSmartRecommendation(); // Mettre à jour l'astuce
            } catch (error) {
                console.error("Erreur lors de la complétion de la tâche:", error);
            }
        } else if (button.classList.contains('delete-task')) {
            if (confirm('Êtes-vous sûr de vouloir supprimer cette tâche ?')) {
                try {
                    await api.deleteTask(taskId);
                    loadTaskData(); // Recharger les tâches
                    loadSmartRecommendation(); // Mettre à jour l'astuce
                } catch (error) {
                    console.error("Erreur lors de la suppression de la tâche:", error);
                }
            }
        }
    });
}

// --- INITIALISATION DE L'APPLICATION (MODIFIÉE V1.6) ---
async function initializeApp() {
    await Promise.all([
        loadSmartRecommendation(),
        loadWeatherTip(), // Ajout de l'astuce météo
        loadWeatherData(),
        loadInteriorData(),
        loadDistantData(),
        loadPlantData(),
        loadTaskData(), // Ajout du chargement des tâches
        loadChart('24h') // Modifié pour correspondre au HTML ('24h' au lieu de 'day')
    ]);
    setupEventListeners();
    
    // Rafraîchit les capteurs (qui lisent la BDD) et l'astuce météo contextuelle
    setInterval(() => { 
        loadInteriorData(); 
        loadDistantData();
        loadWeatherTip(); // Ajouté à la boucle de 60s
    }, 60000); 
    
    // Rafraîchit l'astuce principale (alertes)
    setInterval(() => {
        const currentIcon = document.getElementById('smart-recommendation-icon').className;
        
        // Ne pas rafraîchir si une alerte est déjà affichée (plante, tâche, ou chauffage)
        if (!currentIcon.includes('fa-tint') && !currentIcon.includes('fa-broom') && !currentIcon.includes('fa-fire')) {
            loadRandomTip(); 
        } else {
            // Si une alerte est affichée, on la revérifie au cas où elle serait résolue
            loadSmartRecommendation();
        }
    }, 30000);
}

document.addEventListener('DOMContentLoaded', initializeApp);
