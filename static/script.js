let judges = [];
let selectedJudges = new Set();
let queriesRemaining = 5;

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
    
    console.log('askButton:', askButton);
    console.log('selectAllButton:', selectAllButton);
    
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
        console.log('Adding click listener to Select All button');
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
        const response = await fetch('/api/judges');
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
    console.log('toggleSelectAll called');
    console.log('judges:', judges);
    console.log('selectedJudges.size:', selectedJudges.size);
    
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
        // Select all
        console.log('Selecting all');
        selectedJudges.clear();
        judges.forEach(judge => {
            selectedJudges.add(judge.judge_name);
        });
        document.querySelectorAll('.judge-toggle').forEach(card => {
            card.classList.add('selected');
        });
        if (selectAllButton) selectAllButton.textContent = 'Deselect All';
    }
    
    console.log('selectedJudges after toggle:', selectedJudges);
    updateAskButton();
}

// Update ask button state
function updateAskButton() {
    if (!questionInput || !askButton) return;
    
    const hasQuestion = questionInput.value.trim().length > 0;
    const hasSelectedJudges = selectedJudges.size > 0;
    
    const shouldEnable = hasQuestion && hasSelectedJudges && queriesRemaining > 0;
    askButton.disabled = !shouldEnable;
}

// Check query limit
async function checkQueryLimit() {
    try {
        const response = await fetch('/api/check-limit');
        const data = await response.json();
        queriesRemaining = data.remaining;
        updateQueryStatus();
    } catch (error) {
        console.error('Error checking query limit:', error);
    }
}

// Update query status display
function updateQueryStatus() {
    const statusElement = document.getElementById('queries-remaining');
    if (!statusElement) return;
    
    if (queriesRemaining === 0) {
        statusElement.innerHTML = '<span class="limit-reached">No more queries remaining (5/5 used)</span>';
        askButton.disabled = true;
    } else {
        statusElement.innerHTML = `Queries remaining: <span class="queries-count">${queriesRemaining}/5</span>`;
    }
}

// Show progress in status bar
function showProgress(completed, total) {
    const statusElement = document.getElementById('queries-remaining');
    if (statusElement) {
        statusElement.innerHTML = `<span class="processing">Processing judges: ${completed}/${total} completed...</span>`;
    }
}

// Hide progress and restore query status
function hideProgress() {
    updateQueryStatus();
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
        
        // Check if this is async processing (multiple judges)
        if (data.job_id) {
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
        askButton.disabled = false;
        loading.style.display = 'none';
    }
}

// Handle async processing with progress updates
async function handleAsyncProcessing(jobId, question) {
    // Show initial progress in status bar
    showProgress(0, selectedJudges.size);
    
    // Clear responses and show the section
    responsesContainer.innerHTML = '';
    responsesSection.style.display = 'block';
    
    // Create summary container
    const summaryDiv = document.createElement('div');
    summaryDiv.className = 'response-summary';
    summaryDiv.innerHTML = '<h3>Response Summary</h3><div id="summary-content">Waiting for responses...</div>';
    responsesContainer.appendChild(summaryDiv);

    // Poll for progress every 5 seconds
    const pollInterval = setInterval(async () => {
        try {
            const progressResponse = await fetch(`/api/progress/${jobId}`);
            const progressData = await progressResponse.json();
            
            // Update status bar with progress
            showProgress(progressData.completed, progressData.total);
            
            // Update summary in real-time
            updateSummaryDisplay(progressData.summary);
            
            // Add new responses as they arrive
            updateResponsesDisplay(progressData.responses);
            
            if (progressData.status === 'completed') {
                clearInterval(pollInterval);
                hideProgress();
            }
        } catch (error) {
            console.error('Error checking progress:', error);
            clearInterval(pollInterval);
            hideProgress();
        }
    }, 5000); // Poll every 5 seconds
}

// Update summary display in real-time
function updateSummaryDisplay(summary) {
    const summaryContent = document.getElementById('summary-content');
    if (!summaryContent) return;
    
    if (!summary || Object.keys(summary).length === 0) {
        summaryContent.innerHTML = 'Waiting for responses...';
        return;
    }
    
    summaryContent.innerHTML = '';
    Object.entries(summary).forEach(([level, judges]) => {
        const summaryItem = document.createElement('div');
        summaryItem.className = `summary-item ${level}`;
        summaryItem.innerHTML = `
            <span class="support-level ${level}">${level.replace('_', ' ')}</span>: 
            ${judges.join(', ')} (${judges.length})
        `;
        summaryContent.appendChild(summaryItem);
    });
}

// Update responses display as they arrive
function updateResponsesDisplay(responses) {
    // Remove existing response cards (keep summary)
    const existingCards = responsesContainer.querySelectorAll('.response-card');
    existingCards.forEach(card => card.remove());
    
    // Add all current responses
    responses.forEach(response => {
        const responseCard = document.createElement('div');
        responseCard.className = `response-card ${response.support_level}`;
        
        responseCard.innerHTML = `
            <div class="response-header">
                <h3 style="color: var(--${response.support_level})">${response.judge_title}</h3>
                <span class="support-level ${response.support_level}">${response.support_level.replace('_', ' ')}</span>
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

// Display responses
function displayResponses(data) {
    responsesContainer.innerHTML = '';
    
    if (!data.responses || data.responses.length === 0) {
        responsesContainer.innerHTML = '<p>No responses received.</p>';
        responsesSection.style.display = 'block';
        return;
    }
    
    // Create summary by support level
    const summary = {};
    data.responses.forEach(response => {
        const level = response.support_level || 'neutral';
        if (!summary[level]) {
            summary[level] = [];
        }
        summary[level].push(response.judge_title);
    });
    
    // Display summary
    if (Object.keys(summary).length > 0) {
        const summaryDiv = document.createElement('div');
        summaryDiv.className = 'response-summary';
        summaryDiv.innerHTML = '<h3>Response Summary</h3>';
        
        Object.entries(summary).forEach(([level, judges]) => {
            const summaryItem = document.createElement('div');
            summaryItem.className = `summary-item ${level}`;
            summaryItem.innerHTML = `
                <span class="support-level ${level}">${level.replace('_', ' ')}</span>: 
                ${judges.join(', ')} (${judges.length})
            `;
            summaryDiv.appendChild(summaryItem);
        });
        
        responsesContainer.appendChild(summaryDiv);
    }
    
    data.responses.forEach(response => {
        const responseCard = document.createElement('div');
        responseCard.className = `response-card ${response.support_level}`;
        
        responseCard.innerHTML = `
            <div class="response-header">
                <h3 style="color: var(--${response.support_level})">${response.judge_title}</h3>
                <span class="support-level ${response.support_level}">${response.support_level.replace('_', ' ')}</span>
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
