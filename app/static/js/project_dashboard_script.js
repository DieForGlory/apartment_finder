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
    renderPlanFactChart(document.getElementById('currencyToggle')?.checked);

    // Add listener to the currency toggle
    const currencyToggle = document.getElementById('currencyToggle');
    if (currencyToggle) {
        currencyToggle.addEventListener('change', function() {
            renderPlanFactChart(this.checked);
        });
    }
});
