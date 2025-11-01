/*
 * Fichier : templates/ui.js
 * Rôle : Gère toutes les manipulations du DOM (affichage, modales, graphique).
 */

let chartInstance = null;
const editModalOverlay = document.getElementById('edit-plant-modal');
const editForm = document.getElementById('edit-plant-form');
let activeModal = null;

// ======================= GESTION DES MODALES =======================

function openModal(modalOverlay) {
    if (modalOverlay) {
        modalOverlay.classList.add('active');
        activeModal = modalOverlay;
    }
}

export function closeModal() {
    if (activeModal) {
        activeModal.classList.remove('active');
        activeModal = null;
    }
}

document.querySelectorAll('.modal-overlay').forEach(modal => {
    const closeButton = modal.querySelector('.modal-close');
    if (closeButton) closeButton.addEventListener('click', closeModal);
    modal.addEventListener('click', (event) => {
        if (event.target === modal) closeModal();
    });
});

// ======================= AFFICHAGE (RENDERING) =======================

export function displaySmartRecommendation(data) {
    document.getElementById('smart-recommendation-text').textContent = data.message;
    document.getElementById('smart-recommendation-icon').className = `fa-solid ${data.icon}`;
}

export function displayWeatherData(data) {
    if (!data || typeof data.temperature !== 'number') return;
    document.getElementById('weather-temp').textContent = `${data.temperature.toFixed(1)} °C`;
    document.getElementById('weather-feels').textContent = `${data.feels_like.toFixed(1)} °C`;
    document.getElementById('weather-humidity').textContent = `${data.humidity.toFixed(1)} %`;
    document.getElementById('weather-pressure').textContent = `${data.pressure.toFixed(0)} hPa`;
    document.getElementById('weather-description').textContent = data.description;
    const iconElement = document.getElementById('weather-icon');
    iconElement.src = `https://openweathermap.org/img/wn/${data.icon}@2x.png`;
    iconElement.style.display = 'block';
}

export function displaySenseHATData(data) {
    if (data && typeof data.temperature === 'number') {
        document.getElementById('interior-temp').textContent = `${data.temperature.toFixed(1)} °C`;
        document.getElementById('interior-humidity').textContent = `${data.humidity.toFixed(1)} %`;
        document.getElementById('interior-pressure').textContent = `${data.pressure.toFixed(0)} hPa`;
        document.getElementById('interior-timestamp').textContent = `Dernière lecture: ${data.timestamp.split(' ')[1]}`;
    } else {
        document.getElementById('interior-temp').textContent = `-- °C`;
        document.getElementById('interior-humidity').textContent = `-- %`;
        document.getElementById('interior-pressure').textContent = `-- hPa`;
        document.getElementById('interior-timestamp').textContent = `En attente de données...`;
    }
}

export function displayESP32Data(data) {
    if (data && typeof data.temperature === 'number') {
        document.getElementById('distant-temp').textContent = `${data.temperature.toFixed(1)} °C`;
        document.getElementById('distant-humidity').textContent = `${data.humidity.toFixed(1)} %`;
        document.getElementById('distant-timestamp').textContent = `Dernière lecture: ${data.timestamp.split(' ')[1]}`;
    } else {
        document.getElementById('distant-temp').textContent = `-- °C`;
        document.getElementById('distant-humidity').textContent = `-- %`;
        document.getElementById('distant-timestamp').textContent = `En attente de données...`;
    }
}

export function createChart(chartData) {
    const ctx = document.getElementById('myChart').getContext('2d');
    if (chartInstance) {
        chartInstance.destroy();
    }

    let timeUnit = 'hour';
    if (chartData.datasets.length > 0 && chartData.datasets[0].data.length > 1) {
        const firstPoint = new Date(chartData.datasets[0].data[0].x);
        const lastPoint = new Date(chartData.datasets[0].data[chartData.datasets[0].data.length - 1].x);
        const diffDays = (lastPoint - firstPoint) / (1000 * 60 * 60 * 24);
        if (diffDays > 2) {
            timeUnit = 'day';
        }
    }

    chartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            datasets: chartData.datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            scales: {
                x: {
                    type: 'time',
                    time: {
                        unit: timeUnit,
                        tooltipFormat: 'dd MMM HH:mm',
                        displayFormats: {
                            hour: 'HH:mm',
                            day: 'dd MMM'
                        }
                    },
                    adapters: {
                        date: {
                            locale: 'fr'
                        }
                    },
                    title: {
                        display: true,
                        text: 'Date / Heure'
                    }
                },
                y_temp: { type: 'linear', display: true, position: 'left', title: { display: true, text: 'Température (°C)' } },
                y_hum: { type: 'linear', display: true, position: 'right', title: { display: true, text: 'Humidité (%)' }, grid: { drawOnChartArea: false } }
            }
        }
    });
}

export function displayPlants(plants) {
    const container = document.getElementById('plant-container');
    container.innerHTML = '';
    if (!plants || plants.length === 0) {
        container.innerHTML = '<p style="grid-column: 1 / -1;">Aucune plante trouvée.</p>';
        return;
    }
    plants.forEach(plant => {
        const plantCard = document.createElement('div');
        plantCard.className = 'plant';
        const daysSinceWatered = plant.days_since_watered;
        const waterFrequency = plant.watering_frequency;
        const percentage = Math.max(0, 100 - (daysSinceWatered / waterFrequency) * 100);
        let statusColor = 'var(--success-color)';
        if (percentage < 30) statusColor = 'var(--warning-color)';
        if (percentage <= 0) statusColor = 'var(--danger-color)';
        plantCard.innerHTML = `
            <div class="plant-header">
                <span class="plant-header-title">${plant.name}</span>
                <div class="plant-actions">
                    <button class="action-btn edit" title="Modifier" data-plant-id="${plant.id}"><i class="fa-solid fa-pencil"></i></button>
                    <button class="action-btn delete" title="Supprimer" data-plant-id="${plant.id}"><i class="fa-solid fa-trash"></i></button>
                </div>
            </div>
            <div class="plant-body">
                <p><strong>Type :</strong> ${plant.type_name}</p>
                <p><strong>Dernier arrosage :</strong> Il y a ${daysSinceWatered} jour(s)</p>
                <div class="water-progress-bar"><div class="water-progress" style="width: ${percentage.toFixed(1)}%; background-color: ${statusColor};"></div></div>
                <button class="water-button" data-plant-id="${plant.id}">Arroser maintenant</button>
            </div>`;
        container.appendChild(plantCard);
    });
}

export function populatePlantTypes(types) {
    if (!types) return;
    const addSelect = document.getElementById('add-plant-type');
    const editSelect = document.getElementById('edit-plant-type');
    addSelect.innerHTML = '<option value="" selected disabled>Choisir un type...</option>';
    editSelect.innerHTML = '';
    types.forEach(type => {
        const option = `<option value="${type.id}">${type.name}</option>`;
        addSelect.innerHTML += option;
        editSelect.innerHTML += option;
    });
}

export function openEditPlantModal(plant) {
    editForm.querySelector('#edit-plant-id').value = plant.id;
    editForm.querySelector('#edit-plant-name').value = plant.name;
    editForm.querySelector('#edit-plant-type').value = plant.type_id;
    const lastWateredDate = new Date(plant.last_watered_date).toISOString().split('T')[0];
    editForm.querySelector('#edit-plant-last-watered').value = lastWateredDate;
    openModal(editModalOverlay);
}
