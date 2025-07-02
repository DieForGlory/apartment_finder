document.addEventListener('DOMContentLoaded', function() {
    const currencyToggle = document.getElementById('currencyToggle');
    const currencyLabel = document.getElementById('currencyLabel');
    const usdRate = parseFloat(document.body.dataset.usdRate) || 12650;

    const STORAGE_KEYS = {
        currency: 'planFactReport_currencyIsUSD',
        activeTab: 'planFactReport_activeTab'
    };

    function updateCurrency(isUsd) {
        document.querySelectorAll('.currency-value').forEach(el => {
            const uzsValue = parseFloat(el.dataset.uzsValue);
            if (isNaN(uzsValue)) return;

            let displayValue;
            if (isUsd) {
                if(currencyLabel) currencyLabel.textContent = 'USD';
                let usdValue = uzsValue / usdRate;
                displayValue = '$' + usdValue.toLocaleString('en-US', { maximumFractionDigits: 0 });
            } else {
                if(currencyLabel) currencyLabel.textContent = 'UZS';
                displayValue = uzsValue.toLocaleString('ru-RU', { maximumFractionDigits: 0 });
            }

            if (el.classList.contains('metric-value') || el.classList.contains('metric-sub-value')) {
                const prefix = el.textContent.includes('План:') ? 'План: ' : '';
                displayValue = prefix + displayValue;
            }

            el.textContent = displayValue;
        });
    }

    function restoreState() {
        const savedCurrencyIsUSD = localStorage.getItem(STORAGE_KEYS.currency);
        if (savedCurrencyIsUSD === 'true') {
            if(currencyToggle) currencyToggle.checked = true;
        }
        updateCurrency(currencyToggle ? currencyToggle.checked : false);

        const savedTabId = localStorage.getItem(STORAGE_KEYS.activeTab);
        if (savedTabId) {
            const tabTrigger = document.querySelector(`button[data-bs-target="${savedTabId}"]`);
            if (tabTrigger) {
                const tab = new bootstrap.Tab(tabTrigger);
                tab.show();
            }
        }
    }

    if(currencyToggle) {
        currencyToggle.addEventListener('change', function() {
            localStorage.setItem(STORAGE_KEYS.currency, this.checked);
            updateCurrency(this.checked);
        });
    }

    document.querySelectorAll('button[data-bs-toggle="tab"]').forEach(tab => {
        tab.addEventListener('shown.bs.tab', function (event) {
            const activeTabId = event.target.dataset.bsTarget;
            localStorage.setItem(STORAGE_KEYS.activeTab, activeTabId);
        });
    });

    // Логика поиска по проектам
    const searchInput = document.getElementById('projectSearchInput');
    const projectsList = document.getElementById('projects-list');
    if (searchInput && projectsList) {
        const allProjectCards = projectsList.querySelectorAll('.project-card');

        searchInput.addEventListener('input', function() {
            const searchTerm = searchInput.value.toLowerCase().trim();

            allProjectCards.forEach(card => {
                const projectNameEl = card.querySelector('.project-name a');
                if (projectNameEl) {
                    const projectName = projectNameEl.textContent.toLowerCase();
                    if (projectName.includes(searchTerm)) {
                        card.style.display = '';
                    } else {
                        card.style.display = 'none';
                    }
                }
            });
        });
    }

    // Инициализация
    restoreState();
});
