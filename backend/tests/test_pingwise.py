"""
test_pingwise.py — Algorithmic & Unit Tests for Pingwise Kademlia DHT.

Validates:
1. XOR metric properties (Identity, Symmetry, Triangle Inequality, Unidirectionality)
2. K-bucket LRU eviction and capacity invariants
3. Routing table tiering and prefix mapping
4. Iterative lookup convergence in O(log N) steps
5. STORE / FIND_VALUE key-value persistence
6. Churn resilience: random node additions and drops
"""

import math
import random
import unittest
from backend.pingwise_core import (
    ID_BITS,
    K,
    ALPHA,
    PingwiseID,
    Contact,
    KBucket,
    RoutingTable,
    PingwiseNode,
    PingwiseNetwork,
)


class TestPingwiseIDAndXORMetric(unittest.TestCase):
    """Formal mathematical validation of the XOR distance metric."""

    def test_id_range_validation(self):
        """IDs must fall strictly within [0, 2^ID_BITS)."""
        valid_id = PingwiseID(0)
        self.assertEqual(valid_id.value, 0)
        valid_max = PingwiseID((1 << ID_BITS) - 1)
        self.assertEqual(valid_max.value, 65535)

        with self.assertRaises(ValueError):
            PingwiseID(-1)
        with self.assertRaises(ValueError):
            PingwiseID(1 << ID_BITS)

    def test_identity_property(self):
        """Identity of indiscernibles: d(x, y) = 0 <=> x == y."""
        for _ in range(50):
            x = PingwiseID.random()
            self.assertEqual(PingwiseID.xor_distance(x, x), 0)
            self.assertEqual(PingwiseID.bucket_index(0), -1)

    def test_symmetry_property(self):
        """Symmetry: d(x, y) == d(y, x)."""
        for _ in range(50):
            x = PingwiseID.random()
            y = PingwiseID.random()
            self.assertEqual(
                PingwiseID.xor_distance(x, y),
                PingwiseID.xor_distance(y, x)
            )

    def test_triangle_inequality_property(self):
        """Triangle inequality: d(x, z) <= d(x, y) + d(y, z)."""
        for _ in range(100):
            x = PingwiseID.random()
            y = PingwiseID.random()
            z = PingwiseID.random()
            d_xz = PingwiseID.xor_distance(x, z)
            d_xy = PingwiseID.xor_distance(x, y)
            d_yz = PingwiseID.xor_distance(y, z)
            self.assertLessEqual(d_xz, d_xy + d_yz)

    def test_unidirectionality_property(self):
        """Unidirectionality: For any x and delta >= 0, exactly one y satisfies d(x, y) = delta."""
        for _ in range(50):
            x = PingwiseID.random()
            delta = random.randint(0, (1 << ID_BITS) - 1)
            y_val = x.value ^ delta
            y = PingwiseID(y_val)
            self.assertEqual(PingwiseID.xor_distance(x, y), delta)

    def test_bucket_index_log2(self):
        """Bucket index corresponds to floor(log2(distance))."""
        # Distance 1 (2^0) -> index 0
        self.assertEqual(PingwiseID.bucket_index(1), 0)
        # Distance 2 (2^1) -> index 1
        self.assertEqual(PingwiseID.bucket_index(2), 1)
        # Distance 3 (2^1 + 1) -> index 1
        self.assertEqual(PingwiseID.bucket_index(3), 1)
        # Distance 4 (2^2) -> index 2
        self.assertEqual(PingwiseID.bucket_index(4), 2)
        # Distance 65535 -> index 15
        self.assertEqual(PingwiseID.bucket_index(65535), 15)


class TestKBucket(unittest.TestCase):
    """Validates LRU eviction and capacity constraints in K-buckets."""

    def test_capacity_and_lru_eviction(self):
        bucket = KBucket(capacity=K)
        contacts = [Contact(PingwiseID(i)) for i in range(K)]

        for c in contacts:
            self.assertTrue(bucket.add(c))

        self.assertEqual(bucket.size, K)
        self.assertTrue(bucket.is_full())
        # Least recently seen is contacts[0]
        self.assertEqual(bucket.head().id.value, 0)

        # Re-adding contacts[0] should move it to tail (most recently seen)
        bucket.add(contacts[0])
        self.assertEqual(bucket.size, K)
        self.assertEqual(bucket.tail().id.value, 0)
        self.assertEqual(bucket.head().id.value, 1)

        # Adding new contact when full: head (contacts[1]) evicted
        new_contact = Contact(PingwiseID(999))
        bucket.add(new_contact)
        self.assertEqual(bucket.size, K)
        self.assertFalse(bucket.contains(PingwiseID(1)))
        self.assertTrue(bucket.contains(PingwiseID(999)))


class TestRoutingTable(unittest.TestCase):
    """Validates node distance sorting and contact discovery."""

    def test_routing_table_find_closest(self):
        owner = PingwiseID(0x0000)
        rt = RoutingTable(owner)

        # Add contacts at various distances
        peers = [PingwiseID(0x0001), PingwiseID(0x0010), PingwiseID(0x0100), PingwiseID(0x1000)]
        for p in peers:
            rt.add_contact(Contact(p))

        # Closest to 0x0002 should be 0x0001 (dist = 3), then 0x0010 (dist = 18)
        target = PingwiseID(0x0002)
        closest = rt.find_closest(target, count=2)
        self.assertEqual(len(closest), 2)
        self.assertEqual(closest[0].id.value, 0x0001)
        self.assertEqual(closest[1].id.value, 0x0010)


class TestKademliaLookupAndStorage(unittest.TestCase):
    """Validates network bootstrapping, iterative lookup, and file storage."""

    def setUp(self):
        self.net = PingwiseNetwork()
        self.net.initialize(node_count=35)

    def test_network_connectivity(self):
        """Nodes must successfully bootstrap and discover peers."""
        stats = self.net.get_stats()
        self.assertEqual(stats["total_nodes"], 35)
        self.assertGreater(stats["avg_routing_table_size"], 1.0)

    def test_store_and_lookup_file(self):
        """Stored key-value files must be retrievable via iterative lookup."""
        store_res = self.net.store_file("distributed_systems.pdf", "Data-Hash-Payload-1234")
        self.assertTrue(len(store_res["stored_on"]) > 0)

        # Lookup should locate the exact value
        lookup_res = self.net.lookup_file("distributed_systems.pdf")
        self.assertTrue(lookup_res["found"])
        self.assertEqual(lookup_res["value"], "Data-Hash-Payload-1234")
        self.assertGreaterEqual(lookup_res["hops"], 0)

    def test_log_n_hop_bound(self):
        """Average lookup hops should be bounded by O(log N)."""
        theoretical_log2n = math.log2(35) # ~ 5.13
        # Perform 10 lookups
        for i in range(10):
            self.net.store_file(f"test_key_{i}", f"val_{i}")
            res = self.net.lookup_file(f"test_key_{i}")
            self.assertTrue(res["found"])
            # Individual lookup should never exceed ~ 2 * log2(N)
            self.assertLessEqual(res["hops"], math.ceil(theoretical_log2n * 2) + 2)


class TestChurnSimulation(unittest.TestCase):
    """Validates DHT resilience under concurrent node departures and arrivals."""

    def test_churn_resilience(self):
        net = PingwiseNetwork()
        net.initialize(node_count=40)

        # Store test file
        net.store_file("churn_test_file", "Persistent-Across-Churn")

        # Simulate network churn
        churn_res = net.simulate_churn(add_count=10, remove_count=8)
        self.assertEqual(churn_res["added"], 10)
        self.assertEqual(churn_res["removed"], 8)

        # File should still be found (K-replication protects against peer drops)
        lookup_res = net.lookup_file("churn_test_file")
        self.assertTrue(lookup_res["found"])
        self.assertEqual(lookup_res["value"], "Persistent-Across-Churn")


if __name__ == "__main__":
    unittest.main()
