"""
=============================================================================
Industrial Gas Telemetry & Supervisory Autonomous Bridge (Edge-to-Cloud)
Subsystem: Edge RTU Data Acquisition, Threshold Analyzer & SCADA Link
=============================================================================
"""

import os
import sys
import time
import json
import logging
import argparse
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    serial = None

try:
    import requests
except ImportError:
    print("[FATAL] Python 'requests' library missing. Install via: pip install requests pyserial")
    sys.exit(1)

# ---------------------------------------------------------------------------
# CONFIGURATION & INDUSTRIAL SETPOINTS
# ---------------------------------------------------------------------------
DEFAULT_COM_PORT = os.getenv("INDUSTRIAL_SERIAL_PORT", "COM3")
DEFAULT_BAUD_RATE = int(os.getenv("INDUSTRIAL_BAUD_RATE", "9600"))
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://wmiavglbygzevjueqwcr.supabase.co").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndtaWF2Z2xieWd6ZXZqdWVxd2NyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTMwMjkyMjMsImV4cCI6MjEwODYwNTIyM30.M4xwwRBtTP_epI-Y1gMFIhSqtjLHARAdPY8gA3JArCM")

# Gas concentration safety thresholds (parts per million)
THRESHOLD_NORMAL_MAX = 599      # PPM < 600
THRESHOLD_WARNING_MAX = 1000    # 600 <= PPM <= 1000
# CRITICAL: PPM > 1000

POLL_INTERVAL_SECS = 1.0        # Rate for supervisory actuator command sync
TELEMETRY_INTERVAL_SECS = 1.0   # Rate for pushing telemetry to cloud

# ---------------------------------------------------------------------------
# LOGGING SETUP
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [SCADA-BRIDGE] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("IndustrialBridge")


# ---------------------------------------------------------------------------
# SUPABASE REST API ADAPTER
# ---------------------------------------------------------------------------
class SupabaseIndustrialClient:
    """Lightweight, highly-resilient REST interface for Supabase Realtime DB."""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "apikey": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        })

    def is_configured(self) -> bool:
        return bool(self.base_url and self.api_key and not self.base_url.startswith("https://your-project"))

    def push_telemetry(self, ppm: int, status: str) -> bool:
        """Pushes discrete gas sensor telemetry sample to database."""
        if not self.is_configured():
            logger.debug("Cloud synchronization bypassed (Supabase credentials not configured).")
            return False

        endpoint = f"{self.base_url}/rest/v1/gas_telemetry"
        payload = {
            "ppm": ppm,
            "status": status,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        try:
            resp = self.session.post(endpoint, json=payload, timeout=3.5)
            if resp.status_code in (200, 201):
                return True
            logger.error(f"Failed to ingest telemetry payload: HTTP {resp.status_code} - {resp.text}")
        except Exception as exc:
            logger.error(f"Network transport fault during telemetry push: {exc}")
        return False

    def get_device_controls(self, device_id: int = 1) -> Optional[Dict[str, Any]]:
        """Polls supervisory setpoints and actuator states from cloud registry."""
        if not self.is_configured():
            return None

        endpoint = f"{self.base_url}/rest/v1/device_controls?id=eq.{device_id}&select=*"
        try:
            resp = self.session.get(endpoint, timeout=3.0)
            if resp.status_code == 200:
                rows = resp.json()
                return rows[0] if rows else None
            logger.error(f"Failed to fetch supervisory controls: HTTP {resp.status_code}")
        except Exception as exc:
            logger.error(f"Network transport fault during supervisory poll: {exc}")
        return None

    def update_device_controls(self, device_id: int, valve_state: str, fan_state: str) -> bool:
        """Publishes edge autonomous overrides to supervisory cloud registry."""
        if not self.is_configured():
            return False

        endpoint = f"{self.base_url}/rest/v1/device_controls?id=eq.{device_id}"
        payload = {
            "valve_state": valve_state,
            "fan_state": fan_state,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        try:
            resp = self.session.patch(endpoint, json=payload, timeout=3.5)
            return resp.status_code in (200, 204)
        except Exception as exc:
            logger.error(f"Failed to patch device controls: {exc}")
            return False


# ---------------------------------------------------------------------------
# HARDWARE SERIAL INTERFACE & MOCK TELEMETRY GENERATOR
# ---------------------------------------------------------------------------
class SerialRTUInterface:
    """Handles bidirectional RS-232/USB serial communication with Arduino Uno."""

    def __init__(self, port: str, baud: int, simulate: bool = False):
        self.port = port
        self.baud = baud
        self.simulate = simulate
        self.conn: Optional[Any] = None
        self._sim_ppm = 250
        self._sim_trend = 1

    def connect(self) -> bool:
        if self.simulate:
            logger.warning("[SIMULATION MODE] Operating synthetic hardware telemetry loop.")
            return True

        if serial is None:
            logger.error("pyserial package not installed. Defaulting to simulation mode.")
            self.simulate = True
            return True

        try:
            logger.info(f"Establishing RTU link on {self.port} @ {self.baud} baud...")
            self.conn = serial.Serial(
                port=self.port,
                baudrate=self.baud,
                timeout=1.0,
                write_timeout=1.0
            )
            time.sleep(2.0)  # Arduino DTR reset stabilization delay
            self.conn.reset_input_buffer()
            self.conn.reset_output_buffer()
            logger.info(f"Industrial RTU link active on {self.port}.")
            return True
        except Exception as err:
            logger.error(f"Unable to open physical port {self.port}: {err}")
            logger.warning("Failing over to synthetic simulation mode for continuous operations.")
            self.simulate = True
            return True

    def read_telemetry_line(self) -> Optional[int]:
        """Reads raw string from Arduino and parses integer gas concentration (PPM)."""
        if self.simulate:
            # Generate realistic industrial profile with intermittent spikes
            time.sleep(0.9)
            import random
            if random.random() < 0.08:
                self._sim_ppm = min(1400, self._sim_ppm + random.randint(180, 350))
            elif self._sim_ppm > 300:
                self._sim_ppm = max(200, self._sim_ppm - random.randint(40, 90))
            else:
                self._sim_ppm = max(180, min(550, self._sim_ppm + random.randint(-15, 20)))
            return int(self._sim_ppm)

        if not self.conn or not self.conn.is_open:
            return None

        try:
            raw_line = self.conn.readline().decode("utf-8", errors="ignore").strip()
            if not raw_line:
                return None

            # Support clean raw integer (e.g., "482") or prefixed (e.g., "PPM: 482")
            clean_digits = "".join(ch for ch in raw_line if ch.isdigit())
            if clean_digits:
                return int(clean_digits)
            logger.debug(f"Non-telemetry stream packet received: {raw_line}")
        except Exception as exc:
            logger.error(f"Serial stream read exception: {exc}")
        return None

    def write_actuator_command(self, command: str) -> bool:
        """Sends discrete machine control directive across serial interface."""
        formatted_cmd = f"{command.strip()}\n"
        if self.simulate:
            logger.info(f"[SIMULATED ACTUATOR] Command dispatched: {command.strip()}")
            return True

        if self.conn and self.conn.is_open:
            try:
                self.conn.write(formatted_cmd.encode("utf-8"))
                self.conn.flush()
                logger.info(f"[RTU ACTUATION] Successfully transmitted serial directive: {command.strip()}")
                return True
            except Exception as exc:
                logger.error(f"Serial write fault during command dispatch: {exc}")
        return False

    def close(self):
        if self.conn and self.conn.is_open:
            try:
                self.conn.close()
                logger.info("Serial communication interface closed.")
            except Exception:
                pass


# ---------------------------------------------------------------------------
# CORE PROCESS ORCHESTRATOR
# ---------------------------------------------------------------------------
def evaluate_threshold(ppm: int) -> str:
    """Evaluates OSHA/Industrial hazardous gas safety envelope."""
    if ppm < 600:
        return "NORMAL"
    elif ppm <= 1000:
        return "WARNING"
    else:
        return "CRITICAL"


def main():
    parser = argparse.ArgumentParser(description="Industrial Gas Telemetry & Supervisory Cloud Bridge")
    parser.add_argument("--port", default=DEFAULT_COM_PORT, help="Hardware COM port (e.g., COM3, /dev/ttyUSB0)")
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD_RATE, help="Serial baud rate (default: 9600)")
    parser.add_argument("--simulate", action="store_true", help="Force synthetic telemetry simulation mode")
    parser.add_argument("--url", default=SUPABASE_URL, help="Supabase Project API URL")
    parser.add_argument("--key", default=SUPABASE_KEY, help="Supabase Anon/Service-Role API Key")
    args = parser.parse_args()

    logger.info("=================================================================")
    logger.info(" HAZARDOUS GAS DETECTION & AUTONOMOUS CONTAINMENT BRIDGE ACTIVE ")
    logger.info("=================================================================")
    logger.info(f"Target Serial Port: {args.port} | Baud Rate: {args.baud}")

    cloud_client = SupabaseIndustrialClient(args.url, args.key)
    if cloud_client.is_configured():
        logger.info(f"Supabase Gateway Configured: {args.url}")
    else:
        logger.warning("Supabase credentials unpopulated. Running edge ingestion without cloud push.")
        logger.warning("Supply via environment variables SUPABASE_URL and SUPABASE_KEY or CLI arguments.")

    rtu = SerialRTUInterface(port=args.port, baud=args.baud, simulate=args.simulate)
    rtu.connect()

    last_poll_time = 0.0
    cached_valve_state: Optional[str] = None
    cached_fan_state: Optional[str] = None
    autonomous_containment_active = False

    try:
        while True:
            # 1. READ RAW SENSOR TELEMETRY FROM RTU
            ppm = rtu.read_telemetry_line()

            if ppm is not None:
                status = evaluate_threshold(ppm)
                logger.info(f"Gas Reading: {ppm:>4} PPM | Safety Envelope: [{status}]")

                # 2. AUTONOMOUS LOCAL SAFETY INTERLOCK (FAIL-SAFE CONTAINMENT)
                if status == "CRITICAL" and not autonomous_containment_active:
                    logger.critical(">>> CRITICAL GAS LEAKAGE DETECTED! INITIATING AUTONOMOUS CONTAINMENT <<<")
                    autonomous_containment_active = True
                    
                    # Direct hardware safety interlock commands
                    rtu.write_actuator_command("VALVE_CLOSED")
                    rtu.write_actuator_command("FAN_ON")

                    # Synchronize autonomous fail-safe state to supervisory cloud
                    cloud_client.update_device_controls(1, valve_state="CLOSED", fan_state="ON")
                    cached_valve_state = "CLOSED"
                    cached_fan_state = "ON"

                elif status == "NORMAL" and autonomous_containment_active:
                    logger.info("Telemetry returned to NORMAL. Containment interlock stabilized.")
                    autonomous_containment_active = False

                # 3. PUSH TELEMETRY SAMPLE TO CLOUD BUS
                cloud_client.push_telemetry(ppm, status)

            # 4. SUPERVISORY ACTUATION CONTROL DISPATCH & POLLING
            current_time = time.time()
            if current_time - last_poll_time >= POLL_INTERVAL_SECS:
                last_poll_time = current_time
                controls = cloud_client.get_device_controls(device_id=1)

                if controls:
                    remote_valve = controls.get("valve_state")
                    remote_fan = controls.get("fan_state")

                    # Detect supervisory state delta and dispatch to hardware
                    if remote_valve and remote_valve != cached_valve_state:
                        logger.info(f"[SUPERVISORY COMMAND] Pipeline Valve Override -> {remote_valve}")
                        command = f"VALVE_{remote_valve}"
                        rtu.write_actuator_command(command)
                        cached_valve_state = remote_valve

                    if remote_fan and remote_fan != cached_fan_state:
                        logger.info(f"[SUPERVISORY COMMAND] Ventilation Fan Override -> {remote_fan}")
                        command = f"FAN_{remote_fan}"
                        rtu.write_actuator_command(command)
                        cached_fan_state = remote_fan

    except KeyboardInterrupt:
        logger.info("Manual shutdown signal received. Halting bridge subsystems gracefully...")
    finally:
        rtu.close()
        logger.info("SCADA Bridge de-energized cleanly.")


if __name__ == "__main__":
    main()
