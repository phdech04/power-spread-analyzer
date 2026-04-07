import React, { useEffect, useState } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, AreaChart, Area,
} from 'recharts';
import { fetchCongestion } from '../utils/api';

const cardStyle = { background: '#1a1a2e', borderRadius: 8, padding: 20, marginBottom: 20 };
const metricGrid = { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 20 };
const metricCard = { background: '#16213e', borderRadius: 8, padding: '12px 16px', textAlign: 'center' };

export default function CongestionPanel({ isoA, isoB, days }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchCongestion(isoA, isoB, days)
      .then((d) => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, [isoA, isoB, days]);

  if (loading) return <div style={cardStyle}>Analyzing congestion components...</div>;
  if (!data) return <div style={cardStyle}>Failed to load congestion data.</div>;

  const ftr = data.ftr_valuation || {};
  const cong = (data.congestion_spread || []).map((d) => ({ ...d, date: d.date?.slice(0, 10) }));

  return (
    <div>
      <div style={metricGrid}>
        <div style={metricCard}>
          <div style={{ color: '#888', fontSize: 12 }}>Avg Daily Cong. Spread</div>
          <div style={{ fontSize: 20, fontWeight: 700, color: '#00d4ff' }}>
            ${(ftr.avg_daily_congestion_spread || 0).toFixed(2)}
          </div>
        </div>
        <div style={metricCard}>
          <div style={{ color: '#888', fontSize: 12 }}>Annual FTR Value</div>
          <div style={{ fontSize: 20, fontWeight: 700, color: '#51cf66' }}>
            ${(ftr.annual_ftr_value_est || 0).toLocaleString()}
          </div>
        </div>
        <div style={metricCard}>
          <div style={{ color: '#888', fontSize: 12 }}>Monthly FTR Value</div>
          <div style={{ fontSize: 20, fontWeight: 700 }}>
            ${(ftr.avg_monthly_ftr_value || 0).toLocaleString()}
          </div>
        </div>
        <div style={metricCard}>
          <div style={{ color: '#888', fontSize: 12 }}>Positive Days</div>
          <div style={{ fontSize: 20, fontWeight: 700 }}>{(ftr.positive_days_pct || 0).toFixed(0)}%</div>
        </div>
      </div>

      <div style={cardStyle}>
        <h3 style={{ marginTop: 0 }}>Spread Decomposition: Energy vs Congestion</h3>
        <ResponsiveContainer width="100%" height={350}>
          <AreaChart data={cong}>
            <CartesianGrid strokeDasharray="3 3" stroke="#333" />
            <XAxis dataKey="date" stroke="#888" tick={{ fontSize: 11 }} />
            <YAxis stroke="#888" />
            <Tooltip contentStyle={{ background: '#1a1a2e', border: '1px solid #333' }} />
            <Legend />
            <Area type="monotone" dataKey="energy_spread" stackId="1" fill="#00d4ff" stroke="#00d4ff" fillOpacity={0.5} name="Energy Spread" />
            <Area type="monotone" dataKey="congestion_spread" stackId="1" fill="#845ef7" stroke="#845ef7" fillOpacity={0.5} name="Congestion Spread" />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div style={cardStyle}>
        <h3 style={{ marginTop: 0 }}>Congestion Contribution to Total Spread (%)</h3>
        <ResponsiveContainer width="100%" height={250}>
          <LineChart data={cong}>
            <CartesianGrid strokeDasharray="3 3" stroke="#333" />
            <XAxis dataKey="date" stroke="#888" tick={{ fontSize: 11 }} />
            <YAxis stroke="#888" unit="%" />
            <Tooltip contentStyle={{ background: '#1a1a2e', border: '1px solid #333' }} />
            <Line type="monotone" dataKey="congestion_pct" stroke="#ff6b6b" dot={false} strokeWidth={2} name="Congestion %" />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
