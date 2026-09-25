"""Shared Fair Share server, SQLite store, and local iRacing connector."""

import asyncio
import json
from pathlib import Path
import sqlite3
import webbrowser

from aiohttp import web
import irsdk

HOST = "127.0.0.1"
PORT = 8080
TICK_SECONDS = 0.25
ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(__file__).resolve().parent / "fair_share.db"

ir = irsdk.IRSDK()
clients = {}
active_driver = None
stint_start_lap = 0


def database():
    db = sqlite3.connect(DB_PATH)
    db.execute("CREATE TABLE IF NOT EXISTS races (code TEXT PRIMARY KEY, state TEXT NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)")
    return db


def load_state(room):
    with database() as db:
        row = db.execute("SELECT state FROM races WHERE code = ?", (room,)).fetchone()
    return json.loads(row[0]) if row else None


def save_state(room, state):
    encoded = json.dumps(state, separators=(",", ":"))
    with database() as db:
        db.execute("INSERT INTO races(code,state) VALUES(?,?) ON CONFLICT(code) DO UPDATE SET state=excluded.state, updated_at=CURRENT_TIMESTAMP", (room, encoded))


def clean_room(value):
    value = "".join(c for c in str(value).upper() if c.isalnum() or c in "_-")
    return (value or "WING24")[:20]


def current_driver_name():
    info = ir["DriverInfo"] or {}
    car_idx = info.get("DriverCarIdx")
    for driver in info.get("Drivers", []):
        if driver.get("CarIdx") == car_idx:
            return driver.get("UserName") or driver.get("AbbrevName")
    return None


def telemetry_snapshot():
    global active_driver, stint_start_lap
    if not ir.is_initialized or not ir.is_connected:
        active_driver = None
        return {"connected": False}
    completed, elapsed = ir["LapCompleted"], ir["SessionTime"]
    lap = int(completed) if isinstance(completed, (int, float)) else 0
    driver = current_driver_name()
    if active_driver != driver:
        active_driver, stint_start_lap = driver, lap
    return {"connected": True, "lap": lap, "elapsed": float(elapsed) if isinstance(elapsed, (int, float)) else 0, "driverName": driver, "stintLaps": max(0, lap - stint_start_lap)}


def room_clients(room):
    return [socket for socket, joined in clients.items() if joined == room]


async def broadcast(room, payload, skip=None):
    targets = room_clients(room)
    payload["clients"] = len(targets)
    encoded = json.dumps(payload)
    for socket in targets:
        if socket is not skip and not socket.closed:
            await socket.send_str(encoded)


async def websocket_handler(request):
    socket = web.WebSocketResponse(heartbeat=20)
    await socket.prepare(request)
    clients[socket] = None
    try:
        async for message in socket:
            if message.type != web.WSMsgType.TEXT:
                continue
            try:
                data = json.loads(message.data)
            except json.JSONDecodeError:
                continue
            kind, room = data.get("type"), clean_room(data.get("room"))
            if kind == "join":
                clients[socket] = room
                state = load_state(room)
                await socket.send_json({"type": "joined", "room": room, "state": state, "clients": len(room_clients(room))})
                await broadcast(room, {"type": "state", "room": room, "state": state}, skip=socket)
            elif kind == "state" and clients.get(socket) == room and isinstance(data.get("state"), dict):
                save_state(room, data["state"])
                await broadcast(room, {"type": "state", "room": room, "state": data["state"]}, skip=socket)
    finally:
        room = clients.pop(socket, None)
        if room:
            await broadcast(room, {"type": "state", "room": room, "state": load_state(room)})
    return socket


async def telemetry_loop(app):
    while True:
        if not ir.is_initialized:
            ir.startup(test_file=None)
        elif not ir.is_connected:
            ir.shutdown()
        payload = {"type": "telemetry", "data": telemetry_snapshot()}
        for room in set(room for room in clients.values() if room):
            await broadcast(room, payload.copy())
        await asyncio.sleep(TICK_SECONDS)


async def start_background(app):
    app["telemetry"] = asyncio.create_task(telemetry_loop(app))


async def stop_background(app):
    app["telemetry"].cancel()
    await asyncio.gather(app["telemetry"], return_exceptions=True)


def main():
    database().close()
    app = web.Application()
    app.router.add_get("/", lambda _request: web.FileResponse(ROOT / "index.html"))
    app.router.add_get("/ws", websocket_handler)
    app.router.add_static("/", ROOT)
    app.on_startup.append(start_background)
    app.on_cleanup.append(stop_background)
    url = f"http://{HOST}:{PORT}"
    print(f"Fair Share shared server running at {url}")
    print(f"Race data is stored in {DB_PATH}")
    webbrowser.open(url)
    web.run_app(app, host=HOST, port=PORT, print=None)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
