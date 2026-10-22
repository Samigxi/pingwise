# Pingwise — Peer-to-Peer Distributed Hash Table (DHT) Simulator

<p align="center">
  <img src="assets/pingwise-icon.png" width="96" height="96" alt="Pingwise Logo" style="border-radius: 16px; filter: drop-shadow(0 0 16px rgba(0, 240, 255, 0.6));">
</p>

<p align="center">
  <strong>A high-performance Kademlia DHT simulator engineered for Design and Analysis of Algorithms (DAA).</strong><br>
  Demonstrates decentralized $O(\log N)$ key-value routing using the XOR metric space, k-bucket routing tables, iterative node lookups, and empirical churn benchmarking.
</p>

---

## 🌟 Overview & Algorithmic Problem Statement

### The Problem
Centralized databases create single points of failure and bandwidth bottlenecks. Decentralized peer-to-peer protocols (such as BitTorrent, IPFS, and Ethereum discv5) require a mechanism to find which specific node holds a key **without broadcast-pinging every computer on earth**.

### The DAA Paradigm
- **Bitwise Searching & XOR Metric Space:** Distance is calculated using bitwise exclusive-OR:
  $$d(x, y) = x \oplus y$$
- **Metric Tree Routing Tables:** Each simulated node maintains a routing table organized into $B$ specialized k-buckets covering exponentially expanding distance tiers $[2^i, 2^{i+1})$.
- **Metric-Halving Iterative Search:** Every iterative lookup query halves the XOR distance to the target, guaranteeing convergence to the $k$ closest nodes in strictly $O(\log N)$ steps.
- **Churn Resilience & LRU Replacement:** Simulated network churn tests DHT survivability under random mid-execution node departures and arrivals.

---

## 🚀 Key Features

- **🧠 Pure Algorithm Backend (Python):**
  - Bitwise 16-bit identifier space ($2^{16} = 65,536$ addresses)
  - Mathematical verification of XOR metric properties (Identity, Symmetry, Triangle Inequality, Unidirectionality)
  - Full Kademlia RPC primitives (`PING`, `STORE`, `FIND_NODE`, `FIND_VALUE`)
  - Parallel asynchronous iterative lookup algorithm with shortlist pruning
  - Automated network churn simulation and empirical benchmarks
- **🎨 Vibrant Glassmorphism Frontend (D3.js + HTML5 Canvas):**
  - Real-time 60 FPS force-directed network graph and Chord-style circular ID ring layouts
  - Animated glowing particle trails tracing each hop in a lookup route
  - Interactive node inspector showing 16-bit bucket occupancy mini-bars and local storage
  - High-DPI (Retina) Canvas metrics dashboard:
    1. **Hop Count Distribution** (Bar chart histogram)
    2. **Lookup Success Rate Under Churn** (Line chart with gradient area)
    3. **Network Scale vs Theoretical $O(\log_2 N)$** (Comparative curve)
    4. **Routing Table Heatmap** (Grid of k-bucket occupancy across active peers)

---

## 📐 Algorithm Complexity & Mathematical Proofs

### Time & Space Complexity Summary

| Operation | Complexity | Mathematical Explanation |
| :--- | :---: | :--- |
| **XOR Distance Metric** | $\mathcal{O}(1)$ | Single machine-word bitwise XOR instruction: $a \oplus b$. |
| **Bucket Index Lookup** | $\mathcal{O}(1)$ | Index of highest set bit via integer bit-length: $\lfloor \log_2(d) \rfloor$. |
| **Local Contact Insertion** | $\mathcal{O}(k)$ | LRU cache eviction and duplicate promotion within fixed capacity $k=4$. |
| **Find $k$ Closest Contacts** | $\mathcal{O}(N \log k)$ | Priority queue / sort over aggregated routing table entries. |
| **Iterative Node Lookup** | $\mathcal{O}(\log N)$ | In each round, common prefix increases by $\ge 1$ bit, halving remaining distance. |
| **File Store / Retrieve** | $\mathcal{O}(\log N)$ | Iterative lookup to find $k$ closest neighborhood + $\mathcal{O}(1)$ local map write/read. |
| **Network Join Bootstrap** | $\mathcal{O}(\log N)$ | Mutual introduction with bootstrap peer + self-lookup populating k-buckets. |
| **Routing Table Storage** | $\mathcal{O}(k \cdot B)$ | $B = 16$ buckets, each storing up to $k=4$ contacts (max 64 contacts per node). |

### Formal XOR Metric Properties

1. **Identity of Indiscernibles:**
   $$d(x, y) = 0 \iff x = y$$
2. **Symmetry:**
   $$d(x, y) = x \oplus y = y \oplus x = d(y, x)$$
   *Significance:* Passive mutual routing table learning without asymmetric coordinate transformations.
3. **Triangle Inequality:**
   $$d(x, z) \le d(x, y) + d(y, z)$$
   *Proof:* Since $x \oplus z = (x \oplus y) \oplus (y \oplus z)$ and $a \oplus b \le a + b$ for all non-negative integers.
4. **Unidirectionality:**
   $$\forall x \in \{0, 1\}^B, \; \forall \Delta \ge 0, \; \exists ! \; y \in \{0, 1\}^B \text{ such that } d(x, y) = \Delta$$
   *Significance:* For any point and distance, exactly one point exists. All lookups for a given key converge along monotonic unidirectional paths, enabling cache optimization.

---

## 🛠️ Project Architecture

```
PBL 3/
├── run.py                     # Entry point — starts Flask application
├── requirements.txt           # Python dependencies (flask, flask-cors)
├── README.md                  # Comprehensive documentation and proofs
├── assets/
│   ├── pingwise-icon.png      # High-res glowing node icon
│   └── pingwise-logo.svg      # Vector SVG network logo
├── backend/
│   ├── pingwise_core.py       # Full Kademlia DHT Engine (all algorithms)
│   ├── app.py                 # Flask REST API endpoints
│   └── tests/
│       ├── test_pingwise.py   # Algorithmic unit tests (XOR, KBuckets, Lookups)
│       └── test_api.py        # REST API integration tests
└── frontend/
    ├── index.html             # Single-page web application
    ├── css/
    │   └── index.css          # Dark-mode glassmorphism design system
    └── js/
        ├── pingwise-viz.js    # D3 force physics + Canvas rendering & particle trails
        ├── pingwise-metrics.js# Canvas chart engine (histograms, line charts, heatmaps)
        └── app.js             # UI controller & REST API communication
```

---

## ⚡ Quick Start

### 1. Requirements
- Python 3.9+ installed
- Web browser (Chrome, Edge, Firefox, or Safari)

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the Simulator
```bash
python run.py
```
Open **[http://localhost:5000](http://localhost:5000)** in your browser.

### 4. Run the Unit & Integration Tests
```bash
python -m unittest discover -s backend/tests
```

---

## 🧪 Computational Benchmarks

The benchmark suite (`POST /api/benchmark/run` or via the **Run Benchmark** button in the UI) empirically validates the DHT's performance:
1. **Initial Baseline:** Measures average lookup hops in a quiescent network against theoretical $\log_2(N)$.
2. **Network Churn:** In each round, drops random nodes and introduces newcomers, measuring lookup success rate and hop degradation.
3. **Replication Resilience:** Demonstrates how $k=4$ replication guarantees $>95\%$ retrieval success even when $20-30\%$ of nodes are randomly terminated.
