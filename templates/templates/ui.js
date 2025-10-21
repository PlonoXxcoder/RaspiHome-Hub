import * as api from './api.js';

let chartInstance;
let plantsCache = []; // Cache pour la recherche en direct

// Cache des éléments du DOM pour un accès rapide
const DOMElements = {
    plantContainer: document.getElementById('plant-container'),
    plantSearchInput: document.getElementById('plant-search-input'),
    historyModal: document.getElementById('history-modal'),
    historyModalTitle: document.getElementById('history-modal-title'),
    historyModalList: document.getElementById('history-modal-list'),
    recommendationIcon: document.getElementById('smart-recommendation-icon'),
    recommendationText: document.getElementById('smart-recommendation-text'),
};

/** Affiche ou met à jour les données météo en temps réel. */
export async function updateWeatherData() {
    try {
        const data = await api.fetchCurrentData();
        document.getElementById('weather-temp').textContent = `${data.temperature}°C`;
        document.getElementById('weather-heat').textContent = `${data.heat_index}°C`;
        document.getElementById('weather-hum').textContent = `${data.humidite}%`;
        document.getElementById('weather-pres').textContent = `${data.pression} hPa`;
    } catch (error) {
        console.error("Impossible de mettre à jour la météo.");
    }
}

/** Crée ou met à jour le graphique d'évolution. */
export async function updateChart() {
    try {
        const period = document.getElementById('period').value;
        const data = await api.fetchHistory(period);
        const ctx = document.getElementById('myChart').getContext('2d');

        if (chartInstance) {
            chartInstance.destroy();
        }
        chartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.datetime,
                datasets: [
                    { label: 'Température (°C)', data: data.temp, borderColor: '#ff6384', yAxisID: 'y' },
                    { label: 'Humidité (%)', data: data.hum, borderColor: '#36a2eb', yAxisID: 'y' }
                ]
            },
            options: {
                responsive: true, interaction: { mode: 'index', intersect: false },
                scales: { y: { position: 'left', title: { display: true, text: '°C / %' } } }
            }
        });
    } catch (error) {
        console.error("Impossible de mettre à jour le graphique.");
    }
}

/** Affiche la recommandation intelligente en haut de page. */
export async function updateSmartRecommendation() {
    try {
        const data = await api.fetchSmartRecommendation();
        DOMElements.recommendationIcon.className = `fa-solid ${data.icon}`;
        DOMElements.recommendationText.innerHTML = data.message;
    } catch (error) {
        DOMElements.recommendationText.textContent = "Impossible de charger la recommandation.";
    }
}

/** Crée et affiche les cartes des plantes. */
export async function renderPlants() {
    try {
        const plants = await api.fetchPlants();
        plantsCache = plants;
        DOMElements.plantContainer.innerHTML = '';

        if (plants.length === 0) {
            DOMElements.plantContainer.innerHTML = '<p class="empty-state">Aucune plante. Ajoutez-en une pour commencer !</p>';
            return;
        }

        plants.forEach(plant => {
            const plantCard = createPlantCard(plant);
            DOMElements.plantContainer.appendChild(plantCard);
        });
        filterPlants(); // Applique le filtre de recherche
    } catch (error) {
        DOMElements.plantContainer.innerHTML = '<p class="empty-state">Erreur lors du chargement des plantes.</p>';
    }
}

/** Crée l'élément HTML pour une seule carte de plante. */
function createPlantCard(plant) {
    const card = document.createElement('div');
    card.className = `plant ${plant.is_due ? 'due' : ''}`;
    card.dataset.plantId = plant.id;
    card.dataset.plantName = plant.name;
    card.dataset.plantType = plant.type;

    card.innerHTML = `
        <div class="plant-header">
            <h3 class="plant-name-display"><i class="fa-solid fa-leaf"></i> ${plant.name}</h3>
            <div class="plant-actions">
                <button class="action-btn edit-btn" title="Modifier"><i class="fa-solid fa-pencil"></i></button>
                <button class="action-btn history-btn" title="Historique"><i class="fa-solid fa-clock-rotate-left"></i></button>
                <button class="action-btn delete-btn" title="Supprimer"><i class="fa-solid fa-trash"></i></button>
            </div>
        </div>
        <div class="plant-body">
            <div class="plant-info">
                <span class="plant-type-tag">${plant.type.charAt(0).toUpperCase() + plant.type.slice(1)}</span>
                <p>Prochain arrosage : <strong>${plant.status}</strong></p>
            </div>
            ${plant.is_due ? `<button class="water-button">Marquer comme arrosé</button>` : ''}
        </div>
    `;
    return card;
}

/** Filtre les plantes affichées en fonction du texte dans la barre de recherche. */
export function filterPlants() {
    const searchTerm = DOMElements.plantSearchInput.value.toLowerCase();
    const plantCards = DOMElements.plantContainer.querySelectorAll('.plant');

    plantCards.forEach(card => {
        const name = card.dataset.plantName.toLowerCase();
        const type = card.dataset.plantType.toLowerCase();
        const isVisible = name.includes(searchTerm) || type.includes(searchTerm);
        card.classList.toggle('hidden', !isVisible);
    });
}

/** Affiche la modale de l'historique d'arrosage pour une plante. */
export async function showHistoryModal(plantId, plantName) {
    DOMElements.historyModalTitle.textContent = `Historique d'arrosage de ${plantName}`;
    DOMElements.historyModalList.innerHTML = '<li>Chargement...</li>';
    DOMElements.historyModal.style.display = 'flex';

    try {
        const history = await api.fetchWateringHistory(plantId);
        DOMElements.historyModalList.innerHTML = '';
        if (history.length > 0) {
            history.forEach(dateStr => {
                const li = document.createElement('li');
                const date = new Date(dateStr + 'T00:00:00');
                li.textContent = date.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' });
                DOMElements.historyModalList.appendChild(li);
            });
        } else {
            DOMElements.historyModalList.innerHTML = '<li>Aucun historique d\'arrosage trouvé.</li>';
        }
    } catch (error) {
        DOMElements.historyModalList.innerHTML = '<li>Erreur lors du chargement de l\'historique.</li>';
    }
}

/** Remplit les listes déroulantes des types de plantes. */
export async function populatePlantTypes() {
    try {
        const types = await api.fetchPlantTypes();
        const selectElement = document.getElementById('plant-type-select');
        const datalistElement = document.getElementById('plant-type-list');
        selectElement.innerHTML = '<option value="">-- Choisir --</option>';
        datalistElement.innerHTML = '';
        types.forEach(type => {
            const typeCapitalized = type.charAt(0).toUpperCase() + type.slice(1);
            const option = document.createElement('option');
            option.value = type;
            option.textContent = typeCapitalized;
            selectElement.appendChild(option);
            const datalistOption = document.createElement('option');
            datalistOption.value = typeCapitalized;
            datalistElement.appendChild(datalistOption);
        });
    } catch (error) {
        console.error("Impossible de peupler les types de plantes.");
    }
}
