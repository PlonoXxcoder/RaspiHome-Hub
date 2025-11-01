// Fichier : templates/theme.js
document.addEventListener('DOMContentLoaded', () => {
    const themeToggle = document.getElementById('theme-toggle-checkbox');
    const body = document.body;

    // Fonction pour appliquer le thème en fonction de l'état (dark/light)
    const applyTheme = (theme) => {
        if (theme === 'dark') {
            body.classList.add('dark-mode');
            if(themeToggle) themeToggle.checked = true;
        } else {
            body.classList.remove('dark-mode');
            if(themeToggle) themeToggle.checked = false;
        }
    };

    // Au chargement de la page, vérifier le thème sauvegardé dans le localStorage
    // S'il n'y en a pas, on utilise le thème clair par défaut
    const savedTheme = localStorage.getItem('theme') || 'light';
    applyTheme(savedTheme);

    // Ajouter un écouteur d'événement sur le changement de la case à cocher
    if(themeToggle) {
        themeToggle.addEventListener('change', () => {
            // Déterminer le nouveau thème en fonction de l'état de la case
            const newTheme = themeToggle.checked ? 'dark' : 'light';
            
            // Appliquer le nouveau thème
            applyTheme(newTheme);
            
            // Sauvegarder le choix dans le localStorage pour les futures visites
            localStorage.setItem('theme', newTheme);
        });
    }
});
