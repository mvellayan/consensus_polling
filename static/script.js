// State management
let judges = [];
let selectedJudges = new Set();
let queriesRemaining = 5;

// DOM elements
const questionInput = document.getElementById('question');
const judgesGrid = document.getElementById('judges-grid');
const selectAllBtn = document.getElementById('select-all');
const askButton = document.getElementById('ask-button');
const loading = document.getElementById('loading');
const responsesSection = document.getElementById('responses-section');
const responsesContainer = document.getElementById('responses-container');
const queriesRemainingSpan = document.getElementById('queries-remaining');

// Initialize
async function init() {
    await loadJudges();
    await checkQueryLimit();
}

// Load judges from API
async function loadJudges() {
    try {
        const response = await fetch('/api/judges');
        judges = await response.json();
        renderJudges();
    } catch (error) {
        console.error('Error loading judges:', error);
    }
}

// Render judge toggles
function renderJudges() {
    judgesGrid.innerHTML = judges.map(judge => `
        <div class="judge-toggle" data-judge="${judge.judge_name}">
            <img src="/static/images/${judge.judge_name}.jpg" alt="${judge.judge_title}" onerror="this.style.display='none'">
            <span>${judge.judge_title}</span>
        </div>
    `).join('');

    // Add click handlers
    document.querySelectorAll('.judge-toggle').forEach(btn => {
        btn.addEventListener('click', () => toggleJudge(btn.dataset.judge, btn));
    });
}

// Toggle judge selection
function toggleJudge(judgeName, element) {
    if (selectedJudges.has(judgeName)) {
        selectedJudges.delete(judgeName);
        element.classList.remove('selected');
    } else {
        selectedJudges.add(judgeName);
        element.classList.add('selected');
    }
    updateSelectAllButton();
}

// Select/deselect all judges
selectAllBtn.addEventListener('click', () => {
    const allSelected = selectedJudges.size === judges.length;

    if (allSelected) {
        selectedJudges.clear();
        document.querySelectorAll('.judge-toggle').forEach(btn => {
            btn.classList.remove('selected');
        });
        selectAllBtn.textContent = 'Select All';
    } else {
        judges.forEach(judge => selectedJudges.add(judge.judge_name));
        document.querySelectorAll('.judge-toggle').forEach(btn => {
            btn.classList.add('selected');
        });
        selectAllBtn.textContent = 'Deselect All';
    }
});

// Update select all button text
function updateSelectAllButton() {
    if (selectedJudges.size === judges.length) {
        selectAllBtn.textContent = 'Deselect All';
    } else {
        selectAllBtn.textContent = 'Select All';
    }
}

// Check query limit
async function checkQueryLimit() {
    try {
        const response = await fetch('/api/check-limit');
        const data = await response.json();
        queriesRemaining = data.remaining;
        updateQueryStatus();
    } catch (error) {
        console.error('Error checking limit:', error);
    }
}

// Update query status display
function updateQueryStatus() {
    queriesRemainingSpan.textContent = `${queriesRemaining} of 5 questions remaining`;

    if (queriesRemaining === 0) {
        askButton.disabled = true;
        askButton.textContent = 'Query Limit Reached';
    }
}

// Ask the AI Supreme Court
askButton.addEventListener('click', async () => {
    const question = questionInput.value.trim();

    if (!question) {
        showAlert('Please enter a question', 'error');
        return;
    }

    if (selectedJudges.size === 0) {
        showAlert('Please select at least one Justice', 'error');
        return;
    }

    if (queriesRemaining === 0) {
        showAlert('You have reached the maximum number of queries (5)', 'warning');
        return;
    }

    // Show loading state
    askButton.disabled = true;
    loading.style.display = 'flex';
    responsesSection.style.display = 'none';

    try {
        const response = await fetch('/api/query', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                question: question,
                judges: Array.from(selectedJudges)
            })
        });

        if (response.status === 429) {
            showAlert('Query limit reached. Maximum 5 queries per IP address.', 'warning');
            return;
        }

        if (!response.ok) {
            const error = await response.json();
            showAlert(error.error || 'An error occurred', 'error');
            return;
        }

        const data = await response.json();
        displayResponses(data);

        // Update query count
        await checkQueryLimit();

    } catch (error) {
        console.error('Error querying judges:', error);
        showAlert('An error occurred while querying the Justices', 'error');
    } finally {
        askButton.disabled = queriesRemaining === 0;
        loading.style.display = 'none';
    }
});

// Display responses
function displayResponses(data) {
    responsesSection.style.display = 'block';
    responsesContainer.innerHTML = data.responses.map((response, index) => `
        <div class="response-card" data-support="${response.support_level}" data-index="${index}">
            <div class="response-header">
                <div class="judge-info">
                    <h3>${response.judge_title}</h3>
                    <p class="response-brief">${response.brief}</p>
                </div>
                <span class="expand-icon">▼</span>
            </div>
            <div class="response-body">
                <div class="response-full">${response.full_response}</div>
            </div>
        </div>
    `).join('');

    // Add click handlers for expanding responses
    document.querySelectorAll('.response-header').forEach(header => {
        header.addEventListener('click', () => {
            const card = header.closest('.response-card');
            card.classList.toggle('expanded');
        });
    });

    // Scroll to responses
    responsesSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// Show alert message
function showAlert(message, type = 'error') {
    const existingAlert = document.querySelector('.alert');
    if (existingAlert) {
        existingAlert.remove();
    }

    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    alert.textContent = message;

    const main = document.querySelector('main');
    main.insertBefore(alert, main.firstChild);

    setTimeout(() => alert.remove(), 5000);
}

// Initialize on load
init();
