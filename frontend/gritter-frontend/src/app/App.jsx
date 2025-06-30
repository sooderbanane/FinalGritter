// App.jsx
import React from 'react';
import AnomalyChart from './AnomalyChart';

function App() {
  return (
    <div style={{ padding: '2rem', fontFamily: 'Arial, sans-serif' }}>
      <h1>Sensor Request Dashboard</h1>
      <p>This shows hourly request counts with anomalies flagged on top.</p>
      <AnomalyChart />
    </div>
  );
}

export default App;
