"use client";

import React, { useState, useEffect } from 'react';
import Papa from 'papaparse';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  ScatterController,
  LineController,
  Tooltip,
  Legend
} from 'chart.js';
import { Chart } from 'react-chartjs-2';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  ScatterController,
  LineController,
  Tooltip,
  Legend
);

// React component to display anomaly chart
export default function AnomalyChart() {
  const [dataRows, setDataRows] = useState([]);

  useEffect(() => {
    // function to load CSV and update state
    const loadData = async () => {
      try {
        const response = await fetch('/minute_counts.csv');
        const text = await response.text();
        Papa.parse(text, {
          header: true,
          dynamicTyping: true,
          complete: (result) => {
            // result.data is array of {min, request_count, is_anomaly}
            setDataRows(result.data.filter(r => r.min));
          }
        });
      } catch (err) {
        console.error('Error loading CSV:', err);
      }
    };

    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, []);

  // prepare chart data
  const labels = dataRows.map(row => row.min);
  const counts = dataRows.map(row => row.request_count);
  const anomalies = dataRows
    .filter(row => row.is_anomaly)
    .map(row => ({ x: row.min, y: row.request_count }));

  const chartData = {
    labels,
    datasets: [
      {
        type: 'line',
        label: 'Requests per Minute',
        data: counts,
        borderColor: 'blue',
        tension: 0.4,
        fill: false,
      },
      {
        type: 'scatter',
        label: 'Anomaly',
        data: anomalies,
        backgroundColor: 'red',
        borderColor: 'red',
        pointStyle: 'cross',
        pointRadius: 6,
      }
    ]
  };

  const options = {
    responsive: true,
    plugins: {
      tooltip: {
        callbacks: {
          label: (context) => {
            if (context.dataset.type === 'scatter') {
              return `⚠️ Anomaly: ${context.parsed.y}`;
            }
            return `Requests: ${context.parsed.y}`;
          }
        }
      }
    },
    scales: {
      x: {
        title: { display: true, text: 'Minute' }
      },
      y: {
        title: { display: true, text: 'Request Count' }
      }
    }
  };

  return (
    <div className="p-4">
      <h2 className="text-xl font-semibold mb-4">Request Count with Anomalies</h2>
      <Chart type="scatter" data={chartData} options={options} />
    </div>
  );
}
