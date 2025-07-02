document.addEventListener('DOMContentLoaded', function () {
    if (typeof charts_json_data === 'undefined') {
        console.error('Chart data not found.');
        return;
    }

    const chartData = charts_json_data;
    let planFactChart = null; // Variable to hold the chart instance

    const usdRate = parseFloat(document.body.dataset.usdRate) || 12650;

    // Function to initialize or update the plan/fact chart
    function renderPlanFactChart(isUsd = false) {
        const dynamics = chartData.plan_fact_dynamics_yearly;
        if (!dynamics) return;

        const divisor = isUsd ? usdRate : 1;
        const currencyPrefix = isUsd ? '$' : '';
        const currencySuffix = isUsd ? '' : ' UZS';

        const chartConfig = {
            type: 'bar',
            data: {
                labels: dynamics.labels,
                datasets: [
                    {
                        type: 'line',
                        label: 'План контрактации',
                        data: dynamics.plan_volume.map(v => v / divisor),
                        borderColor: 'rgba(54, 162, 235, 1)',
                        backgroundColor: 'rgba(54, 162, 235, 0.2)',
                        fill: false,
                        tension: 0.1
                    },
                    {
                        type: 'bar',
                        label: 'Факт контрактации',
                        data: dynamics.fact_volume.map(v => v / divisor),
                        backgroundColor: 'rgba(75, 192, 192, 0.7)',
                    },
                    {
                        type: 'line',
                        label: 'План поступлений',
                        data: dynamics.plan_income.map(v => v / divisor),
                        borderColor: 'rgba(255, 99, 132, 1)',
                        backgroundColor: 'rgba(255, 99, 132, 0.2)',
                        fill: false,
                        tension: 0.1
                    },
                    {
                        type: 'bar',
                        label: 'Факт поступлений',
                        data: dynamics.fact_income.map(v => v / divisor),
                        backgroundColor: 'rgba(255, 206, 86, 0.7)',
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return currencyPrefix + new Intl.NumberFormat('ru-RU').format(value.toFixed(0));
                            }
                        }
                    }
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                let label = context.dataset.label || '';
                                if (label) {
                                    label += ': ';
                                }
                                if (context.parsed.y !== null) {
                                    label += currencyPrefix + new Intl.NumberFormat('ru-RU').format(context.parsed.y);
                                }
                                return label;
                            }
                        }
                    }
                }
            }
        };

        const planFactCtx = document.getElementById('planFactChart');
        if (!planFactCtx) return;

        if (planFactChart) {
            // Update existing chart
            planFactChart.data = chartConfig.data;
            planFactChart.options.scales.y.ticks.callback = chartConfig.options.scales.y.ticks.callback;
            planFactChart.options.plugins.tooltip.callbacks.label = chartConfig.options.plugins.tooltip.callbacks.label;
            planFactChart.update();
        } else {
            // Create new chart
            planFactChart = new Chart(planFactCtx, chartConfig);
        }
    }

    // Initial chart render
      function renderRemaindersChart() {
        const remaindersData = chartData.remainders_chart_data;
        if (!remaindersData || !remaindersData.data.length) {
            // Можно показать сообщение, если данных нет
            const container = document.getElementById('remaindersChart')?.parentElement;
            if(container) container.innerHTML = '<div class="alert alert-secondary text-center">Нет данных для построения диаграммы остатков.</div>';
            return;
        }

        const ctx = document.getElementById('remaindersChart');
        if(!ctx) return;

        new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: remaindersData.labels,
                datasets: [{
                    label: 'Кол-во остатков, шт.',
                    data: remaindersData.data,
                    backgroundColor: [
                        'rgba(255, 99, 132, 0.7)',
                        'rgba(54, 162, 235, 0.7)',
                        'rgba(255, 206, 86, 0.7)',
                        'rgba(75, 192, 192, 0.7)',
                        'rgba(153, 102, 255, 0.7)',
                    ],
                    borderColor: 'var(--bs-tertiary-bg)',
                    borderWidth: 3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                    },
                    title: {
                        display: false
                    }
                }
            }
        });
    }
    function renderAnalysisChart(canvasId, chartData, chartLabel) {
        if (!chartData || !chartData.data || !chartData.data.length) {
            const container = document.getElementById(canvasId)?.parentElement;
            if (container) container.innerHTML = '<div class="alert alert-secondary text-center">Нет данных для анализа.</div>';
            return;
        }
        const ctx = document.getElementById(canvasId);
        if (!ctx) return;

        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: chartData.labels,
                datasets: [{
                    label: chartLabel,
                    data: chartData.data,
                    backgroundColor: 'rgba(75, 192, 192, 0.7)',
                    borderColor: 'rgba(75, 192, 192, 1)',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { beginAtZero: true }
                },
                plugins: {
                    legend: { display: false }
                }
            }
        });
    }

    // Инициализация графиков
    renderPlanFactChart(document.getElementById('currencyToggle')?.checked);
    renderRemaindersChart(); // <--- Вызываем новую функцию
    if(charts_json_data.sales_analysis) {
        renderAnalysisChart('floorChart', charts_json_data.sales_analysis.by_floor, 'Продано квартир, шт.');
        renderAnalysisChart('roomsChart', charts_json_data.sales_analysis.by_rooms, 'Продано квартир, шт.');
        renderAnalysisChart('areaChart', charts_json_data.sales_analysis.by_area, 'Продано квартир, шт.');
    }

    // Слушатель на переключатель валют (остается без изменений)
    const currencyToggle = document.getElementById('currencyToggle');
    if (currencyToggle) {
        currencyToggle.addEventListener('change', function() {
            renderPlanFactChart(this.checked);
        });
    }
});
