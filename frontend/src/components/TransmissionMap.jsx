import React, { useEffect, useState } from 'react';
import { fetchTransmission } from '../utils/api';

const cardStyle = { background: '#1a1a2e', borderRadius: 8, padding: 20, marginBottom: 20 };
const thStyle = { textAlign: 'left', padding: '10px 12px', borderBottom: '1px solid #333', color: '#888' };
const tdStyle = { padding: '10px 12px', borderBottom: '1px solid #222' };

export default function TransmissionMap() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchTransmission()
      .then((d) => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  if (loading) return <div style={cardStyle}>Loading transmission data...</div>;
  if (!data) return <div style={cardStyle}>Failed to load transmission data.</div>;

  const nodes = data.iso_nodes || [];
  const flows = data.flows || [];

  // Simple SVG map of US with ISO positions
  const mapWidth = 800;
  const mapHeight = 500;

  // Convert lat/lon to SVG coordinates (approximate US projection)
  const project = (lat, lon) => {
    const x = ((lon + 125) / 60) * mapWidth;
    const y = ((50 - lat) / 20) * mapHeight;
    return [Math.max(20, Math.min(x, mapWidth - 20)), Math.max(20, Math.min(y, mapHeight - 20))];
  };

  return (
    <div>
      <div style={cardStyle}>
        <h3 style={{ marginTop: 0 }}>Inter-ISO Transmission Network</h3>
        <svg width="100%" viewBox={`0 0 ${mapWidth} ${mapHeight}`} style={{ background: '#0a0a0f', borderRadius: 8 }}>
          {/* Flow lines */}
          {flows.map((flow) => {
            const [x1, y1] = project(flow.from_coords[0], flow.from_coords[1]);
            const [x2, y2] = project(flow.to_coords[0], flow.to_coords[1]);
            const width = Math.max(2, flow.utilization_pct / 20);
            return (
              <g key={flow.id}>
                <line x1={x1} y1={y1} x2={x2} y2={y2}
                  stroke={flow.color} strokeWidth={width} opacity={0.6} />
                <text
                  x={(x1 + x2) / 2} y={(y1 + y2) / 2 - 8}
                  fill="#888" fontSize={9} textAnchor="middle"
                >
                  {flow.utilization_pct}%
                </text>
              </g>
            );
          })}

          {/* ISO nodes */}
          {nodes.map((node) => {
            const [x, y] = project(node.lat, node.lon);
            return (
              <g key={node.iso}>
                <circle cx={x} cy={y} r={18} fill="#16213e" stroke="#00d4ff" strokeWidth={2} />
                <text x={x} y={y + 1} fill="#00d4ff" fontSize={9} textAnchor="middle" dominantBaseline="middle" fontWeight={700}>
                  {node.iso.replace('ISO-', '')}
                </text>
                <text x={x} y={y + 28} fill="#888" fontSize={8} textAnchor="middle">
                  {node.city}
                </text>
              </g>
            );
          })}

          {/* Legend */}
          <g transform="translate(20, 420)">
            <text fill="#888" fontSize={10} fontWeight={600}>Congestion Level:</text>
            {[
              { label: 'Low (<65%)', color: '#44ff44' },
              { label: 'Medium (65-85%)', color: '#ffaa00' },
              { label: 'High (>85%)', color: '#ff4444' },
            ].map(({ label, color }, i) => (
              <g key={label} transform={`translate(${i * 150 + 110}, 0)`}>
                <rect width={12} height={12} fill={color} rx={2} y={-10} />
                <text x={16} fill="#888" fontSize={9} dominantBaseline="middle">{label}</text>
              </g>
            ))}
          </g>
        </svg>
      </div>

      <div style={cardStyle}>
        <h3 style={{ marginTop: 0 }}>Transmission Interface Details</h3>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr>
              <th style={thStyle}>Interface</th>
              <th style={thStyle}>Capacity</th>
              <th style={thStyle}>Flow</th>
              <th style={thStyle}>Utilization</th>
              <th style={thStyle}>Congestion</th>
            </tr>
          </thead>
          <tbody>
            {flows.sort((a, b) => b.utilization_pct - a.utilization_pct).map((f) => (
              <tr key={f.id}>
                <td style={tdStyle}>
                  <div style={{ fontWeight: 600 }}>{f.name}</div>
                </td>
                <td style={tdStyle}>{f.capacity_mw?.toLocaleString()} MW</td>
                <td style={tdStyle}>{Math.abs(f.flow_mw)?.toLocaleString()} MW</td>
                <td style={tdStyle}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div style={{
                      width: 60, height: 8, background: '#0a0a0f', borderRadius: 4, overflow: 'hidden',
                    }}>
                      <div style={{
                        width: `${f.utilization_pct}%`, height: '100%',
                        background: f.color, borderRadius: 4,
                      }} />
                    </div>
                    {f.utilization_pct}%
                  </div>
                </td>
                <td style={tdStyle}>
                  <span style={{
                    color: f.color, fontWeight: 600,
                    textTransform: 'uppercase', fontSize: 11,
                  }}>
                    {f.congestion_level}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
