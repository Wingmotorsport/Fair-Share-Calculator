import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'connector'))
from team_tracking import TeamTracker, read_sample


def sample(lap=0, seconds=0, uid='101', name='Alex', key='race:1:team24'):
    return dict(key=key, carKey='team24', sessionType='Race', teamName='Wing',
                carNumber='24', track='Bathurst', driverId=uid, driverName=name,
                lap=lap, elapsed=seconds)


class SDK(dict):
    is_initialized = is_connected = True


def sdk_fixture():
    return SDK(PlayerCarIdx=1, CarIdxLapCompleted=[99, 5], SessionTime=120,
               SessionNum=2, WeekendInfo={'SubSessionID': 123, 'TrackName': 'Bathurst'},
               DriverInfo={'Drivers': [
                   {'CarIdx': 0, 'UserID': 999, 'UserName': 'Other team', 'TeamID': 99},
                   {'CarIdx': 1, 'UserID': 101, 'UserName': 'Alex', 'TeamID': 24, 'CarNumber': '24'}]},
               SessionInfo={'Sessions': [{'SessionNum': 2, 'SessionType': 'Race'}]})


class TrackingTests(unittest.TestCase):
    def setUp(self):
        self.tracker = TeamTracker()

    def assert_conserved(self, result):
        self.assertEqual(result['lap'], result['unallocated'] + sum(d['laps'] for d in result['drivers']))

    def test_initial_history_not_given_to_current_driver(self):
        s = self.tracker.update(sample(95, 500))
        self.assertEqual(s['unallocated'], 95)
        self.assertEqual(s['drivers'][0]['laps'], 0)
        self.assertTrue(s['partialStint'])
        self.assert_conserved(s)

    def test_lap_credits_once_for_repeated_packets(self):
        self.tracker.update(sample())
        for _ in range(10):
            s = self.tracker.update(sample(1, 1))
        self.assertEqual(s['drivers'][0]['laps'], 1)
        self.assertEqual(s['stintLaps'], 1)
        self.assert_conserved(s)

    def test_swap_keeps_previous_totals_and_resets_stint(self):
        self.tracker.update(sample())
        self.tracker.update(sample(1, 1))
        self.tracker.update(sample(1, 2, '202', 'Jordan'))
        s = self.tracker.update(sample(2, 3, '202', 'Jordan'))
        self.assertEqual([d['laps'] for d in s['drivers']], [1, 1])
        self.assertEqual(s['stintLaps'], 1)
        self.assertEqual(s['logs'][0]['laps'], 1)
        self.assert_conserved(s)

    def test_lap_on_swap_boundary_is_unallocated(self):
        self.tracker.update(sample())
        s = self.tracker.update(sample(1, 1, '202', 'Jordan'))
        self.assertEqual(s['unallocated'], 1)
        self.assertEqual(s['stintLaps'], 0)
        self.assertTrue(s['partialStint'])
        self.assert_conserved(s)

    def test_disconnect_gap_is_not_guessed(self):
        self.tracker.update(sample())
        self.tracker.update(sample(1, 1))
        self.tracker.disconnect()
        s = self.tracker.update(sample(4, 240))
        self.assertEqual(s['drivers'][0]['laps'], 1)
        self.assertEqual(s['unallocated'], 3)
        self.assertTrue(s['partialStint'])
        self.assert_conserved(s)

    def test_long_poll_gap_is_detected(self):
        self.tracker.update(sample())
        s = self.tracker.update(sample(2, 240))
        self.assertEqual(s['unallocated'], 2)

    def test_restart_restores_totals(self):
        self.tracker.update(sample())
        self.tracker.update(sample(1, 1))
        restored = TeamTracker(self.tracker.state)
        restored.update(sample(1, 2))
        s = restored.update(sample(2, 3))
        self.assertEqual(s['drivers'][0]['laps'], 2)
        self.assert_conserved(s)

    def test_practice_and_race_are_separate(self):
        self.tracker.update(sample(10, 500, key='practice'))
        s = self.tracker.update(sample(key='race'))
        self.assertEqual(s['lap'], 0)
        self.assertEqual(s['unallocated'], 0)
        self.assertFalse(s['partialStint'])

    def test_name_change_uses_same_id(self):
        self.tracker.update(sample())
        s = self.tracker.update(sample(1, 1, name='Alex Taylor'))
        self.assertEqual(len(s['drivers']), 1)
        self.assertEqual(s['drivers'][0]['name'], 'Alex Taylor')

    def test_two_drivers_with_same_name_keep_separate_ids(self):
        self.tracker.update(sample())
        s = self.tracker.update(sample(0, 1, uid='202'))
        self.assertEqual(len(s['drivers']), 2)

    def test_regressive_sample_does_not_remove_laps(self):
        self.tracker.update(sample())
        self.tracker.update(sample(1, 1))
        s = self.tracker.update(sample())
        self.assertFalse(s['connected'])
        self.assertEqual(s['lap'], 1)

    def test_other_car_is_not_used(self):
        s = read_sample(sdk_fixture())
        self.assertEqual(s['lap'], 5)
        self.assertEqual(s['driverId'], '101')
        self.assertEqual(s['sessionType'], 'Race')

    def test_missing_identity_does_not_guess(self):
        sdk = sdk_fixture()
        sdk['DriverInfo']['Drivers'][1].pop('UserID')
        self.assertIsNone(read_sample(sdk))

    def test_ambiguous_driver_is_rejected(self):
        sdk = sdk_fixture()
        sdk['DriverInfo']['Drivers'].append(copy.deepcopy(sdk['DriverInfo']['Drivers'][1]))
        self.assertIsNone(read_sample(sdk))

    def test_replay_and_negative_laps_are_rejected(self):
        sdk = sdk_fixture()
        sdk['IsReplayPlaying'] = True
        self.assertIsNone(read_sample(sdk))
        sdk['IsReplayPlaying'] = False
        sdk['CarIdxLapCompleted'][1] = -1
        self.assertIsNone(read_sample(sdk))


if __name__ == '__main__':
    unittest.main()
