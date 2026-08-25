import unittest

from td5gauge import Service


def sample(**overrides):
    values = {
        "updated_at": 1000.0,
        "rpm": 900,
        "speed_kmh": 0,
        "voltage_v": 14.1,
        "coolant_c": 88.0,
        "air_c": 25.0,
        "fuel_c": 55.0,
        "map_kpa": 100.0,
        "aap_kpa": 100.0,
        "boost_kpa": 0.0,
        "maf_kg_h": 0.0,
        "wastegate_percent": 0.0,
        "throttle_1": 0.0,
        "injector_balance": [0, 0, 0, 0, 0],
        "engine_on": True,
    }
    values.update(overrides)
    return values


class ServiceTests(unittest.TestCase):
    def test_fault_read_is_manual_after_connection(self):
        self.assertFalse(Service(None, simulate=True).dtc_requested)

    def test_coolant_thresholds_include_critical(self):
        service = Service(None, simulate=True)
        service._evaluate_alerts(sample(coolant_c=98.0))
        self.assertEqual(service.active_alerts["Coolant"]["level"], "warn")

        service._evaluate_alerts(sample(updated_at=1001.0, coolant_c=103.0))
        self.assertEqual(service.active_alerts["Coolant"]["level"], "danger")

        service._evaluate_alerts(sample(updated_at=1002.0, coolant_c=105.0))
        self.assertEqual(service.active_alerts["Coolant"]["level"], "critical")

    def test_alternator_low_voltage_requires_running_engine(self):
        service = Service(None, simulate=True)
        service._evaluate_alerts(sample(voltage_v=12.7, engine_on=False))
        self.assertNotIn("Alternator", service.active_alerts)

        service._evaluate_alerts(sample(updated_at=1001.0, voltage_v=12.7, engine_on=True))
        self.assertEqual(service.active_alerts["Alternator"]["level"], "danger")
