/*
 * Fichier : templates/ui.js
 * Rôle : Gère toutes les manipulations du DOM (affichage, modales, graphique).
 */

let chartInstance = null;
const editModalOverlay = document.getElementById('edit-plant-modal');
const addModalOverlay = document.getElementById('add-plant-modal');
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

export function openAddPlantModal() {
    if (addModalOverlay) {
        document.getElementById('add-plant-form-new').reset();
        document.getElementById('new-type-fields').style.display = 'none';
        document.getElementById('new-plant-type-select').value = "";
        const newTypeNameInput = document.getElementById('new-type-name');
        const newTypeSummerInput = document.getElementById('new-type-summer');
        const newTypeWinterInput = document.getElementById('new-type-winter');
        newTypeNameInput.required = false;
        newTypeSummerInput.required = false;
        newTypeWinterInput.required = false;
        openModal(addModalOverlay);
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
    const textElement = document.getElementById('smart-recommendation-text');
    const iconElement = document.getElementById('smart-recommendation-icon');
    if (textElement && iconElement) {
        textElement.textContent = data.message;
        iconElement.className = `fa-solid ${data.icon}`;
    }
}

/**
 * Affiche l'astuce météo contextuelle dans la carte dédiée.
 * @param {object} data - L'objet astuce (ex: {message: "...", icon: "..."})
 */
export function displayWeatherTip(data) {
    const textElement = document.getElementById('weather-tip-text');
    const iconElement = document.getElementById('weather-tip-icon');
    if (textElement && iconElement) {
        textElement.textContent = data.message;
        iconElement.className = `fa-solid ${data.icon}`;
    }
}

export function displayWeatherData(data) {
    if (!data || typeof data.temperature !== 'number') return;
    document.getElementById('weather-temp').textContent = `${data.temperature.toFixed(1)} °C`;
    document.getElementById('weather-feels').textContent = `${data.feels_like.toFixed(1)} °C`;
    document.getElementById('weather-humidity').textContent = `${data.humidity.toFixed(1)} %`;
    document.getElementById('weather-pressure').textContent = `${data.pressure.toFixed(0)} hPa`;
    document.getElementById('weather-description').textContent = data.description;

    const iconContainer = document.getElementById('animated-weather-icon-container');
    if (!iconContainer) {
        console.error("Erreur critique : L'élément 'animated-weather-icon-container' est introuvable dans index.html !");
        return;
    }
    const weatherIconCode = data.icon.slice(0, 2);

    iconContainer.querySelectorAll('.icon').forEach(icon => {
        icon.style.display = 'none';
    });

    let iconToShow = null;
    switch (weatherIconCode) {
        case '01': iconToShow = iconContainer.querySelector('.sunny'); break;
        case '02': case '03': case '04': iconToShow = iconContainer.querySelector('.cloudy'); break;
        case '09': iconToShow = iconContainer.querySelector('.sun-shower'); break;
        case '10': iconToShow = iconContainer.querySelector('.rainy'); break;
        case '11': iconToShow = iconContainer.querySelector('.thunder-storm'); break;
        case '13': iconToShow = iconContainer.querySelector('.flurries'); break;
        default: iconToShow = iconContainer.querySelector('.cloudy'); break;
    }

    if (iconToShow) {
        iconToShow.style.display = 'inline-block';
    }
}

/**
 * Affiche les données du Sense HAT.
 * Ne cache PAS la carte, pour permettre le débogage.
 */
export function displaySenseHATData(data) {
    const card = document.getElementById('interior-card');
    if (!card) return;
    card.style.display = 'block'; // S'assurer que la carte est visible

    if (data && data.timestamp === "Capteur désactivé") {
        document.getElementById('interior-temp').textContent = `-- °C`;
        document.getElementById('interior-humidity').textContent = `-- %`;
        document.getElementById('interior-pressure').textContent = `-- hPa`;
        document.getElementById('interior-timestamp').textContent = `Capteur désactivé`;
    } else if (data && typeof data.temperature === 'number') {
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
    if (data && data.timestamp === "Aucune donnée") {
        document.getElementById('distant-temp').textContent = `-- °C`;
        document.getElementById('distant-humidity').textContent = `-- %`;
        document.getElementById('distant-timestamp').textContent = `En attente de données...`;
        return;
    }

    if (data && typeof data.temperature === 'number') {
        document.getElementById('distant-temp').textContent = `${data.temperature.toFixed(1)} °C`;
        document.getElementById('distant-humidity').textContent = `${data.humidity.toFixed(1)} %`;
        document.getElementById('distant-timestamp').textContent = data.timestamp;
    } else {
        document.getElementById('distant-temp').textContent = `-- °C`;
        document.getElementById('distant-humidity').textContent = `-- %`;
        document.getElementById('distant-timestamp').textContent = `...`;
    }
}

/**
 * Crée le graphique.
 * Accepte 'viewPeriod' pour définir le zoom initial.
 * @param {object} chartData - Les données (datasets)
 * @param {object} configData - La config (seuils, etc.)
 * @param {string} viewPeriod - La vue sélectionnée (ex: '24h', '7d')
 */
export function createChart(chartData, configData, viewPeriod = '30d') {
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

    const nightZones = {};
    if (configData && configData.sunrise && configData.sunset) {
        nightZones.nightStart = { type: 'box', xMin: new Date(new Date().setHours(0,0,0,0)), xMax: new Date(configData.sunrise), backgroundColor: 'rgba(100, 100, 100, 0.1)', borderColor: 'transparent' };
        nightZones.nightEnd = { type: 'box', xMin: new Date(configData.sunset), xMax: new Date(new Date().setHours(23,59,59,999)), backgroundColor: 'rgba(100, 100, 100, 0.1)', borderColor: 'transparent' };
    }
    const tempThresholds = {};
    if(configData && configData.temp_ideal_min) {
        tempThresholds.min = { type: 'line', yMin: configData.temp_ideal_min, yMax: configData.temp_ideal_min, borderColor: 'rgba(0, 255, 0, 0.3)', borderWidth: 2, borderDash: [5, 5], label: { content: `${configData.temp_ideal_min}°C`, display: true, position: 'start' } };
        tempThresholds.max = { type: 'line', yMin: configData.temp_ideal_max, yMax: configData.temp_ideal_max, borderColor: 'rgba(255, 0, 0, 0.3)', borderWidth: 2, borderDash: [5, 5], label: { content: `${configData.temp_ideal_max}°C`, display: true, position: 'start' } };
    }

    
    // Définition du zoom initial basé sur la vue
    const now = new Date();
    let initialMin = undefined; // 'undefined' = zoom automatique
    let initialMax = new Date(now); // On zoome toujours jusqu'à "maintenant"

    if (viewPeriod === '8h') {
        initialMin = new Date(new Date().setHours(now.getHours() - 8));
        timeUnit = 'hour'; // Forcer l'unité en 'hour'
    } else if (viewPeriod === '24h') {
        initialMin = new Date(new Date().setDate(now.getDate() - 1));
        timeUnit = 'hour'; // Forcer l'unité en 'hour'
    } else if (viewPeriod === '7d') {
        initialMin = new Date(new Date().setDate(now.getDate() - 7));
        timeUnit = 'day'; // Forcer l'unité en 'day'
    }
    // Si viewPeriod est '30d', initialMin reste undefined, le graphique
    // affichera toutes les données chargées (30 jours).
    
    chartInstance = new Chart(ctx, {
        type: 'line',
        data: { datasets: chartData.datasets },
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
                    adapters: { date: { locale: 'fr' }},
                    title: { display: true, text: 'Date / Heure' },
                    // Application du zoom initial
                    min: initialMin,
                    max: initialMax
                },
                y_temp: { type: 'linear', display: true, position: 'left', title: { display: true, text: 'Température (°C)' } },
                y_hum: { type: 'linear', display: true, position: 'right', title: { display: true, text: 'Humidité (%)' }, grid: { drawOnChartArea: false } }
            },
            plugins: {
                zoom: { 
                    pan: { enabled: true, mode: 'x' }, 
                    zoom: { wheel: { enabled: true }, pinch: { enabled: true }, mode: 'x' }
                },
                annotation: { annotations: { ...nightZones, ...tempThresholds }}
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
        
        let statusColorVar = 'var(--success-color)';
        if (percentage < 30) { statusColorVar = 'var(--warning-color)'; }
        if (percentage <= 0) { statusColorVar = 'var(--danger-color)'; }

        plantCard.style.setProperty('--plant-shadow-color', statusColorVar);
        
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
                <div class="water-progress-bar">
                    <div class="water-progress" style="width: ${percentage.toFixed(1)}%; background-color: ${statusColorVar};"></div>
                </div>
                <button class="water-button" data-plant-id="${plant.id}">Arroser maintenant</button>
            </div>`;
        container.appendChild(plantCard);
    });
}

export function displayTasks(tasks) {
    const container = document.getElementById('task-container');
    container.innerHTML = '';
    if (!tasks || tasks.length === 0) {
        container.innerHTML = '<p style="grid-column: 1 / -1;">Aucune tâche configurée.</p>';
        return;
    }

    tasks.forEach(task => {
        const taskCard = document.createElement('div');
        taskCard.className = 'plant'; 
        
        const percentage = task.urgency_percentage;
        
        let statusColorVar = 'var(--success-color)';
        if (percentage < 30) { statusColorVar = 'var(--warning-color)'; }
        if (percentage <= 0) { statusColorVar = 'var(--danger-color)'; }

        taskCard.style.setProperty('--plant-shadow-color', statusColorVar);
        
        let frequencyText = `Tous les ${task.frequency_days} jours`;
        if (task.frequency_days === 1) { frequencyText = "Chaque jour"; }

        taskCard.innerHTML = `
            <div class="plant-header">
                <span class="plant-header-title">${task.name}</span>
                <div class="plant-actions">
                    <button class="action-btn delete-task" title="Supprimer Tâche" data-task-id="${task.id}"><i class="fa-solid fa-trash"></i></button>
                </div>
            </div>
            <div class="plant-body">
                <p><strong>Fréquence :</strong> ${frequencyText}</p>
                <p><strong>Dernière exécution :</strong> Il y a ${task.days_since_completed} jour(s)</p>
                <div class="water-progress-bar">
                    <div class="water-progress" style="width: ${percentage.toFixed(1)}%; background-color: ${statusColorVar};"></div>
                </div>
                <button class="complete-task-button" data-task-id="${task.id}" style="background-color: var(--success-color); color: white; width: 100%; margin-top: 1rem;">Marquer comme fait</button>
            </div>`;
        container.appendChild(taskCard);
    });
}

export function populatePlantTypes(types) {
    if (!types) return;
    const editSelect = document.getElementById('edit-plant-type');
    const newAddSelect = document.getElementById('new-plant-type-select');
    if (editSelect) {
        editSelect.innerHTML = '';
        types.forEach(type => {
            const option = `<option value="${type.id}">${type.name}</option>`;
            editSelect.innerHTML += option;
        });
    }
    if (newAddSelect) {
        newAddSelect.innerHTML = '<option value="" disabled selected>Choisir un type existant</option><option value="--new--">--- Ajouter un nouveau type ---</option>';
        types.forEach(type => {
            const option = `<option value="${type.id}">${type.name}</option>`;
            newAddSelect.innerHTML += option;
        });
    }
}

export function openEditPlantModal(plant) {
    if (editForm) {
        editForm.querySelector('#edit-plant-id').value = plant.id;
        editForm.querySelector('#edit-plant-name').value = plant.name;
        editForm.querySelector('#edit-plant-type').value = plant.type_id;
        openModal(editModalOverlay);
    }
}
