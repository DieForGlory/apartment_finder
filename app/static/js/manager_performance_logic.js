document.addEventListener('DOMContentLoaded', function() {
    if (typeof pageData === 'undefined' || !pageData) {
        console.error('Данные для инициализации скрипта не найдены.');
        return;
    }

    const usdRate = pageData.usdRate || 1;
    const performanceData = pageData.performance;
    const monthNames = pageData.monthNames;
    const currencySwitcher = document.getElementById('currency-switcher');

    let performanceChartVolume, performanceChartIncome;

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
            options: { /* ... опции графика ... */ }
        });
    }

    function updateCurrencyDisplay(isUsd) {
        // Эта функция теперь также обрабатывает поле kpi-result
        document.querySelectorAll('.money-value, .kpi-result').forEach(el => {
            const uzsValue = parseFloat(el.dataset.uzsValue);
            if (isNaN(uzsValue)) return;

            const value = isUsd ? uzsValue / usdRate : uzsValue;
            const symbol = isUsd ? '$ ' : '';

            // Отдельная логика для KPI, чтобы всегда был символ валюты UZS
            if (el.classList.contains('kpi-result')) {
                 el.textContent = `${symbol}${value.toLocaleString('ru-RU', { maximumFractionDigits: 0 })} ${isUsd ? '' : 'UZS'}`;
                 return;
            }

            if (el.nextElementSibling && el.nextElementSibling.classList.contains('currency-symbol')) {
                 el.textContent = value.toLocaleString('ru-RU', { maximumFractionDigits: 0 });
            } else {
                 el.textContent = `${symbol}${value.toLocaleString('ru-RU', { maximumFractionDigits: 0 })}`;
            }
        });

        document.querySelectorAll('.currency-symbol, .table-currency-label, .chart-currency-label').forEach(el => {
            el.textContent = isUsd ? 'USD' : 'UZS';
        });
    }

    function handleCurrencyChange() {
        const isUsd = currencySwitcher.checked;
        updateCurrencyDisplay(isUsd);
        performanceChartVolume = createOrUpdateChart('performanceChartVolume', performanceChartVolume, 'fact_volume', 'fact_volume', isUsd);
        performanceChartIncome = createOrUpdateChart('performanceChartIncome', performanceChartIncome, 'plan_income', 'fact_income', isUsd);
    }

    if (currencySwitcher && usdRate > 1) {
        currencySwitcher.addEventListener('change', handleCurrencyChange);
    }

    // Первоначальная отрисовка всех значений
    handleCurrencyChange();
});