# iRacing Fair Share

Website frontend for theendurance fair-share calculator.

## Features
- Laps / Time / Hybrid fair-share modes
- Multiple drivers
- Minimum % of total race laps
- Maximum % of total race laps
- Maximum % of race laps per stint
- Automatic conversion to actual lap limits
- Live timer and stint tracking
- Driver swap log
- Recommended next driver
- Browser save/load
- Responsive desktop/tablet/mobile layout
- WebSocket endpoint for a local iRacing telemetry bridge

## Hosting
This is a static site. Put `index.html` in a GitHub repository and enable GitHub Pages.

## Automatic laps without iRacing

Enable **Estimate completed laps from the race timer**. While the timer is
running, the site adds one completed lap each time the configured average-lap
duration passes. Editing the current lap resets the estimate from that point.

## Local iRacing connector

On the Windows PC running iRacing, double-click
`connector/start-connector.bat`. Its first run creates a private Python
environment and installs `pyirsdk` and `aiohttp`. The connector opens the site
at `http://127.0.0.1:8080`; enter a race code and click **Join shared race**.
The website and WebSocket both use port 8080, which also allows one secure
tunnel to carry the complete app later.

When Cloudflare Tunnel is installed, the launcher also opens a **Fair Share
Public Tunnel** window. Copy its `https://...trycloudflare.com` address. On the
GitHub Pages calculator, change **Server WebSocket** to the same address with
`https://` replaced by `wss://` and `/ws` added, then join the same race code.
For example: `wss://example.trycloudflare.com/ws`.

Quick Tunnel addresses are temporary and change whenever the tunnel restarts.
Keep both connector windows open for the whole race.

The GitHub Pages copy remains useful for timer/manual mode. For live telemetry,
use the local page opened by the connector.

The server stores race-room state in `connector/fair_share.db` using SQLite.
Browsers using the same race code receive synchronized setup, laps, timer,
drivers, and stint logs. The connector also supplies completed laps, session
time, and the active driver name; website names should match iRacing names.

Example message:
```json
{"lap":123,"driverIndex":1,"elapsed":5321.4,"stintLaps":18}
```

The connector only works on the iRacing PC because the iRacing SDK exposes
telemetry through local Windows shared memory.


## Driver limit alerts

The race control panel and driver dashboard show a green **Minimum met**
confirmation once a driver's minimum laps are complete. Separate maximum-total
and maximum-stint counters turn amber with **5 laps remaining**, count down
through 4, 3, 2 and 1, and turn red at **LIMIT REACHED — 0 laps remaining**.
Exceeding a limit shows a red **LIMIT EXCEEDED** warning while preserving the
minimum achievement. A zero percentage keeps that maximum unlimited.

Alerts use the existing completed-lap source: telemetry, timer estimates or
manual lap entry. They are visual warnings; they do not control the car.

Run the limit boundary checks with `node tests/limit-alerts.cjs`.
