import React, { useState, useEffect } from 'react';
import Papa from 'papaparse';
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, ScatterController, LineController, Tooltip, Legend } from 'chart.js';
import { Chart } from 'react-chartjs-2';



ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, ScatterController, LineController, Tooltip, Legend);

export default function AnomalyChart() { 
    const [hourlyData, setHourlyData] = useState([]);

    useEffect(() => {
        const fetchData = async () => {
            const response = await fetch ('/hourly.csv?cachebust=' + Date.now());
            const text = await response.text();

            Papa.parse(text, { 
                header: true, 
                dynamicTyping: true, 
                complete: (result) => {
                    console.log(resourceLimits.data);
                    setHourlyData(result.data);
                }
            });
        };
        fetchData();
        
    })
}