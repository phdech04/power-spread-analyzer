import axios from 'axios';

const API_BASE = '/api';

export async function fetchISOs() {
  const res = await axios.get(`${API_BASE}/isos`);
  return res.data.isos;
}

export async function fetchPrices(iso, days = 365) {
  const res = await axios.get(`${API_BASE}/prices`, { params: { iso, days } });
  return res.data;
}

export async function fetchSpread(isoA, isoB, days = 365) {
  const res = await axios.get(`${API_BASE}/spread`, {
    params: { iso_a: isoA, iso_b: isoB, days },
  });
  return res.data;
}

export async function runBacktest(params) {
  const res = await axios.get(`${API_BASE}/backtest`, { params });
  return res.data;
}

export async function fetchRisk(isoA, isoB, days = 365) {
  const res = await axios.get(`${API_BASE}/risk`, {
    params: { iso_a: isoA, iso_b: isoB, days },
  });
  return res.data;
}

// ── New API Functions ─────────────────────────────────────────────────

export async function fetchForecast(isoA, isoB, days = 365, model = 'lstm', horizon = 1) {
  const res = await axios.get(`${API_BASE}/forecast`, {
    params: { iso_a: isoA, iso_b: isoB, days, model, horizon },
  });
  return res.data;
}

export async function fetchPortfolio(days = 365, target = 'max_sharpe', maxWeight = 0.3) {
  const res = await axios.get(`${API_BASE}/portfolio`, {
    params: { days, target, max_weight: maxWeight },
  });
  return res.data;
}

export async function fetchFrontier(days = 365) {
  const res = await axios.get(`${API_BASE}/portfolio/frontier`, { params: { days } });
  return res.data;
}

export async function fetchCorrelation(days = 365) {
  const res = await axios.get(`${API_BASE}/correlation`, { params: { days } });
  return res.data;
}

export async function fetchCongestion(isoA, isoB, days = 365) {
  const res = await axios.get(`${API_BASE}/congestion`, {
    params: { iso_a: isoA, iso_b: isoB, days },
  });
  return res.data;
}

export async function fetchGas(iso = 'ERCOT', days = 365) {
  const res = await axios.get(`${API_BASE}/gas`, { params: { iso, days } });
  return res.data;
}

export async function fetchRenewables(iso = 'CAISO', days = 90) {
  const res = await axios.get(`${API_BASE}/renewables`, { params: { iso, days } });
  return res.data;
}

export async function fetchMonteCarlo(isoA, isoB, days = 365, nSim = 5000) {
  const res = await axios.get(`${API_BASE}/montecarlo`, {
    params: { iso_a: isoA, iso_b: isoB, days, n_simulations: nSim },
  });
  return res.data;
}

export async function fetchTransmission() {
  const res = await axios.get(`${API_BASE}/transmission`);
  return res.data;
}

export async function fetchVolatility(isoA, isoB, days = 365) {
  const res = await axios.get(`${API_BASE}/volatility`, {
    params: { iso_a: isoA, iso_b: isoB, days },
  });
  return res.data;
}

export async function fetchEvents(iso = null, category = null, days = 180) {
  const res = await axios.get(`${API_BASE}/events`, {
    params: { iso, category, days },
  });
  return res.data;
}

export async function fetchPairEvents(isoA, isoB, days = 90) {
  const res = await axios.get(`${API_BASE}/events/pair`, {
    params: { iso_a: isoA, iso_b: isoB, days },
  });
  return res.data;
}

export async function fetchJournal() {
  const res = await axios.get(`${API_BASE}/journal`);
  return res.data;
}

export async function fetchAlerts(limit = 50) {
  const res = await axios.get(`${API_BASE}/alerts`, { params: { limit } });
  return res.data;
}
