import json
import unittest
from pathlib import Path

from scripts.replay_v2_incidents import replay


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "tests" / "evaluation" / "v2_incidents.json"


class V2IncidentReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def test_manifest_is_frozen_and_identifiers_are_unique(self):
        self.assertTrue(self.manifest["frozen_before_first_run"])
        identifiers = [item["id"] for item in self.manifest["incidents"]]
        self.assertEqual(len(identifiers), len(set(identifiers)))
        self.assertEqual(identifiers, sorted(identifiers))

    def test_every_incident_has_auditable_metadata(self):
        for incident in self.manifest["incidents"]:
            with self.subTest(incident=incident["id"]):
                self.assertTrue(incident["historical_symptom"].strip())
                self.assertTrue(incident["layer"].strip())
                self.assertIn(
                    incident["disposition"],
                    {
                        "fixed",
                        "fixed_by_removal_and_live_replay",
                        "fixed_fail_closed",
                        "fixed_refusal",
                        "not_applicable_by_removal",
                    },
                )
                self.assertIn(
                    incident["check"]["type"],
                    {
                        "source_absence",
                        "unit_tests",
                        "route_only",
                        "route_and_contract",
                    },
                )

    def test_offline_incident_replay_passes(self):
        report = replay(
            self.manifest,
            live=False,
            repeat=1,
            progress=False,
        )
        failures = [
            (item["id"], item["offline"])
            for item in report["results"]
            if not item["passed"]
        ]
        self.assertEqual(failures, [])
        self.assertEqual(report["summary"]["incidents_total"], 17)
        self.assertEqual(report["summary"]["incidents_passed"], 17)


if __name__ == "__main__":
    unittest.main()
