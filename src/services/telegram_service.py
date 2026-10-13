import os
import html
import time
import queue
import threading
import requests
from typing import Optional
try:
    from core.config import config
except ImportError:
    from src.core.config import config

class TelegramService:
    def __init__(self,
                 token: str = config.telegram_bot_token,
                 chat_id: str = config.telegram_chat_id,
                 enabled: bool = config.telegram_enabled):
        self.bot_token = token
        self.chat_id = chat_id
        self.enabled = enabled
        self.send_telemetry_status = config.telegram_send_status

        self.last_alert_time = {}
        self.cooldown_sec = 30.0
        self.last_telemetry_time = 0.0
        self.min_telemetry_sec = config.update_interval_sec

        self._queue = queue.Queue(maxsize=250)
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()

    def _worker_loop(self):
        while True:
            try:
                html_msg = self._queue.get()
                self._post_telegram_sync(html_msg)
                self._queue.task_done()
                time.sleep(0.3)  # Telegram API rate limit safety
            except Exception as e:
                time.sleep(1.0)

    def _post_telegram_sync(self, html_message: str) -> bool:
        if not self.enabled or not self.bot_token or not self.chat_id:
            return False
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": html_message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        try:
            resp = requests.post(url, json=payload, timeout=8.0)
            return resp.status_code == 200
        except Exception:
            return False

    def dispatch_async(self, html_msg: str):
        if not self.enabled:
            return
        try:
            self._queue.put_nowait(html_msg)
        except queue.Full:
            pass

    def alert_actuation_event(self, action: str, load: str, reason: str, curr: float, limit: float, details: str = ""):
        now = time.time()
        key = f"ACT_{action}_{load}_{reason}"
        if now - self.last_alert_time.get(key, 0.0) < 5.0:
            return
        self.last_alert_time[key] = now

        icon = "⚡"
        if action == "TRIP": icon = "🚨"
        elif action == "SHED": icon = "📉"
        elif action == "RESTORE": icon = "✅"
        elif action == "FAULT": icon = "⚠️"

        safe_action = html.escape(str(action))
        safe_load = html.escape(str(load)).upper()
        safe_reason = html.escape(str(reason))
        safe_details = html.escape(str(details)) if details else ""

        msg = (
            f"<b>{icon} SMART GRID ACTUATION EVENT: {safe_action}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Branch:</b> <code>{safe_load}</code>\n"
            f"• <b>Reason:</b> {safe_reason}\n"
            f"• <b>Branch Current:</b> <code>{curr:.1f} mA</code>\n"
            f"• <b>Source Ceiling:</b> <code>{limit:.0f} mA</code>\n"
        )
        if safe_details:
            msg += f"• <b>Context:</b> <i>{safe_details}</i>\n"
        msg += f"━━━━━━━━━━━━━━━━━━━━━\n⏱ <i>{time.strftime('%Y-%m-%d %H:%M:%S')}</i>"
        self.dispatch_async(msg)

    def alert_warning_tier(self, level: int, util: float):
        if level <= 0:
            return
        now = time.time()
        key = f"WARN_TIER_{level}"
        if now - self.last_alert_time.get(key, 0.0) < self.cooldown_sec:
            return
        self.last_alert_time[key] = now

        if level == 1:
            icon = "ℹ️"
            title = "MEDIUM LOAD NOTICE (70%)"
            body = f"Grid utilization reached <b>{util:.1f}%</b>. Advisory tier, no action required."
        elif level == 2:
            icon = "⚠️"
            title = "HIGH CAPACITY UTILIZATION (80%)"
            body = f"Grid utilization reached <b>{util:.1f}%</b>. Approaching 85% shedding threshold."
        else:
            icon = "🚨"
            title = "CRITICAL LOAD SHEDDING ACTIVE (85%)"
            body = f"Grid utilization exceeded <b>{util:.1f}% >= 85.0%</b>. Automated priority shedding in progress."

        msg = (
            f"<b>{icon} {title}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"{body}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n⏱ <i>{time.strftime('%Y-%m-%d %H:%M:%S')}</i>"
        )
        self.dispatch_async(msg)

    def alert_mode_change(self, mode: str):
        safe_mode = html.escape(str(mode))
        msg = (
            f"<b>🔄 GRID CONTROL MODE SWITCHED</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"• Operating Mode: <b>{safe_mode}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n⏱ <i>{time.strftime('%Y-%m-%d %H:%M:%S')}</i>"
        )
        self.dispatch_async(msg)

    def alert_manual_override(self, load: str, state: int):
        state_str = "ENERGIZED (ON)" if state == 1 else "DE-ENERGIZED (OFF)"
        msg = (
            f"<b>🕹️ MANUAL OPERATOR OVERRIDE</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"• Load: <b>{html.escape(load.upper())}</b>\n"
            f"• Commanded State: <code>{state_str}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n⏱ <i>{time.strftime('%Y-%m-%d %H:%M:%S')}</i>"
        )
        self.dispatch_async(msg)

telegram = TelegramService()
