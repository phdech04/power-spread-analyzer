import React, { useEffect, useState } from 'react';
import { fetchEvents } from '../utils/api';

const cardStyle = { background: '#1a1a2e', borderRadius: 8, padding: 20, marginBottom: 20 };
const thStyle = { textAlign: 'left', padding: '10px 12px', borderBottom: '1px solid #333', color: '#888' };
const tdStyle = { padding: '10px 12px', borderBottom: '1px solid #222' };

const impactColors = { high: '#ff6b6b', medium: '#fcc419', low: '#51cf66' };
const categoryIcons = {
  capacity_auction: 'A',
  regulatory: 'R',
  seasonal: 'S',
  maintenance: 'M',
  transmission: 'T',
  generation: 'G',
};

export default function EventCalendar({ isoA, isoB, days }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filterCat, setFilterCat] = useState('');

  useEffect(() => {
    setLoading(true);
    fetchEvents(null, null, days || 180)
      .then((d) => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, [days]);

  if (loading) return <div style={cardStyle}>Loading event calendar...</div>;
  if (!data) return <div style={cardStyle}>Failed to load events.</div>;

  const categories = data.categories || [];
  let events = data.events || [];
  if (filterCat) events = events.filter((e) => e.category === filterCat);

  // Filter to show events relevant to selected ISOs
  const relevant = events.filter(
    (e) => e.isos?.includes(isoA) || e.isos?.includes(isoB)
  );
  const other = events.filter(
    (e) => !e.isos?.includes(isoA) && !e.isos?.includes(isoB)
  );

  const renderEventTable = (eventList, title) => (
    <div style={cardStyle}>
      <h3 style={{ marginTop: 0 }}>{title} ({eventList.length})</h3>
      {eventList.length === 0 ? (
        <p style={{ color: '#888' }}>No events in this period.</p>
      ) : (
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr>
              <th style={thStyle}>Date</th>
              <th style={thStyle}>Event</th>
              <th style={thStyle}>ISOs</th>
              <th style={thStyle}>Category</th>
              <th style={thStyle}>Impact</th>
            </tr>
          </thead>
          <tbody>
            {eventList.map((e, i) => (
              <tr key={i}>
                <td style={tdStyle}>
                  <div>{e.date}</div>
                  {e.date !== e.end_date && (
                    <div style={{ fontSize: 11, color: '#888' }}>to {e.end_date}</div>
                  )}
                </td>
                <td style={tdStyle}>
                  <div style={{ fontWeight: 600 }}>{e.title}</div>
                  <div style={{ fontSize: 11, color: '#888', marginTop: 4 }}>{e.description}</div>
                </td>
                <td style={tdStyle}>
                  <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                    {(e.isos || []).map((iso) => (
                      <span key={iso} style={{
                        background: (iso === isoA || iso === isoB) ? '#00d4ff22' : '#16213e',
                        border: (iso === isoA || iso === isoB) ? '1px solid #00d4ff' : '1px solid #333',
                        padding: '2px 6px', borderRadius: 4, fontSize: 10,
                        color: (iso === isoA || iso === isoB) ? '#00d4ff' : '#888',
                      }}>
                        {iso}
                      </span>
                    ))}
                  </div>
                </td>
                <td style={tdStyle}>
                  <span style={{
                    background: '#16213e', padding: '2px 8px', borderRadius: 4,
                    fontSize: 11, color: '#aaa',
                  }}>
                    {categoryIcons[e.category] || '?'} {e.category?.replace('_', ' ')}
                  </span>
                </td>
                <td style={tdStyle}>
                  <span style={{
                    color: impactColors[e.impact] || '#888',
                    fontWeight: 600, textTransform: 'uppercase', fontSize: 11,
                  }}>
                    {e.impact}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );

  return (
    <div>
      <div style={{ ...cardStyle, display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <span style={{ color: '#888', fontSize: 13 }}>Filter:</span>
        <button
          onClick={() => setFilterCat('')}
          style={{
            background: !filterCat ? '#00d4ff' : '#16213e', color: !filterCat ? '#000' : '#888',
            border: 'none', padding: '6px 12px', borderRadius: 4, cursor: 'pointer', fontSize: 12,
          }}
        >
          All
        </button>
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setFilterCat(cat)}
            style={{
              background: filterCat === cat ? '#00d4ff' : '#16213e',
              color: filterCat === cat ? '#000' : '#888',
              border: 'none', padding: '6px 12px', borderRadius: 4, cursor: 'pointer', fontSize: 12,
            }}
          >
            {cat.replace('_', ' ')}
          </button>
        ))}
      </div>

      {renderEventTable(relevant, `Events Affecting ${isoA} / ${isoB}`)}
      {other.length > 0 && renderEventTable(other, 'Other Market Events')}
    </div>
  );
}
