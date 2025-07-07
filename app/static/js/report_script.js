document.addEventListener('DOMContentLoaded', function() {
    const currencyToggle = document.getElementById('currencyToggle');
    const currencyLabel = document.getElementById('currencyLabel');
    const usdRate = parseFloat(document.body.dataset.usdRate) || 13000;
    const exportLink = document.getElementById('export-link'); // Находим ссылку экспорта

    const STORAGE_KEYS = {
        currency: 'planFactReport_currencyIsUSD',
        activeTab: 'planFactReport_activeTab'
    };

    function updateCurrency(isUsd) {
        // Обновляем все денежные значения на странице
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
                displayValue = uzsValue.toLocaleString('ru-RU', { maximumFractionDigits: 0 }).replace(/,/g, '.');
            }
             el.textContent = displayValue;
        });

        // --- НАЧАЛО: НОВЫЙ БЛОК ДЛЯ ОБНОВЛЕНИЯ ССЫЛКИ ЭКСПОРТА ---
        if (exportLink) {
            const baseUrl = exportLink.dataset.baseUrl;
            if (isUsd) {
                exportLink.href = baseUrl + '?currency=USD';
            } else {
                exportLink.href = baseUrl; // Возвращаем базовый URL без параметров
            }
        }
        // --- КОНЕЦ НОВОГО БЛОКА ---
    }

    function restoreState() {
        const savedCurrencyIsUSD = localStorage.getItem(STORAGE_KEYS.currency);
        if (savedCurrencyIsUSD === 'true' && currencyToggle) {
            currencyToggle.checked = true;
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

    // --- НОВАЯ ЛОГИКА СОРТИРОВКИ ТАБЛИЦЫ ---
    function sortTable(table, column, asc = true) {
        const dirModifier = asc ? 1 : -1;
        const tBody = table.tBodies[0];
        const rows = Array.from(tBody.querySelectorAll("tr"));

        const isNumeric = table.querySelector(`th:nth-child(${column + 1})`).dataset.type === 'numeric';

        const sortedRows = rows.sort((a, b) => {
            const aColText = a.querySelector(`td:nth-child(${column + 1})`).textContent.trim();
            const bColText = b.querySelector(`td:nth-child(${column + 1})`).textContent.trim();

            if (isNumeric) {
                const aVal = parseFloat(aColText.replace(/[^0-9.-]+/g,""));
                const bVal = parseFloat(bColText.replace(/[^0-9.-]+/g,""));
                return (aVal - bVal) * dirModifier;
            }

            return aColText.localeCompare(bColText, 'ru', { sensitivity: 'base' }) * dirModifier;
        });

        while (tBody.firstChild) {
            tBody.removeChild(tBody.firstChild);
        }

        tBody.append(...sortedRows);

        table.querySelectorAll("th").forEach(th => th.classList.remove("th-asc", "th-desc"));
        table.querySelector(`th:nth-child(${column + 1})`).classList.toggle("th-asc", asc);
        table.querySelector(`th:nth-child(${column + 1})`).classList.toggle("th-desc", !asc);
    }

    document.querySelectorAll("#summaryTable th[data-sortable]").forEach(headerCell => {
        headerCell.addEventListener("click", () => {
            const tableElement = headerCell.parentElement.parentElement.parentElement;
            const headerIndex = Array.prototype.indexOf.call(headerCell.parentElement.children, headerCell);
            const currentIsAsc = headerCell.classList.contains("th-asc");
            sortTable(tableElement, headerIndex, !currentIsAsc);
        });
    });


    // --- НОВАЯ ЛОГИКА ПОИСКА В ТАБЛИЦЕ ---
    const searchInput = document.getElementById('projectSearchInput');
    const tableBody = document.getElementById('summaryTableBody');
    if (searchInput && tableBody) {
        const allRows = Array.from(tableBody.querySelectorAll('tr'));

        searchInput.addEventListener('input', function() {
            const searchTerm = searchInput.value.toLowerCase().trim();

            allRows.forEach(row => {
                const projectNameEl = row.querySelector('.project-link');
                if (projectNameEl) {
                    const projectName = projectNameEl.textContent.toLowerCase();
                    if (projectName.includes(searchTerm)) {
                        row.style.display = '';
                    } else {
                        row.style.display = 'none';
                    }
                }
            });
        });
    }

    // Инициализация при загрузке
    if (currencyToggle) {
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

    restoreState();
});