// app/static/js/manager_performance_logic.js

document.addEventListener('DOMContentLoaded', function() {
    // Проверяем, существуют ли данные на странице
    if (typeof pageData === 'undefined' || !pageData) {
        console.error('Данные для инициализации скрипта не найдены.');
        return;
    }

    const usdRate = pageData.usdRate || 1;
    const performanceData = pageData.performance;
    const monthNames = pageData.monthNames;
    const currencySwitcher = document.getElementById('currency-switcher');

    let performanceChartVolume, performanceChartIncome;

    /**
     * Универсальная функция для создания или обновления графика
     * @param {string} canvasId - ID элемента canvas
     * @param {object} chartInstance - Переменная для хранения экземпляра графика
     * @param {string} planKey - Ключ для плановых данных (e.g., 'plan_volume')
     * @param {string} factKey - Ключ для фактических данных (e.g., 'fact_volume')
     * @param {boolean} isUsd - Включен ли режим USD
     * @returns {object} - Новый экземпляр графика
     */
    function createOrUpdateChart(canvasId, chartInstance, planKey, factKey, isUsd) {
        const ctx = document.getElementById(canvasId)?.getContext('2d');
        if (!ctx) return chartInstance;

        if (chartInstance) {
            chartInstance.destroy();
        }

        const labels = performanceData.map(d => monthNames[d.month] || d.month);
        const planData = performanceData.map(d => isUsd ? d[planKey] / usdRate : d[planKey]);
        const factData = performanceData.map(d => isUsd ? d[factKey] / usdRate : d[factKey]);
        const currency = isUsd ? 'USD' : 'UZS';

        return new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'План',
                    data: planData,
                    backgroundColor: 'rgba(255, 193, 7, 0.4)',
                    borderColor: 'rgba(255, 193, 7, 1)',
                    borderWidth: 1
                }, {
                    label: 'Факт',
                    data: factData,
                    backgroundColor: 'rgba(25, 135, 84, 0.6)',
                    borderColor: 'rgba(25, 135, 84, 1)',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: value => new Intl.NumberFormat('ru-RU').format(value)
                        }
                    }
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: context => {
                                let label = context.dataset.label || '';
                                if (label) label += ': ';
                                if (context.parsed.y !== null) {
                                    label += new Intl.NumberFormat('ru-RU', { style: 'currency', currency: currency, maximumFractionDigits: 0 }).format(context.parsed.y);
                                }
                                return label;
                            }
                        }
                    }
                }
            }
        });
    }

    /**
     * Обновляет все денежные поля на странице в соответствии с выбранной валютой
     * @param {boolean} isUsd - Включен ли режим USD
     */
    function updateCurrencyDisplay(isUsd) {
        // Обновление текстовых значений
        document.querySelectorAll('.money-value').forEach(el => {
            const uzsValue = parseFloat(el.dataset.uzsValue);
            if (isNaN(uzsValue)) return;

            const value = isUsd ? uzsValue / usdRate : uzsValue;
            const currency = isUsd ? 'USD' : 'UZS';
            const symbol = isUsd ? '$' : '';

            // Форматируем с символом или без, в зависимости от контекста
            if (el.nextElementSibling && el.nextElementSibling.classList.contains('currency-symbol')) {
                 el.textContent = value.toLocaleString('ru-RU', { maximumFractionDigits: 0 });
            } else {
                 el.textContent = `${symbol} ${value.toLocaleString('ru-RU', { maximumFractionDigits: 0 })}`;
            }
        });

        // Обновление символов рядом с суммами
        document.querySelectorAll('.currency-symbol').forEach(el => {
            el.textContent = isUsd ? '' : 'UZS';
        });

        // Обновление заголовков в таблице и на графиках
        const newLabel = isUsd ? 'USD' : 'UZS';
        document.querySelectorAll('.table-currency-label, .chart-currency-label').forEach(el => {
            el.textContent = newLabel;
        });
    }

    function handleCurrencyChange() {
        const isUsd = currencySwitcher.checked;
        updateCurrencyDisplay(isUsd);
        performanceChartVolume = createOrUpdateChart('performanceChartVolume', performanceChartVolume, 'plan_volume', 'fact_volume', isUsd);
        performanceChartIncome = createOrUpdateChart('performanceChartIncome', performanceChartIncome, 'plan_income', 'fact_income', isUsd);
    }

    if (currencySwitcher && usdRate > 1) {
        currencySwitcher.addEventListener('change', handleCurrencyChange);
    }

    // Первоначальная отрисовка
    handleCurrencyChange();
});