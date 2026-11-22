#!/usr/bin/env python3
"""
ThermoPro TP920 Bluetooth monitor -> ntfy.sh push alerts.

Runs on a laptop (macOS, Windows, Linux) or a Raspberry Pi. Connects to a TP920 over BLE (GATT), reads probe temperatures, logs a CSV row
every minute, and pushes alerts to your phone through ntfy.sh.

    python3 tp920_monitor.py                      # real thermometer
    python3 tp920_monitor.py --dry-run --no-notify  # fake data, print alerts
    python3 tp920_monitor.py --dry-run --speed 120  # fake data, real pushes, 120x time

Configuration comes from environment variables, optionally loaded from a
KEY=VALUE file (default: tp920.env next to this script). Real environment
variables override the file. See tp920.env.example for every setting.

CONVENIENCE MONITOR ONLY. It reports numbers; it never decides food is safe.
Verify doneness with an instant-read thermometer in several spots.
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import csv
import datetime as dt
import logging
import math
import os
import random
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Deque, Optional, Tuple

log = logging.getLogger("tp920")

# ---------------------------------------------------------------------------
# Protocol constants (from PaleFlyer/Thermopro_TP920W and
# daniel-corbett/thermopro-cli; confirm with discover.py on your unit)
# ---------------------------------------------------------------------------
SERVICE_UUID = "1086fff0-3343-4817-8bb2-b32206336ce8"
CMD_CHAR = "1086fff1-3343-4817-8bb2-b32206336ce8"   # read/write: commands to base
DATA_CHAR = "1086fff2-3343-4817-8bb2-b32206336ce8"  # read/notify: telemetry frames

# Every frame, both directions: [cmd][len][payload...][checksum]
# checksum = sum of all preceding bytes, mod 256.
LOGIN_CMD = bytes.fromhex("01098a7a13b73ed68b67c2a0")   # replayed app login
INFO_CMD = bytes.fromhex("410041")
UNIT_F_CMD = bytes.fromhex("20010f30")   # display Fahrenheit
UNIT_C_CMD = bytes.fromhex("20010c2d")   # display Celsius (inferred, unused)
ACK_CMD = bytes.fromhex("300030")        # the phone app sends this after each frame
CLOCK_EPOCH = 1577808000                 # 2020-01-01 00:00 at UTC+8

TELEMETRY = 0x30
# Byte offsets of each probe's 2-byte BCD value inside a 0x30 frame.
# TP920 layout (PaleFlyer): battery @2, unit flag @3, probe1 @7-8, probe2 @11-12.
# If discover.py shows your probe value somewhere else, change it here.
PROBE_OFFSETS = {1: 7, 2: 11}
BATTERY_OFFSET = 2
UNIT_OFFSET = 3

# ntfy priorities: 1=min 2=low 3=default 4=high 5=urgent (bypasses quiet modes)
PRIO_HEARTBEAT = 2   # silent-ish, shows in the list
PRIO_INFO = 3
PRIO_THRESHOLD = 4
PRIO_URGENT = 5


def make_frame(cmd: int, payload: bytes = b"") -> bytes:
    body = bytes([cmd, len(payload)]) + payload
    return body + bytes([sum(body) & 0xFF])


def clock_cmd(now: Optional[float] = None) -> bytes:
    secs = int(now if now is not None else time.time()) - CLOCK_EPOCH
    return make_frame(0x28, secs.to_bytes(4, "big"))


def decode_bcd_tenths(hi: int, lo: int) -> Optional[float]:
    """Decode 4 BCD digits as tenths of a degree. Returns None for no reading.

    ffff = probe unplugged, eeee/dddd = error/out-of-range markers. Any nibble
    above 9 is not valid BCD, so it is rejected instead of being turned into a
    huge or negative number.
    """
    if (hi, lo) in ((0xFF, 0xFF), (0xEE, 0xEE), (0xDD, 0xDD)):
        return None
    nibbles = (hi >> 4, hi & 0xF, lo >> 4, lo & 0xF)
    if any(n > 9 for n in nibbles):
        return None
    return (nibbles[0] * 1000 + nibbles[1] * 100 + nibbles[2] * 10 + nibbles[3]) / 10.0


@dataclass
class Telemetry:
    battery: int
    unit_flag: int
    probes: dict  # probe number -> temperature in WIRE units, or None


def parse_frame(data: bytes) -> Optional[Telemetry]:
    """Parse a 0x30 telemetry notification. Returns None for anything else."""
    if len(data) < 3 or data[0] != TELEMETRY:
        return None
    n = data[1]
    if len(data) < n + 3:
        log.debug("short frame: %s", data.hex())
        return None
    if (sum(data[: n + 2]) & 0xFF) != data[n + 2]:
        log.warning("checksum mismatch, ignoring frame %s", data.hex())
        return None
    probes = {}
    for p, off in PROBE_OFFSETS.items():
        probes[p] = decode_bcd_tenths(data[off], data[off + 1]) if off + 1 < n + 2 else None
    return Telemetry(battery=data[BATTERY_OFFSET], unit_flag=data[UNIT_OFFSET], probes=probes)


def c_to_f(c: float) -> float:
    return c * 9.0 / 5.0 + 32.0


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
def _floats(s: str) -> list:
    return sorted(float(x) for x in s.replace(" ", "").split(",") if x)


@dataclass
class Config:
    # --- ntfy ---
    ntfy_topic: str = ""                    # TP920_NTFY_TOPIC (required unless --no-notify)
    ntfy_server: str = "https://ntfy.sh"    # TP920_NTFY_SERVER
    ntfy_token: str = ""                    # TP920_NTFY_TOKEN (only for protected/self-hosted topics)
    # --- device ---
    address: str = ""                       # TP920_ADDRESS, e.g. AA:BB:CC:DD:EE:FF (blank = scan by name)
    name_prefixes: tuple = ("Thermo", "TP")  # TP920_NAME_PREFIXES
    probe: int = 1                          # TP920_PROBE: which probe is in the breast
    wire_unit: str = "C"                    # TP920_WIRE_UNIT: unit of raw probe values (C per community notes)
    send_ack: bool = True                   # TP920_SEND_ACK: mimic the app's per-frame ack
    data_timeout_s: float = 60.0            # TP920_DATA_TIMEOUT_SECONDS: poll/reconnect if silent this long
    log_raw: bool = False                   # TP920_LOG_RAW: log every raw frame (debugging)
    # --- alerts (edit these freely) ---
    thresholds_f: list = field(default_factory=lambda: [140.0, 150.0, 160.0, 165.0])  # TP920_THRESHOLDS_F
    threshold_rearm_f: float = 5.0          # TP920_THRESHOLD_REARM_F: drop this far below to re-arm
    stall_minutes: float = 30.0             # TP920_STALL_MINUTES
    stall_min_rise_f: float = 1.0           # TP920_STALL_MIN_RISE_F: rising less than this = "stalled"
    stall_min_temp_f: float = 100.0         # TP920_STALL_MIN_TEMP_F: ignore flat readings below this
    blind_minutes: float = 5.0              # TP920_BLIND_MINUTES: no reading this long = urgent alert
    heartbeat_minutes: float = 15.0         # TP920_HEARTBEAT_MINUTES (0 disables)
    # --- logging ---
    log_interval_s: float = 60.0            # TP920_LOG_INTERVAL_SECONDS
    csv_path: str = "tp920_log.csv"         # TP920_CSV_PATH


def load_env_file(path: Path) -> dict:
    """Minimal KEY=VALUE parser (same format systemd EnvironmentFile uses)."""
    out = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        if k.startswith("export "):
            k = k[7:].strip()
        out[k] = v.strip().strip('"').strip("'")
    return out


def load_config(path: Optional[str]) -> Config:
    env = {}
    p = Path(path) if path else Path(__file__).with_name("tp920.env")
    if p.exists():
        env.update(load_env_file(p))
        log.info("loaded config file %s", p)
    elif path:
        sys.exit(f"config file not found: {p}")
    env.update({k: v for k, v in os.environ.items() if k.startswith("TP920_")})

    c = Config()

    def get(key, conv, attr):
        if key in env and env[key] != "":
            try:
                setattr(c, attr, conv(env[key]))
            except ValueError:
                sys.exit(f"bad value for {key}: {env[key]!r}")

    truthy = lambda s: s.lower() in ("1", "true", "yes", "on")
    get("TP920_NTFY_TOPIC", str, "ntfy_topic")
    get("TP920_NTFY_SERVER", lambda s: s.rstrip("/"), "ntfy_server")
    get("TP920_NTFY_TOKEN", str, "ntfy_token")
    get("TP920_ADDRESS", str, "address")
    get("TP920_NAME_PREFIXES", lambda s: tuple(x.strip() for x in s.split(",") if x.strip()), "name_prefixes")
    get("TP920_PROBE", int, "probe")
    get("TP920_WIRE_UNIT", lambda s: s.strip().upper()[:1], "wire_unit")
    get("TP920_SEND_ACK", truthy, "send_ack")
    get("TP920_DATA_TIMEOUT_SECONDS", float, "data_timeout_s")
    get("TP920_LOG_RAW", truthy, "log_raw")
    get("TP920_THRESHOLDS_F", _floats, "thresholds_f")
    get("TP920_THRESHOLD_REARM_F", float, "threshold_rearm_f")
    get("TP920_STALL_MINUTES", float, "stall_minutes")
    get("TP920_STALL_MIN_RISE_F", float, "stall_min_rise_f")
    get("TP920_STALL_MIN_TEMP_F", float, "stall_min_temp_f")
    get("TP920_BLIND_MINUTES", float, "blind_minutes")
    get("TP920_HEARTBEAT_MINUTES", float, "heartbeat_minutes")
    get("TP920_LOG_INTERVAL_SECONDS", float, "log_interval_s")
    get("TP920_CSV_PATH", str, "csv_path")

    if c.probe not in PROBE_OFFSETS:
        sys.exit(f"TP920_PROBE must be one of {sorted(PROBE_OFFSETS)}")
    if c.wire_unit not in ("C", "F"):
        sys.exit("TP920_WIRE_UNIT must be C or F")
    return c


# ---------------------------------------------------------------------------
# Clock: real time normally; sped up in dry-run so you can test alerts fast
# ---------------------------------------------------------------------------
class Clock:
    def __init__(self, speed: float = 1.0):
        self.speed = speed
        self._real0 = time.monotonic()
        self._wall0 = time.time()

    def now(self) -> float:
        """Current (possibly simulated) epoch seconds."""
        return self._wall0 + (time.monotonic() - self._real0) * self.speed

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds / self.speed)

    def fmt(self, t: float) -> str:
        return dt.datetime.fromtimestamp(t).strftime("%H:%M")


# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------
HISTORY_KEEP_S = 90 * 60     # keep 90 min of samples (stall window + margin)
HISTORY_STEP_S = 10          # store at most one sample per 10 s


@dataclass
class State:
    started: float
    temp_f: Optional[float] = None          # latest valid reading
    temp_time: Optional[float] = None       # when it was taken
    battery: Optional[int] = None
    connected: bool = False
    probe_present: bool = False
    history: Deque[Tuple[float, float]] = field(default_factory=collections.deque)

    def add_reading(self, t: float, temp_f: float) -> None:
        self.temp_f, self.temp_time = temp_f, t
        self.probe_present = True
        if not self.history or t - self.history[-1][0] >= HISTORY_STEP_S:
            self.history.append((t, temp_f))
        while self.history and t - self.history[0][0] > HISTORY_KEEP_S:
            self.history.popleft()

    def rate_per_10min(self, now: float) -> Optional[float]:
        """Least-squares slope over the last 10 minutes, in degF per 10 min."""
        pts = [(t, f) for t, f in self.history if now - t <= 600]
        if len(pts) < 2 or pts[-1][0] - pts[0][0] < 120:   # need >= 2 min of data
            return None
        mt = sum(t for t, _ in pts) / len(pts)
        mf = sum(f for _, f in pts) / len(pts)
        den = sum((t - mt) ** 2 for t, _ in pts)
        if den == 0:
            return None
        return sum((t - mt) * (f - mf) for t, f in pts) / den * 600


def status_line(state: State, clock: Clock, cfg: Config) -> str:
    """Current temp + rate. Included in every message."""
    now = clock.now()
    rate = state.rate_per_10min(now)
    rate_s = f"{rate:+.1f}°F/10min" if rate is not None else "n/a"
    if state.temp_f is None:
        temp_s = "no reading yet"
    elif now - (state.temp_time or 0) > 90:
        temp_s = f"last {state.temp_f:.1f}°F at {clock.fmt(state.temp_time)} (no current reading)"
    else:
        temp_s = f"{state.temp_f:.1f}°F"
    s = f"Breast (probe {cfg.probe}): {temp_s}\nRate: {rate_s}"
    if state.battery is not None:
        s += f"\nBattery: {state.battery}%"
    return s


# ---------------------------------------------------------------------------
# ntfy.sh notifier
# ---------------------------------------------------------------------------
class Notifier:
    def __init__(self, cfg: Config, enabled: bool):
        self.cfg = cfg
        self.enabled = enabled

    async def send(self, title: str, body: str, priority: int = PRIO_INFO, tags: str = "") -> None:
        log.info("ALERT [p%d] %s | %s", priority, title, body.replace("\n", " | "))
        if not self.enabled:
            return
        for attempt in range(1, 4):
            try:
                await asyncio.to_thread(self._post, title, body, priority, tags)
                return
            except Exception as e:  # network down etc: log, retry, never crash
                log.warning("ntfy send failed (attempt %d/3): %s", attempt, e)
                await asyncio.sleep(5 * attempt)
        log.error("giving up on notification: %s", title)

    def _post(self, title: str, body: str, priority: int, tags: str) -> None:
        url = f"{self.cfg.ntfy_server}/{self.cfg.ntfy_topic}"
        headers = {
            # HTTP headers must be ASCII; the degree sign goes in the body only.
            "Title": title.encode("ascii", "replace").decode(),
            "Priority": str(priority),
        }
        if tags:
            headers["Tags"] = tags
        if self.cfg.ntfy_token:
            headers["Authorization"] = f"Bearer {self.cfg.ntfy_token}"
        req = urllib.request.Request(url, data=body.encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15) as r:
            if r.status >= 300:
                raise RuntimeError(f"HTTP {r.status}")


# ---------------------------------------------------------------------------
# Data sources: real BLE, or fake data for --dry-run
# ---------------------------------------------------------------------------
def handle_telemetry(tel: Telemetry, cfg: Config, state: State, clock: Clock) -> None:
    state.battery = tel.battery
    raw = tel.probes.get(cfg.probe)
    if raw is None:
        if state.probe_present:
            log.warning("probe %d reports no reading (unplugged?)", cfg.probe)
        state.probe_present = False
        return
    temp_f = raw if cfg.wire_unit == "F" else c_to_f(raw)
    if not state.probe_present:
        log.info("probe %d reading: %.1f°F", cfg.probe, temp_f)
    state.add_reading(clock.now(), temp_f)


async def find_device(cfg: Config):
    from bleak import BleakScanner
    if cfg.address:
        return await BleakScanner.find_device_by_address(cfg.address, timeout=20.0)
    prefixes = tuple(p.lower() for p in cfg.name_prefixes)
    return await BleakScanner.find_device_by_filter(
        lambda d, adv: (adv.local_name or d.name or "").lower().startswith(prefixes),
        timeout=20.0,
    )


async def ble_source(cfg: Config, state: State, clock: Clock) -> None:
    """Connect, handshake, stream. Reconnects forever with backoff."""
    from bleak import BleakClient

    loop = asyncio.get_running_loop()
    backoff = 2.0
    attempt = 0
    while True:
        attempt += 1
        try:
            log.info("searching for TP920 (attempt %d)...", attempt)
            device = await find_device(cfg)
            if device is None:
                raise RuntimeError("TP920 not found (off, out of range, or phone app connected?)")
            log.info("found %s (%s), connecting", device.name, device.address)

            disconnected = asyncio.Event()

            def on_disconnect(_client):
                loop.call_soon_threadsafe(disconnected.set)

            async with BleakClient(device, disconnected_callback=on_disconnect, timeout=30.0) as client:
                last_rx = time.monotonic()

                async def safe_ack():
                    try:
                        await client.write_gatt_char(CMD_CHAR, ACK_CMD, response=True)
                    except Exception as e:
                        log.debug("ack failed: %s", e)

                def on_notify(_sender, data: bytearray):
                    nonlocal last_rx
                    data = bytes(data)
                    if cfg.log_raw:
                        log.info("raw %s", data.hex(" "))
                    try:
                        tel = parse_frame(data)
                    except Exception:
                        log.exception("failed to parse %s", data.hex())
                        return
                    if tel is None:
                        return
                    last_rx = time.monotonic()
                    handle_telemetry(tel, cfg, state, clock)
                    if cfg.send_ack:
                        asyncio.ensure_future(safe_ack())

                await client.start_notify(DATA_CHAR, on_notify)
                # Startup handshake: login, info, set clock, set Fahrenheit display.
                for label, cmd in (("login", LOGIN_CMD), ("info", INFO_CMD),
                                   ("clock", clock_cmd()), ("unit F", UNIT_F_CMD)):
                    log.debug("write %s: %s", label, cmd.hex())
                    await client.write_gatt_char(CMD_CHAR, cmd, response=True)
                    await asyncio.sleep(0.3)

                state.connected = True
                log.info("connected and handshake sent")
                backoff = 2.0
                last_rx = time.monotonic()

                while not disconnected.is_set():
                    try:
                        await asyncio.wait_for(disconnected.wait(), timeout=5.0)
                    except asyncio.TimeoutError:
                        pass
                    if disconnected.is_set():
                        break
                    if time.monotonic() - last_rx > cfg.data_timeout_s:
                        # The base may only notify on change; poll once before
                        # deciding the link is dead.
                        log.info("no data for %.0f s, polling fff2", cfg.data_timeout_s)
                        val = bytes(await asyncio.wait_for(client.read_gatt_char(DATA_CHAR), 15))
                        tel = parse_frame(val)
                        if tel is None:
                            raise RuntimeError(f"no telemetry (poll returned {val.hex() or 'nothing'})")
                        handle_telemetry(tel, cfg, state, clock)
                        last_rx = time.monotonic()
                log.warning("TP920 disconnected")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.warning("BLE error: %s: %s", type(e).__name__, e)
        finally:
            state.connected = False

        log.info("reconnecting in %.0f s", backoff)
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, 30.0)


def fake_profile(minutes: float) -> Optional[float]:
    """Fake turkey-breast curve (degF) for dry-run, by elapsed minutes.

    0-60 min    rise from 40F at 0.8F/min
    60-68 min   simulated Bluetooth drop (returns None)  -> "blind" alert
    68-140 min  keep rising to ~150F
    140-200 min flat at ~150F                            -> stall alert
    200+ min    rise 0.5F/min to 172F and hold
    """
    if 60 <= minutes < 68:
        return None
    if minutes < 140:
        t = 40 + 0.8 * minutes
    elif minutes < 200:
        t = 152 + 0.3 * math.sin(minutes / 3)
    else:
        t = min(152 + 0.5 * (minutes - 200), 172)
    return t + random.uniform(-0.15, 0.15)


async def fake_source(cfg: Config, state: State, clock: Clock) -> None:
    log.info("DRY RUN: generating fake readings at %.0fx speed", clock.speed)
    state.battery = 88
    while True:
        minutes = (clock.now() - state.started) / 60
        t = fake_profile(minutes)
        if t is None:
            if state.connected:
                log.warning("DRY RUN: simulating Bluetooth disconnect")
            state.connected = False
        else:
            if not state.connected:
                log.info("DRY RUN: simulated connect")
            state.connected = True
            state.add_reading(clock.now(), t)
        await clock.sleep(5)


# ---------------------------------------------------------------------------
# CSV logger
# ---------------------------------------------------------------------------
async def csv_logger(cfg: Config, state: State, clock: Clock) -> None:
    path = Path(cfg.csv_path)
    new = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["timestamp", f"probe{cfg.probe}_f", "rate_f_per_10min", "connected", "battery_pct"])
        log.info("logging to %s every %.0f s", path.resolve(), cfg.log_interval_s)
        while True:
            await clock.sleep(cfg.log_interval_s)
            now = clock.now()
            fresh = state.temp_f is not None and now - (state.temp_time or 0) <= 90
            rate = state.rate_per_10min(now)
            w.writerow([
                dt.datetime.fromtimestamp(now).isoformat(timespec="seconds"),
                f"{state.temp_f:.1f}" if fresh else "",
                f"{rate:.2f}" if rate is not None else "",
                int(state.connected),
                state.battery if state.battery is not None else "",
            ])
            fh.flush()


# ---------------------------------------------------------------------------
# Alert engine
# ---------------------------------------------------------------------------
async def alert_engine(cfg: Config, state: State, clock: Clock, notifier: Notifier) -> None:
    status = lambda: status_line(state, clock, cfg)
    await notifier.send("TP920 monitor started",
                        f"Watching probe {cfg.probe}. Thresholds: "
                        + ", ".join(f"{t:g}°F" for t in cfg.thresholds_f) + "\n" + status(),
                        PRIO_INFO, "thermometer")

    alerted: set = set()           # thresholds already announced
    stall_alerted_at: Optional[float] = None   # temp when stall alert fired
    blind = False
    last_heartbeat = clock.now()

    while True:
        await clock.sleep(5)
        now = clock.now()
        cur = state.temp_f
        fresh = cur is not None and now - (state.temp_time or 0) <= 90

        # --- 1. Lost readings (Bluetooth down or probe unplugged) ---------------
        last_seen = state.temp_time or state.started
        if not blind and now - last_seen > cfg.blind_minutes * 60:
            blind = True
            why = ("Bluetooth connection to the TP920 is down." if not state.connected
                   else f"Connected, but probe {cfg.probe} reports no reading (unplugged?).")
            await notifier.send(f"NO READINGS for {cfg.blind_minutes:g}+ min",
                                f"{why} You are blind; check the smoker.\n{status()}",
                                PRIO_URGENT, "rotating_light")
        elif blind and fresh:
            blind = False
            await notifier.send("Readings are back", status(), PRIO_INFO, "white_check_mark")

        if not fresh:
            continue

        # --- 2. Threshold crossings -------------------------------------------
        # Each threshold fires once; it re-arms if the temp falls rearm_f below it.
        for t in cfg.thresholds_f:
            if t in alerted and cur < t - cfg.threshold_rearm_f:
                alerted.discard(t)
        crossed = [t for t in cfg.thresholds_f if t not in alerted and cur >= t]
        if crossed:
            alerted.update(crossed)
            await notifier.send(f"Breast reached {max(crossed):g}F",
                                f"Crossed {', '.join(f'{t:g}°F' for t in crossed)}.\n{status()}",
                                PRIO_THRESHOLD, "poultry_leg")

        # --- 3. Stall: no meaningful rise over the stall window ----------------
        window = cfg.stall_minutes * 60
        pts = [(t, f) for t, f in state.history if now - t <= window]
        covered = pts and pts[0][0] <= now - window + 60 and len(pts) >= 10
        if stall_alerted_at is not None and cur >= stall_alerted_at + 3 * cfg.stall_min_rise_f:
            log.info("temperature rising again; stall alert re-armed")
            stall_alerted_at = None
        if covered and stall_alerted_at is None and cur >= cfg.stall_min_temp_f:
            rise = max(f for _, f in pts) - pts[0][1]
            if rise < cfg.stall_min_rise_f:
                stall_alerted_at = cur
                await notifier.send(
                    f"Temp flat for {cfg.stall_minutes:g} min",
                    f"Rose only {rise:+.1f}°F in {cfg.stall_minutes:g} min. This may be the "
                    f"normal stall (evaporative cooling), or the fire/fuel may be dropping. "
                    f"Check the smoker temperature.\n{status()}",
                    PRIO_URGENT, "warning")

        # --- 4. Heartbeat --------------------------------------------------------
        if cfg.heartbeat_minutes > 0 and now - last_heartbeat >= cfg.heartbeat_minutes * 60:
            last_heartbeat = now
            extra = "\n(flat / possible stall)" if stall_alerted_at is not None else ""
            await notifier.send("TP920 heartbeat", status() + extra, PRIO_HEARTBEAT, "thermometer")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def _started_ok(proc: subprocess.Popen, name: str) -> None:
    time.sleep(1.0)  # give the helper a moment to fail if it's going to
    if proc.poll() is None:
        log.info("sleep blocked with %s (keep the lid open and the charger in)", name)
    else:
        log.warning("%s failed; disable sleep in your power settings instead", name)


def keep_awake() -> None:
    """Stop the computer from sleeping while the monitor runs (laptops!).

    A sleeping laptop drops Bluetooth and Wi-Fi, so you'd get no readings and
    no alerts. The block ends when this script exits. Closing the lid can
    still force sleep on most laptops, so keep it open and plugged in.
    """
    try:
        if sys.platform == "darwin":
            # caffeinate exits by itself when our PID exits.
            _started_ok(subprocess.Popen(["caffeinate", "-i", "-w", str(os.getpid())]), "caffeinate")
        elif sys.platform.startswith("win"):
            import ctypes
            ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
            log.info("sleep blocked via SetThreadExecutionState (keep the lid open)")
        elif shutil.which("systemd-inhibit"):
            # The inhibitor holds until `tail` sees our PID exit.
            _started_ok(subprocess.Popen(
                ["systemd-inhibit", "--what=sleep:idle", "--who=tp920-monitor",
                 "--why=Monitoring smoker", "tail", f"--pid={os.getpid()}", "-f", "/dev/null"],
                stderr=subprocess.DEVNULL), "systemd-inhibit")
        else:
            log.warning("can't block sleep on this system; disable sleep in power settings")
    except Exception as e:
        log.warning("could not block sleep (%s); disable sleep in power settings", e)


async def supervise(name: str, fn: Callable, *args) -> None:
    """Run a task forever; if it crashes, log the traceback and restart it."""
    while True:
        try:
            await fn(*args)
            log.error("task %s exited unexpectedly; restarting", name)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("task %s crashed; restarting in 5 s", name)
        await asyncio.sleep(5)


async def run(cfg: Config, dry_run: bool, speed: float, notify: bool) -> None:
    clock = Clock(speed if dry_run else 1.0)
    state = State(started=clock.now())
    notifier = Notifier(cfg, notify)
    source = fake_source if dry_run else ble_source
    await asyncio.gather(
        supervise("source", source, cfg, state, clock),
        supervise("csv", csv_logger, cfg, state, clock),
        supervise("alerts", alert_engine, cfg, state, clock, notifier),
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="ThermoPro TP920 BLE monitor with ntfy.sh alerts")
    ap.add_argument("--config", help="KEY=VALUE config file (default: tp920.env beside script)")
    ap.add_argument("--dry-run", action="store_true", help="use fake temperature data")
    ap.add_argument("--speed", type=float, default=60.0,
                    help="dry-run time multiplier (default 60: one simulated minute per second)")
    ap.add_argument("--no-notify", action="store_true", help="log alerts instead of sending them")
    ap.add_argument("--allow-sleep", action="store_true",
                    help="don't block system sleep (by default the monitor keeps the computer awake)")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    if not args.verbose:
        logging.getLogger("bleak").setLevel(logging.WARNING)

    cfg = load_config(args.config)
    if args.dry_run and "TP920_CSV_PATH" not in os.environ:
        cfg.csv_path = str(Path(cfg.csv_path).with_name("tp920_dryrun.csv"))
    if not args.no_notify and not cfg.ntfy_topic:
        sys.exit("Set TP920_NTFY_TOPIC (env or tp920.env), or pass --no-notify.")
    if not args.dry_run:
        try:
            import bleak  # noqa: F401
        except ImportError:
            sys.exit("bleak is not installed. Run: pip install bleak")
        if not args.allow_sleep:
            keep_awake()

    try:
        asyncio.run(run(cfg, args.dry_run, args.speed, not args.no_notify))
    except KeyboardInterrupt:
        log.info("stopped")


if __name__ == "__main__":
    main()
