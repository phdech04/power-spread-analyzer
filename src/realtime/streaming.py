"""
WebSocket streaming server for real-time price feeds and trading signals.
Pushes live LMP updates, spread calculations, and z-score signals to clients.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Set

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and room-based broadcasting."""

    def __init__(self):
        self.active_connections: Dict[str, Set] = {}  # room -> set of websockets

    async def connect(self, websocket, room: str = "default"):
        await websocket.accept()
        if room not in self.active_connections:
            self.active_connections[room] = set()
        self.active_connections[room].add(websocket)
        logger.info(f"Client connected to room '{room}' ({len(self.active_connections[room])} clients)")

    def disconnect(self, websocket, room: str = "default"):
        if room in self.active_connections:
            self.active_connections[room].discard(websocket)
            if not self.active_connections[room]:
                del self.active_connections[room]

    async def broadcast(self, message: dict, room: str = "default"):
        if room not in self.active_connections:
            return
        dead = set()
        for ws in self.active_connections[room]:
            try:
                await ws.send_json(message)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.active_connections[room].discard(ws)


class PriceStreamSimulator:
    """
    Simulates real-time price updates using OU process.
    In production, replace with actual ISO API polling.
    """

    def __init__(self, config: dict):
        self.config = config
        self.current_prices: Dict[str, float] = {}
        self.price_history: Dict[str, list] = {}
        self._init_prices()

    def _init_prices(self):
        for iso, cfg in self.config["isos"].items():
            base = cfg["base_price"]
            self.current_prices[iso] = base + np.random.randn() * 3
            self.price_history[iso] = [self.current_prices[iso]]

    def tick(self) -> Dict[str, dict]:
        """Generate one tick of price updates for all ISOs."""
        now = datetime.utcnow()
        hour = now.hour
        updates = {}

        for iso, cfg in self.config["isos"].items():
            base = cfg["base_price"]
            vol = cfg["volatility"] * 0.01 * base
            theta = 0.15
            dt = 1.0 / (24 * 60)  # per-minute tick

            # OU step
            prev = self.current_prices[iso]
            noise = np.random.randn() * vol * np.sqrt(dt)
            new_price = prev + theta * (base - prev) * dt + noise

            # Diurnal effect
            diurnal = 5 * np.sin(np.pi * (hour - 6) / 16) if 6 <= hour <= 22 else -2
            new_price += diurnal * dt * 10

            # ISO-specific
            if iso == "CAISO" and 10 <= hour <= 15:
                new_price -= 3 * dt * 10  # solar dip
            elif iso == "ERCOT" and 14 <= hour <= 18:
                new_price += 2 * np.random.rand() * dt * 10

            # Random spike
            if np.random.rand() < 0.001:
                new_price += np.random.exponential(20)

            new_price = max(new_price, -10)
            self.current_prices[iso] = new_price
            self.price_history[iso].append(new_price)

            # Keep last 1440 ticks (24h at 1/min)
            if len(self.price_history[iso]) > 1440:
                self.price_history[iso] = self.price_history[iso][-1440:]

            updates[iso] = {
                "iso": iso,
                "lmp": round(new_price, 2),
                "timestamp": now.isoformat(),
                "change": round(new_price - prev, 3),
                "change_pct": round((new_price - prev) / abs(prev) * 100, 3) if prev != 0 else 0,
            }

        return updates

    def compute_live_spread(self, iso_a: str, iso_b: str) -> dict:
        """Compute current spread and rolling z-score from live data."""
        price_a = self.current_prices.get(iso_a, 0)
        price_b = self.current_prices.get(iso_b, 0)
        spread = price_a - price_b

        # Rolling z-score from recent history
        hist_a = self.price_history.get(iso_a, [])
        hist_b = self.price_history.get(iso_b, [])
        min_len = min(len(hist_a), len(hist_b))

        zscore = 0.0
        if min_len >= 20:
            spreads = np.array(hist_a[-min_len:]) - np.array(hist_b[-min_len:])
            window = min(20, len(spreads))
            recent = spreads[-window:]
            mean = np.mean(recent)
            std = np.std(recent)
            if std > 0:
                zscore = (spread - mean) / std

        # Signal
        signal = "FLAT"
        if zscore < -1.5:
            signal = "LONG"
        elif zscore > 1.5:
            signal = "SHORT"
        elif abs(zscore) < 0.3:
            signal = "EXIT"

        return {
            "iso_a": iso_a,
            "iso_b": iso_b,
            "price_a": round(price_a, 2),
            "price_b": round(price_b, 2),
            "spread": round(spread, 2),
            "zscore": round(zscore, 3),
            "signal": signal,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def get_snapshot(self) -> dict:
        """Current state of all ISOs."""
        return {
            iso: {
                "iso": iso,
                "lmp": round(price, 2),
                "timestamp": datetime.utcnow().isoformat(),
            }
            for iso, price in self.current_prices.items()
        }


manager = ConnectionManager()
