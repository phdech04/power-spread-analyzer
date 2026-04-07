import React, { useEffect, useState } from 'react';
import { fetchCorrelation } from '../utils/api';

const cardStyle = { background: '#1a1a2e', borderRadius: 8, padding: 20, marginBottom: 20 };

function getColor(value) {
  if (value >= 0.7) return '#51cf66';
  if (value >= 0.3) return '#8ce99a';
  if (value >= 0) return '#1a1a2e';
  if (value >= -0.3) return '#ffa8a8';
  return '#ff6b6b';
}

export default function CorrelationHeatmap({ days }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchCorrelation(days)
      .then((d) => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, [days]);

  if (loading) return <div style={cardStyle}>Computing correlations for 28 pairs...</div>;
  if (!data || data.error) return <div style={cardStyle}>Failed to load correlation data.</div>;

  const pairs = data.pairs || [];
  const matrix = data.matrix || {};
  const cellSize = Math.min(40, 700 / pairs.length);

  return (
    <div>
      <div style={cardStyle}>
        <h3 style={{ marginTop: 0 }}>Spread Return Correlation Matrix ({pairs.length} pairs)</h3>
        <div style={{ overflowX: 'auto' }}>
          <div style={{ display: 'inline-block', minWidth: pairs.length * cellSize + 120 }}>
            {/* Header row */}
            <div style={{ display: 'flex', marginLeft: 120 }}>
              {pairs.map((p) => (
                <div key={p} style={{
                  width: cellSize, height: 80, fontSize: 8, writingMode: 'vertical-rl',
                  textAlign: 'center', color: '#888', overflow: 'hidden',
                }}>
                  {p.replace('-', '\n')}
                </div>
              ))}
            </div>

            {/* Matrix rows */}
            {pairs.map((rowPair) => (
              <div key={rowPair} style={{ display: 'flex', alignItems: 'center' }}>
                <div style={{ width: 120, fontSize: 10, color: '#aaa', textAlign: 'right', paddingRight: 8, flexShrink: 0 }}>
                  {rowPair}
                </div>
                {pairs.map((colPair) => {
                  const val = matrix[rowPair]?.[colPair] ?? 0;
                  return (
                    <div
                      key={colPair}
                      title={`${rowPair} / ${colPair}: ${val.toFixed(3)}`}
                      style={{
                        width: cellSize,
                        height: cellSize,
                        background: getColor(val),
                        border: '1px solid #0a0a0f',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: cellSize > 30 ? 8 : 6,
                        color: Math.abs(val) > 0.5 ? '#fff' : '#888',
                        cursor: 'pointer',
                      }}
                    >
                      {cellSize > 25 ? val.toFixed(2) : ''}
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        </div>

        {/* Legend */}
        <div style={{ display: 'flex', gap: 16, marginTop: 16, justifyContent: 'center' }}>
          {[
            { label: 'Strong +', color: '#51cf66' },
            { label: 'Weak +', color: '#8ce99a' },
            { label: 'Neutral', color: '#1a1a2e' },
            { label: 'Weak -', color: '#ffa8a8' },
            { label: 'Strong -', color: '#ff6b6b' },
          ].map(({ label, color }) => (
            <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11 }}>
              <div style={{ width: 14, height: 14, background: color, borderRadius: 2, border: '1px solid #333' }} />
              {label}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
