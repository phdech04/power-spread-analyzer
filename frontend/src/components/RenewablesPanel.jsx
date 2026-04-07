import React, { useEffect, useState } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, AreaChart, Area, LineChart, Line,
} from 'recharts';
import { fetchRenewables } from '../utils/api';

const cardStyle = { background: '#1a1a2e', borderRadius: 8, padding: 20, marginBottom: 20 };
const metricGrid = { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 20 };
const metricCard = { background: '#16213e', borderRadius: 8, padding: '12px 16px', textAlign: 'center' };

export default function RenewablesPanel({ isoA, days }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchRenewables(isoA, Math.min(days, 90))
      .then((d) => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, [isoA, days]);

  if (loading) return <div style={cardStyle}>Computing renewable generation forecasts...</div>;
  if (!data) return <div style={cardStyle}>Failed to load renewable data.</div>;

  const s = data.summary || {};
  const duck = data.duck_curve || [];
  const hourly = data.hourly_avg || [];

  return (
    <div>
      <div style={metricGrid}>
        <div style={metricCard}>
          <div style={{ color: '#888', fontSize: 12 }}>Wind Capacity</div>
          <div style={{ fontSize: 20, fontWeight: 700, color: '#00d4ff' }}>{s.wind_capacity_gw || 0} GW</div>
        </div>
        <div style={metricCard}>
          <div style={{ color: '#888', fontSize: 12 }}>Solar Capacity</div>
          <div style={{ fontSize: 20, fontWeight: 700, color: '#fcc419' }}>{s.solar_capacity_gw || 0} GW</div>
        </div>
        <div style={metricCard}>
          <div style={{ color: '#888', fontSize: 12 }}>Avg Wind CF</div>
          <div style={{ fontSize: 20, fontWeight: 700 }}>{((s.avg_wind_cf || 0) * 100).toFixed(0)}%</div>
        </div>
        <div style={metricCard}>
          <div style={{ color: '#888', fontSize: 12 }}>Peak Renewable %</div>
          <div style={{ fontSize: 20, fontWeight: 700, color: '#51cf66' }}>{(s.peak_renewable_pct || 0).toFixed(0)}%</div>
        </div>
      </div>

      <div style={cardStyle}>
        <h3 style={{ marginTop: 0 }}>Average Hourly Generation Profile</h3>
        <ResponsiveContainer width="100%" height={300}>
          <AreaChart data={hourly}>
            <CartesianGrid strokeDasharray="3 3" stroke="#333" />
            <XAxis dataKey="hour" stroke="#888" label={{ value: 'Hour of Day', position: 'insideBottom', offset: -5, fill: '#888' }} />
            <YAxis stroke="#888" label={{ value: 'GW', angle: -90, position: 'insideLeft', fill: '#888' }} />
            <Tooltip contentStyle={{ background: '#1a1a2e', border: '1px solid #333' }} />
            <Legend />
            <Area type="monotone" dataKey="solar_generation_gw" stackId="1" fill="#fcc419" stroke="#fcc419" fillOpacity={0.7} name="Solar" />
            <Area type="monotone" dataKey="wind_generation_gw" stackId="1" fill="#00d4ff" stroke="#00d4ff" fillOpacity={0.7} name="Wind" />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {duck.length > 0 && (
        <div style={cardStyle}>
          <h3 style={{ marginTop: 0 }}>Duck Curve Analysis — Net Load Shape</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={duck}>
              <CartesianGrid strokeDasharray="3 3" stroke="#333" />
              <XAxis dataKey="hour" stroke="#888" />
              <YAxis stroke="#888" label={{ value: 'GW', angle: -90, position: 'insideLeft', fill: '#888' }} />
              <Tooltip contentStyle={{ background: '#1a1a2e', border: '1px solid #333' }} />
              <Legend />
              <Line type="monotone" dataKey="estimated_load_gw" stroke="#888" dot={false} strokeWidth={2} strokeDasharray="5 5" name="Gross Load" />
              <Line type="monotone" dataKey="net_load_gw" stroke="#ff6b6b" dot={false} strokeWidth={2} name="Net Load" />
              <Line type="monotone" dataKey="total_renewable_gw" stroke="#51cf66" dot={false} strokeWidth={2} name="Renewable Gen" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
