import React, { useState } from 'react';
import MarketOverview from './components/MarketOverview';
import SpreadChart from './components/SpreadChart';
import WeatherCorrelation from './components/WeatherCorrelation';
import BacktestPanel from './components/BacktestPanel';
import RiskDashboard from './components/RiskDashboard';
import ForecastPanel from './components/ForecastPanel';
import PortfolioPanel from './components/PortfolioPanel';
import CorrelationHeatmap from './components/CorrelationHeatmap';
import CongestionPanel from './components/CongestionPanel';
import GasPanel from './components/GasPanel';
import RenewablesPanel from './components/RenewablesPanel';
import MonteCarloPanel from './components/MonteCarloPanel';
import VolatilityPanel from './components/VolatilityPanel';
import EventCalendar from './components/EventCalendar';
import TransmissionMap from './components/TransmissionMap';
import LiveStream from './components/LiveStream';

const TABS = [
  'Overview', 'Spreads', 'Forecast', 'Portfolio', 'Backtest',
  'Risk', 'Monte Carlo', 'Congestion', 'Gas/Spark',
  'Renewables', 'Volatility', 'Correlation', 'Transmission',
  'Events', 'Weather', 'Live',
];

const ISOS = ['ERCOT', 'PJM', 'CAISO', 'MISO', 'NYISO', 'ISO-NE', 'SPP', 'IESO'];

const styles = {
  app: {
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    maxWidth: 1400,
    margin: '0 auto',
    padding: '20px',
    background: '#0a0a0f',
    color: '#e0e0e0',
    minHeight: '100vh',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
    borderBottom: '1px solid #333',
    paddingBottom: 12,
  },
  title: {
    fontSize: 22,
    fontWeight: 700,
    color: '#00d4ff',
  },
  subtitle: {
    fontSize: 11,
    color: '#555',
    marginTop: 2,
  },
  controls: {
    display: 'flex',
    gap: 10,
    alignItems: 'center',
  },
  select: {
    background: '#1a1a2e',
    color: '#e0e0e0',
    border: '1px solid #333',
    padding: '6px 10px',
    borderRadius: 6,
    fontSize: 13,
  },
  label: {
    fontSize: 12,
    color: '#888',
  },
  tabContainer: {
    display: 'flex',
    gap: 2,
    marginBottom: 20,
    overflowX: 'auto',
    paddingBottom: 4,
  },
  tab: {
    padding: '8px 14px',
    border: 'none',
    borderRadius: '6px 6px 0 0',
    cursor: 'pointer',
    fontSize: 12,
    fontWeight: 500,
    transition: 'all 0.2s',
    whiteSpace: 'nowrap',
  },
  tabActive: {
    background: '#1a1a2e',
    color: '#00d4ff',
  },
  tabInactive: {
    background: 'transparent',
    color: '#666',
  },
};

export default function App() {
  const [activeTab, setActiveTab] = useState(0);
  const [isoA, setIsoA] = useState('ERCOT');
  const [isoB, setIsoB] = useState('PJM');
  const [days, setDays] = useState(365);

  return (
    <div style={styles.app}>
      <div style={styles.header}>
        <div>
          <div style={styles.title}>Cross-ISO Power Spread Analyzer</div>
          <div style={styles.subtitle}>v2.0 — 8 ISOs | ML Forecasting | Portfolio Optimization | Real-Time Streaming</div>
        </div>
        <div style={styles.controls}>
          <span style={styles.label}>A:</span>
          <select style={styles.select} value={isoA} onChange={(e) => setIsoA(e.target.value)}>
            {ISOS.map((iso) => <option key={iso} value={iso}>{iso}</option>)}
          </select>
          <span style={styles.label}>B:</span>
          <select style={styles.select} value={isoB} onChange={(e) => setIsoB(e.target.value)}>
            {ISOS.map((iso) => <option key={iso} value={iso}>{iso}</option>)}
          </select>
          <span style={styles.label}>Days:</span>
          <select style={styles.select} value={days} onChange={(e) => setDays(Number(e.target.value))}>
            {[30, 90, 180, 365, 730].map((d) => <option key={d} value={d}>{d}</option>)}
          </select>
        </div>
      </div>

      <div style={styles.tabContainer}>
        {TABS.map((tab, i) => (
          <button
            key={tab}
            onClick={() => setActiveTab(i)}
            style={{
              ...styles.tab,
              ...(i === activeTab ? styles.tabActive : styles.tabInactive),
            }}
          >
            {tab}
          </button>
        ))}
      </div>

      {activeTab === 0 && <MarketOverview isoA={isoA} isoB={isoB} days={days} />}
      {activeTab === 1 && <SpreadChart isoA={isoA} isoB={isoB} days={days} />}
      {activeTab === 2 && <ForecastPanel isoA={isoA} isoB={isoB} days={days} />}
      {activeTab === 3 && <PortfolioPanel isoA={isoA} isoB={isoB} days={days} />}
      {activeTab === 4 && <BacktestPanel isoA={isoA} isoB={isoB} days={days} />}
      {activeTab === 5 && <RiskDashboard isoA={isoA} isoB={isoB} days={days} />}
      {activeTab === 6 && <MonteCarloPanel isoA={isoA} isoB={isoB} days={days} />}
      {activeTab === 7 && <CongestionPanel isoA={isoA} isoB={isoB} days={days} />}
      {activeTab === 8 && <GasPanel isoA={isoA} days={days} />}
      {activeTab === 9 && <RenewablesPanel isoA={isoA} days={days} />}
      {activeTab === 10 && <VolatilityPanel isoA={isoA} isoB={isoB} days={days} />}
      {activeTab === 11 && <CorrelationHeatmap days={days} />}
      {activeTab === 12 && <TransmissionMap />}
      {activeTab === 13 && <EventCalendar isoA={isoA} isoB={isoB} days={days} />}
      {activeTab === 14 && <WeatherCorrelation isoA={isoA} isoB={isoB} days={days} />}
      {activeTab === 15 && <LiveStream isoA={isoA} isoB={isoB} />}
    </div>
  );
}
