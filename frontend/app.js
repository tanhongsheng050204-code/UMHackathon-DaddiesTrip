document.getElementById('generate-btn').addEventListener('click', async () => {
    const prompt = document.getElementById('prompt-input').value;
    if (!prompt) return;

    const btn = document.getElementById('generate-btn');
    const overlay = document.getElementById('full-page-overlay');
    const overlaySpinner = document.getElementById('overlay-spinner');
    const overlayMessage = document.getElementById('overlay-message');
    const overlayError = document.getElementById('overlay-error');
    const overlayClose = document.getElementById('overlay-close');
    const resultsSection = document.getElementById('results-section');

    overlaySpinner.classList.remove('hidden');
    overlayMessage.innerText = 'Orchestrating your trip...';
    overlayError.classList.add('hidden');
    overlayClose.classList.add('hidden');

    btn.disabled = true;
    overlay.classList.remove('hidden');
    resultsSection.classList.add('hidden');

    let success = false;
    startProgress();

    try {
        const response = await fetch('/api/plan-trip', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt })
        });

        const data = await response.json();

        if (response.ok) {
            renderBudgetAnalysis(data.budget_recommendation);
            if (data.flight_options && data.flight_options.length > 0) {
                renderFlightOptions(data.flight_options);
            } else if (data.flights) {
                renderFlightOptions([data.flights]);
            }
            renderItinerary(data.itinerary);
            renderLedger(data.split, data.itinerary, data.flights || (data.flight_options && data.flight_options[0]));
            resultsSection.classList.remove('hidden');
            resultsSection.scrollIntoView({ behavior: 'smooth' });
            success = true;
        } else {
            stopProgress(false);
            showErrorInOverlay(data.detail || 'Failed to generate itinerary.');
        }
    } catch (error) {
        console.error('Frontend Error:', error);
        stopProgress(false);
        showErrorInOverlay('Frontend Error: ' + error.message);
    } finally {
        btn.disabled = false;
        if (success) {
            stopProgress(true);
            setTimeout(() => { overlay.classList.add('hidden'); }, 500);
        }
    }
});

function startProgress() {
    const container = document.getElementById('progress-container');
    const bar = document.getElementById('progress-bar');
    const statusText = document.getElementById('overlay-status-text');
    let progress = 0;
    
    const statuses = [
        { threshold: 0, text: 'Planner: Drafting logical route...' },
        { threshold: 20, text: 'Booking: Sourcing flights and hotels...' },
        { threshold: 40, text: 'Budget: Optimizing costs and currency...' },
        { threshold: 60, text: 'Edge Agent: Validating data integrity...' },
        { threshold: 80, text: 'Translator: Finalizing local details...' },
        { threshold: 95, text: 'Polishing the itinerary...' }
    ];

    bar.style.width = '0%';
    container.classList.remove('hidden');
    statusText.classList.remove('hidden');

    window._progressInterval = setInterval(() => {
        if (progress < 95) {
            progress += Math.random() * 4;
            progress = Math.min(progress, 95);
            bar.style.width = `${progress}%`;
            const current = [...statuses].reverse().find(s => progress >= s.threshold);
            if (current) statusText.innerText = current.text;
        }
    }, 800);
}

function stopProgress(success) {
    clearInterval(window._progressInterval);
    const bar = document.getElementById('progress-bar');
    const statusText = document.getElementById('overlay-status-text');
    if (success) {
        bar.style.width = '100%';
        statusText.innerText = 'Done!';
    }
}

function showErrorInOverlay(errorMessage) {
    const overlaySpinner = document.getElementById('overlay-spinner');
    const overlayMessage = document.getElementById('overlay-message');
    const overlayError = document.getElementById('overlay-error');
    const overlayClose = document.getElementById('overlay-close');

    overlaySpinner.classList.add('hidden');
    overlayMessage.innerText = 'Error';
    overlayError.innerText = errorMessage;
    overlayError.classList.remove('hidden');
    overlayClose.classList.remove('hidden');
}

document.getElementById('overlay-close').addEventListener('click', () => {
    document.getElementById('full-page-overlay').classList.add('hidden');
});

function renderBudgetAnalysis(recommendation) {
    const banner = document.getElementById('budget-banner');
    const status = document.getElementById('budget-status');
    const message = document.getElementById('budget-message');
    
    if (!recommendation) { banner.classList.add('hidden'); return; }
    
    banner.classList.remove('hidden', 'success', 'warning');
    
    if (recommendation.is_sufficient) {
        banner.classList.add('success');
        status.innerText = 'Budget Looks Good';
    } else {
        banner.classList.add('warning');
        status.innerText = 'Budget Alert';
    }
    message.innerText = recommendation.message;
}

let selectedFlightOption = null;

function renderFlightOptions(options) {
    const section = document.querySelector('.flights-section');
    const list = document.getElementById('flight-options-list');
    const costEl = document.getElementById('flight-cost');
    const sourceEl = document.getElementById('flight-source');
    
    if (!options || options.length === 0) { section.classList.add('hidden'); return; }
    
    section.classList.remove('hidden');
    list.innerHTML = '';
    
    options.forEach((opt, i) => {
        const dep = opt.departure || {};
        const ret = opt.return || {};
        const airline = opt.airline || `Option ${i+1}`;
        const cost = opt.cost_myr || 0;
        const depStr = `KUL ${dep.time || ''} ${dep.date || ''}`;
        const retStr = `${ret.airport || '?'} → KUL ${ret.time || ''}`;
        
        const row = document.createElement('label');
        row.className = 'flight-option-row' + (i === 0 ? ' selected' : '');
        row.innerHTML = `
            <input type="radio" name="flight_pick" value="${i}" ${i === 0 ? 'checked' : ''}>
            <div class="flight-option-info">
                <span class="flight-airline">${airline}</span>
                <span class="flight-route">${depStr} → ${retStr}</span>
            </div>
            <span class="flight-option-price">RM ${cost}</span>
        `;
        row.querySelector('input').addEventListener('change', () => {
            document.querySelectorAll('.flight-option-row').forEach(r => r.classList.remove('selected'));
            row.classList.add('selected');
            selectedFlightOption = opt;
            costEl.innerText = `RM ${cost}`;
            const src = opt.source || '#';
            sourceEl.href = src.startsWith('http') ? src : `https://${src}`;
        });
        list.appendChild(row);
    });
    
    selectedFlightOption = options[0];
    costEl.innerText = `RM ${options[0].cost_myr || 0}`;
    const src0 = options[0].source || '#';
    sourceEl.href = src0.startsWith('http') ? src0 : `https://${src0}`;
}

function renderItinerary(itinerary) {
    const container = document.getElementById('itinerary-content');
    container.innerHTML = '';

    itinerary.forEach(day => {
        const card = document.createElement('div');
        card.className = 'day-card';
        
        const activitiesHtml = day.activities ? day.activities.map(act => {
            const gmapLink = `https://www.google.com/maps/search/${encodeURIComponent((act.name || 'attraction'))}`;
            const sourceHref = (act.source && act.source.startsWith('http')) ? act.source : gmapLink;
            const nameLC = (act.name || '').toLowerCase();
            const isTicketed = nameLC.includes('ticket required');
            const isFree = nameLC.includes('free');
            const badgeHtml = isTicketed
                ? `<span class="ticket-badge required">🎟 Ticket Required</span>`
                : isFree ? `<span class="ticket-badge free">✓ Free Entry</span>` : '';
            return `
            <li>
                <div class="activity-header">
                    <span class="activity-name">${act.name}</span>
                    ${badgeHtml}
                </div>
                <div class="activity-meta">
                    <span class="cost-tag">RM ${act.cost_myr || 0}</span>
                    <a href="${sourceHref}" target="_blank" class="source-link">📍 Map ↗</a>
                </div>
            </li>`;
        }).join('') : '';

        const hotelName = day.hotel ? day.hotel.name : 'Not Specified';
        const hotelCost = day.hotel ? day.hotel.cost_myr : 0;
        const foodRecs = day.food_recommendations ? day.food_recommendations.join(', ') : 'No recommendations';
        const foodCost = day.daily_food_cost_myr || 0;
        const transRoute = day.transportation ? day.transportation.route : 'Local transit';
        const transCost = day.transportation ? day.transportation.cost_myr : 0;

        card.innerHTML = `
            <h4>Day ${day.day}: ${day.location}</h4>
            <ul>${activitiesHtml}</ul>
            <div class="daily-modules">
                <div class="module-box">
                    <h5>🏨 Stay</h5>
                    <p>${hotelName}</p>
                    <span class="cost-tag">RM ${hotelCost} / night</span>
                </div>
                <div class="module-box">
                    <h5>🍜 Eat</h5>
                    <p>${foodRecs}</p>
                    <span class="cost-tag">RM ${foodCost} / day</span>
                </div>
                <div class="module-box">
                    <h5>🚇 Transit</h5>
                    <p>${transRoute}</p>
                    <span class="cost-tag">RM ${transCost} / day</span>
                </div>
            </div>
        `;
        container.appendChild(card);
    });
}

let currentTripData = null;

function renderLedger(split, itinerary, flights) {
    if (!split || !split.primary_currency) return;
    currentTripData = { split, itinerary, flights };
    document.getElementById('total-cost').innerText = `RM ${split.total_myr}`;
    document.getElementById('split-person').innerText = `RM ${split.split_per_person_myr}`;
    document.getElementById('local-currency-label').innerText = `Local (${split.destination_currency})`;
    document.getElementById('split-local').innerText = `${split.split_per_person_local} ${split.destination_currency}`;
}

document.getElementById('review-budget-btn').addEventListener('click', () => {
    if (!currentTripData) return;
    populateAccountingTable(currentTripData);
    document.getElementById('budget-modal').classList.remove('hidden');
});

document.getElementById('close-budget-btn').addEventListener('click', () => {
    document.getElementById('budget-modal').classList.add('hidden');
});

function populateAccountingTable(data) {
    const { split, itinerary, flights } = data;
    let hotelTotal = 0, foodTotal = 0, transTotal = 0, actTotal = 0;
    
    itinerary.forEach(day => {
        hotelTotal += (day.hotel ? day.hotel.cost_myr : 0);
        foodTotal += (day.daily_food_cost_myr || 0);
        transTotal += (day.transportation ? day.transportation.cost_myr : 0);
        if (day.activities) day.activities.forEach(act => actTotal += (act.cost_myr || 0));
    });

    const flightCost = selectedFlightOption ? (selectedFlightOption.cost_myr || 0) : (flights ? (flights.cost_myr || 0) : 0);
    
    document.getElementById('acc-flights').innerText = `RM ${flightCost}`;
    document.getElementById('acc-hotel').innerText = `RM ${hotelTotal}`;
    document.getElementById('acc-food').innerText = `RM ${foodTotal}`;
    document.getElementById('acc-trans').innerText = `RM ${transTotal}`;
    document.getElementById('acc-act').innerText = `RM ${actTotal}`;
    document.getElementById('acc-total').innerText = `RM ${split.total_myr}`;
}

// Live card preview
document.getElementById('card-input').addEventListener('input', (e) => {
    let val = e.target.value.replace(/\D/g, '').substring(0, 16);
    let formatted = val.match(/.{1,4}/g)?.join(' ') || val;
    e.target.value = formatted;
    document.getElementById('card-number-display').innerText = formatted || '•••• •••• •••• ••••';
});

document.getElementById('card-holder').addEventListener('input', (e) => {
    document.getElementById('card-holder-display').innerText = e.target.value.toUpperCase() || 'YOUR NAME';
});

document.getElementById('card-expiry').addEventListener('input', (e) => {
    let val = e.target.value.replace(/\D/g, '').substring(0, 4);
    if (val.length >= 3) val = val.substring(0, 2) + '/' + val.substring(2);
    e.target.value = val;
    document.getElementById('card-expiry-display').innerText = val || 'MM/YY';
});

// Payment Sequence
document.getElementById('settle-btn').addEventListener('click', async () => {
    const cardInput = document.getElementById('card-input').value.replace(/\s/g, '');
    const msgEl = document.getElementById('settle-message');

    if (cardInput.length < 16) {
        msgEl.innerText = 'Please enter a valid 16-digit card number.';
        msgEl.style.color = 'var(--error)';
        return;
    }

    document.getElementById('budget-modal').classList.add('hidden');
    const paymentModal = document.getElementById('payment-modal');
    const statusText = document.getElementById('payment-status-text');
    
    paymentModal.classList.remove('hidden');
    statusText.innerText = 'Processing...';

    setTimeout(async () => {
        try {
            const response = await fetch('/api/settle', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ group_id: "group_123", user_id: "user_1", card_number: cardInput })
            });
            const data = await response.json();

            if (response.ok) {
                statusText.innerText = 'Payment Successful!';
                setTimeout(() => paymentModal.classList.add('hidden'), 3000);
            } else {
                paymentModal.classList.add('hidden');
                msgEl.innerText = data.detail;
                msgEl.style.color = 'var(--error)';
                document.getElementById('budget-modal').classList.remove('hidden');
            }
        } catch (error) {
            paymentModal.classList.add('hidden');
            msgEl.innerText = 'Connection failed.';
            msgEl.style.color = 'var(--error)';
            document.getElementById('budget-modal').classList.remove('hidden');
        }
    }, 2000);
});
