let judges = [];
let selectedJudges = new Set();
let queryInfo = { ip: null, count: 0 }; // informational only — no query limit
let isProcessing = false; // Flag to prevent button re-enabling during processing

// DOM elements - will be found after DOM loads
let judgesGrid, questionInput, askButton, loading, responsesSection, responsesContainer, queryStatus, selectAllButton;

// Initialize the application
document.addEventListener('DOMContentLoaded', async () => {
    console.log('DOM loaded');

    // Find all DOM elements after DOM is loaded
    judgesGrid = document.getElementById('judges-grid');
    questionInput = document.getElementById('question');
    askButton = document.getElementById('ask-button');
    loading = document.getElementById('loading');
    responsesSection = document.getElementById('responses-section');
    responsesContainer = document.getElementById('responses-container');
    queryStatus = document.getElementById('query-status');
    selectAllButton = document.getElementById('select-all');

    await loadJudges();
    await checkQueryLimit();
    await loadTotalQueryCount();

    if (askButton) {
        askButton.addEventListener('click', handleAskQuestion);
    }

    if (questionInput) {
        questionInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !askButton.disabled) {
                handleAskQuestion();
            }
        });
        questionInput.addEventListener('input', updateAskButton);
    }

    // Add Select All button functionality
    if (selectAllButton) {
        selectAllButton.addEventListener('click', () => {
            console.log('Select All clicked');
            toggleSelectAll();
        });
    } else {
        console.error('Select All button not found');
    }

    // About modal functionality
    initializeAboutModal();
});

// Load judges from API
async function loadJudges() {
    try {
        const response = await fetch(`${window.location.origin}/api/judges`);
        judges = await response.json();
        renderJudges();
    } catch (error) {
        console.error('Error loading judges:', error);
        showAlert('Failed to load judges', 'error');
    }
}

// Render judges grid
function renderJudges() {
    judgesGrid.innerHTML = '';
    
    judges.forEach(judge => {
        const judgeCard = document.createElement('div');
        judgeCard.className = 'judge-toggle';
        judgeCard.innerHTML = `
            <img src="/static/images/${judge.judge_name}.jpg" alt="${judge.judge_title}" onerror="this.src='${judge.image}'">
            <h3>${judge.judge_title}</h3>
        `;
        
        judgeCard.addEventListener('click', () => {
            if (selectedJudges.has(judge.judge_name)) {
                selectedJudges.delete(judge.judge_name);
                judgeCard.classList.remove('selected');
            } else {
                selectedJudges.add(judge.judge_name);
                judgeCard.classList.add('selected');
            }
            
            // Update Select All button text
            if (selectedJudges.size === judges.length) {
                if (selectAllButton) selectAllButton.textContent = 'Deselect All';
            } else {
                if (selectAllButton) selectAllButton.textContent = 'Select All';
            }
            
            updateAskButton();
        });
        
        judgesGrid.appendChild(judgeCard);
    });
}

// Toggle select all judges
function toggleSelectAll() {

    if (!judges || judges.length === 0) {
        console.log('No judges available');
        return;
    }
    
    const allSelected = selectedJudges.size === judges.length;
    console.log('allSelected:', allSelected);
    
    if (allSelected) {
        // Deselect all
        console.log('Deselecting all');
        selectedJudges.clear();
        document.querySelectorAll('.judge-toggle').forEach(card => {
            card.classList.remove('selected');
        });
        if (selectAllButton) selectAllButton.textContent = 'Select All';
    } else {
        selectedJudges.clear();
        judges.forEach(judge => {
            selectedJudges.add(judge.judge_name);
        });
        document.querySelectorAll('.judge-toggle').forEach(card => {
            card.classList.add('selected');
        });
        if (selectAllButton) selectAllButton.textContent = 'Deselect All';
    }
    
    updateAskButton();
}

// Update ask button state
function updateAskButton() {
    if (!questionInput || !askButton) return;
    
    // Don't enable button if we're currently processing
    if (isProcessing) {
        askButton.disabled = true;
        return;
    }
    
    const hasQuestion = questionInput.value.trim().length > 0;
    const hasSelectedJudges = selectedJudges.size > 0;

    const shouldEnable = hasQuestion && hasSelectedJudges;
    askButton.disabled = !shouldEnable;
}

// Fetch this IP's address + query count (informational; there is no limit)
async function checkQueryLimit() {
    try {
        const response = await fetch(`${window.location.origin}/api/check-limit`);
        const data = await response.json();
        queryInfo = { ip: data.ip_address, count: data.count };
        updateQueryStatus();
    } catch (error) {
        console.error('Error fetching query info:', error);
    }
}

// Load total query count
async function loadTotalQueryCount() {
    try {
        const response = await fetch(`${window.location.origin}/api/total-queries`);
        const data = await response.json();

        const countElement = document.getElementById('total-query-count');
        if (countElement) {
            // Format number with commas
            countElement.textContent = data.total.toLocaleString();
        }
    } catch (error) {
        console.error('Error loading total query count:', error);
        const countElement = document.getElementById('total-query-count');
        if (countElement) {
            countElement.textContent = '1200+';
        }
    }
}

// Show this IP's address + query count (informational; no limit)
function updateQueryStatus() {
    const statusElement = document.getElementById('queries-remaining');
    if (!statusElement) return;

    const ip = queryInfo.ip ? escapeHtml(String(queryInfo.ip)) : 'unknown';
    const n = Number(queryInfo.count) || 0;
    statusElement.innerHTML =
        `IP: <span class="queries-count">${ip}</span> &middot; ` +
        `<span class="queries-count">${n}</span> ${n === 1 ? 'query' : 'queries'}`;
}

// Escape HTML to safely render streamed model text as text content
function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// Look up a judge's metadata (title/image) by its slug name (e.g. "roberts")
function getJudgeMeta(slug) {
    const match = (judges || []).find(j => j.judge_name === slug);
    if (match) {
        return {
            title: match.judge_title || slug,
            image: `/static/images/${match.judge_name}.jpg`,
            fallback: match.image || ''
        };
    }
    // Fallback if the slug isn't in the loaded judge list
    const title = slug.charAt(0).toUpperCase() + slug.slice(1);
    return { title, image: `/static/images/${slug}.jpg`, fallback: '' };
}

// Handle ask question — streams the NDJSON response from POST /api/query
async function handleAskQuestion() {
    const question = questionInput.value.trim();

    if (!question) {
        showAlert('Please enter a question', 'warning');
        return;
    }

    if (selectedJudges.size === 0) {
        showAlert('Please select at least one Justice', 'warning');
        return;
    }

    askButton.disabled = true;
    isProcessing = true; // Set processing flag
    loading.style.display = 'flex';

    // Reset the results area and build the scaffold (syllabus + summary + cards)
    responsesSection.style.display = 'block';
    setupResultsScaffold();

    // Per-judge state for the current stream. Recreated on retry.
    let judgeCards = {};
    const MAX_ATTEMPTS = 2;
    const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

    try {
        // Lambda response streaming can reset a reused connection, so the 2nd+
        // query may fail at stream-open. Retry once on a fresh connection IF
        // nothing was rendered yet (a mid-stream failure must NOT retry).
        for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
            judgeCards = {};
            if (attempt > 1) setupResultsScaffold();
            let receivedData = false;
            try {
                const response = await fetch(`${window.location.origin}/api/query`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        question: question,
                        judges: Array.from(selectedJudges)
                    })
                });

                if (!response.ok || !response.body) {
                    if (attempt < MAX_ATTEMPTS) { await sleep(400); continue; }
                    let msg = 'An error occurred while querying the Justices';
                    try { const err = await response.json(); msg = err.error || msg; }
                    catch (e) { /* non-JSON error body */ }
                    showAlert(msg, 'error');
                    responsesSection.style.display = 'none';
                    return;
                }

                // Stream NDJSON. Tokens may split mid-line across chunks, so
                // buffer the trailing partial line and parse only complete lines.
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';
                while (true) {
                    const { value, done } = await reader.read();
                    if (done) break;
                    receivedData = true;
                    buffer += decoder.decode(value, { stream: true });
                    let newlineIndex;
                    while ((newlineIndex = buffer.indexOf('\n')) !== -1) {
                        const line = buffer.slice(0, newlineIndex);
                        buffer = buffer.slice(newlineIndex + 1);
                        handleStreamLine(line, judgeCards);
                    }
                }
                buffer += decoder.decode();
                if (buffer.trim().length > 0) handleStreamLine(buffer, judgeCards);
                return; // completed
            } catch (error) {
                console.error(`Query attempt ${attempt} failed:`, error);
                if (!receivedData && attempt < MAX_ATTEMPTS) { await sleep(400); continue; }
                showAlert('An error occurred while querying the Justices', 'error');
                return;
            }
        }
    } finally {
        finalizeSyllabus();
        isProcessing = false; // Clear processing flag
        askButton.disabled = false;
        loading.style.display = 'none';
        // Refresh query-count UI now that the stream is complete
        try {
            await checkQueryLimit();
            await loadTotalQueryCount();
        } catch (e) {
            console.error('Error refreshing query counts:', e);
        }
    }
}

// Parse a single NDJSON line and dispatch by event type
function handleStreamLine(line, judgeCards) {
    const trimmed = line.trim();
    if (!trimmed) return;

    let event;
    try {
        event = JSON.parse(trimmed);
    } catch (e) {
        console.warn('Skipping unparseable stream line:', trimmed);
        return;
    }

    switch (event.type) {
        case 'token':
            handleTokenEvent(event, judgeCards);
            break;
        case 'judge_done':
            handleJudgeDoneEvent(event, judgeCards);
            break;
        case 'judge_error':
            handleJudgeErrorEvent(event, judgeCards);
            break;
        case 'tally':
            updateSummaryDisplay(event.summary);
            break;
        case 'syllabus_token':
            appendSyllabusToken(event.text);
            break;
        case 'syllabus_error':
            hideSyllabus();
            break;
        case 'done':
            finalizeSyllabus();
            break;
        default:
            console.warn('Unknown stream event type:', event.type);
    }
}

// Build the static scaffold once per query: syllabus block, summary bar
// container, and the responses container (cleared).
function setupResultsScaffold() {
    const syllabus = document.getElementById('syllabus-headline');
    if (syllabus) {
        syllabus.style.display = 'none';
        syllabus.classList.remove('final');
        const textEl = document.getElementById('syllabus-text');
        if (textEl) textEl.textContent = '';
    }

    responsesContainer.innerHTML = '';

    // Summary (vote bar) container — populated on the `tally` event
    const summaryDiv = document.createElement('div');
    summaryDiv.className = 'response-summary';
    summaryDiv.id = 'response-summary';
    summaryDiv.style.display = 'none';
    summaryDiv.innerHTML = '<h3>Response Summary</h3><div id="summary-content"></div>';
    responsesContainer.appendChild(summaryDiv);

    // Container that holds the per-judge cards
    const cardsWrap = document.createElement('div');
    cardsWrap.id = 'judge-cards';
    cardsWrap.className = 'judge-cards';
    responsesContainer.appendChild(cardsWrap);
}

// Lazily create a judge's streaming card on its first token
function ensureJudgeCard(slug, judgeCards) {
    if (judgeCards[slug]) return judgeCards[slug];

    const meta = getJudgeMeta(slug);
    const card = document.createElement('div');
    card.className = 'response-card streaming';
    card.dataset.judge = slug;
    card.innerHTML = `
        <div class="response-header">
            <img class="judge-avatar" src="${meta.image}" alt="${escapeHtml(meta.title)}"
                 onerror="this.onerror=null;this.src='${meta.fallback}'">
            <h3 class="judge-name">${escapeHtml(meta.title)}</h3>
            <div class="card-labels"></div>
        </div>
        <div class="response-content">
            <div class="streaming-text"></div>
        </div>
    `;

    const cardsWrap = document.getElementById('judge-cards') || responsesContainer;
    cardsWrap.appendChild(card);

    const entry = {
        card,
        textEl: card.querySelector('.streaming-text'),
        buffer: ''
    };
    judgeCards[slug] = entry;
    return entry;
}

// `token` — append a streaming delta to that judge's card
function handleTokenEvent(event, judgeCards) {
    const entry = ensureJudgeCard(event.judge, judgeCards);
    entry.buffer += (event.text || '');
    // textContent is safe (no HTML injection) and preserves whitespace via CSS
    entry.textEl.textContent = entry.buffer;
}

// `judge_done` — finalize a card: outcome color, Certainty/Scope labels,
// brief + expandable full response
function handleJudgeDoneEvent(event, judgeCards) {
    const entry = ensureJudgeCard(event.judge, judgeCards);
    const card = entry.card;
    const meta = getJudgeMeta(event.judge);

    const outcome = event.outcome || 'unknown';
    card.classList.remove('streaming');
    card.classList.add(outcome, 'done');

    // Certainty / Scope chips (only when non-null)
    const labelsEl = card.querySelector('.card-labels');
    if (labelsEl) {
        labelsEl.innerHTML = '';
        if (event.certainty) {
            const chip = document.createElement('span');
            chip.className = 'card-chip certainty';
            chip.textContent = event.certainty;
            labelsEl.appendChild(chip);
        }
        if (event.scope) {
            const chip = document.createElement('span');
            chip.className = 'card-chip scope';
            chip.textContent = event.scope;
            labelsEl.appendChild(chip);
        }
    }

    // Color the judge's name to match the outcome
    const nameEl = card.querySelector('.judge-name');
    if (nameEl) nameEl.style.color = `var(--${outcome})`;

    const brief = event.brief || event.full_response || entry.buffer || '';
    const full = event.full_response || entry.buffer || '';

    const contentEl = card.querySelector('.response-content');
    if (contentEl) {
        contentEl.innerHTML = `
            <div class="brief-response">
                <p>${escapeHtml(brief)}</p>
                <button class="expand-btn" onclick="toggleResponse(this)">Read Full Response</button>
            </div>
            <div class="full-response" style="display: none;">
                <p>${escapeHtml(full)}</p>
                <button class="collapse-btn" onclick="toggleResponse(this)">Show Less</button>
            </div>
        `;
    }
}

// `judge_error` — put that card into an error state; others keep streaming
function handleJudgeErrorEvent(event, judgeCards) {
    const entry = ensureJudgeCard(event.judge, judgeCards);
    const card = entry.card;
    card.classList.remove('streaming');
    card.classList.add('unknown', 'error');

    const contentEl = card.querySelector('.response-content');
    if (contentEl) {
        contentEl.innerHTML = `
            <div class="response-error">
                <p>This Justice could not respond: ${escapeHtml(event.error || 'unknown error')}</p>
            </div>
        `;
    }
}

// --- Syllabus headline (typing reveal) ---
function appendSyllabusToken(text) {
    const syllabus = document.getElementById('syllabus-headline');
    const textEl = document.getElementById('syllabus-text');
    if (!syllabus || !textEl) return;
    syllabus.style.display = 'block';
    textEl.textContent += (text || '');
}

function finalizeSyllabus() {
    const syllabus = document.getElementById('syllabus-headline');
    if (!syllabus) return;
    // Only mark "final" if it actually has content (not hidden by an error)
    const textEl = document.getElementById('syllabus-text');
    if (syllabus.style.display !== 'none' && textEl && textEl.textContent.trim()) {
        syllabus.classList.add('final');
    }
}

function hideSyllabus() {
    const syllabus = document.getElementById('syllabus-headline');
    if (syllabus) syllabus.style.display = 'none';
}

// Helper function to determine text color based on outcome
function getTextColorForOutcome(outcome) {
    const darkTextOutcomes = ['support'];
    return darkTextOutcomes.includes(outcome) ? 'black' : 'white';
}

// Helper function to get outcome description
function getOutcomeDescription(outcome) {
    const descriptions = {
        'support': 'Support the action/ruling',
        'overturn': 'Overturn the action/ruling',
        'remand': 'Send back for further review'
    };
    return descriptions[outcome] || '';
}

// Create summary legend showing all possible outcomes
function createSummaryLegend(container) {
    const outcomes = [
        { key: 'support', label: 'Support', description: 'Support the action/ruling' },
        { key: 'overturn', label: 'Overturn', description: 'Overturn the action/ruling' },
        { key: 'remand', label: 'Remand', description: 'Send back for further review' }
    ];

    const legendDiv = document.createElement('div');
    legendDiv.className = 'summary-legend';

    outcomes.forEach(outcome => {
        const legendItem = document.createElement('div');
        legendItem.className = `legend-item ${outcome.key}`;
        legendItem.setAttribute('data-tooltip', outcome.description);
        legendItem.innerHTML = `
            <div class="legend-color ${outcome.key}"></div>
            <span>${outcome.label}</span>
        `;
        legendDiv.appendChild(legendItem);
    });

    container.appendChild(legendDiv);
}

// Update summary display in real-time
function updateSummaryDisplay(summary) {
    const summaryContent = document.getElementById('summary-content');
    if (!summaryContent) return;

    // Reveal the summary block once we have a tally
    const summaryWrap = document.getElementById('response-summary');
    if (summaryWrap) summaryWrap.style.display = 'block';

    if (!summary || Object.keys(summary).length === 0) {
        summaryContent.innerHTML = 'Waiting for responses...';
        return;
    }

    // Debug logging - show grouping
    console.log('=== SUMMARY GROUPING ===');
    console.log('Summary object:', JSON.stringify(summary, null, 2));
    Object.entries(summary).forEach(([outcome, judges]) => {
        console.log(`${judges.length} ${outcome}: [${judges.join(', ')}]`);
    });
    console.log('========================');

    // Calculate total judges
    const totalJudges = Object.values(summary).reduce((sum, judges) => sum + judges.length, 0);

    // Create proportional bar
    const barDiv = document.createElement('div');
    barDiv.className = 'summary-bar';
    barDiv.style.cssText = `
        display: flex;
        width: 80%;
        height: 40px;
        border-radius: 8px;
        overflow: visible;
        margin: 1rem auto 3rem auto;
        border: 1px solid #ccc;
    `;

    // Add segments for each outcome
    Object.entries(summary).forEach(([outcome, judges]) => {
        const segment = document.createElement('div');
        segment.className = `bar-segment ${outcome}`;
        segment.setAttribute('data-tooltip', getOutcomeDescription(outcome));

        // Get last names only
        const lastNames = judges.map(name => name.split(' ').pop());

        segment.style.cssText = `
            flex: ${judges.length};
            background: var(--${outcome});
            display: flex;
            align-items: center;
            justify-content: center;
            color: ${getTextColorForOutcome(outcome)};
            font-size: 0.8rem;
            font-weight: 600;
            padding: 0 4px;
            text-align: center;
            overflow: hidden;
            position: relative;
        `;

        segment.innerHTML = `${judges.length} ${lastNames.join(', ')}`;
        barDiv.appendChild(segment);
    });

    summaryContent.innerHTML = '';
    summaryContent.appendChild(barDiv);

    // Add legend
    createSummaryLegend(summaryContent);
}

// Toggle response expansion
function toggleResponse(button) {
    const responseCard = button.closest('.response-card');
    const briefResponse = responseCard.querySelector('.brief-response');
    const fullResponse = responseCard.querySelector('.full-response');
    
    if (fullResponse.style.display === 'none') {
        briefResponse.style.display = 'none';
        fullResponse.style.display = 'block';
    } else {
        briefResponse.style.display = 'block';
        fullResponse.style.display = 'none';
    }
}

// Show alert
function showAlert(message, type = 'info') {
    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    alert.textContent = message;

    document.body.appendChild(alert);

    setTimeout(() => {
        alert.remove();
    }, 5000);
}

// Initialize About Modal
function initializeAboutModal() {
    const aboutLink = document.getElementById('about-link');
    const aboutModal = document.getElementById('about-modal');
    const modalClose = document.querySelector('.modal-close');

    // Open modal when About link is clicked
    if (aboutLink) {
        aboutLink.addEventListener('click', (e) => {
            e.preventDefault();
            aboutModal.style.display = 'block';
            document.body.style.overflow = 'hidden'; // Prevent scrolling
        });
    }

    // Close modal when X is clicked
    if (modalClose) {
        modalClose.addEventListener('click', () => {
            aboutModal.style.display = 'none';
            document.body.style.overflow = 'auto'; // Restore scrolling
        });
    }

    // Close modal when clicking outside the modal content
    window.addEventListener('click', (e) => {
        if (e.target === aboutModal) {
            aboutModal.style.display = 'none';
            document.body.style.overflow = 'auto'; // Restore scrolling
        }
    });

    // Close modal with Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && aboutModal.style.display === 'block') {
            aboutModal.style.display = 'none';
            document.body.style.overflow = 'auto'; // Restore scrolling
        }
    });
}
