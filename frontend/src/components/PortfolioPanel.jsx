import React, { useEffect, useState } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ScatterChart, Scatter, Cell,
} from 'recharts';
import { fetchPortfolio } from '../utils/api';

const cardStyle = { background: '#1a1a2e', borderRadius: 8, padding: 20, marginBottom: 20 };
const metricGrid = { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 20 };
const metricCard = { background: '#16213e', borderRadius: 8, padding: '12px 16px', textAlign: 'center' };

export default function PortfolioPanel({ isoA, isoB, days }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchPortfolio(days)
      .then((d) => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, [days]);

  if (loading) return <div style={cardStyle}>Optimizing portfolio across 28 pairs...</div>;
  if (!data || data.error) return <div style={cardStyle}>Failed to optimize portfolio.</div>;

  const allocs = (data.allocations || []).filter((a) => Math.abs(a.weight) > 0.005);
  const pairStats = (data.pair_stats || []).slice(0, 15);

  return (
    <div>
      <div style={metricGrid}>
        <div style={metricCard}>
          <div style={{ color: '#888', fontSize: 12 }}>Portfolio Return</div>
          <div style={{ fontSize: 20, fontWeight: 700, color: data.portfolio_return >= 0 ? '#51cf66' : '#ff6b6b' }}>
            {((data.portfolio_return || 0) * 100).toFixed(1)}%
          </div>
        </div>
        <div style={metricCard}>
          <div style={{ color: '#888', fontSize: 12 }}>Portfolio Vol</div>
          <div style={{ fontSize: 20, fontWeight: 700 }}>
            {((data.portfolio_volatility || 0) * 100).toFixed(1)}%
          </div>
        </div>
        <div style={metricCard}>
          <div style={{ color: '#888', fontSize: 12 }}>Sharpe Ratio</div>
          <div style={{ fontSize: 20, fontWeight: 700, color: '#00d4ff' }}>
            {(data.portfolio_sharpe || 0).toFixed(3)}
          </div>
        </div>
        <div style={metricCard}>
          <div style={{ color: '#888', fontSize: 12 }}>Active Pairs</div>
          <div style={{ fontSize: 20, fontWeight: 700 }}>{data.n_active_pairs || 0}</div>
        </div>
      </div>

      <div style={cardStyle}>
        <h3 style={{ marginTop: 0 }}>Optimal Allocations</h3>
        <ResponsiveContainer width="100%" height={Math.max(300, allocs.length * 28)}>
          <BarChart data={allocs} layout="vertical" margin={{ left: 100 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#333" />
            <XAxis type="number" stroke="#888" tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
            <YAxis type="category" dataKey="pair" stroke="#888" tick={{ fontSize: 11 }} width={90} />
            <Tooltip
              contentStyle={{ background: '#1a1a2e', border: '1px solid #333' }}
              formatter={(v) => `${(v * 100).toFixed(1)}%`}
            />
            <Bar dataKey="weight" radius={[0, 4, 4, 0]}>
              {allocs.map((a, i) => (
                <Cell key={i} fill={a.weight > 0 ? '#51cf66' : '#ff6b6b'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div style={cardStyle}>
        <h3 style={{ marginTop: 0 }}>Top Pairs by Sharpe Ratio</h3>
        <ResponsiveContainer width="100%" height={350}>
          <ScatterChart>
            <CartesianGrid strokeDasharray="3 3" stroke="#333" />
            <XAxis dataKey="annual_volatility" stroke="#888" name="Volatility" tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
            <YAxis dataKey="annual_return" stroke="#888" name="Return" tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
            <Tooltip
              contentStyle={{ background: '#1a1a2e', border: '1px solid #333' }}
              formatter={(v) => `${(v * 100).toFixed(1)}%`}
            />
            <Scatter data={pairStats} fill="#00d4ff" />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
