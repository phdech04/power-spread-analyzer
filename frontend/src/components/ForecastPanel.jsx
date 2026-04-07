import React, { useState } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, ReferenceLine,
} from 'recharts';
import { fetchForecast } from '../utils/api';

const cardStyle = { background: '#1a1a2e', borderRadius: 8, padding: 20, marginBottom: 20 };
const metricGrid = { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 20 };
const metricCard = { background: '#16213e', borderRadius: 8, padding: '12px 16px', textAlign: 'center' };
const btnStyle = {
  background: '#00d4ff', color: '#000', border: 'none', padding: '10px 24px',
  borderRadius: 6, cursor: 'pointer', fontWeight: 600, fontSize: 14,
};
const selectStyle = {
  background: '#16213e', color: '#e0e0e0', border: '1px solid #333',
  padding: '8px 12px', borderRadius: 4,
};

export default function ForecastPanel({ isoA, isoB, days }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [model, setModel] = useState('lstm');
  const [horizon, setHorizon] = useState(1);

  const handleRun = () => {
    setLoading(true);
    fetchForecast(isoA, isoB, days, model, horizon)
      .then((d) => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  };

  const m = data?.metrics || {};
  const forecasts = (data?.forecasts || []).map((f) => ({
    ...f,
    date: f.date?.slice(0, 10),
  }));

  return (
    <div>
      <div style={cardStyle}>
        <h3 style={{ marginTop: 0 }}>ML Spread Forecasting</h3>
        <div style={{ display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap' }}>
          <label style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            Model:
            <select style={selectStyle} value={model} onChange={(e) => setModel(e.target.value)}>
              <option value="lstm">LSTM</option>
              <option value="transformer">Transformer</option>
              <option value="gbm">Gradient Boosting</option>
            </select>
          </label>
          <label style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            Horizon:
            <select style={selectStyle} value={horizon} onChange={(e) => setHorizon(Number(e.target.value))}>
              <option value={1}>1-Day</option>
              <option value={5}>5-Day</option>
              <option value={10}>10-Day</option>
            </select>
          </label>
          <button style={btnStyle} onClick={handleRun} disabled={loading}>
            {loading ? 'Training...' : 'Run Forecast'}
          </button>
        </div>
        <div style={{ color: '#888', fontSize: 12, marginTop: 8 }}>
          Model: {data?.model_type || 'N/A'} | Uses walk-forward validation (no lookahead bias)
        </div>
      </div>

      {data && !data.error && (
        <>
          <div style={metricGrid}>
            <div style={metricCard}>
              <div style={{ color: '#888', fontSize: 12 }}>Direction Accuracy</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: m.direction_accuracy > 0.55 ? '#51cf66' : '#ff6b6b' }}>
                {((m.direction_accuracy || 0) * 100).toFixed(1)}%
              </div>
            </div>
            <div style={metricCard}>
              <div style={{ color: '#888', fontSize: 12 }}>RMSE</div>
              <div style={{ fontSize: 20, fontWeight: 700 }}>{(m.rmse || 0).toFixed(3)}</div>
            </div>
            <div style={metricCard}>
              <div style={{ color: '#888', fontSize: 12 }}>MAE</div>
              <div style={{ fontSize: 20, fontWeight: 700 }}>{(m.mae || 0).toFixed(3)}</div>
            </div>
            <div style={metricCard}>
              <div style={{ color: '#888', fontSize: 12 }}>Test Samples</div>
              <div style={{ fontSize: 20, fontWeight: 700 }}>{m.n_test || 0}</div>
            </div>
          </div>

          <div style={cardStyle}>
            <h3 style={{ marginTop: 0 }}>Actual vs Predicted Spread</h3>
            <ResponsiveContainer width="100%" height={350}>
              <LineChart data={forecasts}>
                <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                <XAxis dataKey="date" stroke="#888" tick={{ fontSize: 11 }} />
                <YAxis stroke="#888" />
                <Tooltip contentStyle={{ background: '#1a1a2e', border: '1px solid #333' }} />
                <Legend />
                <Line type="monotone" dataKey="actual_spread" stroke="#00d4ff" dot={false} strokeWidth={2} name="Actual" />
                <Line type="monotone" dataKey="forecast_spread" stroke="#845ef7" dot={false} strokeWidth={2} strokeDasharray="5 5" name="Forecast" />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div style={cardStyle}>
            <h3 style={{ marginTop: 0 }}>Predicted vs Actual Changes</h3>
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={forecasts}>
                <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                <XAxis dataKey="date" stroke="#888" tick={{ fontSize: 11 }} />
                <YAxis stroke="#888" />
                <Tooltip contentStyle={{ background: '#1a1a2e', border: '1px solid #333' }} />
                <Legend />
                <ReferenceLine y={0} stroke="#555" />
                <Line type="monotone" dataKey="actual_change" stroke="#51cf66" dot={false} name="Actual Change" />
                <Line type="monotone" dataKey="predicted_change" stroke="#ff6b6b" dot={false} strokeDasharray="3 3" name="Predicted Change" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </>
      )}

      {data?.error && (
        <div style={cardStyle}><p style={{ color: '#ff6b6b' }}>{data.error}</p></div>
      )}
    </div>
  );
}
