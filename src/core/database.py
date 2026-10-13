import os
import sqlite3
import datetime
from typing import List, Dict, Any, Optional
try:
    from core.config import config
except ImportError:
    from src.core.config import config

class DatabaseManager:
    def __init__(self, db_path: str = config.db_path):
        self.db_path = db_path
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for zero-lock concurrent multi-threaded reads/writes
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
        except Exception:
            pass
        return conn

    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS telemetry_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    mode TEXT,
                    current_limit REAL,
                    hospital_relay INTEGER,
                    hospital_current REAL,
                    street_relay INTEGER,
                    street_current REAL,
                    house_relay INTEGER,
                    house_current REAL,
                    industry_relay INTEGER,
                    industry_current REAL,
                    critical_current REAL,
                    total_current REAL,
                    total_power REAL,
                    predicted_current REAL,
                    predicted_power REAL,
                    fault_detected INTEGER,
                    fault_load TEXT,
                    fault_type TEXT,
                    severity TEXT,
                    warning_level INTEGER,
                    warning_message TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS grid_actuation_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    action_type TEXT,
                    load_name TEXT,
                    reason TEXT,
                    current_mA REAL,
                    limit_mA REAL,
                    details TEXT
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_ts ON telemetry_logs (timestamp);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_actuation_ts ON grid_actuation_events (timestamp);")
            conn.commit()

    def log_telemetry(self, row: dict) -> bool:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO telemetry_logs (
                        timestamp, mode, current_limit,
                        hospital_relay, hospital_current,
                        street_relay, street_current,
                        house_relay, house_current,
                        industry_relay, industry_current,
                        critical_current, total_current, total_power,
                        predicted_current, predicted_power,
                        fault_detected, fault_load, fault_type, severity,
                        warning_level, warning_message
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    row.get("timestamp", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                    row.get("mode", "DUAL SMPS"),
                    row.get("current_limit", 5000.0),
                    row.get("hospital_relay", 1),
                    row.get("hospital_current", 0.0),
                    row.get("street_relay", 1),
                    row.get("street_current", 0.0),
                    row.get("house_relay", 1),
                    row.get("house_current", 0.0),
                    row.get("industry_relay", 1),
                    row.get("industry_current", 0.0),
                    row.get("critical_current", 0.0),
                    row.get("total_current", 0.0),
                    row.get("total_power", 0.0),
                    row.get("predicted_current", 0.0),
                    row.get("predicted_power", 0.0),
                    row.get("fault_detected", 0),
                    row.get("fault_load", "NONE"),
                    row.get("fault_type", "NORMAL"),
                    row.get("severity", "NONE"),
                    row.get("warning_level", 0),
                    row.get("warning_message", "NORMAL")
                ))
                conn.commit()
                return True
        except Exception as e:
            print(f"[Database] Error logging telemetry: {e}")
            return False

    def log_actuation(self, action_type: str, load_name: str, reason: str, current_mA: float, limit_mA: float, details: str = "") -> bool:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("""
                    INSERT INTO grid_actuation_events (timestamp, action_type, load_name, reason, current_mA, limit_mA, details)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (ts, action_type, load_name, reason, current_mA, limit_mA, details))
                conn.commit()
                return True
        except Exception as e:
            print(f"[Database] Error logging actuation event: {e}")
            return False

    def get_latest_telemetry(self) -> Optional[Dict[str, Any]]:
        try:
            with self.get_connection() as conn:
                row = conn.execute("SELECT * FROM telemetry_logs ORDER BY id DESC LIMIT 1").fetchone()
                return dict(row) if row else None
        except Exception as e:
            print(f"[Database] Error reading latest telemetry: {e}")
            return None

    def get_recent_history(self, limit: int = 35) -> List[Dict[str, Any]]:
        try:
            with self.get_connection() as conn:
                rows = conn.execute(
                    "SELECT timestamp, current_limit, total_current, predicted_current, hospital_current, street_current, house_current, industry_current, critical_current "
                    "FROM telemetry_logs ORDER BY id DESC LIMIT ?", (limit,)
                ).fetchall()
                points = []
                for r in reversed(rows):
                    ts = str(r["timestamp"] or "")
                    clean_time = ts[-8:] if len(ts) >= 8 else ts
                    tot_i = max(0.0, round(float(r["total_current"] or 0.0), 1))
                    pred_i = max(0.0, round(float(r["predicted_current"] if ("predicted_current" in r.keys() and r["predicted_current"] is not None) else tot_i), 1))
                    points.append({
                        "time": clean_time,
                        "total_current": tot_i,
                        "predicted_current": pred_i,
                        "limit": float(r["current_limit"] or 1000.0),
                        "hospital": max(0.0, round(float(r["hospital_current"] or 0.0), 1)),
                        "street": max(0.0, round(float(r["street_current"] or 0.0), 1)),
                        "house": max(0.0, round(float(r["house_current"] or 0.0), 1)),
                        "industry": max(0.0, round(float(r["industry_current"] or 0.0), 1)),
                        "critical": max(0.0, round(float(r["critical_current"] or 0.0), 1)),
                    })
                return points
        except Exception as e:
            print(f"[Database] Error reading history: {e}")
            return []

    def get_recent_events(self, limit: int = 20) -> List[Dict[str, Any]]:
        try:
            with self.get_connection() as conn:
                rows = conn.execute(
                    "SELECT id, timestamp, action_type, load_name, reason, current_mA, limit_mA, details "
                    "FROM grid_actuation_events ORDER BY id DESC LIMIT ?", (limit,)
                ).fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            print(f"[Database] Error reading events: {e}")
            return []

db = DatabaseManager()
