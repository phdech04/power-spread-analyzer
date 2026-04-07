import React, { useEffect, useState } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, BarChart, Bar, Cell,
} from 'recharts';
import { fetchVolatility } from '../utils/api';

const cardStyle = { background: '#1a1a2e', borderRadius: 8, padding: 20, marginBottom: 20 };
const metricGrid = { display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 20 };
const metricCard = { background: '#16213e', borderRadius: 8, padding: '12px 16px', textAlign: 'center' };
const thStyle = { textAlign: 'left', padding: '10px 12px', borderBottom: '1px solid #333', color: '#888' };
const tdStyle = { padding: '10px 12px', borderBottom: '1px solid #222' };

export default function VolatilityPanel({ isoA, isoB, days }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchVolatility(isoA, isoB, days)
      .then((d) => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, [isoA, isoB, days]);

  if (loading) return <div style={cardStyle}>Computing volatility surface...</div>;
  if (!data) return <div style={cardStyle}>Failed to load volatility data.</div>;

  const cone = data.vol_cone || {};
  const termStructure = data.term_structure || [];
  const rvTable = data.realized_vol_table || [];
  const chain = data.option_chain || [];

  return (
    <div>
      <div style={metricGrid}>
        <div style={metricCard}>
          <div style={{ color: '#888', fontSize: 12 }}>Current 20d Vol</div>
          <div style={{ fontSize: 20, fontWeight: 700, color: '#00d4ff' }}>
            {((cone.current || 0) * 100).toFixed(1)}%
          </div>
        </div>
        <div style={metricCard}>
          <div style={{ color: '#888', fontSize: 12 }}>Vol Percentile</div>
          <div style={{ fontSize: 20, fontWeight: 700, color: cone.percentile > 75 ? '#ff6b6b' : cone.percentile > 50 ? '#fcc419' : '#51cf66' }}>
            {(cone.percentile || 0).toFixed(0)}th
          </div>
        </div>
        <div style={metricCard}>
          <div style={{ color: '#888', fontSize: 12 }}>Current Spread</div>
          <div style={{ fontSize: 20, fontWeight: 700 }}>${(data.current_spread || 0).toFixed(2)}</div>
        </div>
      </div>

      <div style={cardStyle}>
        <h3 style={{ marginTop: 0 }}>Volatility Term Structure</h3>
        <ResponsiveContainer width="100%" height={250}>
          <LineChart data={termStructure}>
            <CartesianGrid strokeDasharray="3 3" stroke="#333" />
            <XAxis dataKey="days" stroke="#888" label={{ value: 'Days', position: 'insideBottom', offset: -5, fill: '#888' }} />
            <YAxis stroke="#888" tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
            <Tooltip contentStyle={{ background: '#1a1a2e', border: '1px solid #333' }} formatter={(v) => `${(v * 100).toFixed(1)}%`} />
            <Line type="monotone" dataKey="annualized_vol" stroke="#00d4ff" dot strokeWidth={2} name="Annualized Vol" />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div style={cardStyle}>
        <h3 style={{ marginTop: 0 }}>Volatility Cone</h3>
        <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap', justifyContent: 'center' }}>
          {['p5', 'p25', 'p50', 'p75', 'p95'].map((p) => (
            <div key={p} style={{ textAlign: 'center' }}>
              <div style={{ color: '#888', fontSize: 11 }}>{p.toUpperCase()}</div>
              <div style={{ fontSize: 16, fontWeight: 600 }}>{((cone[p] || 0) * 100).toFixed(1)}%</div>
            </div>
          ))}
        </div>
      </div>

      {chain.length > 0 && (
        <div style={cardStyle}>
          <h3 style={{ marginTop: 0 }}>Theoretical Option Chain (30-Day Expiry)</h3>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr>
                <th style={thStyle}>Strike</th>
                <th style={thStyle}>Call Price</th>
                <th style={thStyle}>Put Price</th>
                <th style={thStyle}>Delta</th>
                <th style={thStyle}>Moneyness</th>
              </tr>
            </thead>
            <tbody>
              {chain.map((c, i) => (
                <tr key={i} style={{ background: Math.abs(c.moneyness - 1) < 0.05 ? '#16213e' : 'transparent' }}>
                  <td style={tdStyle}>${c.strike?.toFixed(2)}</td>
                  <td style={tdStyle}>${c.call_price?.toFixed(4)}</td>
                  <td style={tdStyle}>${c.put_price?.toFixed(4)}</td>
                  <td style={tdStyle}>{c.delta?.toFixed(3)}</td>
                  <td style={tdStyle}>{c.moneyness?.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {rvTable.length > 0 && (
        <div style={cardStyle}>
          <h3 style={{ marginTop: 0 }}>Realized Volatility by Window</h3>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr>
                <th style={thStyle}>Window</th>
                <th style={thStyle}>Current</th>
                <th style={thStyle}>Average</th>
                <th style={thStyle}>Min</th>
                <th style={thStyle}>Max</th>
              </tr>
            </thead>
            <tbody>
              {rvTable.map((r, i) => (
                <tr key={i}>
                  <td style={tdStyle}>{r.window_label}</td>
                  <td style={tdStyle}>{r.current_vol != null ? `${(r.current_vol * 100).toFixed(1)}%` : 'N/A'}</td>
                  <td style={tdStyle}>{((r.avg_vol || 0) * 100).toFixed(1)}%</td>
                  <td style={tdStyle}>{((r.min_vol || 0) * 100).toFixed(1)}%</td>
                  <td style={tdStyle}>{((r.max_vol || 0) * 100).toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
