<<<<<<< HEAD
// --- VARIABLES GLOBALES ---
let chart; // Stocke l'instance du graphique pour pouvoir la détruire et la recréer
let allPlantRules = {}; // Cache pour les règles d'arrosage afin d'éviter des appels API répétés
let duePlantTipIndex = 0; // Index pour parcourir les astuces des plantes à arroser

// --- FONCTIONS ASYNCHRONES POUR LES APPELS API ---

/**
 * Récupère les données météo en temps réel et met à jour l'affichage.
 */
async function loadCurrentData() {
    const elements = {
        temp: document.querySelector("#weather-temp"),
        heat: document.querySelector("#weather-heat"),
        hum: document.querySelector("#weather-hum"),
        pres: document.querySelector("#weather-pres")
    };
    try {
        const response = await fetch('/alldata');
        if (!response.ok) throw new Error(response.status);
        const data = await response.json();
        elements.temp.textContent = `${data.temperature}°C`;
        elements.heat.textContent = `${data.heat_index}°C`;
        elements.hum.textContent = `${data.humidite}%`;
        elements.pres.textContent = `${data.pression} hPa`;
    } catch (error) {
        Object.values(elements).forEach(el => { el.textContent = "Erreur" });
    }
}

/**
 * Met à jour le graphique avec les données historiques pour la période sélectionnée.
 */
async function updateChart() {
    try {
        const period = document.getElementById('period').value;
        const response = await fetch(`/history?period=${period}`);
        if (!response.ok) throw new Error(response.status);
        const data = await response.json();

        const ctx = document.getElementById('myChart');
        if (chart) {
            chart.destroy(); // Détruire l'ancien graphique avant d'en créer un nouveau
        }
        chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.datetime,
                datasets: [{
                    label: 'Température (°C)',
                    data: data.temp,
                    borderColor: '#ff6384',
                    yAxisID: 'y',
                }, {
                    label: 'Ressentie (°C)',
                    data: data.heat_index,
                    borderColor: '#ff9f40',
                    yAxisID: 'y',
                }, {
                    label: 'Humidité (%)',
                    data: data.hum,
                    borderColor: '#36a2eb',
                    yAxisID: 'y',
                }, {
                    label: 'Pression (hPa)',
                    data: data.pres,
                    borderColor: '#4bc0c0',
                    yAxisID: 'y1',
                }]
            },
            options: {
                responsive: true,
                interaction: { mode: 'index', intersect: false },
                elements: { point: { radius: 0, hoverRadius: 5 } },
                scales: {
                    y: { position: 'left', title: { display: true, text: '°C / %' } },
                    y1: { position: 'right', title: { display: true, text: 'hPa' }, grid: { drawOnChartArea: false } }
                }
            }
        });
    } catch (error) {
        console.error(error);
    }
}

/**
 * Charge les plantes de l'utilisateur et les affiche.
 * @returns {Array<string>} Un tableau des types de plantes qui nécessitent un arrosage.
 */
async function loadPlantData() {
    const duePlantTypes = new Set();
    try {
        const response = await fetch('/plants');
        if (!response.ok) throw new Error(`Erreur: ${response.status}`);
        const plants = await response.json();

        const container = document.getElementById('plant-container');
        container.innerHTML = '';

        if (Object.keys(plants).length === 0) {
            container.innerHTML = '<p>Aucune plante. Ajoutez-en une ci-dessous !</p>';
        } else {
            for (const id in plants) {
                const plant = plants[id];
                if (plant.is_due) {
                    duePlantTypes.add(plant.type);
                }
                const plantElement = document.createElement('div');
                plantElement.className = `plant ${plant.is_due ? 'due' : ''}`;
                const typeCapitalized = plant.type.charAt(0).toUpperCase() + plant.type.slice(1);

                let plantHTML = `
                    <div class="plant-header">
                        <h3><i class="fa-solid fa-leaf"></i> ${plant.nom}</h3>
                        <button class="delete-btn" onclick="deletePlant('${id}', '${plant.nom}')" title="Supprimer ${plant.nom}"><i class="fa-solid fa-trash"></i></button>
                    </div>
                    <div class="plant-body">
                        <span class="plant-type-tag" onclick="showTipsFor('${plant.type}')">${typeCapitalized}</span>
                        <p>Prochain arrosage : <strong>${plant.status}</strong></p>
                        ${plant.is_due ? `<button onclick="confirmWatering('${id}')">Marquer comme arrosé</button>` : ''}
                    </div>
                `;
                plantElement.innerHTML = plantHTML;
                container.appendChild(plantElement);
            }
        }
    } catch (error) {
        document.getElementById('plant-container').innerHTML = '<p>Impossible de charger les données des plantes.</p>';
    }
    return Array.from(duePlantTypes);
}

/**
 * Gère la suppression d'une plante après confirmation.
 */
window.deletePlant = async function(id, name) {
    if (!confirm(`Êtes-vous sûr de vouloir supprimer la plante "${name}" ? Cette action est irréversible.`)) {
        return;
    }
    try {
        const response = await fetch(`/delete_plant/${id}`, { method: 'POST' });
        if (!response.ok) throw new Error("La suppression a échoué sur le serveur.");
        loadPlantData(); // Recharger la liste des plantes
    } catch (error) {
        alert("Une erreur est survenue. Impossible de supprimer la plante.");
    }
}

/**
 * Affiche une modale avec des conseils pour un type de plante spécifique.
 */
window.showTipsFor = async function(plantType) {
    const modal = document.getElementById('tips-modal');
    const modalTitle = document.getElementById('modal-title');
    const modalList = document.getElementById('modal-tips-list');
    const typeCapitalized = plantType.charAt(0).toUpperCase() + plantType.slice(1);
    
    modalTitle.textContent = `Conseils pour ${typeCapitalized}`;
    modalList.innerHTML = '<li>Chargement...</li>';
    modal.style.display = 'flex';

    try {
        // Appelle l'API plusieurs fois pour avoir une liste variée de conseils
        const tipPromises = Array(5).fill().map(() => fetch(`/tip_for_type/${plantType}`));
        const tipResponses = await Promise.all(tipPromises);
        const tipData = await Promise.all(tipResponses.map(res => res.json()));

        // Utilise un Set pour s'assurer que les conseils sont uniques
        const uniqueTips = new Set(tipData.map(tip => tip.tip));

        modalList.innerHTML = '';
        if (uniqueTips.size > 0) {
            uniqueTips.forEach(tipText => {
                const li = document.createElement('li');
                li.textContent = tipText;
                modalList.appendChild(li);
            });
        } else {
            modalList.innerHTML = '<li>Aucun conseil spécifique trouvé.</li>';
        }
    } catch (error) {
        modalList.innerHTML = '<li>Impossible de charger les conseils.</li>';
    }
}

/**
 * Confirme l'arrosage d'une plante et met à jour l'interface.
 */
window.confirmWatering = async function(id) {
    try {
        await fetch(`/watered/${id}`, { method: 'POST' });
        const duePlants = await loadPlantData();
        await updateSmartTip(duePlants);
    } catch (error) {
        console.error(error);
    }
}

/**
 * Met à jour l'astuce du jour, en privilégiant les plantes à arroser.
 */
async function updateSmartTip(duePlants = []) {
    const tipElement = document.getElementById('plant-tip');
    if (!tipElement) return;

    let apiUrl = '/tips';
    if (duePlants.length > 0) {
        const currentType = duePlants[duePlantTipIndex];
        apiUrl = `/tip_for_type/${currentType}`;
        // Prépare l'index pour la prochaine actualisation
        duePlantTipIndex = (duePlantTipIndex + 1) % duePlants.length;
    }

    try {
        tipElement.classList.add('fade-out');
        const response = await fetch(apiUrl);
        if (!response.ok) throw new Error('Failed to fetch tip');
        const data = await response.json();
        // Attendre la fin de l'animation de fondu avant de changer le texte
        setTimeout(() => {
            tipElement.innerHTML = `<strong>${data.category}:</strong> ${data.tip}`;
            tipElement.classList.remove('fade-out');
        }, 500);
    } catch (error) {
        tipElement.textContent = "Impossible de charger les astuces.";
        tipElement.classList.remove('fade-out');
    }
}

/**
 * Charge les règles d'arrosage et les stocke dans une variable globale.
 */
async function loadPlantRules() {
    try {
        const response = await fetch('/plant_rules');
        if (!response.ok) throw new Error('Failed to fetch plant rules');
        allPlantRules = await response.json();
    } catch (error) {
        console.error(error);
    }
}

/**
 * Remplit les listes de sélection des types de plantes.
 */
async function populatePlantTypes() {
    try {
        const response = await fetch('/plant_types');
        if (!response.ok) throw new Error('Failed to fetch plant types');
        const types = await response.json();

        const selectElement = document.getElementById('plant-type');
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
        console.error(error);
    }
}

/**
 * Gère la soumission du formulaire d'ajout de plante.
 */
async function handleAddPlant(event) {
    event.preventDefault();
    const nameInput = document.getElementById('plant-name');
    const typeSelect = document.getElementById('plant-type');
    try {
        const response = await fetch('/add_plant', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ nom: nameInput.value, type: typeSelect.value })
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.message || 'Failed to add plant');
        nameInput.value = '';
        typeSelect.selectedIndex = 0;
        loadPlantData();
    } catch (error) {
        alert(`Erreur: ${error.message}`);
    }
}

/**
 * Gère la soumission du formulaire de gestion des types de plantes.
 */
async function handleManagePlantType(event) {
    event.preventDefault();
    const nameInput = document.getElementById('type-search-name');
    const summerInput = document.getElementById('summer-weeks');
    const winterInput = document.getElementById('winter-weeks');
    const payload = {
        type_name: nameInput.value,
        summer_weeks: summerInput.value,
        winter_weeks: winterInput.value,
    };
    try {
        const response = await fetch('/add_plant_type', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.message || 'Failed to save type');
        nameInput.value = '';
        summerInput.value = '';
        winterInput.value = '';
        await Promise.all([populatePlantTypes(), loadPlantRules()]); // Mettre à jour les listes
        alert(`Type "${payload.type_name}" sauvegardé!`);
    } catch (error) {
        console.error(error);
        alert(`Erreur: ${error.message}`);
    }
}

// --- ÉVÉNEMENTS ET INITIALISATION ---

document.addEventListener('DOMContentLoaded', async () => {
    // --- NOUVELLE GESTION DU THÈME ---
    const themeCheckbox = document.querySelector('.theme-switch__checkbox');
    const body = document.body;

    const applyTheme = (theme) => {
        body.classList.toggle('dark-mode', theme === 'dark');
        themeCheckbox.checked = (theme === 'dark');
    };

    themeCheckbox.addEventListener('change', () => {
        const newTheme = body.classList.contains('dark-mode') ? 'light' : 'dark';
        applyTheme(newTheme);
        localStorage.setItem('theme', newTheme);
    });
    
    // Appliquer le thème au chargement : localStorage > préférence système > clair par défaut
    const savedTheme = localStorage.getItem('theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    applyTheme(savedTheme || (prefersDark ? 'dark' : 'light'));
    
    // --- GESTION DE LA MODALE ---
    const modal = document.getElementById('tips-modal');
    const closeModalBtn = document.getElementById('modal-close-btn');
    closeModalBtn.addEventListener('click', () => modal.style.display = 'none');
    modal.addEventListener('click', (event) => {
        if (event.target === modal) {
            modal.style.display = 'none';
        }
    });

    // --- AUTRES ÉVÉNEMENTS ---
    const refreshBtn = document.getElementById('refresh-weather-btn');
    refreshBtn.addEventListener('click', async () => {
        refreshBtn.disabled = true;
        refreshBtn.classList.add('loading');
        await loadCurrentData();
        setTimeout(() => {
            refreshBtn.classList.remove('loading');
            refreshBtn.disabled = false;
        }, 500);
    });

    // --- CHARGEMENT INITIAL DES DONNÉES ---
    await loadPlantRules();
    loadCurrentData();
    updateChart();
    populatePlantTypes();

    const initialPlantLoad = async () => {
        const duePlants = await loadPlantData();
        await updateSmartTip(duePlants);
    };
    initialPlantLoad();

    // --- INTERVALLES DE MISE À JOUR ---
    setInterval(initialPlantLoad, 15000); // Mettre à jour les plantes et l'astuce toutes les 15s
    setInterval(loadCurrentData, 60000); // Mettre à jour la météo toutes les 60s

    // --- ÉCOUTEURS D'ÉVÉNEMENTS SUR LES FORMULAIRES ET INPUTS ---
    document.getElementById('period').addEventListener('change', updateChart);
    document.getElementById('add-plant-form').addEventListener('submit', handleAddPlant);
    document.getElementById('manage-type-form').addEventListener('submit', handleManagePlantType);

    const typeSearchInput = document.getElementById('type-search-name');
    const manageTypeBtn = document.getElementById('manage-type-btn');
    const summerWeeksInput = document.getElementById('summer-weeks');
    const winterWeeksInput = document.getElementById('winter-weeks');
    
    typeSearchInput.addEventListener('input', (event) => {
        const searchKey = event.target.value.toLowerCase().trim().replace(/ /g, '_');
        const existingRule = allPlantRules[searchKey];
        if (existingRule) {
            summerWeeksInput.value = existingRule[0];
            winterWeeksInput.value = existingRule[1];
            manageTypeBtn.textContent = 'Modifier';
            manageTypeBtn.style.backgroundColor = '#ffc107'; // Jaune
        } else {
            summerWeeksInput.value = '';
            winterWeeksInput.value = '';
            manageTypeBtn.textContent = 'Créer';
            manageTypeBtn.style.backgroundColor = '#6c757d'; // Gris
        }
    });
});
=======
// --- FICHIER : templates/script.js ---
let chart;let allPlantRules={};let duePlantTipIndex=0;async function loadCurrentData(){const e={temp:document.querySelector("#weather-temp"),heat:document.querySelector("#weather-heat"),hum:document.querySelector("#weather-hum"),pres:document.querySelector("#weather-pres")};try{const t=await fetch("/alldata");if(!t.ok)throw new Error(t.status);const a=await t.json();e.temp.textContent=`${a.temperature}°C`,e.heat.textContent=`${a.heat_index}°C`,e.hum.textContent=`${a.humidite}%`,e.pres.textContent=`${a.pression} hPa`}catch(t){Object.values(e).forEach(e=>{e.textContent="Erreur"})}}async function updateChart(){try{const e=document.getElementById("period").value,t=await fetch(`/history?period=${e}`);if(!t.ok)throw new Error(t.status);const a=await t.json(),d=document.getElementById("myChart");chart&&chart.destroy(),chart=new Chart(d,{type:"line",data:{labels:a.datetime,datasets:[{label:"Température (°C)",data:a.temp,borderColor:"#ff6384",yAxisID:"y"},{label:"Ressentie (°C)",data:a.heat_index,borderColor:"#ff9f40",yAxisID:"y"},{label:"Humidité (%)",data:a.hum,borderColor:"#36a2eb",yAxisID:"y"},{label:"Pression (hPa)",data:a.pres,borderColor:"#4bc0c0",yAxisID:"y1"}]},options:{responsive:!0,interaction:{mode:"index",intersect:!1},elements:{point:{radius:0,hoverRadius:5}},scales:{y:{position:"left",title:{display:!0,text:"°C / %"}},y1:{position:"right",title:{display:!0,text:"hPa"},grid:{drawOnChartArea:!1}}}}})}catch(e){console.error(e)}}async function loadPlantData(){const e=new Set;try{const t=await fetch("/plants");if(!t.ok)throw new Error(`Erreur: ${t.status}`);const a=await t.json(),d=document.getElementById("plant-container");if(d.innerHTML="",0===Object.keys(a).length)d.innerHTML="<p>Aucune plante. Ajoutez-en une ci-dessous !</p>";else for(const o in a){const i=a[o];i.is_due&&e.add(i.type);const n=document.createElement("div");n.className=`plant ${i.is_due?"due":""}`;const c=i.type.charAt(0).toUpperCase()+i.type.slice(1);let l=`<div class="plant-header"><h3><i class="fa-solid fa-leaf"></i> ${i.nom}</h3><button class="delete-btn" onclick="deletePlant('${o}', '${i.nom}')" title="Supprimer ${i.nom}"><i class="fa-solid fa-trash"></i></button></div><div class="plant-body"><span class="plant-type-tag" onclick="showTipsFor('${i.type}')">${c}</span><p>Prochain arrosage : <strong>${i.status}</strong></p>${i.is_due?`<button onclick="confirmWatering('${o}')">Marquer comme arrosé</button>`:""}</div>`;n.innerHTML=l,d.appendChild(n)}}catch(t){document.getElementById("plant-container").innerHTML="<p>Impossible de charger les données des plantes.</p>"}return Array.from(e)}async function deletePlant(e,t){if(!confirm(`Êtes-vous sûr de vouloir supprimer la plante "${t}" ? Cette action est irréversible.`))return;try{const a=await fetch(`/delete_plant/${e}`,{method:"POST"});if(!a.ok)throw new Error("La suppression a échoué sur le serveur.");loadPlantData()}catch(e){alert("Une erreur est survenue. Impossible de supprimer la plante.")}}async function showTipsFor(e){const t=document.getElementById("tips-modal"),a=document.getElementById("modal-title"),d=document.getElementById("modal-tips-list"),o=e.charAt(0).toUpperCase()+e.slice(1);a.textContent=`Conseils pour ${o}`,d.innerHTML="<li>Chargement...</li>",t.style.display="flex";try{const i=Array(5).fill().map(()=>fetch(`/tip_for_type/${e}`)),n=await Promise.all(i),c=await Promise.all(n.map(e=>e.json())),l=new Set(c.map(e=>e.tip));if(d.innerHTML="",l.size>0)l.forEach(e=>{const t=document.createElement("li");t.textContent=e,d.appendChild(t)});else d.innerHTML="<li>Aucun conseil spécifique trouvé.</li>"}catch(e){d.innerHTML="<li>Impossible de charger les conseils.</li>"}}async function confirmWatering(e){try{await fetch(`/watered/${e}`,{method:"POST"});const t=await loadPlantData();await updateSmartTip(t)}catch(e){console.error(e)}}async function updateSmartTip(e=[]){const t=document.getElementById("plant-tip");if(!t)return;let a="/tips";if(e.length>0){const d=e[duePlantTipIndex];a=`/tip_for_type/${d}`,duePlantTipIndex=(duePlantTipIndex+1)%e.length}try{t.classList.add("fade-out");const o=await fetch(a);if(!o.ok)throw new Error("!");const i=await o.json();setTimeout(()=>{t.innerHTML=`<strong>${i.category}:</strong> ${i.tip}`,t.classList.remove("fade-out")},500)}catch(e){t.textContent="Impossible de charger les astuces.",t.classList.remove("fade-out")}}async function loadPlantRules(){try{const e=await fetch("/plant_rules");if(!e.ok)throw new Error("!");allPlantRules=await e.json()}catch(e){console.error(e)}}async function populatePlantTypes(){try{const e=await fetch("/plant_types");if(!e.ok)throw new Error("!");const t=await e.json(),a=document.getElementById("plant-type"),d=document.getElementById("plant-type-list");a.innerHTML='<option value="">-- Choisir --</option>',d.innerHTML="",t.forEach(e=>{const t=e.charAt(0).toUpperCase()+e.slice(1),o=document.createElement("option");o.value=e,o.textContent=t,a.appendChild(o);const i=document.createElement("option");i.value=t,d.appendChild(i)})}catch(e){console.error(e)}}async function handleAddPlant(e){e.preventDefault();const t=document.getElementById("plant-name"),a=document.getElementById("plant-type");try{const d=await fetch("/add_plant",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({nom:t.value,type:a.value})}),o=await d.json();if(!d.ok)throw new Error(o.message||"!");t.value="",a.selectedIndex=0,loadPlantData()}catch(e){alert(`Erreur: ${e.message}`)}}async function handleManagePlantType(e){e.preventDefault();const t=document.getElementById("type-search-name"),a=document.getElementById("summer-weeks"),d=document.getElementById("winter-weeks"),o={type_name:t.value,summer_weeks:a.value,winter_weeks:d.value};try{const i=await fetch("/add_plant_type",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(o)}),n=await i.json();if(!i.ok)throw new Error(n.message||"!");t.value="",a.value="",d.value="",await Promise.all([populatePlantTypes(),loadPlantRules()]),alert(`Type "${o.type_name}" sauvegardé!`)}catch(e){console.error(e),alert(`Erreur: ${e.message}`)}}document.addEventListener("DOMContentLoaded",async()=>{const e=document.getElementById("theme-switcher"),t=document.body,a=e=>t.classList.toggle("dark-mode",e==="dark");e.addEventListener("click",()=>{const e=t.classList.contains("dark-mode")?"light":"dark";a(e),localStorage.setItem("theme",e)});const d=localStorage.getItem("theme"),o=window.matchMedia("(prefers-color-scheme: dark)").matches;a(d||(o?"dark":"light"));const i=document.getElementById("tips-modal"),n=document.getElementById("modal-close-btn");n.addEventListener("click",()=>i.style.display="none"),i.addEventListener("click",e=>{e.target===i&&(i.style.display="none")});const c=document.getElementById("refresh-weather-btn");c.addEventListener("click",async()=>{c.disabled=!0,c.classList.add("loading"),await loadCurrentData(),setTimeout(()=>{c.classList.remove("loading"),c.disabled=!1},500)}),await loadPlantRules(),loadCurrentData(),updateChart(),populatePlantTypes();const l=async()=>{const e=await loadPlantData();await updateSmartTip(e)};l(),setInterval(l,15e3),setInterval(loadCurrentData,6e4),document.getElementById("period").addEventListener("change",updateChart),document.getElementById("add-plant-form").addEventListener("submit",handleAddPlant),document.getElementById("manage-type-form").addEventListener("submit",handleManagePlantType);const r=document.getElementById("type-search-name"),s=document.getElementById("manage-type-btn"),m=document.getElementById("summer-weeks"),p=document.getElementById("winter-weeks");r.addEventListener("input",e=>{const t=e.target.value.toLowerCase().trim().replace(/ /g,"_"),a=allPlantRules[t];a?(m.value=a[0],p.value=a[1],s.textContent="Modifier",s.style.backgroundColor="#ffc107"):(m.value="",p.value="",s.textContent="Créer",s.style.backgroundColor="#6c757d")})});
>>>>>>> 2e7f75f72088d2b101e2f1fbcb083d346956a5a0
