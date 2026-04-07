import React, { useState } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, Area, AreaChart,
} from 'recharts';
import { fetchMonteCarlo } from '../utils/api';

const cardStyle = { background: '#1a1a2e', borderRadius: 8, padding: 20, marginBottom: 20 };
const metricGrid = { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 20 };
const metricCard = { background: '#16213e', borderRadius: 8, padding: '12px 16px', textAlign: 'center' };
const btnStyle = {
  background: '#00d4ff', color: '#000', border: 'none', padding: '10px 24px',
  borderRadius: 6, cursor: 'pointer', fontWeight: 600, fontSize: 14,
};

export default function MonteCarloPanel({ isoA, isoB, days }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleRun = () => {
    setLoading(true);
    fetchMonteCarlo(isoA, isoB, days, 5000)
      .then((d) => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  };

  const stats = data?.statistics || {};

  // Build percentile path chart data
  const paths = data?.percentile_paths || {};
  const chartData = [];
  const p50 = paths.p50 || [];
  for (let i = 0; i < p50.length; i += 5) { // sample every 5th point
    chartData.push({
      day: i,
      p5: paths.p5?.[i],
      p25: paths.p25?.[i],
      p50: paths.p50?.[i],
      p75: paths.p75?.[i],
      p95: paths.p95?.[i],
    });
  }

  return (
    <div>
      <div style={cardStyle}>
        <h3 style={{ marginTop: 0 }}>Monte Carlo Simulation</h3>
        <p style={{ color: '#888', fontSize: 13, marginBottom: 12 }}>
          Block-bootstrap {data?.n_simulations?.toLocaleString() || '5,000'} equity paths
          over {data?.horizon_days || 252} trading days using historical return distribution.
        </p>
        <button style={btnStyle} onClick={handleRun} disabled={loading}>
          {loading ? 'Simulating...' : 'Run Monte Carlo (5,000 paths)'}
        </button>
      </div>

      {data && !data.error && (
        <>
          <div style={metricGrid}>
            <div style={metricCard}>
              <div style={{ color: '#888', fontSize: 12 }}>Mean Terminal Value</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: stats.mean_terminal > (data.initial_equity || 100000) ? '#51cf66' : '#ff6b6b' }}>
                ${(stats.mean_terminal || 0).toLocaleString()}
              </div>
            </div>
            <div style={metricCard}>
              <div style={{ color: '#888', fontSize: 12 }}>Prob of Loss</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: '#ff6b6b' }}>
                {(stats.prob_loss || 0).toFixed(1)}%
              </div>
            </div>
            <div style={metricCard}>
              <div style={{ color: '#888', fontSize: 12 }}>Avg Max Drawdown</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: '#ff6b6b' }}>
                {(stats.avg_max_drawdown || 0).toFixed(1)}%
              </div>
            </div>
            <div style={metricCard}>
              <div style={{ color: '#888', fontSize: 12 }}>P(20%+ DD)</div>
              <div style={{ fontSize: 20, fontWeight: 700 }}>
                {(stats.prob_20pct_drawdown || 0).toFixed(1)}%
              </div>
            </div>
          </div>

          <div style={{ ...metricGrid, gridTemplateColumns: 'repeat(5, 1fr)' }}>
            {[
              { label: 'P5 Terminal', value: stats.p5_terminal, color: '#ff6b6b' },
              { label: 'P25 Terminal', value: stats.p25_terminal, color: '#ffa8a8' },
              { label: 'Median', value: stats.median_terminal, color: '#e0e0e0' },
              { label: 'P75 Terminal', value: stats.p75_terminal, color: '#8ce99a' },
              { label: 'P95 Terminal', value: stats.p95_terminal, color: '#51cf66' },
            ].map(({ label, value, color }) => (
              <div key={label} style={metricCard}>
                <div style={{ color: '#888', fontSize: 12 }}>{label}</div>
                <div style={{ fontSize: 16, fontWeight: 700, color }}>
                  ${(value || 0).toLocaleString()}
                </div>
              </div>
            ))}
          </div>

          <div style={cardStyle}>
            <h3 style={{ marginTop: 0 }}>Equity Path Percentile Bands</h3>
            <ResponsiveContainer width="100%" height={400}>
              <AreaChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                <XAxis dataKey="day" stroke="#888" label={{ value: 'Trading Days', position: 'insideBottom', offset: -5, fill: '#888' }} />
                <YAxis stroke="#888" tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
                <Tooltip contentStyle={{ background: '#1a1a2e', border: '1px solid #333' }} formatter={(v) => `$${v?.toLocaleString()}`} />
                <Legend />
                <Area type="monotone" dataKey="p95" stroke="#51cf66" fill="#51cf66" fillOpacity={0.1} name="P95" />
                <Area type="monotone" dataKey="p75" stroke="#8ce99a" fill="#8ce99a" fillOpacity={0.15} name="P75" />
                <Area type="monotone" dataKey="p50" stroke="#00d4ff" fill="#00d4ff" fillOpacity={0.2} name="Median" strokeWidth={2} />
                <Area type="monotone" dataKey="p25" stroke="#ffa8a8" fill="#ffa8a8" fillOpacity={0.15} name="P25" />
                <Area type="monotone" dataKey="p5" stroke="#ff6b6b" fill="#ff6b6b" fillOpacity={0.1} name="P5" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </div>
  );
}
