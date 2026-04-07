import React, { useEffect, useState, useRef } from 'react';

const cardStyle = { background: '#1a1a2e', borderRadius: 8, padding: 20, marginBottom: 20 };
const metricCard = { background: '#16213e', borderRadius: 8, padding: '12px 16px', textAlign: 'center' };

export default function LiveStream({ isoA, isoB }) {
  const [prices, setPrices] = useState({});
  const [spread, setSpread] = useState(null);
  const [connected, setConnected] = useState(false);
  const [history, setHistory] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const wsRef = useRef(null);

  useEffect(() => {
    const wsUrl = `ws://localhost:8000/ws/spread?iso_a=${isoA}&iso_b=${isoB}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.type === 'spread_tick' && msg.data) {
        setSpread(msg.data);
        setHistory((prev) => {
          const next = [...prev, msg.data].slice(-120); // keep last 120 ticks (4 min)
          return next;
        });
        if (msg.alerts?.length > 0) {
          setAlerts((prev) => [...msg.alerts, ...prev].slice(0, 20));
        }
      } else if (msg.type === 'snapshot') {
        setPrices(msg.data || {});
      }
    };

    return () => ws.close();
  }, [isoA, isoB]);

  const signalColor = {
    LONG: '#51cf66', SHORT: '#ff6b6b', EXIT: '#fcc419', FLAT: '#888',
  };

  return (
    <div>
      <div style={{ ...cardStyle, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h3 style={{ margin: 0 }}>Live Market Stream</h3>
          <span style={{ fontSize: 12, color: '#888' }}>
            {isoA} vs {isoB} | 2-second tick interval
          </span>
        </div>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          color: connected ? '#51cf66' : '#ff6b6b',
          fontWeight: 600, fontSize: 13,
        }}>
          <div style={{
            width: 10, height: 10, borderRadius: '50%',
            background: connected ? '#51cf66' : '#ff6b6b',
            animation: connected ? 'pulse 2s infinite' : 'none',
          }} />
          {connected ? 'CONNECTED' : 'DISCONNECTED'}
        </div>
      </div>

      {spread && (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12, marginBottom: 20 }}>
            <div style={metricCard}>
              <div style={{ color: '#888', fontSize: 11 }}>{isoA} Price</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: '#00d4ff' }}>
                ${spread.price_a}
              </div>
            </div>
            <div style={metricCard}>
              <div style={{ color: '#888', fontSize: 11 }}>{isoB} Price</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: '#845ef7' }}>
                ${spread.price_b}
              </div>
            </div>
            <div style={metricCard}>
              <div style={{ color: '#888', fontSize: 11 }}>Live Spread</div>
              <div style={{ fontSize: 22, fontWeight: 700 }}>
                ${spread.spread}
              </div>
            </div>
            <div style={metricCard}>
              <div style={{ color: '#888', fontSize: 11 }}>Z-Score</div>
              <div style={{
                fontSize: 22, fontWeight: 700,
                color: Math.abs(spread.zscore) > 1.5 ? '#ff6b6b' : Math.abs(spread.zscore) > 0.5 ? '#fcc419' : '#51cf66',
              }}>
                {spread.zscore}
              </div>
            </div>
            <div style={metricCard}>
              <div style={{ color: '#888', fontSize: 11 }}>Signal</div>
              <div style={{
                fontSize: 22, fontWeight: 700,
                color: signalColor[spread.signal] || '#888',
              }}>
                {spread.signal}
              </div>
            </div>
          </div>

          {/* Mini sparkline using CSS bars */}
          <div style={cardStyle}>
            <h4 style={{ marginTop: 0, marginBottom: 8 }}>Z-Score Trail (last {history.length} ticks)</h4>
            <div style={{ display: 'flex', alignItems: 'center', height: 80, gap: 1 }}>
              {history.map((h, i) => {
                const z = h.zscore || 0;
                const height = Math.min(Math.abs(z) / 3 * 40, 40);
                return (
                  <div key={i} style={{
                    width: Math.max(2, 500 / history.length),
                    height: height,
                    background: z > 1.5 ? '#ff6b6b' : z < -1.5 ? '#51cf66' : '#00d4ff',
                    opacity: 0.5 + (i / history.length) * 0.5,
                    alignSelf: z >= 0 ? 'flex-start' : 'flex-end',
                    borderRadius: 1,
                  }} />
                );
              })}
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#555' }}>
              <span>+3.0</span>
              <span>0</span>
              <span>-3.0</span>
            </div>
          </div>

          {alerts.length > 0 && (
            <div style={cardStyle}>
              <h4 style={{ marginTop: 0, color: '#ff6b6b' }}>Recent Alerts</h4>
              {alerts.slice(0, 5).map((a, i) => (
                <div key={i} style={{
                  padding: '8px 12px', marginBottom: 4,
                  background: '#16213e', borderRadius: 4,
                  borderLeft: '3px solid #ff6b6b',
                  fontSize: 12,
                }}>
                  <strong>{a.rule}</strong>: {a.metric}={a.value?.toFixed(3)} ({a.condition} {a.threshold})
                  <span style={{ color: '#888', marginLeft: 8 }}>{a.timestamp?.slice(11, 19)}</span>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {!connected && (
        <div style={{ ...cardStyle, textAlign: 'center', color: '#888' }}>
          <p>WebSocket not connected. Start the backend:</p>
          <code style={{ color: '#00d4ff' }}>uvicorn src.api.app:app --reload --port 8000</code>
        </div>
      )}

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
    </div>
  );
}
