"""Shared Fair Share server and authoritative iRacing team tracker."""
import asyncio
import json
import logging
from pathlib import Path
import sqlite3
import time
import webbrowser
from contextlib import contextmanager

from aiohttp import web
import irsdk
from team_tracking import TeamTracker, read_sample

HOST, PORT = '127.0.0.1', 8080
TICK_SECONDS = 0.25
ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(__file__).resolve().parent / 'fair_share.db'
ir = irsdk.IRSDK()
clients = {}
tracker = TeamTracker()
latest = {'connected': False, 'reason': 'Waiting for iRacing team telemetry'}


@contextmanager
def database():
    db = sqlite3.connect(DB_PATH)
    db.execute('CREATE TABLE IF NOT EXISTS races (code TEXT PRIMARY KEY, state TEXT NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)')
    db.execute('CREATE TABLE IF NOT EXISTS team_sessions (session_key TEXT PRIMARY KEY, state TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS room_cars (code TEXT PRIMARY KEY, car_key TEXT NOT NULL)')
    try:
        with db:
            yield db
    finally:
        db.close()


def load_state(room):
    with database() as db:
        row = db.execute('SELECT state FROM races WHERE code = ?', (room,)).fetchone()
    return json.loads(row[0]) if row else None


def save_state(room, state):
    with database() as db:
        db.execute('INSERT INTO races(code,state) VALUES(?,?) ON CONFLICT(code) DO UPDATE SET state=excluded.state, updated_at=CURRENT_TIMESTAMP', (room, json.dumps(state)))


def persist_tracker():
    if tracker.state:
        with database() as db:
            db.execute('INSERT OR REPLACE INTO team_sessions VALUES(?,?)', (tracker.state['key'], json.dumps(tracker.state)))


def clean_room(value):
    return (''.join(c for c in str(value).upper() if c.isalnum() or c in '_-') or 'WING24')[:20]


def telemetry_for(room):
    if not latest.get('carKey'):
        return latest
    with database() as db:
        row = db.execute('SELECT car_key FROM room_cars WHERE code=?', (room,)).fetchone()
        if not row and latest.get('connected'):
            db.execute('INSERT INTO room_cars VALUES(?,?)', (room, latest['carKey']))
        elif row and row[0] != latest['carKey']:
            return {'connected': False, 'reason': 'This race code belongs to a different car. Use a new race code for this team.'}
    return latest


def room_clients(room):
    return [socket for socket, joined in clients.items() if joined == room]


async def broadcast(room, payload, skip=None):
    payload = dict(payload, clients=len(room_clients(room)))
    for socket in room_clients(room):
        if socket is not skip and not socket.closed:
            try:
                await socket.send_json(payload)
            except (ConnectionError, RuntimeError):
                pass


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
            except (ValueError, TypeError):
                continue
            if not isinstance(data, dict):
                continue
            kind, room = data.get('type'), clean_room(data.get('room'))
            if kind == 'join':
                clients[socket] = room
                await socket.send_json({'type': 'joined', 'room': room, 'state': load_state(room), 'clients': len(room_clients(room))})
                await socket.send_json({'type': 'telemetry', 'data': telemetry_for(room)})
            elif kind == 'state' and clients.get(socket) == room and isinstance(data.get('state'), dict):
                # Browser settings cannot modify the separate authoritative ledger.
                save_state(room, data['state'])
                await broadcast(room, {'type': 'state', 'room': room, 'state': data['state']}, skip=socket)
                await broadcast(room, {'type': 'telemetry', 'data': telemetry_for(room)})
    finally:
        clients.pop(socket, None)
    return socket


async def telemetry_loop(app):
    global tracker, latest
    last_saved = 0
    while True:
        try:
            if not ir.is_initialized:
                ir.startup(test_file=None)
            elif not ir.is_connected:
                ir.shutdown()
            sample = None
            if ir.is_initialized and ir.is_connected:
                ir.freeze_var_buffer_latest()
                try:
                    sample = read_sample(ir)
                finally:
                    ir.unfreeze_var_buffer_latest()
            if sample:
                if not tracker.state or tracker.state['key'] != sample['key']:
                    persist_tracker()
                    with database() as db:
                        row = db.execute('SELECT state FROM team_sessions WHERE session_key=?', (sample['key'],)).fetchone()
                    tracker = TeamTracker(json.loads(row[0]) if row else None)
                before = (tracker.state or {}).get('lap'), (tracker.state or {}).get('driverId')
                latest = tracker.update(sample)
                changed = before != (sample['lap'], sample['driverId'])
                if changed or time.monotonic() - last_saved >= 1:
                    persist_tracker()
                    last_saved = time.monotonic()
            else:
                tracker.disconnect()
                latest = tracker.snapshot(False, 'Telemetry unavailable — totals held; no estimated laps added')
        except Exception:
            logging.exception('iRacing telemetry read failed; retrying')
            tracker.disconnect()
            latest = tracker.snapshot(False, 'Telemetry read failed — totals held; reconnecting')
        for room in set(r for r in clients.values() if r):
            await broadcast(room, {'type': 'telemetry', 'data': telemetry_for(room)})
        await asyncio.sleep(TICK_SECONDS)


async def start_background(app):
    app['telemetry'] = asyncio.create_task(telemetry_loop(app))


async def stop_background(app):
    app['telemetry'].cancel()
    await asyncio.gather(app['telemetry'], return_exceptions=True)
    persist_tracker()


def create_app():
    app = web.Application()
    app.router.add_get('/', lambda request: web.FileResponse(ROOT / 'index.html'))
    app.router.add_get('/ws', websocket_handler)
    # Never serve the SQLite database or the entire connector directory.
    app.router.add_get('/index.html', lambda request: web.FileResponse(ROOT / 'index.html'))
    app.on_startup.append(start_background)
    app.on_cleanup.append(stop_background)
    return app


def main():
    with database():
        pass
    url = f'http://{HOST}:{PORT}'
    print(f'Fair Share team tracker running at {url}')
    print('Keep this connector and iRacing connected throughout the race.')
    webbrowser.open(url)
    web.run_app(create_app(), host=HOST, port=PORT, print=None)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
