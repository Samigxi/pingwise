"""
pingwise_core.py — Kademlia DHT Simulator Engine for Pingwise.

Implements a complete Kademlia Distributed Hash Table simulation with:
- 16-bit node/key ID space (64K addresses)
- XOR-based distance metric and routing
- K-bucket routing tables with LRU eviction
- Iterative node and value lookup algorithms
- Network simulation with churn and benchmarking

References:
    Maymounkov, P. & Mazières, D. (2002). "Kademlia: A Peer-to-Peer
    Information System Based on the XOR Metric."
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ID_BITS: int = 16          # 16-bit node/key IDs → 64K address space
K: int = 4                 # k-bucket capacity (replication parameter)
ALPHA: int = 3             # concurrency parameter for parallel lookups


# ---------------------------------------------------------------------------
# PingwiseID
# ---------------------------------------------------------------------------

class PingwiseID:
    """Immutable 16-bit identifier used for both nodes and keys.

    All distance computations use the XOR metric, which satisfies
    the triangle inequality and forms an ultrametric space.

    Attributes:
        value: Integer in [0, 2^ID_BITS).
    """

    __slots__ = ("value",)

    def __init__(self, value: int) -> None:
        """Create a PingwiseID from an integer.

        Args:
            value: Integer in [0, 2^ID_BITS).

        Raises:
            ValueError: If *value* is outside the valid range.
        """
        if not (0 <= value < 2 ** ID_BITS):
            raise ValueError(
                f"ID value must be in [0, {2 ** ID_BITS}), got {value}"
            )
        self.value = value

    # -- factory methods ----------------------------------------------------

    @staticmethod
    def random() -> "PingwiseID":
        """Return a uniformly random 16-bit ID."""
        return PingwiseID(random.randint(0, 2 ** ID_BITS - 1))

    @staticmethod
    def from_hex(hex_str: str) -> "PingwiseID":
        """Parse a hex string (with or without ``0x`` prefix).

        Args:
            hex_str: e.g. ``"0x00a3"`` or ``"00a3"``.
        """
        return PingwiseID(int(hex_str, 16))

    # -- XOR helpers --------------------------------------------------------

    @staticmethod
    def xor_distance(a: "PingwiseID", b: "PingwiseID") -> int:
        """Return the XOR distance between two IDs as an integer.

        Complexity: O(1).
        """
        return a.value ^ b.value

    @staticmethod
    def bucket_index(distance: int) -> int:
        """Return the index of the highest set bit (0-indexed).

        This determines which k-bucket a contact belongs to.  A distance
        of 0 means the IDs are identical; we return -1 by convention.

        Complexity: O(1).
        """
        if distance == 0:
            return -1
        return distance.bit_length() - 1

    # -- serialisation ------------------------------------------------------

    def to_binary(self) -> str:
        """Return a 16-character binary string with leading zeros."""
        return format(self.value, f"0{ID_BITS}b")

    def to_hex(self) -> str:
        """Return a 4-character hex string prefixed with ``0x``."""
        return f"0x{self.value:04x}"

    def to_dict(self) -> dict:
        """Serialise to a plain dict for JSON transport."""
        return {
            "value": self.value,
            "hex": self.to_hex(),
            "binary": self.to_binary(),
        }

    # -- operators ----------------------------------------------------------

    def __xor__(self, other: "PingwiseID") -> int:
        return self.value ^ other.value

    def __eq__(self, other: object) -> bool:
        if isinstance(other, PingwiseID):
            return self.value == other.value
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.value)

    def __lt__(self, other: "PingwiseID") -> bool:
        return self.value < other.value

    def __repr__(self) -> str:
        return f"PingwiseID({self.to_hex()})"


# ---------------------------------------------------------------------------
# Contact
# ---------------------------------------------------------------------------

@dataclass
class Contact:
    """A lightweight reference to a remote node.

    Attributes:
        id: The node's PingwiseID.
        last_seen: UNIX timestamp of the most recent interaction.
    """

    id: PingwiseID
    last_seen: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "id": self.id.to_dict(),
            "last_seen": self.last_seen,
        }


# ---------------------------------------------------------------------------
# KBucket
# ---------------------------------------------------------------------------

class KBucket:
    """A single k-bucket holding up to *capacity* contacts in LRU order.

    Ordering convention:
        - **Head** (index 0) = Least-Recently Seen (LRS)
        - **Tail** (index -1) = Most-Recently Seen (MRS)

    When the bucket is full and a new contact arrives, the head (stale)
    contact is evicted (simulating a failed PING to the stale node) and
    the new contact is appended at the tail.

    Complexity:
        - add: O(n) where n ≤ K (scan for existing contact).
        - remove: O(n).
    """

    def __init__(self, capacity: int = K) -> None:
        self._contacts: List[Contact] = []
        self.capacity: int = capacity

    # -- mutators -----------------------------------------------------------

    def add(self, contact: Contact) -> bool:
        """Insert or refresh a contact.

        * If the contact is already present, move it to the tail and
          update ``last_seen``.
        * If the bucket is not full, append at the tail.
        * If the bucket is full, evict the head and append (simulated
          stale-node eviction).

        Returns:
            ``True`` — the contact is always added in this simulation.
        """
        # Check for existing entry
        for i, c in enumerate(self._contacts):
            if c.id == contact.id:
                self._contacts.pop(i)
                contact.last_seen = time.time()
                self._contacts.append(contact)
                return True

        if not self.is_full():
            self._contacts.append(contact)
        else:
            # Evict LRS (head) — simulates failed ping to stale node
            self._contacts.pop(0)
            self._contacts.append(contact)
        return True

    def remove(self, contact_id: PingwiseID) -> None:
        """Remove the contact with the given ID, if present."""
        self._contacts = [c for c in self._contacts if c.id != contact_id]

    # -- accessors ----------------------------------------------------------

    def head(self) -> Optional[Contact]:
        """Return the LRS contact, or ``None`` if empty."""
        return self._contacts[0] if self._contacts else None

    def tail(self) -> Optional[Contact]:
        """Return the MRS contact, or ``None`` if empty."""
        return self._contacts[-1] if self._contacts else None

    def is_full(self) -> bool:
        return len(self._contacts) >= self.capacity

    def contains(self, contact_id: PingwiseID) -> bool:
        return any(c.id == contact_id for c in self._contacts)

    @property
    def size(self) -> int:
        return len(self._contacts)

    def to_list(self) -> List[Contact]:
        """Return a shallow copy of the internal contacts list."""
        return list(self._contacts)

    def to_dict(self) -> dict:
        return {
            "size": self.size,
            "capacity": self.capacity,
            "contacts": [c.to_dict() for c in self._contacts],
        }


# ---------------------------------------------------------------------------
# RoutingTable
# ---------------------------------------------------------------------------

class RoutingTable:
    """Array of ID_BITS k-buckets indexed by XOR-distance bit length.

    Bucket *i* holds contacts whose XOR distance to the owner has its
    highest set bit at position *i* (i.e. distance in [2^i, 2^(i+1))).

    Complexity:
        - add_contact: O(K) (bucket lookup + insert).
        - find_closest: O(N log N) where N = total contacts (sort step).
    """

    def __init__(self, owner_id: PingwiseID) -> None:
        self.owner_id: PingwiseID = owner_id
        self.buckets: List[KBucket] = [KBucket(K) for _ in range(ID_BITS)]

    def add_contact(self, contact: Contact) -> bool:
        """Add *contact* to the appropriate bucket.

        Returns ``False`` if the contact is the owner itself (skip).
        """
        if contact.id == self.owner_id:
            return False
        distance = PingwiseID.xor_distance(self.owner_id, contact.id)
        idx = PingwiseID.bucket_index(distance)
        if idx < 0:
            return False
        return self.buckets[idx].add(contact)

    def remove_contact(self, contact_id: PingwiseID) -> None:
        """Remove *contact_id* from the appropriate bucket."""
        distance = PingwiseID.xor_distance(self.owner_id, contact_id)
        idx = PingwiseID.bucket_index(distance)
        if idx >= 0:
            self.buckets[idx].remove(contact_id)

    def find_closest(
        self, target_id: PingwiseID, count: int = K
    ) -> List[Contact]:
        """Return up to *count* contacts closest to *target_id*.

        Aggregates every contact across all buckets, sorts by XOR
        distance to *target_id*, and returns the top *count*.

        Complexity: O(N log N) where N = total_contacts.
        """
        all_contacts = self.get_all_contacts()
        all_contacts.sort(
            key=lambda c: PingwiseID.xor_distance(c.id, target_id)
        )
        return all_contacts[:count]

    def get_all_contacts(self) -> List[Contact]:
        """Return a flat list of every contact in the table."""
        contacts: List[Contact] = []
        for bucket in self.buckets:
            contacts.extend(bucket.to_list())
        return contacts

    def get_bucket_stats(self) -> List[dict]:
        """Per-bucket statistics for visualisation."""
        return [
            {
                "index": i,
                "size": bucket.size,
                "capacity": K,
                "contacts": [c.to_dict() for c in bucket.to_list()],
            }
            for i, bucket in enumerate(self.buckets)
        ]

    @property
    def total_contacts(self) -> int:
        """Total number of contacts across all buckets."""
        return sum(b.size for b in self.buckets)

    def to_dict(self) -> dict:
        return {
            "owner_id": self.owner_id.to_dict(),
            "total_contacts": self.total_contacts,
            "buckets": self.get_bucket_stats(),
        }


# ---------------------------------------------------------------------------
# PingwiseNode
# ---------------------------------------------------------------------------

class PingwiseNode:
    """A single simulated Kademlia node.

    Each node owns a routing table, a local key-value store, and
    exposes the four Kademlia RPCs (PING, STORE, FIND_NODE, FIND_VALUE)
    as direct method calls within the simulation.

    Attributes:
        id: Unique PingwiseID.
        routing_table: The node's k-bucket routing table.
        storage: Local key→value store  (key_int → value_str).
        is_alive: Whether the node is reachable.
    """

    def __init__(self, node_id: PingwiseID) -> None:
        self.id: PingwiseID = node_id
        self.routing_table: RoutingTable = RoutingTable(node_id)
        self.storage: Dict[int, str] = {}
        self.is_alive: bool = True

    # -- simulated RPCs -----------------------------------------------------

    def ping(self, target_node: "PingwiseNode") -> bool:
        """PING RPC — returns whether *target_node* is alive."""
        return target_node.is_alive

    def store(self, key: int, value: str) -> None:
        """STORE RPC — persist *value* under *key* in local storage."""
        self.storage[key] = value

    def find_node(self, target_id: PingwiseID) -> List[Contact]:
        """FIND_NODE RPC — return K closest contacts to *target_id*.

        Complexity: O(N log N) dominated by ``RoutingTable.find_closest``.
        """
        return self.routing_table.find_closest(target_id, K)

    def find_value(self, key: int) -> dict:
        """FIND_VALUE RPC — return the value if stored locally, else
        return the K closest contacts (same as FIND_NODE).

        Returns:
            ``{"found": True, "value": v}`` or
            ``{"found": False, "contacts": [Contact, ...]}``.
        """
        if key in self.storage:
            return {"found": True, "value": self.storage[key]}
        return {
            "found": False,
            "contacts": self.find_node(PingwiseID(key)),
        }

    # -- iterative lookups --------------------------------------------------

    def iterative_find_node(
        self,
        network_nodes: Dict[int, "PingwiseNode"],
        target_id: PingwiseID,
    ) -> dict:
        """Kademlia iterative FIND_NODE lookup.

        Algorithm (simplified for simulation):
            1. Seed *shortlist* with K closest contacts from own table.
            2. Repeatedly query up to ALPHA unqueried contacts in the
               shortlist, merging returned contacts.
            3. Terminate when:
               - No unqueried contacts remain, **or**
               - The closest contact has not changed and all K closest
                 have been queried (convergence).

        Args:
            network_nodes: Global map ``{id_int: PingwiseNode}`` enabling
                           direct method-call simulation of RPCs.
            target_id: The ID being looked up.

        Returns:
            ``{"closest": list[Contact], "hops": int, "path": list[int]}``

        Complexity:
            Expected O(log N) hops in a balanced network of N nodes,
            with each hop touching up to ALPHA contacts.
        """
        # Step 1 — seed shortlist from own routing table
        shortlist: List[Contact] = self.routing_table.find_closest(
            target_id, K
        )
        queried: set = set()
        queried.add(self.id.value)
        hops: int = 0
        path: List[int] = [self.id.value]
        seen_ids: set = {c.id.value for c in shortlist}
        seen_ids.add(self.id.value)

        prev_closest_id: Optional[int] = None

        while True:
            # Sort shortlist by distance to target
            shortlist.sort(
                key=lambda c: PingwiseID.xor_distance(c.id, target_id)
            )

            # Step 3a — pick up to ALPHA closest unqueried contacts
            to_query: List[Contact] = []
            for c in shortlist:
                if c.id.value not in queried:
                    to_query.append(c)
                    if len(to_query) >= ALPHA:
                        break

            # Step 3b — no unqueried contacts → terminate
            if not to_query:
                break

            # Step 3c — query each selected contact
            for contact in to_query:
                queried.add(contact.id.value)

                # Check reachability
                if (
                    contact.id.value not in network_nodes
                    or not network_nodes[contact.id.value].is_alive
                ):
                    continue

                remote_node = network_nodes[contact.id.value]
                returned_contacts = remote_node.find_node(target_id)
                hops += 1
                path.append(contact.id.value)

                # Mutual discovery — add self to queried node's table
                remote_node.routing_table.add_contact(
                    Contact(id=self.id, last_seen=time.time())
                )

                # Merge returned contacts into shortlist
                for rc in returned_contacts:
                    if rc.id.value not in seen_ids and rc.id.value != self.id.value:
                        seen_ids.add(rc.id.value)
                        shortlist.append(rc)

            # Re-sort after merge
            shortlist.sort(
                key=lambda c: PingwiseID.xor_distance(c.id, target_id)
            )

            # Step 3e — convergence check
            current_closest_id = (
                shortlist[0].id.value if shortlist else None
            )
            if current_closest_id == prev_closest_id:
                # Check if all K closest have been queried
                k_closest = shortlist[:K]
                if all(c.id.value in queried for c in k_closest):
                    break
            prev_closest_id = current_closest_id

        # Serialise contacts for the result
        result_closest = [
            c.to_dict() for c in shortlist[:K]
        ]
        return {"closest": result_closest, "hops": hops, "path": path}

    def iterative_find_value(
        self,
        network_nodes: Dict[int, "PingwiseNode"],
        key: int,
    ) -> dict:
        """Kademlia iterative FIND_VALUE lookup.

        Behaves identically to ``iterative_find_node`` except:
        - Each queried node is asked ``find_value(key)`` instead of
          ``find_node(target_id)``.
        - If any node holds the value, the lookup short-circuits and
          returns it immediately.

        Returns:
            On success: ``{"found": True, "value": str, "hops": int, "path": list}``
            On failure: ``{"found": False, "hops": int, "path": list, "closest": list}``
        """
        target_id = PingwiseID(key)
        shortlist: List[Contact] = self.routing_table.find_closest(
            target_id, K
        )
        queried: set = set()
        queried.add(self.id.value)
        hops: int = 0
        path: List[int] = [self.id.value]
        seen_ids: set = {c.id.value for c in shortlist}
        seen_ids.add(self.id.value)

        prev_closest_id: Optional[int] = None

        # Check own storage first
        if key in self.storage:
            return {
                "found": True,
                "value": self.storage[key],
                "hops": 0,
                "path": path,
            }

        while True:
            shortlist.sort(
                key=lambda c: PingwiseID.xor_distance(c.id, target_id)
            )

            to_query: List[Contact] = []
            for c in shortlist:
                if c.id.value not in queried:
                    to_query.append(c)
                    if len(to_query) >= ALPHA:
                        break

            if not to_query:
                break

            for contact in to_query:
                queried.add(contact.id.value)

                if (
                    contact.id.value not in network_nodes
                    or not network_nodes[contact.id.value].is_alive
                ):
                    continue

                remote_node = network_nodes[contact.id.value]
                result = remote_node.find_value(key)
                hops += 1
                path.append(contact.id.value)

                # Mutual discovery
                remote_node.routing_table.add_contact(
                    Contact(id=self.id, last_seen=time.time())
                )

                if result["found"]:
                    return {
                        "found": True,
                        "value": result["value"],
                        "hops": hops,
                        "path": path,
                    }

                # Merge returned contacts
                for rc in result["contacts"]:
                    if rc.id.value not in seen_ids and rc.id.value != self.id.value:
                        seen_ids.add(rc.id.value)
                        shortlist.append(rc)

            shortlist.sort(
                key=lambda c: PingwiseID.xor_distance(c.id, target_id)
            )

            current_closest_id = (
                shortlist[0].id.value if shortlist else None
            )
            if current_closest_id == prev_closest_id:
                k_closest = shortlist[:K]
                if all(c.id.value in queried for c in k_closest):
                    break
            prev_closest_id = current_closest_id

        result_closest = [c.to_dict() for c in shortlist[:K]]
        return {
            "found": False,
            "hops": hops,
            "path": path,
            "closest": result_closest,
        }

    # -- network join -------------------------------------------------------

    def join_network(
        self,
        network_nodes: Dict[int, "PingwiseNode"],
        bootstrap_node: "PingwiseNode",
    ) -> None:
        """Join an existing Kademlia network via *bootstrap_node*.

        Steps:
            1. Add the bootstrap node to own routing table.
            2. Add self to the bootstrap node's routing table.
            3. Perform an iterative lookup for *own ID* to populate
               routing table with nearby nodes.
            4. Add every discovered contact to own routing table.

        Complexity: O(log N) hops for the self-lookup.
        """
        # Step 1 & 2 — mutual introduction
        self.routing_table.add_contact(
            Contact(id=bootstrap_node.id, last_seen=time.time())
        )
        bootstrap_node.routing_table.add_contact(
            Contact(id=self.id, last_seen=time.time())
        )

        # Step 3 — self-lookup
        lookup_result = self.iterative_find_node(network_nodes, self.id)

        # Step 4: add discovered contacts (both closest and path hops for diverse distance tiers)
        for contact_dict in lookup_result["closest"]:
            cid = PingwiseID(contact_dict["id"]["value"])
            self.routing_table.add_contact(
                Contact(id=cid, last_seen=time.time())
            )
        for hop_id in lookup_result["path"]:
            if hop_id != self.id.value:
                self.routing_table.add_contact(
                    Contact(id=PingwiseID(hop_id), last_seen=time.time())
                )

    # -- serialisation ------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "id": self.id.to_dict(),
            "is_alive": self.is_alive,
            "storage_count": len(self.storage),
            "routing_table_size": self.routing_table.total_contacts,
            "storage_keys": list(self.storage.keys()),
        }


# ---------------------------------------------------------------------------
# PingwiseNetwork — Main Simulation Controller
# ---------------------------------------------------------------------------

class PingwiseNetwork:
    """Top-level controller that orchestrates a simulated Kademlia network.

    Manages node lifecycle, file storage/lookup, churn simulation, and
    benchmarking.  Exposes serialisable snapshots for the frontend
    visualisation layer.

    Attributes:
        nodes: Map of ``{id_int: PingwiseNode}`` for all live nodes.
        files: Map of stored files with replication metadata.
        event_log: Chronological list of network events.
        lookup_stats: Per-lookup metrics for aggregate analysis.
        network_size_history: Timestamped network size samples.
    """

    def __init__(self) -> None:
        self.nodes: Dict[int, PingwiseNode] = {}
        self.files: Dict[int, dict] = {}
        self.event_log: List[dict] = []
        self.lookup_stats: List[dict] = []
        self.network_size_history: List[Tuple[float, int]] = []

    # -- helpers ------------------------------------------------------------

    def _alive_nodes(self) -> Dict[int, PingwiseNode]:
        """Return a dict of only alive nodes."""
        return {k: v for k, v in self.nodes.items() if v.is_alive}

    def _log_event(self, event: dict) -> dict:
        """Append *event* to the log and return it."""
        event.setdefault("timestamp", time.time())
        self.event_log.append(event)
        return event

    def _record_size(self) -> None:
        self.network_size_history.append(
            (time.time(), len(self._alive_nodes()))
        )

    @staticmethod
    def _hash_key(key: str) -> int:
        """Deterministic hash mapping an arbitrary key string into
        the 16-bit ID space."""
        return hash(key) % (2 ** ID_BITS)

    # -- network lifecycle --------------------------------------------------

    def initialize(self, node_count: int) -> dict:
        """Create a fresh network with *node_count* nodes.

        The first node is created without bootstrapping.  Each subsequent
        node joins via a randomly chosen existing node.

        Args:
            node_count: Number of nodes to create (≥ 1).

        Returns:
            Network snapshot dict.

        Complexity: O(N log N) — N joins each taking O(log N) hops.
        """
        # Clear state
        self.nodes.clear()
        self.files.clear()
        self.event_log.clear()
        self.lookup_stats.clear()
        self.network_size_history.clear()

        if node_count < 1:
            node_count = 1

        # First node — no bootstrap
        first_id = PingwiseID.random()
        first_node = PingwiseNode(first_id)
        self.nodes[first_id.value] = first_node
        self._log_event({
            "type": "node_added",
            "node_id": first_id.value,
            "node_hex": first_id.to_hex(),
            "bootstrap": None,
        })
        self._record_size()

        # Remaining nodes
        for _ in range(node_count - 1):
            new_id = PingwiseID.random()
            while new_id.value in self.nodes:
                new_id = PingwiseID.random()

            # Bootstrap via random existing alive node BEFORE adding new_node to self.nodes
            bootstrap = random.choice(list(self._alive_nodes().values()))

            new_node = PingwiseNode(new_id)
            self.nodes[new_id.value] = new_node
            new_node.join_network(self.nodes, bootstrap)

            self._log_event({
                "type": "node_added",
                "node_id": new_id.value,
                "node_hex": new_id.to_hex(),
                "bootstrap": bootstrap.id.value,
            })
            self._record_size()

        return self.get_snapshot()

    def add_node(self) -> dict:
        """Add a single new node to the running network.

        Returns:
            ``{"node": dict, "event": dict, "snapshot": dict}``
        """
        new_id = PingwiseID.random()
        while new_id.value in self.nodes:
            new_id = PingwiseID.random()

        new_node = PingwiseNode(new_id)
        self.nodes[new_id.value] = new_node

        alive = self._alive_nodes()
        # Exclude the new node itself when choosing a bootstrap
        candidates = {k: v for k, v in alive.items() if k != new_id.value}
        if candidates:
            bootstrap = random.choice(list(candidates.values()))
            new_node.join_network(self.nodes, bootstrap)

        event = self._log_event({
            "type": "node_added",
            "node_id": new_id.value,
            "node_hex": new_id.to_hex(),
        })
        self._record_size()

        return {
            "node": new_node.to_dict(),
            "event": event,
            "snapshot": self.get_snapshot(),
        }

    def remove_node(self, node_id: Optional[int] = None) -> dict:
        """Remove a node from the network.

        If *node_id* is ``None``, a random alive node is chosen.

        Returns:
            Result dict with removed node info and snapshot.
        """
        alive = self._alive_nodes()
        if not alive:
            return {"error": "No alive nodes to remove"}

        if node_id is None:
            node_id = random.choice(list(alive.keys()))
        elif node_id not in self.nodes:
            return {"error": f"Node {node_id} not found"}

        target_node = self.nodes[node_id]
        target_node.is_alive = False

        # Remove from every other node's routing table
        for nid, node in self.nodes.items():
            if nid != node_id and node.is_alive:
                node.routing_table.remove_contact(PingwiseID(node_id))

        # Remove from nodes dict
        del self.nodes[node_id]

        event = self._log_event({
            "type": "node_removed",
            "node_id": node_id,
            "node_hex": PingwiseID(node_id).to_hex(),
        })
        self._record_size()

        return {
            "removed_id": node_id,
            "removed_hex": PingwiseID(node_id).to_hex(),
            "event": event,
            "snapshot": self.get_snapshot(),
        }

    # -- file operations ----------------------------------------------------

    def store_file(self, key: str, value: str) -> dict:
        """Store a file in the DHT.

        Steps:
            1. Hash *key* to a 16-bit integer.
            2. From a random alive node, perform iterative FIND_NODE
               to locate the K closest nodes to the key.
            3. STORE the value on each of those nodes.

        Returns:
            Detailed result including key mapping and storage nodes.
        """
        alive = self._alive_nodes()
        if not alive:
            return {"error": "No alive nodes in network"}

        key_int = self._hash_key(key)
        key_id = PingwiseID(key_int)

        # Pick random starting node
        start_node = random.choice(list(alive.values()))
        lookup_result = start_node.iterative_find_node(self.nodes, key_id)

        stored_on: List[int] = []
        for contact_dict in lookup_result["closest"]:
            cid = contact_dict["id"]["value"]
            if cid in self.nodes and self.nodes[cid].is_alive:
                self.nodes[cid].store(key_int, value)
                stored_on.append(cid)

        # Track file metadata
        self.files[key_int] = {
            "value": value,
            "stored_on": stored_on,
            "key_hex": key_id.to_hex(),
            "key_name": key,
        }

        self._log_event({
            "type": "file_stored",
            "key": key,
            "key_int": key_int,
            "key_hex": key_id.to_hex(),
            "stored_on": stored_on,
        })

        return {
            "key": key,
            "key_int": key_int,
            "key_hex": key_id.to_hex(),
            "stored_on": stored_on,
            "hops": lookup_result["hops"],
            "path": lookup_result["path"],
        }

    def lookup_file(self, key: str) -> dict:
        """Look up a file by key using iterative FIND_VALUE.

        Returns:
            Result dict with found status, value, hop count, and path.
        """
        alive = self._alive_nodes()
        if not alive:
            return {"error": "No alive nodes in network"}

        key_int = self._hash_key(key)

        start_node = random.choice(list(alive.values()))
        result = start_node.iterative_find_value(self.nodes, key_int)

        # Record stats
        self.lookup_stats.append({
            "hops": result["hops"],
            "success": result["found"],
            "network_size": len(alive),
        })

        return {
            "key": key,
            "key_int": key_int,
            "found": result["found"],
            "value": result.get("value"),
            "hops": result["hops"],
            "path": result["path"],
            "source_node": start_node.id.value,
        }

    # -- churn simulation ---------------------------------------------------

    def simulate_churn(self, add_count: int, remove_count: int) -> dict:
        """Simulate network churn by removing and adding nodes.

        Args:
            add_count: Number of nodes to add.
            remove_count: Number of nodes to remove.

        Returns:
            Event summary with updated stats and snapshot.
        """
        events: List[dict] = []

        # Removals first
        for _ in range(remove_count):
            alive = self._alive_nodes()
            if not alive:
                break
            result = self.remove_node()
            if "event" in result:
                events.append(result["event"])

        # Then additions
        for _ in range(add_count):
            if not self._alive_nodes():
                # Need at least one node; create a seed
                seed_id = PingwiseID.random()
                while seed_id.value in self.nodes:
                    seed_id = PingwiseID.random()
                seed_node = PingwiseNode(seed_id)
                self.nodes[seed_id.value] = seed_node
                events.append(self._log_event({
                    "type": "node_added",
                    "node_id": seed_id.value,
                    "node_hex": seed_id.to_hex(),
                    "bootstrap": None,
                }))
                self._record_size()
                continue

            result = self.add_node()
            if "event" in result:
                events.append(result["event"])

        return {
            "events": events,
            "added": add_count,
            "removed": remove_count,
            "stats": self.get_stats(),
            "snapshot": self.get_snapshot(),
        }

    # -- benchmarking -------------------------------------------------------

    def run_benchmark(
        self,
        node_count: int,
        file_count: int,
        churn_rounds: int,
        churn_add: int,
        churn_remove: int,
    ) -> dict:
        """Run a comprehensive benchmark measuring lookup efficiency.

        Steps:
            1. Initialise network with *node_count* nodes.
            2. Store *file_count* random files.
            3. Look up every file and record metrics (round 0).
            4. For each churn round, apply churn then re-lookup.
            5. Compute aggregate statistics.

        Returns:
            Benchmark data dict with per-round and aggregate metrics,
            plus a hop-count histogram.
        """
        self.initialize(node_count)

        # Store files
        file_keys: List[str] = []
        for i in range(file_count):
            key = f"file_{i}"
            value = f"data_{i}"
            self.store_file(key, value)
            file_keys.append(key)

        rounds: List[dict] = []
        all_hops: List[int] = []

        # Initial round (round 0)
        round_hops: List[int] = []
        round_success: int = 0
        total_lookups: int = 0
        for key in file_keys:
            result = self.lookup_file(key)
            round_hops.append(result["hops"])
            all_hops.append(result["hops"])
            total_lookups += 1
            if result["found"]:
                round_success += 1

        alive_count = len(self._alive_nodes())
        rounds.append({
            "round": 0,
            "avg_hops": sum(round_hops) / len(round_hops) if round_hops else 0,
            "success_rate": round_success / total_lookups if total_lookups else 0,
            "network_size": alive_count,
            "theoretical_max": math.log2(alive_count) if alive_count > 1 else 0,
        })

        # Churn rounds
        for r in range(1, churn_rounds + 1):
            self.simulate_churn(churn_add, churn_remove)

            round_hops = []
            round_success = 0
            total_lookups = 0
            for key in file_keys:
                result = self.lookup_file(key)
                round_hops.append(result["hops"])
                all_hops.append(result["hops"])
                total_lookups += 1
                if result["found"]:
                    round_success += 1

            alive_count = len(self._alive_nodes())
            rounds.append({
                "round": r,
                "avg_hops": (
                    sum(round_hops) / len(round_hops) if round_hops else 0
                ),
                "success_rate": (
                    round_success / total_lookups if total_lookups else 0
                ),
                "network_size": alive_count,
                "theoretical_max": (
                    math.log2(alive_count) if alive_count > 1 else 0
                ),
            })

        # Aggregate stats
        overall_avg_hops = sum(all_hops) / len(all_hops) if all_hops else 0
        overall_success = sum(
            1 for s in self.lookup_stats if s["success"]
        ) / len(self.lookup_stats) if self.lookup_stats else 0

        alive_count = len(self._alive_nodes())
        theoretical_log2n = math.log2(alive_count) if alive_count > 1 else 0

        # Hop distribution histogram
        hop_distribution: Dict[int, int] = {}
        for h in all_hops:
            hop_distribution[h] = hop_distribution.get(h, 0) + 1

        return {
            "node_count": node_count,
            "file_count": file_count,
            "churn_rounds": churn_rounds,
            "rounds": rounds,
            "overall_avg_hops": overall_avg_hops,
            "overall_success_rate": overall_success,
            "theoretical_log2n": theoretical_log2n,
            "hop_distribution": hop_distribution,
            "events": self.event_log[-50:],  # last 50 events for brevity
        }

    # -- query / inspection -------------------------------------------------

    def get_node_details(self, node_id: int) -> dict:
        """Return comprehensive details for a single node.

        Args:
            node_id: Integer ID of the node.

        Returns:
            Full node info including routing table buckets and storage.

        Raises:
            KeyError: If *node_id* is not in the network.
        """
        if node_id not in self.nodes:
            return {"error": f"Node {node_id} not found"}

        node = self.nodes[node_id]
        return {
            "id": node.id.to_dict(),
            "is_alive": node.is_alive,
            "storage": {
                str(k): v for k, v in node.storage.items()
            },
            "storage_count": len(node.storage),
            "routing_table": node.routing_table.to_dict(),
            "routing_table_size": node.routing_table.total_contacts,
            "buckets": node.routing_table.get_bucket_stats(),
        }

    def get_stats(self) -> dict:
        """Aggregate network statistics.

        Returns:
            Dict with node/file counts, lookup averages, and the
            theoretical O(log₂ N) bound for comparison.
        """
        alive = self._alive_nodes()
        n = len(alive)

        avg_hops = 0.0
        success_rate = 0.0
        if self.lookup_stats:
            avg_hops = sum(s["hops"] for s in self.lookup_stats) / len(
                self.lookup_stats
            )
            successes = sum(1 for s in self.lookup_stats if s["success"])
            success_rate = successes / len(self.lookup_stats)

        avg_rt_size = 0.0
        if alive:
            avg_rt_size = sum(
                node.routing_table.total_contacts for node in alive.values()
            ) / n

        return {
            "total_nodes": n,
            "total_files": len(self.files),
            "avg_hops": round(avg_hops, 2),
            "success_rate": round(success_rate, 4),
            "avg_routing_table_size": round(avg_rt_size, 2),
            "total_lookups": len(self.lookup_stats),
            "theoretical_log2n": round(math.log2(n), 2) if n > 1 else 0,
        }

    def get_snapshot(self) -> dict:
        """Return the full serialisable network state for visualisation.

        The ``links`` array contains unique undirected edges derived
        from every alive node's routing table.

        Returns:
            ``{"nodes": [...], "links": [...], "stats": {...}, "files": [...]}``
        """
        alive = self._alive_nodes()

        nodes_list = [
            {
                "id": node.id.value,
                "hex": node.id.to_hex(),
                "is_alive": node.is_alive,
                "storage_count": len(node.storage),
                "routing_table_size": node.routing_table.total_contacts,
            }
            for node in alive.values()
        ]

        # Build unique undirected links
        link_set: set = set()
        for node in alive.values():
            for contact in node.routing_table.get_all_contacts():
                edge = tuple(sorted((node.id.value, contact.id.value)))
                link_set.add(edge)

        links_list = [
            {"source": src, "target": tgt} for src, tgt in link_set
        ]

        files_list = [
            {
                "key": k,
                "key_hex": PingwiseID(k).to_hex(),
                "stored_on": v["stored_on"],
            }
            for k, v in self.files.items()
        ]

        return {
            "nodes": nodes_list,
            "links": links_list,
            "stats": self.get_stats(),
            "files": files_list,
        }
