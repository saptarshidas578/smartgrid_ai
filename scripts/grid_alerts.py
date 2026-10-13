import os
import json
import time
import requests
import datetime
import html
import threading
import queue

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
CONFIG_FILE = os.path.join(PROJECT_ROOT, "docs", "alert_config.json")

# Candidate paths for seamless synchronization across OneDrive and Documents
CANDIDATE_CONFIG_PATHS = [
    CONFIG_FILE,
    r"C:\Users\lenovo\OneDrive\Documents\alert_config.json",
    r"C:\Users\lenovo\Documents\alert_config.json"
]

class GridAlerter:
    """
    Real-Time Push Notification Engine for Smart Grid Telemetry & Events:
    - Transmits formatted real-time 5-second telemetry status cards to Telegram.
    - Transmits instant priority push notifications for grid events (Trips, Sheds, Faults, Restorations).
    - Uses HTML parse mode with entity escaping to prevent Markdown syntax corruption.
    - Non-blocking asynchronous background worker ensures MQTT loop and Web SCADA never freeze.
    - Anti-spam rate limiting & de-duplication for recurring warnings.
    """
    def __init__(self, config_path: str = CONFIG_FILE):
        self.config_path = config_path
        self.bot_token = ""
        self.chat_id = ""
        self.enabled = False
        self.send_telemetry_status_enabled = True
        self.last_alert_time = {}       # key -> timestamp
        self.cooldown_sec = 30.0        # Rate-limit identical warnings for 30s
        self.last_telemetry_time = 0.0  # Timestamp of last 5s status broadcast
        self.min_telemetry_sec = 2.0    # Minimum seconds between status broadcasts (2s interval)
        self._last_mtime = 0.0

        # Background worker thread & message queue (FIFO)
        self._queue = queue.Queue(maxsize=200)
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()

        self.load_config()

    def load_config(self):
        """Loads Telegram credentials from alert_config.json with fallback search."""
        found_cfg = None
        target_path = self.config_path

        # Check candidate locations
        for p in CANDIDATE_CONFIG_PATHS:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        token = data.get("bot_token", "").strip()
                        chat = str(data.get("chat_id", "")).strip()
                        if token and chat:
                            found_cfg = data
                            target_path = p
                            break
                        elif found_cfg is None:
                            found_cfg = data
                            target_path = p
                except Exception:
                    pass

        if found_cfg:
            try:
                self.bot_token = found_cfg.get("bot_token", "").strip()
                self.chat_id = str(found_cfg.get("chat_id", "")).strip()
                self.enabled = bool(self.bot_token and self.chat_id and found_cfg.get("enabled", True))
                self.send_telemetry_status_enabled = bool(found_cfg.get("send_telemetry_status", True))
                self.config_path = target_path
                if os.path.exists(target_path):
                    self._last_mtime = os.path.getmtime(target_path)
            except Exception as e:
                print(f"[Alerter] Error parsing config: {e}")
                self.enabled = False
        else:
            self.save_config("", "", enabled=False)

    def reload_config_if_modified(self):
        """Checks if config file was updated on disk (e.g. from Web Dashboard)."""
        try:
            if os.path.exists(self.config_path):
                mtime = os.path.getmtime(self.config_path)
                if mtime != self._last_mtime:
                    self.load_config()
        except Exception:
            pass

    def save_config(self, bot_token: str, chat_id: str, enabled: bool = True, send_telemetry_status: bool = True):
        """Saves new credentials to alert_config.json and mirrors to candidate paths."""
        self.bot_token = bot_token.strip()
        self.chat_id = str(chat_id).strip()
        self.enabled = bool(self.bot_token and self.chat_id and enabled)
        self.send_telemetry_status_enabled = bool(send_telemetry_status)

        payload = {
            "bot_token": self.bot_token,
            "chat_id": self.chat_id,
            "enabled": self.enabled,
            "send_telemetry_status": self.send_telemetry_status_enabled,
            "notes": "Telegram credentials for Smart Grid SCADA. parse_mode: HTML."
        }

        # Write to all existing candidate directories
        for p in set(CANDIDATE_CONFIG_PATHS):
            d = os.path.dirname(p)
            if os.path.exists(d):
                try:
                    with open(p, "w", encoding="utf-8") as f:
                        json.dump(payload, f, indent=4)
                    if p == self.config_path:
                        self._last_mtime = os.path.getmtime(p)
                except Exception as e:
                    print(f"[Alerter] Error saving config to {p}: {e}")

    def _post_telegram_sync(self, html_message: str) -> bool:
        """Synchronously posts an HTML message to the Telegram Bot API."""
        self.reload_config_if_modified()
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
            if resp.status_code == 200:
                return True
            else:
                print(f"[Alerter] Telegram HTTP {resp.status_code}: {resp.text}")
                return False
        except Exception as e:
            print(f"[Alerter] Telegram send failed: {e}")
            return False

    def _worker_loop(self):
        """Background worker thread draining the dispatch queue asynchronously."""
        while True:
            try:
                msg_item = self._queue.get()
                if msg_item is None:
                    break
                html_msg = msg_item.get("html", "")
                if html_msg:
                    self._post_telegram_sync(html_msg)
                self._queue.task_done()
            except Exception as e:
                print(f"[Alerter] Background worker error: {e}")
                time.sleep(1.0)

    def enqueue_message(self, html_message: str, is_telemetry: bool = False):
        """Queues a message for background transmission without blocking caller."""
        # If queue is getting full, discard older telemetry status updates to preserve priority events
        if self._queue.qsize() > 100 and is_telemetry:
            return
        try:
            self._queue.put_nowait({"html": html_message, "is_telemetry": is_telemetry})
        except queue.Full:
            pass

    def send_telegram_message(self, message: str, is_html: bool = True) -> bool:
        """Direct backward-compatible send method."""
        if not is_html:
            message = html.escape(message)
        return self._post_telegram_sync(message)

    def trigger_alert(self, alert_type: str, title: str, details: str, severity: str = "INFO", force: bool = False) -> bool:
        """
        Dispatches an event alert with rate-limiting and HTML formatting.
        Severity: INFO, WARNING, CRITICAL, EMERGENCY, SUCCESS
        """
        now = time.time()
        last_time = self.last_alert_time.get(alert_type, 0.0)

        if not force and (now - last_time < self.cooldown_sec):
            return False

        self.last_alert_time[alert_type] = now
        timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        emoji_map = {
            "INFO": "ℹ️",
            "WARNING": "⚠️",
            "CRITICAL": "🚨",
            "EMERGENCY": "⛔",
            "SUCCESS": "✅"
        }
        icon = emoji_map.get(severity.upper(), "🔔")

        msg_html = (
            f"{icon} <b>SMART GRID ALERT: {html.escape(title)}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⏱ <b>Time:</b> <code>{timestamp_str}</code>\n"
            f"⚡ <b>Severity:</b> <b>{html.escape(severity.upper())}</b>\n"
            f"📝 <b>Details:</b>\n{details}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>Autonomous Self-Healing Grid Controller</i>"
        )

        # Enqueue for background delivery
        self.enqueue_message(msg_html, is_telemetry=False)

        # Console logging (Unicode safe for Windows cmd)
        status_note = "[Telegram Queued]" if self.enabled else "[Simulation Mode]"
        try:
            print(f"\n[ALERT DISPATCH] {status_note}\n{msg_html}\n")
        except UnicodeEncodeError:
            clean_msg = msg_html.encode('ascii', errors='replace').decode('ascii')
            print(f"\n[ALERT DISPATCH] {status_note}\n{clean_msg}\n")
        return True

    def send_grid_telemetry_status(self, row: dict, in_startup: bool = False, action_taken: str = ""):
        """
        Formats and dispatches the real-time 5-second status of the grid to Telegram.
        Presents measured vs predicted power/current, branch health, and control actions.
        """
        self.reload_config_if_modified()
        if not self.enabled or not self.send_telemetry_status_enabled:
            return

        now = time.time()
        if now - self.last_telemetry_time < self.min_telemetry_sec:
            return
        self.last_telemetry_time = now

        ts = row.get("timestamp", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        mode_str = str(row.get("mode", "SINGLE SMPS")).upper()
        limit = float(row.get("current_limit", 1000.0))
        tot_curr = float(row.get("total_current", 0.0))
        tot_pow_w = float(row.get("total_power", 0.0))
        if tot_pow_w > 100.0:
            tot_pow_w = tot_pow_w / 1000.0  # Convert mW to W if needed

        util_pct = (tot_curr / limit * 100.0) if limit > 0 else 0.0
        pred_curr = float(row.get("predicted_current", tot_curr))
        pred_pow_w = float(row.get("predicted_power", tot_pow_w))
        if pred_pow_w > 100.0:
            pred_pow_w = pred_pow_w / 1000.0

        healthy_cnt = row.get("healthy_loads_count", 3)
        on_cnt = row.get("loads_on_count", 5)
        branch_diag = row.get("branch_diagnostics", {})

        # Build load branch statuses
        branch_lines = []
        load_emojis = {
            "hospital": "🏥",
            "street": "🚦",
            "house": "🏠",
            "industry": "🏭",
            "critical": "🚨"
        }

        loads_order = ["hospital", "street", "house", "industry", "critical"]
        for l in loads_order:
            emoji = load_emojis.get(l, "🔹")
            name = l.capitalize()
            curr = float(row.get(f"{l}_current", 0.0))
            pow_w = float(row.get(f"{l}_power", 0.0))
            if pow_w > 100.0:
                pow_w = pow_w / 1000.0

            if l == "critical":
                relay_state = "FIX"
            else:
                relay_val = row.get(f"{l}_relay", 0)
                relay_state = "ON" if relay_val else "OFF"

            status = branch_diag.get(l, "NORMAL")
            # Format badge
            if "OVERCURRENT" in status:
                badge = "⛔ TRIP"
            elif "RELAY_OFF_CURRENT" in status or "STUCK" in status:
                badge = "⚠️ STUCK"
            elif "NO_CURRENT" in status or "OPEN" in status:
                badge = "⚠️ NO CURR"
            elif relay_state == "OFF":
                badge = "⚡ SHED"
            else:
                badge = "NORMAL"

            line = f"{emoji} <b>{name}:</b> <code>{curr:5.1f} mA</code> • {pow_w:4.2f} W [{relay_state} • {badge}]"
            branch_lines.append(line)

        branches_text = "\n".join(branch_lines)

        # Operational status line
        if in_startup:
            ctrl_line = "⚡ <b>Status:</b> STARTUP OBSERVATION"
        elif action_taken:
            ctrl_line = f"⚙️ <b>Action:</b> {html.escape(action_taken)}"
        else:
            ctrl_line = "⚙️ <b>Control:</b> AUTO • Grid Stable"

        card_html = (
            "⚡ <b>SMART GRID 2-SEC STATUS</b> ⚡\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"⏱ <b>Time:</b> <code>{html.escape(ts)}</code>\n"
            f"🔌 <b>Mode:</b> <code>{html.escape(mode_str)}</code> (Limit: <b>{limit:.0f} mA</b>)\n"
            f"📈 <b>Total Load:</b> <code>{tot_curr:.1f} mA</code> (<b>{util_pct:.1f}%</b>) | <b>{tot_pow_w:.2f} W</b>\n"
            f"🔮 <b>AI Forecast:</b> <code>{pred_curr:.1f} mA</code> | <b>{pred_pow_w:.2f} W</b>\n"
            f"🛡️ <b>Branches:</b> {healthy_cnt}/5 Active &amp; Healthy\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "<b>INDIVIDUAL BRANCHES:</b>\n"
            f"{branches_text}\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"{ctrl_line}"
        )

        self.enqueue_message(card_html, is_telemetry=True)

    def alert_actuation_event(self, action_type: str, load_name: str, reason: str, current_mA: float, limit_mA: float, details: str = ""):
        """
        Dispatches discrete grid actuation and protection events directly to Telegram.
        """
        action_type = str(action_type).upper()
        load_name = str(load_name).upper()

        if action_type == "TRIP":
            severity = "EMERGENCY"
            title = f"OVERCURRENT TRIP - {load_name}"
            body = (
                f"• <b>Branch:</b> <code>{load_name}</code> (ISOLATED)\n"
                f"• <b>Measured:</b> <code>{current_mA:.1f} mA</code>\n"
                f"• <b>Safety Threshold:</b> <code>{limit_mA:.1f} mA</code>\n"
                f"• <b>Reason:</b> {html.escape(reason)}\n"
                f"• <b>Info:</b> {html.escape(details)}"
            )
        elif action_type == "SHED":
            severity = "CRITICAL"
            title = f"CAPACITY LOAD SHED - {load_name}"
            body = (
                f"• <b>Branch Shed:</b> <code>{load_name}</code>\n"
                f"• <b>Grid Current:</b> <code>{current_mA:.1f} mA</code>\n"
                f"• <b>Capacity Limit:</b> <code>{limit_mA:.1f} mA</code>\n"
                f"• <b>Reason:</b> {html.escape(reason)}\n"
                f"• <b>Info:</b> {html.escape(details)}"
            )
        elif action_type == "RESTORE":
            severity = "SUCCESS"
            title = f"LOAD RESTORED - {load_name}"
            body = (
                f"• <b>Branch Reconnected:</b> <code>{load_name}</code>\n"
                f"• <b>Projected Total:</b> <code>{current_mA:.1f} mA</code>\n"
                f"• <b>Safe Limit:</b> <code>{limit_mA:.1f} mA</code>\n"
                f"• <b>Reason:</b> Safe headroom established\n"
                f"• <b>Info:</b> {html.escape(details)}"
            )
        elif action_type == "FAULT":
            severity = "CRITICAL"
            title = f"HARDWARE FAULT - {load_name}"
            body = (
                f"• <b>Branch:</b> <code>{load_name}</code>\n"
                f"• <b>Measured:</b> <code>{current_mA:.1f} mA</code>\n"
                f"• <b>Fault Diagnosis:</b> {html.escape(reason)}\n"
                f"• <b>Info:</b> {html.escape(details)}"
            )
        else:
            severity = "WARNING"
            title = f"CONTROL EVENT: {action_type} - {load_name}"
            body = (
                f"• <b>Action:</b> <code>{action_type}</code> on <code>{load_name}</code>\n"
                f"• <b>Current:</b> <code>{current_mA:.1f} mA</code>\n"
                f"• <b>Reason:</b> {html.escape(reason)}"
            )

        self.trigger_alert(
            alert_type=f"{action_type}_{load_name}",
            title=title,
            details=body,
            severity=severity,
            force=True
        )

    def alert_overcurrent_trip(self, load: str, current_mA: float, limit_mA: float):
        """Instant overcurrent isolation alert."""
        self.alert_actuation_event(
            action_type="TRIP",
            load_name=load,
            reason="Overcurrent 2-SD Baseline Exceeded",
            current_mA=current_mA,
            limit_mA=limit_mA,
            details="Branch isolated immediately for grid protection."
        )

    def alert_stuck_relay(self, load: str, current_mA: float, escalated_load: str = None):
        """Welded relay contact failure alert."""
        esc_note = f"Compensatory Shedding escalated to {escalated_load.upper()}" if escalated_load else "No secondary branch available"
        self.alert_actuation_event(
            action_type="FAULT",
            load_name=load,
            reason="STUCK_CLOSED (Relay contacts welded)",
            current_mA=current_mA,
            limit_mA=0.0,
            details=f"Current flows while relay commanded OFF. {esc_note}."
        )

    def alert_load_shed(self, load: str, utilization_pct: float, current_limit: float):
        """Automated capacity load shedding event."""
        self.alert_actuation_event(
            action_type="SHED",
            load_name=load,
            reason=f"Grid Utilization {utilization_pct:.1f}% >= 85%",
            current_mA=0.0,
            limit_mA=current_limit,
            details=f"Lower priority load shed to protect power sources."
        )

    def alert_load_restored(self, load: str, projected_util_pct: float):
        """Safe reconnection notice."""
        self.alert_actuation_event(
            action_type="RESTORE",
            load_name=load,
            reason=f"Safe Headroom (Projected load {projected_util_pct:.1f}% < 80%)",
            current_mA=0.0,
            limit_mA=0.0,
            details="Reconnection completed with healthy capacity headroom."
        )

    def alert_warning_tier(self, level: int, utilization_pct: float):
        """Advisory / Warning level transitions with rate-limiting."""
        if level == 1:
            self.trigger_alert(
                alert_type="WARN_LEVEL_1",
                title="MEDIUM OVERLOAD PROBABILITY",
                details=f"• <b>Grid Utilization:</b> <code>{utilization_pct:.1f}%</code> (>= 70%)\n• <b>Action:</b> Advisory notice, all loads operational.",
                severity="INFO"
            )
        elif level == 2:
            self.trigger_alert(
                alert_type="WARN_LEVEL_2",
                title="HIGH LOAD SHEDDING PROBABILITY",
                details=f"• <b>Grid Utilization:</b> <code>{utilization_pct:.1f}%</code> (>= 80%)\n• <b>Action:</b> Standby alert, automated shedding armed.",
                severity="WARNING"
            )

    def alert_manual_override(self, load: str, state: int):
        """Operator web manual actuation alert."""
        state_str = "ENERGIZED (ON)" if state == 1 else "DISCONNECTED (OFF)"
        self.trigger_alert(
            alert_type=f"MANUAL_{load.upper()}",
            title="MANUAL WEB ACTUATION",
            details=f"• <b>Load:</b> <code>{load.upper()}</code>\n• <b>Command:</b> <b>{state_str}</b>\n• <b>Source:</b> Remote Operator Web SCADA",
            severity="INFO",
            force=True
        )

    def alert_mode_change(self, new_mode: str):
        """Control mode switch alert."""
        self.trigger_alert(
            alert_type="MODE_CHANGE",
            title="CONTROL MODE SWITCH",
            details=f"• <b>New Mode:</b> <code>{new_mode.upper()}</code>\n• <b>Source:</b> Remote Web SCADA Operator",
            severity="WARNING",
            force=True
        )

    def send_test_alert(self) -> dict:
        """Sends a verification test message synchronously to confirm connection."""
        self.load_config()
        if not self.enabled:
            return {
                "success": False,
                "message": "Telegram credentials not configured or disabled in alert_config.json."
            }

        timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        test_html = (
            "🔔 <b>SMART GRID: SYSTEM TEST PING</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"⏱ <b>Time:</b> <code>{timestamp_str}</code>\n"
            "✅ <b>Status:</b> Operational & Connected\n"
            "📡 <b>Channel:</b> High-Speed HTML Push Notification\n"
            "⚡ <b>SCADA Engine:</b> 5-Second Telemetry & Event Alerter\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "<i>Smart Grid Autonomous Controller Ready!</i>"
        )
        ok = self._post_telegram_sync(test_html)
        return {
            "success": ok,
            "message": "Test ping delivered to your Telegram!" if ok else "Failed to send to Telegram. Check Bot Token and Chat ID."
        }

# Global singleton instance
alerter = GridAlerter()
