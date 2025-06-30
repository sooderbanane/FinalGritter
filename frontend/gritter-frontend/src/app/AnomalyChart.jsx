
"use client";


import React, { useState, useEffect } from 'react';
import Papa from 'papaparse';
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, ScatterController, LineController, Tooltip, Legend } from 'chart.js';
import { Chart } from 'react-chartjs-2';



ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, ScatterController, LineController, Tooltip, Legend);

export default function AnomalyChart() { 
    const [hourlyData, setHourlyData] = useState([]);

    // Extracted callback to reduce nesting
    const handleParseComplete = (file) => (result) => {
        console.log(`Data for ${file}:`, result.data);
        setHourlyData(prev => [...prev, ...result.data]);
        // You can update state here if needed
    };

    useEffect(() => {
        const loadFiles = async () => {
            const res = await fetch('/api/sensors?cachebust=' + Date.now());
            const filenames = await res.json();

            filenames.forEach(async (file) => {
                const response = await fetch(`/sensor_data/${file}`);
                const text = await response.text();

                Papa.parse(text, { 
                    header: true, 
                    dynamicTyping: true,
                    complete: handleParseComplete(file)
                });
            });
        };
        loadFiles();
        const interval = setInterval(loadFiles, 5000);
        return () => clearInterval(interval);
    }, []);




    const labels = hourlyData.map(row => row.min);
    const count = hourlyData.map(row => row.request_count);

    const anomalies = hourlyData.filter(row => row.is_anomaly).map(row => ({x: row.min, y: row.request_count}));

    const chartData = {
        labels, 
        datasets: [
            {
                type: 'line',
                label: 'Request Count',
                data: count,
                borderColor: 'blue',
                tension: 0.3,
                fill: false,
            },
            {
                type: 'scatter',
                label: 'Anomalies',
                data: anomalies,
                pointBackgroundColor: 'red',
                pointBorderColor: 'red',
                pointStyle: 'cross',
                pointRadius: 8,
            }
        ]
    }

    const options = {
        responsive: true,
        plugins: {
            tooltip: {
                callbacks: {
                    label: function(context) {
                        if (context.dataset.type === 'scatter') { 
                            return `❌ Anomaly: ${context.parsed.y}`
                        }
                        return `Requests: ${context.parsed.y}`;
                    }
                }
            }
        },
        scales: {
            x: {title: {display: true, text: 'Minute'}},
            y: {title: {display: true, text: 'Request Count '}},

        },
    }
    return (
        <div>
            <h2>Requests with Anomalies</h2>
            <Chart type='scatter' data={chartData} options={options} />
        </div>
    );
}
