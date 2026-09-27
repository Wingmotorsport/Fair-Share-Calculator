"""HTTP/WebSocket integration with simulated SDK input; no iRacing required."""
import asyncio
import json
from pathlib import Path
import sys
import types
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'connector'))
class OfflineSDK:
    is_initialized = is_connected = False
    def startup(self, **kwargs): return False
    def shutdown(self): pass
sys.modules['irsdk'] = types.SimpleNamespace(IRSDK=OfflineSDK)
from aiohttp.test_utils import TestServer, TestClient
import iracing_connector as server
from team_tracking import TeamTracker
from test_team_tracking import sample


class ConnectorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db = Path(__file__).parent / ('test-'+uuid.uuid4().hex+'.db')
        server.DB_PATH = self.db
        server.clients.clear()
        server.tracker = TeamTracker()
        server.tracker.update(sample())
        server.latest = server.tracker.update(sample(1, 1))
        server.persist_tracker()
        app = server.create_app()
        app.on_startup.clear()  # Inject deterministic snapshots, not an SDK loop.
        app.on_cleanup.clear()
        self.client = TestClient(TestServer(app))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()
        # SQLite connections must be closed before cleanup on Windows.
        import gc
        gc.collect()
        self.db.unlink(missing_ok=True)

    async def join(self, room='TEST'):
        ws = await self.client.ws_connect('/ws')
        await ws.send_json({'type':'join','room':room})
        joined, data = await ws.receive_json(), await ws.receive_json()
        self.assertEqual(joined['type'], 'joined')
        return ws, data['data']

    async def test_two_clients_receive_identical_totals(self):
        a, first = await self.join()
        b, second = await self.join()
        self.assertEqual(first, second)
        self.assertEqual(first['drivers'][0]['laps'], 1)
        await a.close(); await b.close()

    async def test_browser_cannot_change_ledger(self):
        a, _ = await self.join()
        await a.send_json({'type':'state','room':'TEST','state':{'lap':999,'D':[{'laps':999}]}})
        msg = await a.receive_json()
        self.assertEqual(msg['type'], 'telemetry')
        self.assertEqual(msg['data']['lap'], 1)
        await a.close()

    async def test_different_car_does_not_enter_bound_room(self):
        a, _ = await self.join()
        server.latest = dict(server.latest, carKey='another-team')
        self.assertFalse(server.telemetry_for('TEST')['connected'])
        self.assertTrue(server.telemetry_for('NEW')['connected'])
        await a.close()

    async def test_database_and_connector_sources_are_not_public(self):
        for path in ['/connector/fair_share.db','/connector/iracing_connector.py','/../connector/fair_share.db']:
            response = await self.client.get(path)
            self.assertEqual(response.status,404)
        response = await self.client.get('/')
        self.assertEqual(response.status,200)

    async def test_ledger_persisted_separately(self):
        with server.database() as db:
            row = db.execute('SELECT state FROM team_sessions').fetchone()
        restored = TeamTracker(json.loads(row[0]))
        self.assertEqual(restored.snapshot()['drivers'][0]['laps'],1)


if __name__ == '__main__': unittest.main()
