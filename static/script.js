let judges = [];
let selectedJudges = new Set();
let queriesRemaining = 5;
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
    
    const shouldEnable = hasQuestion && hasSelectedJudges && queriesRemaining > 0;
    askButton.disabled = !shouldEnable;
}

// Check query limit
async function checkQueryLimit() {
    try {
        console.log('Checking query limit...');
        const response = await fetch(`${window.location.origin}/api/check-limit`);
        const data = await response.json();
        console.log('Query limit response:', data);
        
        queriesRemaining = data.remaining;
        console.log('Updated queriesRemaining to:', queriesRemaining);
        updateQueryStatus();
    } catch (error) {
        console.error('Error checking query limit:', error);
    }
}

// Update query status display
function updateQueryStatus() {
    console.log('updateQueryStatus called with queriesRemaining:', queriesRemaining);
    const statusElement = document.getElementById('queries-remaining');
    if (!statusElement) {
        console.log('queries-remaining element not found');
        return;
    }

    if (queriesRemaining === 0) {
        statusElement.innerHTML = '<span class="limit-reached">No more queries remaining (5/5 used)</span>';
        askButton.disabled = true;
    } else {
        statusElement.innerHTML = `Queries remaining: <span class="queries-count">${queriesRemaining}/5</span>`;
    }
    console.log('Updated status element to:', statusElement.innerHTML);
}

// Handle ask question
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
    responsesSection.style.display = 'none';

    try {
        const response = await fetch(`${window.location.origin}/api/query`, {
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
        
        // Check if this is async processing (multiple judges)
        if (data.job_id && data.job_id !== null && data.job_id !== undefined) {
            await handleAsyncProcessing(data.job_id, question);
        } else {
            // Single judge - immediate response
            displayResponses(data);
        }

        await checkQueryLimit();

    } catch (error) {
        console.error('Error querying judges:', error);
        showAlert('An error occurred while querying the Justices', 'error');
    } finally {
        isProcessing = false; // Clear processing flag
        askButton.disabled = false;
        loading.style.display = 'none';
    }
}

// Update progress indicator
function updateProgressIndicator(completed, total) {
    const progressIndicator = document.getElementById('progress-indicator');
    const progressCount = document.getElementById('progress-count');
    const progressBar = document.getElementById('progress-bar');
    const waitMessage = document.getElementById('wait-message');

    if (progressIndicator && progressCount && progressBar) {
        progressIndicator.style.display = 'block';
        const percentage = (completed / total) * 100;
        progressCount.textContent = `${completed} of ${total} judges response completed`;
        progressBar.style.width = `${percentage}%`;
    }

    // Show wait message while processing
    if (waitMessage && completed < total) {
        waitMessage.style.display = 'inline';
    }
}

// Hide progress indicator
function hideProgressIndicator() {
    const progressIndicator = document.getElementById('progress-indicator');
    const waitMessage = document.getElementById('wait-message');

    if (progressIndicator) {
        progressIndicator.style.display = 'none';
    }

    if (waitMessage) {
        waitMessage.style.display = 'none';
    }
}

// Handle async processing with progress updates
async function handleAsyncProcessing(jobId, question) {
    // Validate job_id
    if (!jobId || jobId === null || jobId === undefined || jobId === '') {
        console.error('Invalid job_id provided to handleAsyncProcessing');
        return;
    }
    
    // Ensure button stays disabled during async processing
    askButton.disabled = true;
    
    // Clear responses and show the section
    responsesContainer.innerHTML = '';
    responsesSection.style.display = 'block';

    // Show progress indicator
    updateProgressIndicator(0, selectedJudges.size);

    // Create summary container
    const summaryDiv = document.createElement('div');
    summaryDiv.className = 'response-summary';
    summaryDiv.innerHTML = '<h3>Response Summary</h3><div id="summary-content">Waiting for responses...</div>';
    responsesContainer.appendChild(summaryDiv);

    // Poll for progress every 5 seconds
    const pollInterval = setInterval(async () => {
        try {
            const progressResponse = await fetch(`${window.location.origin}/api/progress/${jobId}`);
            const progressData = await progressResponse.json();

            // Update progress indicator
            updateProgressIndicator(progressData.completed, progressData.total);

            // Update summary in real-time
            updateSummaryDisplay(progressData.summary);

            // Add new responses as they arrive
            updateResponsesDisplay(progressData.responses);

            if (progressData.status === 'completed') {
                clearInterval(pollInterval);
                hideProgressIndicator();
                isProcessing = false; // Clear processing flag
                askButton.disabled = false; // Re-enable button when done
            }
        } catch (error) {
            console.error('Error checking progress:', error);
            clearInterval(pollInterval);
            hideProgressIndicator();
            isProcessing = false; // Clear processing flag
            askButton.disabled = false; // Re-enable button on error
        }
    }, 5000); // Poll every 5 seconds
}

// Helper function to determine text color based on outcome
function getTextColorForOutcome(outcome) {
    const darkTextOutcomes = ['affirmed', 'vacated', 'granted', 'reinstated', 'modified'];
    return darkTextOutcomes.includes(outcome) ? 'black' : 'white';
}

// Create summary legend showing all possible outcomes
function createSummaryLegend(container) {
    const outcomes = [
        { key: 'affirmed', label: 'Affirmed' },
        { key: 'reversed', label: 'Reversed' },
        { key: 'vacated', label: 'Vacated' },
        { key: 'remanded', label: 'Remanded' },
        { key: 'denied', label: 'Denied' },
        { key: 'granted', label: 'Granted' },
        { key: 'stayed', label: 'Stayed' },
        { key: 'reinstated', label: 'Reinstated' },
        { key: 'dismissed', label: 'Dismissed' },
        { key: 'modified', label: 'Modified' }
    ];

    const legendDiv = document.createElement('div');
    legendDiv.className = 'summary-legend';

    outcomes.forEach(outcome => {
        const legendItem = document.createElement('div');
        legendItem.className = 'legend-item';
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

    if (!summary || Object.keys(summary).length === 0) {
        summaryContent.innerHTML = 'Waiting for responses...';
        return;
    }

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
        overflow: hidden;
        margin: 1rem auto;
        border: 1px solid #ccc;
    `;

    // Add segments for each outcome
    Object.entries(summary).forEach(([outcome, judges]) => {
        const segment = document.createElement('div');
        segment.className = `bar-segment ${outcome}`;

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
        `;

        segment.innerHTML = `${judges.length} ${lastNames.join(', ')}`;
        barDiv.appendChild(segment);
    });

    summaryContent.innerHTML = '';
    summaryContent.appendChild(barDiv);

    // Add legend
    createSummaryLegend(summaryContent);
}

// Update responses display as they arrive
function updateResponsesDisplay(responses) {
    // Remove existing response cards (keep summary)
    const existingCards = responsesContainer.querySelectorAll('.response-card');
    existingCards.forEach(card => card.remove());
    
    // Add all current responses
    if (responses && Array.isArray(responses)) {
        responses.forEach(response => {
        const responseCard = document.createElement('div');
        responseCard.className = `response-card ${response.support_level}`;
        
        responseCard.innerHTML = `
            <div class="response-header">
                <h3 style="color: var(--${response.support_level})">${response.judge_title}</h3>
            </div>
            <div class="response-content">
                <div class="brief-response">
                    <p>${response.brief}</p>
                    <button class="expand-btn" onclick="toggleResponse(this)">Read Full Response</button>
                </div>
                <div class="full-response" style="display: none;">
                    <p>${response.full_response}</p>
                    <button class="collapse-btn" onclick="toggleResponse(this)">Show Less</button>
                </div>
            </div>
        `;
        
        responsesContainer.appendChild(responseCard);
    });
    }
}

// Display responses
function displayResponses(data) {
    responsesContainer.innerHTML = '';

    if (!data.responses || data.responses.length === 0) {
        responsesContainer.innerHTML = '<p>No responses received.</p>';
        responsesSection.style.display = 'block';
        return;
    }

    // Create summary by outcome
    const summary = {};
    data.responses.forEach(response => {
        const outcome = response.support_level || 'unknown';
        if (!summary[outcome]) {
            summary[outcome] = [];
        }
        summary[outcome].push(response.judge_title);
    });

    // Display summary
    if (Object.keys(summary).length > 0) {
        const summaryDiv = document.createElement('div');
        summaryDiv.className = 'response-summary';
        summaryDiv.innerHTML = '<h3>Response Summary</h3>';

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
            overflow: hidden;
            margin: 1rem auto;
            border: 1px solid #ccc;
        `;

        // Add segments for each outcome
        Object.entries(summary).forEach(([outcome, judges]) => {
            const segment = document.createElement('div');
            segment.className = `bar-segment ${outcome}`;

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
            `;

            segment.innerHTML = `${judges.length} ${lastNames.join(', ')}`;
            barDiv.appendChild(segment);
        });

        summaryDiv.appendChild(barDiv);

        // Add summary content div for legend
        const summaryContent = document.createElement('div');
        summaryContent.id = 'summary-content-static';
        summaryDiv.appendChild(summaryContent);

        // Add legend
        createSummaryLegend(summaryContent);

        responsesContainer.appendChild(summaryDiv);
    }
    
    data.responses.forEach(response => {
        const responseCard = document.createElement('div');
        responseCard.className = `response-card ${response.support_level}`;
        
        responseCard.innerHTML = `
            <div class="response-header">
                <h3 style="color: var(--${response.support_level})">${response.judge_title}</h3>
            </div>
            <div class="response-content">
                <div class="brief-response">
                    <p>${response.brief}</p>
                    <button class="expand-btn" onclick="toggleResponse(this)">Read Full Response</button>
                </div>
                <div class="full-response" style="display: none;">
                    <p>${response.full_response}</p>
                    <button class="collapse-btn" onclick="toggleResponse(this)">Show Less</button>
                </div>
            </div>
        `;
        
        responsesContainer.appendChild(responseCard);
    });
    
    responsesSection.style.display = 'block';
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
