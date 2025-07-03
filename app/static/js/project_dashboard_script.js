document.addEventListener('DOMContentLoaded', function () {
    if (typeof charts_json_data === 'undefined') {
        console.error('Данные для графиков (charts_json_data) не найдены.');
        return;
    }

    const usdRate = parseFloat(document.body.dataset.usdRate) || 12650;
    const initializedCharts = {}; // Хранилище для созданных графиков

    // --- ОБЩАЯ ФУНКЦИЯ ФОРМАТИРОВАНИЯ ВАЛЮТ ---
    function formatCurrency(value, isUsd) {
        const prefix = isUsd ? '$' : '';
        const locale = isUsd ? 'en-US' : 'ru-RU';
        return prefix + new Intl.NumberFormat(locale, { maximumFractionDigits: 0 }).format(value);
    }

    // --- РЕЕСТР ФУНКЦИЙ ДЛЯ СОЗДАНИЯ ГРАФИКОВ ---
    const chartInitializers = {
        'planFactChart': (isUsd) => {
            const dynamics = charts_json_data.plan_fact_dynamics_yearly;
            if (!dynamics) return;
            const divisor = isUsd ? usdRate : 1;
            const ctx = document.getElementById('planFactChart');
            if (!ctx) return;
            initializedCharts['planFactChart'] = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: dynamics.labels,
                    datasets: [
                        { type: 'line', label: 'План контрактации', data: dynamics.plan_volume.map(v => v / divisor), borderColor: 'rgba(54, 162, 235, 1)', fill: false, tension: 0.1 },
                        { type: 'bar', label: 'Факт контрактации', data: dynamics.fact_volume.map(v => v / divisor), backgroundColor: 'rgba(75, 192, 192, 0.7)' },
                        { type: 'line', label: 'План поступлений', data: dynamics.plan_income.map(v => v / divisor), borderColor: 'rgba(255, 99, 132, 1)', fill: false, tension: 0.1 },
                        { type: 'bar', label: 'Факт поступлений', data: dynamics.fact_income.map(v => v / divisor), backgroundColor: 'rgba(255, 206, 86, 0.7)' }
                    ]
                },
                options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true, ticks: { callback: value => formatCurrency(value, isUsd) } } }, plugins: { tooltip: { callbacks: { label: context => `${context.dataset.label}: ${formatCurrency(context.parsed.y, isUsd)}` } } } }
            });
        },
        'remaindersChart': () => {
            const remaindersData = charts_json_data.remainders_chart_data;
            const ctx = document.getElementById('remaindersChart');
            if (!ctx) return;
            if (!remaindersData || !remaindersData.data || !remaindersData.data.length) {
                ctx.parentElement.innerHTML = '<div class="alert alert-secondary text-center">Нет данных для построения диаграммы остатков.</div>';
                return;
            }
            initializedCharts['remaindersChart'] = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: remaindersData.labels,
                    datasets: [{ label: 'Кол-во остатков, шт.', data: remaindersData.data, backgroundColor: ['rgba(255, 99, 132, 0.7)', 'rgba(54, 162, 235, 0.7)', 'rgba(255, 206, 86, 0.7)', 'rgba(75, 192, 192, 0.7)'], borderColor: 'var(--bs-tertiary-bg)', borderWidth: 3 }]
                },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
            });
        },
        'analysisCharts': () => { // Эта функция инициализирует все 3 графика спроса
            if (!charts_json_data.sales_analysis) return;
            const analysisChartsToRender = [
                { id: 'floorChart', data: charts_json_data.sales_analysis.by_floor, label: 'Продано квартир, шт.' },
                { id: 'roomsChart', data: charts_json_data.sales_analysis.by_rooms, label: 'Продано квартир, шт.' },
                { id: 'areaChart', data: charts_json_data.sales_analysis.by_area, label: 'Продано квартир, шт.' }
            ];
            analysisChartsToRender.forEach(chartInfo => {
                const ctx = document.getElementById(chartInfo.id);
                if (!ctx) return;
                if (!chartInfo.data || !chartInfo.data.data || !chartInfo.data.data.length) {
                    ctx.parentElement.innerHTML = '<div class="alert alert-secondary text-center">Нет данных для анализа.</div>'; return;
                }
                initializedCharts[chartInfo.id] = new Chart(ctx, {
                    type: 'bar',
                    data: { labels: chartInfo.data.labels, datasets: [{ label: chartInfo.label, data: chartInfo.data.data, backgroundColor: 'rgba(75, 192, 192, 0.7)' }] },
                    options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true } }, plugins: { legend: { display: false } } }
                });
            });
        },
        'priceDynamicsChart': (isUsd) => {
            const chartData = charts_json_data.price_dynamics;
            const ctx = document.getElementById('priceDynamicsChart');
            if (!ctx) return;
            if (!chartData || !chartData.data || !chartData.data.length) {
                ctx.parentElement.innerHTML = '<div class="alert alert-secondary text-center">Нет данных для анализа динамики цен.</div>'; return;
            }
            const divisor = isUsd ? usdRate : 1;
            initializedCharts['priceDynamicsChart'] = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: chartData.labels,
                    datasets: [{ label: 'Средняя цена за м²', data: chartData.data.map(p => p / divisor), borderColor: 'rgba(153, 102, 255, 1)', backgroundColor: 'rgba(153, 102, 255, 0.2)', fill: true, tension: 0.1 }]
                },
                options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: false, ticks: { callback: value => formatCurrency(value, isUsd) } } }, plugins: { legend: { display: false }, tooltip: { callbacks: { label: context => `${context.dataset.label}: ${formatCurrency(context.parsed.y, isUsd)}` } } } }
            });
        }
    };

    // --- ОСНОВНАЯ ЛОГИКА ---

    // 1. Слушатель переключения вкладок
    const tabs = document.querySelectorAll('button[data-bs-toggle="tab"]');
    tabs.forEach(tab => {
        tab.addEventListener('shown.bs.tab', function (event) {
            const targetPaneId = event.target.getAttribute('data-bs-target');
            const isUsd = document.getElementById('currencyToggle')?.checked;

            // Определяем, какой график нужно нарисовать
            if (targetPaneId === '#remainders-pane' && !initializedCharts['remaindersChart']) {
                chartInitializers.remaindersChart();
            }
            if (targetPaneId === '#analysis-pane' && !initializedCharts['floorChart']) {
                chartInitializers.analysisCharts();
            }
            if (targetPaneId === '#pricing-pane' && !initializedCharts['priceDynamicsChart']) {
                chartInitializers.priceDynamicsChart(isUsd);
            }
        });
    });

    // 2. Первичная инициализация графика на активной по-умолчанию вкладке
    const isInitiallyUsd = document.getElementById('currencyToggle')?.checked;
    if (!initializedCharts['planFactChart']) {
        chartInitializers.planFactChart(isInitiallyUsd);
    }

    // 3. Слушатель переключателя валют
    const currencyToggle = document.getElementById('currencyToggle');
    if (currencyToggle) {
        currencyToggle.addEventListener('change', () => {
            const isNowUsd = currencyToggle.checked;
            // Уничтожаем и перерисовываем только те графики, которые уже были созданы и зависят от валюты
            if (initializedCharts['planFactChart']) {
                initializedCharts['planFactChart'].destroy();
                chartInitializers.planFactChart(isNowUsd);
implements
            }
            if (initializedCharts['priceDynamicsChart']) {
                initializedCharts['priceDynamicsChart'].destroy();
                chartInitializers.priceDynamicsChart(isNowUsd);
            }
        });
    }
});