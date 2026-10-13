import time
import json
from typing import Dict, Any, Tuple, Set, List
try:
    from core.config import config
    from core.database import db
    from services.telegram_service import telegram
except ImportError:
    from src.core.config import config
    from src.core.database import db
    from src.services.telegram_service import telegram

class SafetyEngine:
    def __init__(self):
        self.system_start_time = None
        self.control_mode = "AUTO"  # "AUTO" or "MANUAL"

        self.commanded_relays = {
            "hospital": 1,
            "street": 1,
            "house": 1,
            "industry": 1
        }
        self.relay_turn_on_time = {l: 0.0 for l in self.commanded_relays}
        self.relay_turn_off_time = {l: 0.0 for l in self.commanded_relays}

        self.tripped_relays: Set[str] = set()
        self.stuck_relays: Set[str] = set()

        self.last_shed_time = 0.0
        self.last_restored_time = 0.0
        self.last_capacity_limit = None
        self.last_mode_transition_time = 0.0
        self.recent_actions: List[str] = []

    def evaluate_telemetry(self, row: dict, publish_cmd_fn) -> Tuple[bool, float, str]:
        now = time.time()
        if self.system_start_time is None:
            self.system_start_time = now
            for l in self.commanded_relays:
                self.relay_turn_on_time[l] = now

        elapsed = now - self.system_start_time
        in_startup = elapsed < config.startup_observe_sec
        startup_remaining = max(0.0, config.startup_observe_sec - elapsed)

        limit = float(row.get("current_limit", 5000.0))
        total_current = float(row.get("total_current", 0.0))

        # Detect sudden source transitions (e.g. Dual SMPS -> Single SMPS)
        if self.last_capacity_limit is not None and limit < (self.last_capacity_limit - 10.0):
            self.last_mode_transition_time = now
            action_msg = f"SOURCE DROP: {self.last_capacity_limit:.0f}mA -> {limit:.0f}mA (Settling 15s)"
            self.recent_actions.append(f"[{row['timestamp'][11:]}] {action_msg}")
        self.last_capacity_limit = limit

        utilization = (total_current / limit * 100.0) if limit > 0 else 0.0
        action_taken = None

        # 1. INSTANT 2-SD OVERCURRENT TRIPPING (ALWAYS ACTIVE, EVEN IN STARTUP/MANUAL)
        for load, thresh in config.thresh_2sd.items():
            if load == "critical":
                curr = row.get("critical_current", 0.0)
                if curr > thresh:
                    action_taken = f"CRITICAL OVERCURRENT! ({curr:.1f} mA > {thresh:.1f} mA)"
            else:
                curr = row.get(f"{load}_current", 0.0)
                if curr > thresh and load not in self.tripped_relays:
                    self.tripped_relays.add(load)
                    self.commanded_relays[load] = 0
                    self.relay_turn_off_time[load] = now
                    self.last_shed_time = now

                    cmd = {
                        "cmd": "TRIP",
                        "load": load,
                        "state": 0,
                        "reason": f"OVERCURRENT ({curr:.1f} mA > {thresh:.1f} mA)",
                        "timestamp": row["timestamp"]
                    }
                    publish_cmd_fn(cmd)
                    db.log_actuation("TRIP", load, "OVERCURRENT", curr, limit, f"Tripped: {curr:.1f}mA > {thresh:.1f}mA")
                    telegram.alert_actuation_event("TRIP", load, "OVERCURRENT", curr, limit)
                    action_taken = f"TRIPPED {load.upper()} (Overcurrent: {curr:.1f} mA > {thresh:.1f} mA)"
                    self.recent_actions.append(f"[{row['timestamp'][11:]}] TRIP {load.upper()}: {curr:.1f} mA > {thresh:.1f} mA")

        # 2. STUCK RELAY DETECTION (Welded contacts)
        for load in ["hospital", "street", "house", "industry"]:
            if self.commanded_relays[load] == 0:
                curr = row.get(f"{load}_current", 0.0)
                diag = row.get("branch_diagnostics", {}).get(load, "NORMAL")
                if curr > 25.0 or diag == "RELAY_OFF_CURRENT_DRAWN":
                    if load not in self.stuck_relays:
                        self.stuck_relays.add(load)
                        db.log_actuation("FAULT", load, "STUCK_CLOSED", curr, limit, "Relay commanded OFF but current still flows")
                        telegram.alert_actuation_event("FAULT", load, "STUCK_CLOSED", curr, limit)
                        self.recent_actions.append(f"[{row['timestamp'][11:]}] FAULT {load.upper()}: STUCK CLOSED ({curr:.1f} mA)")
                else:
                    self.stuck_relays.discard(load)

        # 3. GRADUATED WARNING TIERS
        warning_level = 0
        warning_message = "NORMAL"

        if len(self.tripped_relays) > 0 or len(self.stuck_relays) > 0:
            warning_level = 3
            parts = []
            if self.tripped_relays: parts.append(f"Tripped: {','.join(self.tripped_relays).upper()}")
            if self.stuck_relays: parts.append(f"Stuck: {','.join(self.stuck_relays).upper()}")
            warning_message = f"CRITICAL: HARDWARE FAULT [{'; '.join(parts)}]"
        elif limit > 0:
            if utilization >= config.shed_util_pct:
                warning_level = 3
                warning_message = f"CRITICAL: LOAD SHEDDING IN PROGRESS ({utilization:.1f}% >= 85%)"
            elif utilization >= config.high_load_util_pct:
                warning_level = 2
                warning_message = f"HIGH CAPACITY UTILIZATION ({utilization:.1f}% >= 80%)"
            elif utilization >= config.medium_load_util_pct:
                warning_level = 1
                warning_message = f"MEDIUM OVERLOAD PROBABILITY ({utilization:.1f}% >= 70%)"
            else:
                warning_level = 0
                warning_message = "NORMAL"

        telegram.alert_warning_tier(warning_level, utilization)

        # 4. CAPACITY CONTROL: AUTOMATED SHEDDING & PRIORITY RESTORATION
        if in_startup:
            pass  # Suppressed during observation window
        elif self.control_mode == "MANUAL":
            pass  # Suppressed in manual override mode
        else:
            # A. AUTOMATED SHEDDING (>= 85%)
            if utilization >= config.shed_util_pct and limit > 0:
                shed_order = ["industry", "house", "street", "hospital"]
                candidate_shed = None
                for cand in shed_order:
                    if self.commanded_relays[cand] == 1 and cand not in self.stuck_relays:
                        # 15s dwell check unless massive overload
                        on_dwell = now - self.relay_turn_on_time.get(cand, 0.0)
                        if on_dwell < config.relay_settling_sec and utilization < 100.0:
                            continue
                        candidate_shed = cand
                        break

                if candidate_shed:
                    self.commanded_relays[candidate_shed] = 0
                    self.relay_turn_off_time[candidate_shed] = now
                    self.last_shed_time = now

                    cmd = {
                        "cmd": "SHED",
                        "load": candidate_shed,
                        "state": 0,
                        "reason": f"OVERLOAD ({utilization:.1f}% >= 85%)",
                        "timestamp": row["timestamp"]
                    }
                    publish_cmd_fn(cmd)
                    cand_curr = row.get(f"{candidate_shed}_current", 0.0)
                    db.log_actuation("SHED", candidate_shed, "OVERLOAD_85", cand_curr, limit, f"Load {utilization:.1f}%")
                    telegram.alert_actuation_event("SHED", candidate_shed, "OVERLOAD_85", cand_curr, limit, f"Grid {utilization:.1f}%")
                    action_taken = f"SHED {candidate_shed.upper()} (Grid at {utilization:.1f}%)"
                    self.recent_actions.append(f"[{row['timestamp'][11:]}] SHED {candidate_shed.upper()}: Grid at {utilization:.1f}% >= 85%")

            # B. OPPORTUNISTIC PRIORITY PACKING RESTORATION (< 84%)
            elif utilization < config.max_restore_util_pct and limit > 0:
                since_shed = now - self.last_shed_time
                since_restore = now - self.last_restored_time
                since_transition = now - self.last_mode_transition_time

                if (since_restore >= config.restoration_settling_sec and
                    since_shed >= config.restoration_settling_sec and
                    since_transition >= config.restoration_settling_sec):

                    restore_order = ["hospital", "street", "house", "industry"]
                    candidate_to_restore = None
                    cand_proj_curr = 0.0
                    cand_proj_util = 0.0
                    skipped_loads = []

                    for cand in restore_order:
                        is_off = self.commanded_relays.get(cand, 0) == 0
                        is_healthy = (cand not in self.tripped_relays) and (cand not in self.stuck_relays)
                        off_dwell = now - self.relay_turn_off_time.get(cand, 0.0)

                        if is_off and is_healthy and (off_dwell >= config.relay_settling_sec):
                            projected_i = total_current + config.nominal_draws.get(cand, 250.0)
                            projected_u = (projected_i / limit) * 100.0

                            if projected_u <= config.max_restore_util_pct:
                                candidate_to_restore = cand
                                cand_proj_curr = projected_i
                                cand_proj_util = projected_u
                                break
                            else:
                                skipped_loads.append(f"{cand.upper()} ({projected_u:.1f}%)")

                    if candidate_to_restore:
                        cand = candidate_to_restore
                        self.commanded_relays[cand] = 1
                        self.relay_turn_on_time[cand] = now
                        self.last_restored_time = now

                        skip_note = f" [Bypassed {', '.join(skipped_loads)} to fit <= 84%]" if skipped_loads else ""
                        cmd = {
                            "cmd": "RESTORE",
                            "load": cand,
                            "state": 1,
                            "reason": f"HEADROOM_SAFE ({cand_proj_util:.1f}% <= {config.max_restore_util_pct}%){skip_note}",
                            "timestamp": row["timestamp"]
                        }
                        publish_cmd_fn(cmd)
                        db.log_actuation("RESTORE", cand, "HEADROOM_RESTORE", cand_proj_curr, limit, f"Projected {cand_proj_util:.1f}%{skip_note}")
                        telegram.alert_actuation_event("RESTORE", cand, "HEADROOM_RESTORE", cand_proj_curr, limit, f"Target {cand_proj_util:.1f}%")
                        action_taken = f"RESTORED {cand.upper()} (Grid -> {cand_proj_util:.1f}% <= 84%{skip_note})"
                        self.recent_actions.append(f"[{row['timestamp'][11:]}] RESTORE {cand.upper()}: Load -> {cand_proj_util:.1f}%{skip_note}")

        if len(self.recent_actions) > 10:
            self.recent_actions = self.recent_actions[-10:]

        row["warning_level"] = warning_level
        row["warning_message"] = warning_message
        return in_startup, startup_remaining, action_taken

safety_engine = SafetyEngine()
