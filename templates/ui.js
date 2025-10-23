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
    recommendationCard: document.getElementById('smart-recommendation-card'),
};

/**
 * Choisit une couleur dans un dégradé en fonction du temps restant.
 * Utilise les variables CSS pour s'adapter automatiquement au thème clair/sombre.
 * @param {number} daysUntil - Jours restants avant l'arrosage.
 * @param {number} totalInterval - L'intervalle total d'arrosage en jours.
 * @returns {string} La couleur hexadécimale.
 */
function getWateringStatusColor(daysUntil, totalInterval) {
    // Lit les valeurs des variables CSS directement depuis le document
    const style = getComputedStyle(document.body);
    const colors = {
        safe:    style.getPropertyValue('--plant-color-safe').trim(),
        soon:    style.getPropertyValue('--plant-color-soon').trim(),
        due:     style.getPropertyValue('--plant-color-due').trim(),
        overdue: style.getPropertyValue('--plant-color-overdue').trim()
    };

    // Définit les couleurs par défaut (pour le thème clair)
    const defaults = {
        safe: '#81C784',
        soon: '#FFF176',
        due: '#FFB74D',
        overdue: '#E57373'
    };

    // Logique pour choisir la couleur
    if (daysUntil <= 0) {
        return colors.overdue || defaults.overdue;
    }
    if (totalInterval <= 1) {
        return colors.safe || defaults.safe;
    }
    const percentage = (daysUntil / totalInterval) * 100;

    if (percentage > 75) {
        return colors.safe || defaults.safe;
    } else if (percentage > 40) {
        return colors.soon || defaults.soon;
    } else if (percentage > 0) {
        return colors.due || defaults.due;
    } else {
        return colors.overdue || defaults.overdue;
    }
}

/**
 * Affiche ou met à jour les données météo en temps réel.
 */
export async function updateWeatherData() {
    try {
        const data = await api.fetchCurrentData();
        document.getElementById('weather-temp').textContent = `${data.temperature.toFixed(2)}°C`;
        document.getElementById('weather-heat').textContent = `${data.heat_index.toFixed(2)}°C`;
        document.getElementById('weather-hum').textContent = `${data.humidite}%`;
        document.getElementById('weather-pres').textContent = `${data.pression} hPa`;

        const descriptionElement = document.getElementById('weather-description');
        const iconElement = document.getElementById('weather-icon');
        
        if (data.description) {
            descriptionElement.textContent = data.description;
        }
        if (data.icon) {
            iconElement.src = `https://openweathermap.org/img/wn/${data.icon}@2x.png`;
            iconElement.style.display = 'inline-block';
        } else {
            iconElement.style.display = 'none';
        }

    } catch (error) {
        console.error("Impossible de mettre à jour la météo.");
        document.getElementById('weather-description').textContent = "Erreur de connexion";
    }
}

/**
 * Crée ou met à jour le graphique d'évolution.
 */
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

/**
 * Affiche la recommandation intelligente en haut de page.
 */
export async function updateSmartRecommendation() {
    try {
        const data = await api.fetchSmartRecommendation();
        DOMElements.recommendationIcon.className = `fa-solid ${data.icon}`;
        DOMElements.recommendationText.innerHTML = data.message;
        DOMElements.recommendationCard.classList.remove('error');
    } catch (error) {
        DOMElements.recommendationText.textContent = "Impossible de charger la recommandation.";
        DOMElements.recommendationCard.classList.add('error');
    }
}

/**
 * Crée et affiche les cartes des plantes.
 */
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
        filterPlants();
    } catch (error) {
        DOMElements.plantContainer.innerHTML = '<p class="empty-state">Erreur lors du chargement des plantes.</p>';
    }
}

/**
 * Crée l'élément HTML pour une seule carte de plante, avec la couleur dynamique.
 */
function createPlantCard(plant) {
    const card = document.createElement('div');
    card.className = 'plant';
    card.dataset.plantId = plant.id;
    card.dataset.plantName = plant.name;
    card.dataset.plantType = plant.type;

    const statusColor = getWateringStatusColor(plant.days_until_watering, plant.watering_interval);
    
    // Détermine la couleur du texte pour une meilleure lisibilité
    const lightColors = ['#FFF176', '#FFB74D']; // Jaune et Orange clair
    const isLight = lightColors.includes(statusColor.toUpperCase());
    const textColor = isLight ? '#333' : 'white';

    card.innerHTML = `
        <div class="plant-header" style="background-color: ${statusColor}; color: ${textColor};">
            <h3 class="plant-name-display"><i class="fa-solid fa-leaf"></i> ${plant.name}</h3>
            <div class="plant-actions">
                <button class="action-btn edit-btn" title="Modifier" style="color: ${textColor};"><i class="fa-solid fa-pencil"></i></button>
                <button class="action-btn history-btn" title="Historique" style="color: ${textColor};"><i class="fa-solid fa-clock-rotate-left"></i></button>
                <button class="action-btn delete-btn" title="Supprimer" style="color: ${textColor};"><i class="fa-solid fa-trash"></i></button>
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

/**
 * Filtre les plantes affichées en fonction du texte dans la barre de recherche.
 */
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

/**
 * Affiche la modale de l'historique d'arrosage pour une plante.
 */
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

/**
 * Remplit les listes déroulantes des types de plantes.
 */
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
