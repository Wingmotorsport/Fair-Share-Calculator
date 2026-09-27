"""SDK-independent, persistent team lap accounting.

Unknown history and gaps are unallocated rather than attributed by guessing.
"""
import copy
import math


def valid_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def read_sample(sdk):
    """Read the connected team's car, not the spectator camera's car."""
    def get(key, default=None):
        try:
            value = sdk[key]
            return default if value is None else value
        except (KeyError, TypeError, IndexError):
            return default

    if not sdk.is_initialized or not sdk.is_connected:
        return None
    if get('IsReplayPlaying', False):
        return None
    info, weekend = get('DriverInfo', {}), get('WeekendInfo', {})
    idx = get('PlayerCarIdx', info.get('DriverCarIdx'))
    if not isinstance(idx, int) or idx < 0:
        return None
    candidates = [d for d in info.get('Drivers', []) if d.get('CarIdx') == idx and not d.get('CarIsPaceCar')]
    # A car must resolve to one active driver; never choose an arbitrary name.
    if len(candidates) != 1:
        return None
    driver = candidates[0]
    uid = driver.get('UserID')
    if not isinstance(uid, int) or uid <= 0:
        return None
    laps = get('CarIdxLapCompleted', [])
    lap = laps[idx] if idx < len(laps) else None
    elapsed, session_num = get('SessionTime'), get('SessionNum')
    session_id = weekend.get('SubSessionID') or weekend.get('SessionID')
    if not session_id or not isinstance(session_num, int):
        return None
    if not valid_number(lap) or lap < 0 or not valid_number(elapsed) or elapsed < 0:
        return None
    sessions = get('SessionInfo', {}).get('Sessions', [])
    session = next((s for s in sessions if s.get('SessionNum') == session_num), {})
    team = driver.get('TeamID', 0)
    car_key = f"{team}:{driver.get('CarNumber', idx)}:{driver.get('CarID', '')}"
    return {'key': f'{session_id}:{session_num}:{car_key}', 'carKey': car_key,
            'sessionType': session.get('SessionType', 'Session'),
            'teamName': driver.get('TeamName') or 'iRacing team',
            'carNumber': str(driver.get('CarNumber', idx)),
            'track': weekend.get('TrackDisplayName') or weekend.get('TrackName', ''),
            'driverId': str(uid), 'driverName': driver.get('UserName') or str(uid),
            'lap': int(lap), 'elapsed': float(elapsed)}


class TeamTracker:
    def __init__(self, saved=None):
        self.state = copy.deepcopy(saved)
        self.continuous = False

    def disconnect(self):
        self.continuous = False

    def update(self, sample):
        if sample is None:
            self.disconnect()
            return None
        if not self.state or self.state['key'] != sample['key']:
            self.state = {**sample, 'drivers': {}, 'unallocated': sample['lap'],
                          'stintLaps': 0, 'stintSeconds': 0, 'logs': [], 'events': [],
                          'partialStint': sample['lap'] > 0}
            self.continuous = False
        s = self.state
        if sample['lap'] < s['lap'] or sample['elapsed'] < s['elapsed']:
            # Ignore stale/replayed packets; a real session change has a new key.
            self.disconnect()
            return self.snapshot(False, 'Waiting for a current telemetry sample')
        uid, old_uid = sample['driverId'], s['driverId']
        for driver_id, name in [(old_uid, s['driverName']), (uid, sample['driverName'])]:
            s['drivers'].setdefault(driver_id, {'id': driver_id, 'name': name, 'laps': 0, 'time': 0, 'stints': 0})
            s['drivers'][driver_id]['name'] = name
        delta = sample['lap'] - s['lap']
        seconds = sample['elapsed'] - s['elapsed']
        gap = not self.continuous or seconds > 5
        swap = uid != old_uid
        if gap or swap:
            # A lap first observed with a different driver cannot be assigned safely.
            s['unallocated'] += delta
        else:
            s['drivers'][uid]['laps'] += delta
            s['drivers'][uid]['time'] += seconds
            s['stintLaps'] += delta
            s['stintSeconds'] += seconds
            if delta:
                s['events'].insert(0, f"Lap {sample['lap']} credited to {sample['driverName']}")
        if swap:
            if gap or delta:
                s['partialStint'] = True
            previous = s['drivers'][old_uid]
            previous['stints'] += 1
            s['logs'].append({'driver': previous['name'], 'driverId': old_uid,
                              'laps': s['stintLaps'], 'duration': s['stintSeconds'],
                              'partial': s['partialStint'], 'totalLaps': previous['laps']})
            s['stintLaps'] = 0
            s['stintSeconds'] = 0
            s['partialStint'] = bool(gap or delta)
            s['events'].insert(0, f"Driver change: {previous['name']} → {sample['driverName']}")
        elif gap and (delta or seconds):
            # Stint may include missed laps or unseen swaps. Retain confirmed totals.
            s['partialStint'] = True
        if delta and (gap or swap):
            s['events'].insert(0, f'{delta} lap(s) unallocated: telemetry gap or driver-change boundary')
        s.update(sample)
        s['events'] = s['events'][:8]
        self.continuous = True
        return self.snapshot()

    def snapshot(self, connected=True, reason=''):
        if not self.state:
            return {'connected': False, 'reason': reason or 'Waiting for iRacing team telemetry'}
        s = copy.deepcopy(self.state)
        s['drivers'] = list(s['drivers'].values())
        s.update(connected=connected, reason=reason, version=2)
        return s
