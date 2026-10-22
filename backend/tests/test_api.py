"""
test_api.py — REST API Integration Tests for Pingwise DHT Simulator.

Verifies all Flask HTTP endpoints, status codes, JSON responses,
and state changes.
"""

import json
import unittest
from backend.app import app


class TestPingwiseAPI(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.client = self.app.test_client()
        self.client.testing = True

    def test_serve_index(self):
        """GET / should serve the frontend index.html."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"PINGWISE", res.data)

    def test_network_init_endpoint(self):
        """POST /api/network/init should initialize network with N nodes."""
        res = self.client.post(
            "/api/network/init",
            data=json.dumps({"node_count": 25}),
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertEqual(len(data["nodes"]), 25)
        self.assertIn("links", data)
        self.assertIn("stats", data)

    def test_network_snapshot(self):
        """GET /api/network/snapshot should return network state."""
        res = self.client.get("/api/network/snapshot")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertIn("nodes", data)
        self.assertIn("links", data)
        self.assertIn("stats", data)

    def test_add_and_remove_node(self):
        """POST /api/network/add-node and remove-node."""
        # Add
        res_add = self.client.post("/api/network/add-node")
        self.assertEqual(res_add.status_code, 200)
        data_add = json.loads(res_add.data)
        new_id = data_add["node"]["id"]["value"]

        # Remove specific
        res_rem = self.client.post(
            "/api/network/remove-node",
            data=json.dumps({"node_id": new_id}),
            content_type="application/json"
        )
        self.assertEqual(res_rem.status_code, 200)
        data_rem = json.loads(res_rem.data)
        self.assertEqual(data_rem["removed_id"], new_id)

    def test_store_and_lookup_endpoints(self):
        """POST /api/store and POST /api/lookup."""
        self.client.post(
            "/api/network/init",
            data=json.dumps({"node_count": 30}),
            content_type="application/json"
        )

        # Store
        res_store = self.client.post(
            "/api/store",
            data=json.dumps({"key": "test_doc.md", "value": "BitTorrent-Kademlia-Specs"}),
            content_type="application/json"
        )
        self.assertEqual(res_store.status_code, 200)
        store_data = json.loads(res_store.data)
        self.assertTrue(len(store_data["stored_on"]) > 0)

        # Lookup
        res_lookup = self.client.post(
            "/api/lookup",
            data=json.dumps({"key": "test_doc.md"}),
            content_type="application/json"
        )
        self.assertEqual(res_lookup.status_code, 200)
        lookup_data = json.loads(res_lookup.data)
        self.assertTrue(lookup_data["found"])
        self.assertEqual(lookup_data["value"], "BitTorrent-Kademlia-Specs")

    def test_churn_simulation_endpoint(self):
        """POST /api/churn/simulate should execute churn and return stats."""
        res = self.client.post(
            "/api/churn/simulate",
            data=json.dumps({"add_count": 5, "remove_count": 3}),
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertEqual(data["added"], 5)
        self.assertEqual(data["removed"], 3)
        self.assertIn("stats", data)

    def test_benchmark_run_endpoint(self):
        """POST /api/benchmark/run should execute benchmark."""
        res = self.client.post(
            "/api/benchmark/run",
            data=json.dumps({
                "node_count": 25,
                "file_count": 8,
                "churn_rounds": 2,
                "churn_add": 3,
                "churn_remove": 2
            }),
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertIn("overall_avg_hops", data)
        self.assertIn("overall_success_rate", data)
        self.assertIn("hop_distribution", data)
        # 2 churn rounds + 1 initial baseline round = 3 rounds total
        self.assertEqual(len(data["rounds"]), 3)

    def test_node_details_endpoint(self):
        """GET /api/node/<id>/details."""
        snap_res = self.client.get("/api/network/snapshot")
        snap_data = json.loads(snap_res.data)
        if snap_data["nodes"]:
            target_id = snap_data["nodes"][0]["id"]
            res = self.client.get(f"/api/node/{target_id}/details")
            self.assertEqual(res.status_code, 200)
            data = json.loads(res.data)
            self.assertIn("buckets", data)
            self.assertEqual(len(data["buckets"]), 16)

    def test_global_stats_endpoint(self):
        """GET /api/stats."""
        res = self.client.get("/api/stats")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertIn("total_nodes", data)
        self.assertIn("theoretical_log2n", data)


if __name__ == "__main__":
    unittest.main()
