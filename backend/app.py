"""
app.py — Flask REST API Server for Pingwise Kademlia DHT Simulator.

Provides REST endpoints for network operations, node management,
file storage/lookup, churn simulation, and algorithmic benchmarking.
Also serves the frontend static web application.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict
from flask import Flask, request, jsonify, send_from_directory

try:
    from flask_cors import CORS
    HAS_CORS = True
except ImportError:
    HAS_CORS = False

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.pingwise_core import PingwiseNetwork, PingwiseID

FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
if HAS_CORS:
    CORS(app)

# Fallback CORS headers in case flask-cors is not active
@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return response

# Single global network simulation instance
network = PingwiseNetwork()

# Pre-populate with initial 30 nodes so simulator is lively upon launch
try:
    network.initialize(30)
except Exception as e:
    print(f"Warning: Failed to auto-initialize default network: {e}")


# ---------------------------------------------------------------------------
# Static File Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """Serve the single-page application entry point."""
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/assets/<path:filename>")
def serve_assets(filename: str):
    """Serve assets such as logos and graphics."""
    return send_from_directory(ASSETS_DIR, filename)


# ---------------------------------------------------------------------------
# REST API Endpoints
# ---------------------------------------------------------------------------

@app.route("/api/network/init", methods=["POST"])
def api_network_init():
    """Initialize or reset the network with N nodes.

    JSON payload:
        node_count (int, optional): Number of nodes to initialize (default: 50).
    """
    try:
        data = request.get_json(silent=True) or {}
        node_count = int(data.get("node_count", 50))
        if node_count < 1 or node_count > 1000:
            return jsonify({"error": "node_count must be between 1 and 1000"}), 400

        snapshot = network.initialize(node_count)
        return jsonify(snapshot)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/network/snapshot", methods=["GET"])
def api_network_snapshot():
    """Return the current network snapshot (nodes, links, stats, files)."""
    try:
        snapshot = network.get_snapshot()
        return jsonify(snapshot)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/network/add-node", methods=["POST"])
def api_add_node():
    """Add a new node to the active network."""
    try:
        res = network.add_node()
        return jsonify(res)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/network/remove-node", methods=["POST"])
def api_remove_node():
    """Remove a node from the network (simulating departure or failure).

    JSON payload:
        node_id (int, optional): Node ID to remove. If omitted, a random node is chosen.
    """
    try:
        data = request.get_json(silent=True) or {}
        node_id_val = data.get("node_id")
        node_id = int(node_id_val) if node_id_val is not None else None
        res = network.remove_node(node_id)
        return jsonify(res)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/store", methods=["POST"])
def api_store():
    """Store a key-value file on the network across K closest peers.

    JSON payload:
        key (str): File/object key identifier.
        value (str): Content or payload string.
    """
    try:
        data = request.get_json(silent=True) or {}
        key = str(data.get("key", "")).strip()
        value = str(data.get("value", "")).strip()

        if not key:
            return jsonify({"error": "File 'key' is required"}), 400
        if not value:
            return jsonify({"error": "File 'value' is required"}), 400

        res = network.store_file(key, value)
        return jsonify(res)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/lookup", methods=["POST"])
def api_lookup():
    """Locate and retrieve a key-value file using Kademlia iterative lookup.

    JSON payload:
        key (str): Key of the file to lookup.
    """
    try:
        data = request.get_json(silent=True) or {}
        key = str(data.get("key", "")).strip()

        if not key:
            return jsonify({"error": "Lookup 'key' is required"}), 400

        res = network.lookup_file(key)
        return jsonify(res)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/churn/simulate", methods=["POST"])
def api_simulate_churn():
    """Simulate network churn by concurrently adding and dropping peers.

    JSON payload:
        add_count (int, optional): Number of new nodes to join (default: 10).
        remove_count (int, optional): Number of nodes to drop (default: 5).
    """
    try:
        data = request.get_json(silent=True) or {}
        add_count = int(data.get("add_count", 10))
        remove_count = int(data.get("remove_count", 5))

        if add_count < 0 or remove_count < 0:
            return jsonify({"error": "Counts must be non-negative"}), 400

        res = network.simulate_churn(add_count, remove_count)
        return jsonify(res)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/benchmark/run", methods=["POST"])
def api_run_benchmark():
    """Run empirical DAA benchmark comparing average lookup hops vs theoretical O(log N).

    JSON payload:
        node_count (int, optional): Target size of network (default: 100).
        file_count (int, optional): Number of files to test (default: 20).
        churn_rounds (int, optional): Number of churn iteration rounds (default: 5).
        churn_add (int, optional): Nodes added per round (default: 10).
        churn_remove (int, optional): Nodes removed per round (default: 5).
    """
    try:
        data = request.get_json(silent=True) or {}
        node_count = int(data.get("node_count", 100))
        file_count = int(data.get("file_count", 20))
        churn_rounds = int(data.get("churn_rounds", 5))
        churn_add = int(data.get("churn_add", 10))
        churn_remove = int(data.get("churn_remove", 5))

        res = network.run_benchmark(
            node_count=node_count,
            file_count=file_count,
            churn_rounds=churn_rounds,
            churn_add=churn_add,
            churn_remove=churn_remove,
        )
        return jsonify(res)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/node/<int:node_id>/details", methods=["GET"])
def api_node_details(node_id: int):
    """Retrieve detailed state of a specific node: k-buckets, contacts, storage."""
    try:
        details = network.get_node_details(node_id)
        return jsonify(details)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 404
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/stats", methods=["GET"])
def api_stats():
    """Retrieve global network statistics."""
    try:
        stats = network.get_stats()
        return jsonify(stats)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# Catch-all for other frontend assets (css, js, etc.)
@app.route("/<path:path>")
def serve_static(path: str):
    """Serve any remaining static assets from the frontend directory."""
    return send_from_directory(FRONTEND_DIR, path)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
