import React, { useEffect, useState } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, ReferenceLine,
} from 'recharts';
import { fetchGas } from '../utils/api';

const cardStyle = { background: '#1a1a2e', borderRadius: 8, padding: 20, marginBottom: 20 };
const metricGrid = { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 20 };
const metricCard = { background: '#16213e', borderRadius: 8, padding: '12px 16px', textAlign: 'center' };

export default function GasPanel({ isoA, days }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchGas(isoA, days)
      .then((d) => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, [isoA, days]);

  if (loading) return <div style={cardStyle}>Loading gas / spark spread data...</div>;
  if (!data) return <div style={cardStyle}>Failed to load gas data.</div>;

  const s = data.summary || {};
  const spark = (data.spark_spread || []).map((d) => ({ ...d, date: d.date?.slice(0, 10) }));

  return (
    <div>
      <div style={{ ...cardStyle, padding: '12px 20px', fontSize: 13, color: '#888' }}>
        Gas Hub: <span style={{ color: '#00d4ff' }}>{data.gas_hub}</span> | Heat Rate: <span style={{ color: '#00d4ff' }}>{data.heat_rate} MMBtu/MWh</span>
      </div>

      <div style={metricGrid}>
        <div style={metricCard}>
          <div style={{ color: '#888', fontSize: 12 }}>Avg Spark Spread</div>
          <div style={{ fontSize: 20, fontWeight: 700, color: s.mean >= 0 ? '#51cf66' : '#ff6b6b' }}>
            ${(s.mean || 0).toFixed(2)}
          </div>
        </div>
        <div style={metricCard}>
          <div style={{ color: '#888', fontSize: 12 }}>Spark Spread Vol</div>
          <div style={{ fontSize: 20, fontWeight: 700 }}>${(s.std || 0).toFixed(2)}</div>
        </div>
        <div style={metricCard}>
          <div style={{ color: '#888', fontSize: 12 }}>Positive Days</div>
          <div style={{ fontSize: 20, fontWeight: 700, color: '#51cf66' }}>{(s.pct_positive || 0).toFixed(0)}%</div>
        </div>
        <div style={metricCard}>
          <div style={{ color: '#888', fontSize: 12 }}>Avg When Positive</div>
          <div style={{ fontSize: 20, fontWeight: 700 }}>${(s.avg_when_positive || 0).toFixed(2)}</div>
        </div>
      </div>

      <div style={cardStyle}>
        <h3 style={{ marginTop: 0 }}>Spark Spread (Power - Fuel Cost)</h3>
        <ResponsiveContainer width="100%" height={350}>
          <LineChart data={spark}>
            <CartesianGrid strokeDasharray="3 3" stroke="#333" />
            <XAxis dataKey="date" stroke="#888" tick={{ fontSize: 11 }} />
            <YAxis stroke="#888" />
            <Tooltip contentStyle={{ background: '#1a1a2e', border: '1px solid #333' }} />
            <Legend />
            <ReferenceLine y={0} stroke="#555" strokeDasharray="3 3" />
            <Line type="monotone" dataKey="spark_spread" stroke="#51cf66" dot={false} strokeWidth={2} name="Spark Spread" />
            <Line type="monotone" dataKey="power_price" stroke="#00d4ff" dot={false} strokeWidth={1} name="Power Price" />
            <Line type="monotone" dataKey="fuel_cost" stroke="#ff6b6b" dot={false} strokeWidth={1} name="Fuel Cost" />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div style={cardStyle}>
        <h3 style={{ marginTop: 0 }}>Natural Gas Price ($/MMBtu)</h3>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={spark}>
            <CartesianGrid strokeDasharray="3 3" stroke="#333" />
            <XAxis dataKey="date" stroke="#888" tick={{ fontSize: 11 }} />
            <YAxis stroke="#888" />
            <Tooltip contentStyle={{ background: '#1a1a2e', border: '1px solid #333' }} />
            <Line type="monotone" dataKey="gas_price" stroke="#fcc419" dot={false} strokeWidth={2} name="Gas Price" />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
