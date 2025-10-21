import * as api from './api.js';
import * as ui from './ui.js';

/**
 * Gère le clic sur les boutons d'action des cartes de plantes (éditer, historique, supprimer).
 * @param {Event} event - L'objet événement du clic.
 */
async function handlePlantAction(event) {
    const button = event.target.closest('.action-btn');
    if (!button) return;

    const card = button.closest('.plant');
    const plantId = card.dataset.plantId;
    const plantName = card.dataset.plantName;

    if (button.classList.contains('delete-btn')) {
        if (confirm(`Êtes-vous sûr de vouloir supprimer "${plantName}" ?`)) {
            try {
                await api.deletePlant(plantId);
                card.remove(); // Suppression optimiste de l'UI
            } catch (error) {
                alert("Erreur lors de la suppression.");
            }
        }
    } else if (button.classList.contains('history-btn')) {
        ui.showHistoryModal(plantId, plantName);
    } else if (button.classList.contains('edit-btn')) {
        alert("Le mode édition sera bientôt disponible !");
        // Logique future : ui.toggleEditMode(card);
    }
}

/**
 * Gère le clic sur le bouton "Marquer comme arrosé".
 * @param {Event} event - L'objet événement du clic.
 */
async function handleWatering(event) {
    const button = event.target.closest('.water-button');
    if (!button) return;

    const plantId = button.closest('.plant').dataset.plantId;
    
    button.disabled = true;
    button.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';

    try {
        await api.markAsWatered(plantId);
        // Feedback visuel de succès
        button.innerHTML = '<i class="fa-solid fa-check"></i> Arrosé !';
        button.classList.add('success');
        setTimeout(ui.renderPlants, 1200); // Recharger la liste après une seconde
    } catch (error) {
        alert("Erreur lors de la mise à jour.");
        button.disabled = false; // Réactiver le bouton en cas d'erreur
        button.textContent = "Marquer comme arrosé";
    }
}

/**
 * Gère la soumission du formulaire d'ajout de plante.
 * @param {Event} event
 */
async function handleAddPlant(event) {
    event.preventDefault();
    const nameInput = document.getElementById('plant-name');
    const typeSelect = document.getElementById('plant-type-select');
    const button = event.target.querySelector('button');

    button.disabled = true;

    try {
        await api.addPlant({ name: nameInput.value, type: typeSelect.value });
        nameInput.value = '';
        typeSelect.selectedIndex = 0;
        await ui.renderPlants();
    } catch (error) {
        alert(`Erreur: ${error.message}`);
    } finally {
        button.disabled = false;
    }
}

/** Fonction d'initialisation principale. */
async function initialize() {
    // --- GESTIONNAIRES D'ÉVÉNEMENTS ---

    // Délégation d'événements pour toutes les actions sur les cartes de plantes
    document.getElementById('plant-container').addEventListener('click', (event) => {
        handlePlantAction(event);
        handleWatering(event);
    });

    // Barre de recherche
    document.getElementById('plant-search-input').addEventListener('input', ui.filterPlants);

    // Formulaire d'ajout
    document.getElementById('add-plant-form').addEventListener('submit', handleAddPlant);

    // Rafraîchissement manuel de la météo
    document.getElementById('refresh-weather-btn').addEventListener('click', ui.updateWeatherData);

    // Mise à jour du graphique en cas de changement de période
    document.getElementById('period').addEventListener('change', ui.updateChart);

    // Fermeture des modales
    document.getElementById('history-modal-close-btn').addEventListener('click', () => {
        document.getElementById('history-modal').style.display = 'none';
    });
    document.getElementById('tips-modal-close-btn').addEventListener('click', () => {
        document.getElementById('tips-modal').style.display = 'none';
    });
    
    // Thème
    const themeCheckbox = document.querySelector('.theme-switch__checkbox');
    const applyTheme = (theme) => {
        document.body.classList.toggle('dark-mode', theme === 'dark');
        themeCheckbox.checked = (theme === 'dark');
    };
    themeCheckbox.addEventListener('change', () => {
        const newTheme = document.body.classList.contains('dark-mode') ? 'light' : 'dark';
        localStorage.setItem('theme', newTheme);
        applyTheme(newTheme);
    });
    applyTheme(localStorage.getItem('theme') || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'));

    // --- CHARGEMENT INITIAL DES DONNÉES ---
    await ui.populatePlantTypes();
    ui.updateWeatherData();
    ui.updateChart();
    ui.updateSmartRecommendation();
    ui.renderPlants();

    // --- INTERVALLES DE MISE À JOUR ---
    setInterval(ui.updateWeatherData, 60000); // Météo toutes les 60 secondes
    setInterval(() => {
        ui.renderPlants();
        ui.updateSmartRecommendation();
    }, 300000); // Plantes et reco toutes les 5 minutes
}

// Lancement de l'application
document.addEventListener('DOMContentLoaded', initialize);
