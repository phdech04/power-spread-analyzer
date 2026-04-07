"""
Threshold-based alerting system for trading signals.
Supports email, Slack webhook, and in-app notifications.
"""

import json
import logging
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class AlertRule:
    """A single alert condition."""

    def __init__(
        self,
        name: str,
        metric: str,
        condition: str,  # "above", "below", "crosses_above", "crosses_below"
        threshold: float,
        pair: Optional[str] = None,
        cooldown_minutes: int = 30,
    ):
        self.name = name
        self.metric = metric  # "zscore", "spread", "price", "regime"
        self.condition = condition
        self.threshold = threshold
        self.pair = pair
        self.cooldown_minutes = cooldown_minutes
        self.last_triggered = None
        self._prev_value = None

    def evaluate(self, current_value: float) -> bool:
        """Check if alert should fire."""
        # Cooldown check
        if self.last_triggered:
            elapsed = (datetime.utcnow() - self.last_triggered).total_seconds() / 60
            if elapsed < self.cooldown_minutes:
                return False

        fired = False
        if self.condition == "above":
            fired = current_value > self.threshold
        elif self.condition == "below":
            fired = current_value < self.threshold
        elif self.condition == "crosses_above" and self._prev_value is not None:
            fired = self._prev_value <= self.threshold < current_value
        elif self.condition == "crosses_below" and self._prev_value is not None:
            fired = self._prev_value >= self.threshold > current_value

        self._prev_value = current_value

        if fired:
            self.last_triggered = datetime.utcnow()
        return fired

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "metric": self.metric,
            "condition": self.condition,
            "threshold": self.threshold,
            "pair": self.pair,
            "cooldown_minutes": self.cooldown_minutes,
            "last_triggered": self.last_triggered.isoformat() if self.last_triggered else None,
        }


class AlertManager:
    """Manages alert rules and dispatches notifications."""

    def __init__(self):
        self.rules: List[AlertRule] = []
        self.alert_history: List[dict] = []
        self.channels: Dict[str, dict] = {}  # channel_type -> config
        self._setup_default_rules()

    def _setup_default_rules(self):
        """Pre-configured alerts for common trading signals."""
        defaults = [
            AlertRule("Z-Score Entry Long", "zscore", "crosses_below", -1.5, cooldown_minutes=60),
            AlertRule("Z-Score Entry Short", "zscore", "crosses_above", 1.5, cooldown_minutes=60),
            AlertRule("Z-Score Stop Loss", "zscore", "above", 3.0, cooldown_minutes=15),
            AlertRule("Z-Score Stop Loss", "zscore", "below", -3.0, cooldown_minutes=15),
            AlertRule("Spread Spike", "spread", "above", 50.0, cooldown_minutes=30),
            AlertRule("Negative Spread", "spread", "below", -50.0, cooldown_minutes=30),
        ]
        self.rules.extend(defaults)

    def add_rule(self, rule: AlertRule):
        self.rules.append(rule)

    def remove_rule(self, name: str):
        self.rules = [r for r in self.rules if r.name != name]

    def configure_channel(self, channel_type: str, config: dict):
        """Configure a notification channel (slack, email, webhook)."""
        self.channels[channel_type] = config

    def check_alerts(self, data: dict) -> List[dict]:
        """Evaluate all rules against current data. Returns list of fired alerts."""
        fired = []
        for rule in self.rules:
            value = data.get(rule.metric)
            if value is None:
                continue
            if rule.pair and data.get("pair") != rule.pair:
                continue

            if rule.evaluate(value):
                alert = {
                    "rule": rule.name,
                    "metric": rule.metric,
                    "value": value,
                    "threshold": rule.threshold,
                    "condition": rule.condition,
                    "pair": data.get("pair", data.get("iso_a", "") + "-" + data.get("iso_b", "")),
                    "timestamp": datetime.utcnow().isoformat(),
                }
                fired.append(alert)
                self.alert_history.append(alert)
                self._dispatch(alert)

        # Keep last 500 alerts
        if len(self.alert_history) > 500:
            self.alert_history = self.alert_history[-500:]

        return fired

    def _dispatch(self, alert: dict):
        """Send alert through configured channels."""
        message = (
            f"[{alert['rule']}] {alert['pair']}: "
            f"{alert['metric']}={alert['value']:.3f} "
            f"({alert['condition']} {alert['threshold']})"
        )
        logger.warning(f"ALERT: {message}")

        if "slack" in self.channels:
            self._send_slack(message)
        if "email" in self.channels:
            self._send_email(alert, message)
        if "webhook" in self.channels:
            self._send_webhook(alert)

    def _send_slack(self, message: str):
        """Send to Slack webhook."""
        cfg = self.channels.get("slack", {})
        url = cfg.get("webhook_url")
        if not url:
            return
        try:
            requests.post(url, json={"text": f":zap: {message}"}, timeout=5)
        except Exception as e:
            logger.error(f"Slack alert failed: {e}")

    def _send_email(self, alert: dict, message: str):
        """Send email alert."""
        cfg = self.channels.get("email", {})
        try:
            msg = MIMEText(
                f"Alert: {alert['rule']}\n"
                f"Pair: {alert['pair']}\n"
                f"Metric: {alert['metric']} = {alert['value']:.4f}\n"
                f"Condition: {alert['condition']} {alert['threshold']}\n"
                f"Time: {alert['timestamp']}\n"
            )
            msg["Subject"] = f"Power Spread Alert: {alert['rule']}"
            msg["From"] = cfg.get("from_addr", "alerts@powerspread.local")
            msg["To"] = cfg.get("to_addr", "")

            with smtplib.SMTP(cfg.get("smtp_host", "localhost"), cfg.get("smtp_port", 587)) as server:
                if cfg.get("use_tls"):
                    server.starttls()
                if cfg.get("username"):
                    server.login(cfg["username"], cfg["password"])
                server.send_message(msg)
        except Exception as e:
            logger.error(f"Email alert failed: {e}")

    def _send_webhook(self, alert: dict):
        """Send to generic webhook."""
        cfg = self.channels.get("webhook", {})
        url = cfg.get("url")
        if not url:
            return
        try:
            requests.post(url, json=alert, timeout=5)
        except Exception as e:
            logger.error(f"Webhook alert failed: {e}")

    def get_history(self, limit: int = 50) -> List[dict]:
        return self.alert_history[-limit:]

    def get_rules(self) -> List[dict]:
        return [r.to_dict() for r in self.rules]
