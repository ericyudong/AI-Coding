const API_BASE = 'http://localhost:8000';

let currentPage = 1;
let currentCategory = '';
let isTrending = false;

document.addEventListener('DOMContentLoaded', () => {
    loadCategories();
    loadModels();

    document.getElementById('trending-btn').addEventListener('click', () => {
        isTrending = true;
        document.getElementById('trending-btn').classList.add('active');
        document.getElementById('all-btn').classList.remove('active');
        currentPage = 1;
        loadModels();
    });

    document.getElementById('all-btn').addEventListener('click', () => {
        isTrending = false;
        document.getElementById('all-btn').classList.add('active');
        document.getElementById('trending-btn').classList.remove('active');
        currentPage = 1;
        loadModels();
    });

    document.getElementById('category-select').addEventListener('change', (e) => {
        currentCategory = e.target.value;
        currentPage = 1;
        loadModels();
    });

    document.getElementById('prev-btn').addEventListener('click', () => {
        if (currentPage > 1) {
            currentPage--;
            loadModels();
        }
    });

    document.getElementById('next-btn').addEventListener('click', () => {
        currentPage++;
        loadModels();
    });
});

async function loadCategories() {
    try {
        const response = await fetch(`${API_BASE}/categories`);
        const data = await response.json();
        const select = document.getElementById('category-select');
        data.categories.forEach(cat => {
            const option = document.createElement('option');
            option.value = cat;
            option.textContent = cat;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading categories:', error);
    }
}

async function loadModels() {
    try {
        const params = new URLSearchParams({
            page: currentPage,
            limit: 10,
            trending: isTrending
        });
        if (currentCategory) {
            params.append('category', currentCategory);
        }
        const response = await fetch(`${API_BASE}/models?${params}`);
        const models = await response.json();
        renderModels(models);
        updatePagination();
    } catch (error) {
        console.error('Error loading models:', error);
    }
}

function renderModels(models) {
    const container = document.getElementById('models-container');
    container.innerHTML = '';
    models.forEach(model => {
        const card = document.createElement('div');
        card.className = 'model-card';
        card.innerHTML = `
            <h3>${model.name} ${model.is_new ? '<span class="new-badge">NEW</span>' : ''}</h3>
            <p>${model.task}</p>
            <div class="meta">Last Updated: ${model.last_updated} | Downloads: ${model.downloads}</div>
        `;
        container.appendChild(card);
    });
}

function updatePagination() {
    document.getElementById('page-info').textContent = `Page ${currentPage}`;
    document.getElementById('prev-btn').disabled = currentPage === 1;
    // For simplicity, assume there are more pages; in real app, check total pages
}