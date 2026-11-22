#!/usr/bin/env python3
"""
Step one: ThermoPro TP920 BLE discovery.

What it does:
  1. Scans for BLE devices for 15 seconds and prints the name, address and
     RSSI of anything whose name starts with "Thermo" or "TP".
  2. Connects to the first match (or to --address).
  3. Lists every service and characteristic, and reads the readable ones.
  4. Subscribes to every notifiable characteristic and prints raw hex.
  5. After a short quiet period, sends the community-documented startup
     handshake (login, info request, clock, Fahrenheit) so the base starts
     streaming. Use --no-handshake to only listen passively.

Run it next to the smoker with the phone app CLOSED (the TP920 only accepts one
connection at a time), then paste the whole output back.

    python3 discover.py                 # scan + connect to first match
    python3 discover.py --address AA:BB:CC:DD:EE:FF
    python3 discover.py --listen 120    # listen longer after the handshake
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import platform
import sys

try:
    from bleak import BleakClient, BleakScanner
except ImportError:
    sys.exit("bleak is not installed. Run: pip install bleak")

NAME_PREFIXES = ("thermo", "tp")

# Community-documented TP920 UUIDs and commands (see README "Protocol").
CMD_CHAR = "1086fff1-3343-4817-8bb2-b32206336ce8"   # read/write: commands
DATA_CHAR = "1086fff2-3343-4817-8bb2-b32206336ce8"  # read/notify: telemetry


def frame(cmd: int, payload: bytes = b"") -> bytes:
    """[cmd][len][payload][checksum], checksum = sum of all bytes mod 256."""
    body = bytes([cmd, len(payload)]) + payload
    return body + bytes([sum(body) & 0xFF])


def handshake_commands() -> list[tuple[str, bytes]]:
    clock = int(dt.datetime.now().timestamp()) - 1577808000  # 2020-01-01 UTC+8
    return [
        ("login", bytes.fromhex("01098a7a13b73ed68b67c2a0")),
        ("info request", bytes.fromhex("410041")),
        ("set clock", frame(0x28, clock.to_bytes(4, "big"))),
        ("set Fahrenheit", bytes.fromhex("20010f30")),
    ]


def ts() -> str:
    return dt.datetime.now().strftime("%H:%M:%S.%f")[:-3]


def try_decode(data: bytes) -> str:
    """Best-effort decode of a 0x30 telemetry frame, printed beside the hex."""
    if len(data) < 3 or data[0] != 0x30:
        return ""
    n = data[1]
    if len(data) < n + 3:
        return "  (short frame)"
    ok = (sum(data[: n + 2]) & 0xFF) == data[n + 2]

    def bcd(hi: int, lo: int) -> str:
        nib = (hi >> 4, hi & 0xF, lo >> 4, lo & 0xF)
        if any(x > 9 for x in nib):
            return f"none({hi:02x}{lo:02x})"
        c = (nib[0] * 1000 + nib[1] * 100 + nib[2] * 10 + nib[3]) / 10
        return f"{c:.1f}C/{c * 9 / 5 + 32:.1f}F"

    p1 = bcd(data[7], data[8]) if len(data) > 8 else "?"
    p2 = bcd(data[11], data[12]) if len(data) > 12 else "?"
    unit = {0x0F: "F", 0x0C: "C"}.get(data[3], f"0x{data[3]:02x}")
    return (f"  -> checksum {'OK' if ok else 'BAD'}, battery {data[2]}%, "
            f"display {unit}, probe1 {p1}, probe2 {p2}")


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--address", help="connect to this MAC instead of first match")
    ap.add_argument("--scan", type=float, default=15.0, help="scan seconds (15)")
    ap.add_argument("--quiet", type=float, default=10.0,
                    help="seconds to listen before the handshake (10)")
    ap.add_argument("--listen", type=float, default=60.0,
                    help="seconds to listen after the handshake (60)")
    ap.add_argument("--no-handshake", action="store_true")
    args = ap.parse_args()

    print(f"# {dt.datetime.now().isoformat(timespec='seconds')}  python {platform.python_version()}"
          f"  {platform.platform()}")
    try:
        from importlib.metadata import version
        print(f"# bleak {version('bleak')}")
    except Exception:
        pass

    print(f"\n== Scanning for {args.scan:.0f} s ...")
    found = await BleakScanner.discover(timeout=args.scan, return_adv=True)
    matches = []
    for dev, adv in sorted(found.values(), key=lambda da: -(da[1].rssi or -999)):
        name = adv.local_name or dev.name or ""
        if name.lower().startswith(NAME_PREFIXES):
            matches.append(dev)
            print(f"  {name:<20} {dev.address}  RSSI {adv.rssi} dBm")
            if adv.manufacturer_data:
                for cid, val in adv.manufacturer_data.items():
                    print(f"      manufacturer 0x{cid:04x}: {val.hex()}")
            if adv.service_uuids:
                print(f"      service uuids: {', '.join(adv.service_uuids)}")
            if adv.service_data:
                for u, val in adv.service_data.items():
                    print(f"      service data {u}: {val.hex()}")
    print(f"  ({len(found)} BLE devices seen in total, {len(matches)} matched)")

    target = args.address or (matches[0] if matches else None)
    if target is None:
        sys.exit("\nNo ThermoPro found. Is the base on, in range, and the phone app closed?")

    print(f"\n== Connecting to {getattr(target, 'address', target)} ...")
    async with BleakClient(target, timeout=30.0) as client:
        print(f"  connected: {client.is_connected}")

        print("\n== Services and characteristics")
        notifiable = []
        for svc in client.services:
            print(f"  [service] {svc.uuid}  {svc.description}")
            for ch in svc.characteristics:
                props = ",".join(ch.properties)
                line = f"      [char] {ch.uuid}  handle {ch.handle}  ({props})"
                if "read" in ch.properties:
                    try:
                        val = await client.read_gatt_char(ch)
                        line += f"  value={val.hex()}"
                        if val and all(32 <= b < 127 for b in val):
                            line += f" '{val.decode()}'"
                    except Exception as e:  # some chars refuse reads; just note it
                        line += f"  read failed: {e}"
                print(line)
                for d in ch.descriptors:
                    print(f"          [desc] {d.uuid}  handle {d.handle}")
                if "notify" in ch.properties or "indicate" in ch.properties:
                    notifiable.append(ch)

        print("\n== Subscribing to notifications")
        for ch in notifiable:
            def cb(_sender, data: bytearray, uuid=ch.uuid):
                print(f"  {ts()}  {uuid[:8]}  {bytes(data).hex(' ')}{try_decode(bytes(data))}")
            try:
                await client.start_notify(ch, cb)
                print(f"  subscribed {ch.uuid}")
            except Exception as e:
                print(f"  could not subscribe {ch.uuid}: {e}")

        print(f"\n== Listening {args.quiet:.0f} s before any writes (passive)")
        await asyncio.sleep(args.quiet)

        if not args.no_handshake:
            if client.services.get_characteristic(CMD_CHAR) is None:
                print(f"\n!! {CMD_CHAR} not present; skipping handshake")
            else:
                print("\n== Sending handshake to fff1")
                for label, cmd in handshake_commands():
                    print(f"  {ts()}  write {label:<15} {cmd.hex(' ')}")
                    try:
                        await client.write_gatt_char(CMD_CHAR, cmd, response=True)
                    except Exception as e:
                        print(f"     write failed: {e}")
                    await asyncio.sleep(0.5)

        print(f"\n== Listening {args.listen:.0f} s (plug/unplug a probe or warm it in your hand)")
        await asyncio.sleep(args.listen)

        if client.services.get_characteristic(DATA_CHAR) is not None:
            try:
                val = await client.read_gatt_char(DATA_CHAR)
                print(f"\n== Final read of fff2: {val.hex(' ')}{try_decode(bytes(val))}")
            except Exception as e:
                print(f"\n== Final read of fff2 failed: {e}")
    print("\nDone. Paste everything above back, plus what the TP920 screen showed.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
