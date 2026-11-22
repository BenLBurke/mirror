# ThermoPro TP920 Bluetooth Monitor

A laptop (macOS, Windows or Linux) or a Raspberry Pi sits near the smoker, connects to
the TP920 over Bluetooth LE, logs the breast probe to CSV, and pushes alerts
to your phone through [ntfy.sh](https://ntfy.sh) over Wi-Fi.

> **This is a convenience monitor only.** It reports numbers; it never tells
> you food is safe. Targets are 165 °F in the breast and about 175 °F in the
> thigh. Check several spots with an instant-read thermometer before you pull it.

| File | Purpose |
|---|---|
| `discover.py` | Step one: scan, dump GATT services, print raw notifications |
| `tp920_monitor.py` | Step two: the monitor (single file) |
| `tp920.env.example` | Every setting, with defaults. Copy it to `tp920.env` |
| `tp920-monitor.service` | systemd unit so the monitor starts on boot |

## 1a. Set up a laptop (macOS / Windows / Linux)

The laptop stays home within Bluetooth range of the smoker (about 10 m, and
fewer walls is better) and on your Wi-Fi. You can be anywhere with your phone.

**Install** Python 3.9 or newer from python.org (or Homebrew on a Mac), then in
this folder:

```bash
# macOS / Linux
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Windows (PowerShell)
py -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

In the commands below, use `.venv\Scripts\python` on Windows wherever this
README says `.venv/bin/python`.

**Keeping it awake matters most.** A sleeping laptop drops Bluetooth and Wi-Fi,
so you'd get no readings and no alerts. While running, the monitor blocks
idle sleep itself: `caffeinate` on macOS, `SetThreadExecutionState` on Windows,
`systemd-inhibit` on Linux. Turn this off with `--allow-sleep`. It can't stop
**lid-close** sleep, so:

* Keep the lid **open** and the laptop **plugged in**. You can turn the screen
  brightness all the way down.
* Windows: Settings → System → Power → set "When I close the lid" to *Do nothing* if you
  want to close it.
* macOS: grant Bluetooth access the first time. Allow your terminal app in
  System Settings → Privacy & Security → Bluetooth.
* macOS shows a UUID instead of a MAC address. If you set `TP920_ADDRESS`, use
  the value `discover.py` prints.

Skip the systemd section (step 6). On a laptop, just leave the terminal
window running during the cook.

## 1b. Or set up a Raspberry Pi

Any Pi with built-in Bluetooth works (3B+, 4, 5, Zero 2 W). These steps assume
Raspberry Pi OS Bookworm and the user `pi`.

```bash
sudo apt update
sudo apt install -y python3-venv bluez git
sudo usermod -aG bluetooth pi      # then log out and back in

# Put this folder at /home/pi/tp920-monitor (git clone, scp, or USB stick).
cd ~/tp920-monitor
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt   # installs bleak
```

Check that Bluetooth is up: `bluetoothctl show` should say `Powered: yes`. If
it doesn't, run `sudo rfkill unblock bluetooth`.

## 2. Run discovery (step one)

**Close the ThermoPro app on your phone**, or turn off the phone's Bluetooth.
The TP920 accepts only one connection at a time. Then:

```bash
.venv/bin/python discover.py
```

It scans for 15 s and lists any `Thermo*` or `TP*` devices. It then connects to
the closest one and prints every service and characteristic. After that it
subscribes to notifications, listens quietly for 10 s, sends the startup
handshake, and prints raw hex for 60 s. Where it can, it adds a decoded
reading next to each line. Warm the probe in your hand while it runs, and note
what the TP920 screen shows.

Paste the whole output back. Things to check:

* The `fff0` service is present, with `fff1` (read/write) and `fff2` (notify).
* After the handshake, `fff2` sends frames starting `30 0f`. The decoded
  `probe1` value should match the screen.
* If probe 1 decodes as `none(...)` while plugged in, the byte offsets are
  different on your unit. Change `PROBE_OFFSETS` near the top of
  `tp920_monitor.py`.

Options: `--address AA:BB:...`, `--listen 120`, `--no-handshake`.

## 3. Set up ntfy on your phone

1. Install the **ntfy** app (iOS App Store or Google Play). No account is needed.
2. Make up a long, hard-to-guess topic name, such as `turkey-7f3k9q2m`. Anyone
   who knows the name can read your alerts.
3. In the app, tap **+**, enter the topic, and subscribe. Leave the server as `ntfy.sh`.
4. Put the topic in your config:

   ```bash
   cp tp920.env.example tp920.env
   nano tp920.env        # set TP920_NTFY_TOPIC=turkey-7f3k9q2m
   ```
5. Test it: `curl -d "hello from the smoker" ntfy.sh/turkey-7f3k9q2m`

On iOS, allow notifications for ntfy. Urgent alerts use priority 5, which can
break through Focus modes if you allow it.

## 4. Test with a dry run (no thermometer needed)

```bash
.venv/bin/python tp920_monitor.py --dry-run --no-notify   # print alerts only
.venv/bin/python tp920_monitor.py --dry-run               # really push to your phone
.venv/bin/python tp920_monitor.py --dry-run --speed 600   # even faster
```

The dry run fakes a cook at 60× speed (one simulated minute per second). It
includes an 8-minute Bluetooth drop, which triggers the "blind" alert and then
"readings are back". Next comes a 60-minute flat spot at about 152 °F, which
triggers the stall alert. Along the way it crosses every threshold and sends
heartbeats. Dry-run rows go to `tp920_dryrun.csv`.

## 5. Run it for real

```bash
.venv/bin/python tp920_monitor.py        # Ctrl-C to stop
```

Each run does the following:

* Connects, logs in, sets the clock, sets the display to °F, and subscribes to
  temperature frames.
* Writes a CSV row to `tp920_log.csv` every 60 s, with columns `timestamp`,
  `probe1_f`, `rate_f_per_10min`, `connected` and `battery_pct`.
* Reconnects automatically with a 2 → 30 s backoff and logs every attempt. If
  no frame arrives for 60 s, it polls the data characteristic, and reconnects
  if that fails.

### Alerts

Every message includes the current temperature and the rate per 10 minutes.
The rate is a least-squares fit over the last 10 minutes of readings.

| Alert | When | ntfy priority |
|---|---|---|
| Started | on launch, so you know the pipeline works | default |
| Threshold | breast crosses 140, 150, 160, 165 °F (each once; re-arms if it drops 5 °F below) | high |
| Flat / stall | rose less than 1 °F in 30 min, once above 100 °F. Says it may be the normal stall | **urgent** |
| No readings | nothing valid for 5 min, whether from a lost connection or an unplugged probe | **urgent** |
| Readings back | first good reading after a "no readings" alert | default |
| Heartbeat | every 15 min | low |

All the numbers above are set in `tp920.env` (see `tp920.env.example`) or
through environment variables. Priorities and the protocol constants are at the
top of `tp920_monitor.py`.

## 6. (Pi / always-on Linux only) Start on boot with systemd

```bash
# Edit User= and the paths in the unit if you're not user "pi" in ~/tp920-monitor
sudo cp tp920-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tp920-monitor

systemctl status tp920-monitor
journalctl -u tp920-monitor -f        # live logs, including every reconnect
```

The unit restarts the script if it ever exits. To stop it during a cook so the
phone app can connect again, run `sudo systemctl stop tp920-monitor`.

## Protocol notes

These come from [PaleFlyer/Thermopro_TP920W](https://github.com/PaleFlyer/Thermopro_TP920W),
[daniel-corbett/thermopro-cli](https://github.com/daniel-corbett/thermopro-cli) and
[ble_monitor #902](https://github.com/custom-components/ble_monitor/issues/902).
The TP920 doesn't put readings in its advertisements, so the monitor has to
make a GATT connection.

* Service `1086fff0-…`. Commands are written to `fff1`; telemetry is notified on `fff2`.
* Frame layout: `[cmd][len][payload][checksum]`, where checksum = sum of the preceding bytes mod 256.
* Handshake, written to `fff1`:
  * login `01 09 8a 7a 13 b7 3e d6 8b 67 c2 a0`
  * info `41 00 41`
  * clock `28 04 <secs since 2020-01-01 UTC+8> <ck>`
  * Fahrenheit `20 01 0f 30`
* Telemetry frame: `30 0f <battery%> <unit 0f=F/0c=C> 00 ff ff <P1 hi> <P1 lo> ff ff <P2 hi> <P2 lo> ff ff ff ff <ck>`
* Probe values are 4 BCD digits in tenths of °C on the wire, whatever the
  display unit is. For example, `02 33` = 23.3 °C. `ff ff` means unplugged.
  `ee ee`, `dd dd` and any non-BCD nibble are treated as "no reading" and are
  never decoded as a number.
* Unconfirmed: whether the per-frame ack `30 00 30` is needed (it's sent by
  default; set `TP920_SEND_ACK=0` to stop), and whether the base streams
  continuously or only on change. The discovery output will settle both.

## Troubleshooting

* **"TP920 not found"**: check that the base is on, the phone app is closed,
  and the Pi is within about 10 m with few walls in between. Try
  `bluetoothctl scan on` to see if it's visible at all.
* **Connects but no readings**: set `TP920_LOG_RAW=1` and look at the frames
  with `journalctl -u tp920-monitor -f`.
* **`org.bluez.Error.InProgress` or similar**: run `sudo systemctl restart bluetooth`.
  The monitor reconnects on its own.
