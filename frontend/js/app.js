/**
 * app.js — Main Application Orchestrator for Pingwise DHT Simulator.
 *
 * Coordinates UI controls, REST API calls, visualizer rendering,
 * metrics chart updates, and node inspection.
 */

class PingwiseApp {
    constructor() {
        this.visualizer = null;
        this.metrics = null;
        this.currentSnapshot = null;
        this.eventCount = 0;
    }

    async init() {
        console.log("Initializing Pingwise P2P DHT Simulator...");

        // 1. Initialize Visualizer
        const canvas = document.getElementById('network-canvas');
        if (canvas) {
            this.visualizer = new PingwiseVisualizer(canvas);
            this.visualizer.onNodeClick = (nodeId) => this.inspectNode(nodeId);
        }

        // 2. Initialize Metrics Dashboard
        const hopCanvas = document.getElementById('chart-hops');
        const successCanvas = document.getElementById('chart-success');
        const networkSizeCanvas = document.getElementById('chart-network-size');
        const heatmapCanvas = document.getElementById('chart-heatmap');

        this.metrics = new MetricsDashboard(hopCanvas, successCanvas, networkSizeCanvas, heatmapCanvas);

        // 3. Bind UI Controls
        this._bindControls();

        // 4. Initial network fetch
        await this.fetchInitialState();

        this.logEvent('info', 'Pingwise system ready. Kademlia DHT simulator initialized.');
    }

    _bindControls() {
        // Slider display
        const slider = document.getElementById('node-count-slider');
        const sliderDisplay = document.getElementById('node-count-display');
        if (slider && sliderDisplay) {
            slider.addEventListener('input', (e) => {
                sliderDisplay.textContent = e.target.value;
            });
        }

        // Initialize Network button
        const btnInit = document.getElementById('btn-init-network');
        if (btnInit) {
            btnInit.addEventListener('click', () => this.handleInitNetwork());
        }

        // Add Node button
        const btnAdd = document.getElementById('btn-add-node');
        if (btnAdd) {
            btnAdd.addEventListener('click', () => this.handleAddNode());
        }

        // Remove Node button
        const btnRemove = document.getElementById('btn-remove-node');
        if (btnRemove) {
            btnRemove.addEventListener('click', () => this.handleRemoveNode());
        }

        // Store File button
        const btnStore = document.getElementById('btn-store-file');
        if (btnStore) {
            btnStore.addEventListener('click', () => this.handleStoreFile());
        }

        // Lookup File button
        const btnLookup = document.getElementById('btn-lookup-file');
        if (btnLookup) {
            btnLookup.addEventListener('click', () => this.handleLookupFile());
        }

        // Simulate Churn button
        const btnChurn = document.getElementById('btn-simulate-churn');
        if (btnChurn) {
            btnChurn.addEventListener('click', () => this.handleSimulateChurn());
        }

        // Run Benchmark button
        const btnBench = document.getElementById('btn-run-benchmark');
        if (btnBench) {
            btnBench.addEventListener('click', () => this.handleRunBenchmark());
        }

        // Layout Radio Buttons
        const layoutRadios = document.querySelectorAll('input[name="layout"]');
        layoutRadios.forEach(radio => {
            radio.addEventListener('change', (e) => {
                if (e.target.checked && this.visualizer) {
                    this.visualizer.setLayout(e.target.value);
                    this.logEvent('info', `Layout switched to: ${e.target.value === 'ring' ? 'Ring (Circular ID Space)' : 'Force-Directed'}`);
                }
            });
        });
    }

    async fetchInitialState() {
        try {
            const res = await fetch('/api/network/snapshot');
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            this.handleSnapshotUpdate(data);
            await this.refreshHeatmap();
        } catch (err) {
            console.warn("Could not load initial snapshot:", err);
            this.logEvent('info', 'Server connection ready. Click "Initialize Network" to begin.');
        }
    }

    handleSnapshotUpdate(snapshot) {
        this.currentSnapshot = snapshot;
        if (this.visualizer) {
            this.visualizer.updateGraph(snapshot);
        }
        if (snapshot.stats) {
            this.updateHeaderStats(snapshot.stats);
        }
    }

    updateHeaderStats(stats) {
        if (!stats) return;
        const setVal = (id, val) => {
            const el = document.getElementById(id);
            if (el) el.textContent = val;
        };

        setVal('stat-nodes', stats.total_nodes !== undefined ? stats.total_nodes : '--');
        setVal('stat-files', stats.total_files !== undefined ? stats.total_files : '--');
        setVal('stat-hops', stats.avg_hops !== undefined ? stats.avg_hops : '--');
        setVal('stat-success', stats.success_rate !== undefined ? `${Math.round(stats.success_rate * 100)}%` : '--%');
    }

    async handleInitNetwork() {
        const slider = document.getElementById('node-count-slider');
        const count = slider ? parseInt(slider.value, 10) : 50;

        const btn = document.getElementById('btn-init-network');
        this._setButtonLoading(btn, true, 'Building DHT...');

        try {
            const res = await fetch('/api/network/init', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ node_count: count })
            });
            const data = await res.json();
            if (data.error) throw new Error(data.error);

            this.handleSnapshotUpdate(data);
            this.visualizer.clearHighlight();
            this.hideNodeDetails();
            this.hideLookupTrace();
            await this.refreshHeatmap();

            this.logEvent('add', `Network initialized with ${count} nodes and 16-bit XOR ID space.`);
        } catch (err) {
            alert(`Failed to initialize network: ${err.message}`);
            this.logEvent('remove', `Initialization error: ${err.message}`);
        } finally {
            this._setButtonLoading(btn, false, 'Initialize Network');
        }
    }

    async handleAddNode() {
        const btn = document.getElementById('btn-add-node');
        this._setButtonLoading(btn, true);

        try {
            const res = await fetch('/api/network/add-node', { method: 'POST' });
            const data = await res.json();
            if (data.error) throw new Error(data.error);

            this.handleSnapshotUpdate(data.snapshot);
            await this.refreshHeatmap();

            const hex = data.node ? data.node.id.hex : '';
            this.logEvent('add', `Node joined: ${hex} bootstrapped into network.`);
        } catch (err) {
            alert(`Failed to add node: ${err.message}`);
        } finally {
            this._setButtonLoading(btn, false);
        }
    }

    async handleRemoveNode() {
        const btn = document.getElementById('btn-remove-node');
        this._setButtonLoading(btn, true);

        try {
            const res = await fetch('/api/network/remove-node', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({})
            });
            const data = await res.json();
            if (data.error) throw new Error(data.error);

            this.handleSnapshotUpdate(data.snapshot);
            await this.refreshHeatmap();

            const hex = data.event ? `0x${data.event.node_id.toString(16).padStart(4, '0')}` : '';
            this.logEvent('remove', `Node departed: ${hex} removed (churn simulated).`);
        } catch (err) {
            alert(`Failed to remove node: ${err.message}`);
        } finally {
            this._setButtonLoading(btn, false);
        }
    }

    async handleStoreFile() {
        const keyInput = document.getElementById('store-key');
        const valInput = document.getElementById('store-value');
        const key = keyInput ? keyInput.value.trim() : '';
        const value = valInput ? valInput.value.trim() : '';

        if (!key || !value) {
            alert("Please specify both a file key and value.");
            return;
        }

        const btn = document.getElementById('btn-store-file');
        this._setButtonLoading(btn, true, 'Storing...');

        try {
            const res = await fetch('/api/store', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ key, value })
            });
            const data = await res.json();
            if (data.error) throw new Error(data.error);

            // Animate lookup path
            if (data.path && this.visualizer) {
                this.visualizer.highlightLookup(data.path);
            }

            // Populate Trace UI
            this.showLookupTrace({
                title: `STORE Operation for "${key}"`,
                key_hex: data.key_hex,
                hops: data.hops,
                path: data.path,
                found: true,
                value: `Replicated across ${data.stored_on ? data.stored_on.length : 0} closest k-peers`,
                target: `Key Hash: ${data.key_hex}`
            });

            // Update stats & log
            await this.refreshStats();
            this.logEvent('store', `File "${key}" stored across ${data.stored_on ? data.stored_on.length : 0} peers in ${data.hops} hops.`);
        } catch (err) {
            alert(`Store failed: ${err.message}`);
            this.logEvent('remove', `Store error: ${err.message}`);
        } finally {
            this._setButtonLoading(btn, false, 'Store File');
        }
    }

    async handleLookupFile() {
        const keyInput = document.getElementById('lookup-key');
        const key = keyInput ? keyInput.value.trim() : '';

        if (!key) {
            alert("Please provide a file key to search for.");
            return;
        }

        const btn = document.getElementById('btn-lookup-file');
        this._setButtonLoading(btn, true, 'Searching...');

        try {
            const res = await fetch('/api/lookup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ key })
            });
            const data = await res.json();
            if (data.error) throw new Error(data.error);

            // Animate path on canvas
            if (data.path && this.visualizer) {
                this.visualizer.highlightLookup(data.path);
            }

            // Populate Trace UI
            this.showLookupTrace({
                title: `FIND_VALUE Lookup for "${key}"`,
                key_hex: `0x${(data.key_int || 0).toString(16).padStart(4, '0')}`,
                hops: data.hops,
                path: data.path,
                found: data.found,
                value: data.value,
                target: `Target ID: 0x${(data.key_int || 0).toString(16).padStart(4, '0')}`
            });

            await this.refreshStats();

            if (data.found) {
                this.logEvent('lookup', `Lookup SUCCESS: "${key}" found in ${data.hops} hops! Value: "${data.value}"`);
            } else {
                this.logEvent('remove', `Lookup MISS: "${key}" could not be located (${data.hops} hops traversed).`);
            }
        } catch (err) {
            alert(`Lookup failed: ${err.message}`);
            this.logEvent('remove', `Lookup error: ${err.message}`);
        } finally {
            this._setButtonLoading(btn, false, 'Lookup File');
        }
    }

    async handleSimulateChurn() {
        const addEl = document.getElementById('churn-add');
        const remEl = document.getElementById('churn-remove');
        const addCount = addEl ? parseInt(addEl.value, 10) : 10;
        const removeCount = remEl ? parseInt(remEl.value, 10) : 5;

        const btn = document.getElementById('btn-simulate-churn');
        this._setButtonLoading(btn, true, 'Churning...');

        try {
            const res = await fetch('/api/churn/simulate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ add_count: addCount, remove_count: removeCount })
            });
            const data = await res.json();
            if (data.error) throw new Error(data.error);

            this.handleSnapshotUpdate(data.snapshot);
            await this.refreshHeatmap();

            this.logEvent('churn', `Churn event: +${data.added} added, -${data.removed} removed. Network size: ${data.stats ? data.stats.total_nodes : 'N/A'}`);
        } catch (err) {
            alert(`Churn simulation failed: ${err.message}`);
        } finally {
            this._setButtonLoading(btn, false, 'Simulate Churn');
        }
    }

    async handleRunBenchmark() {
        const nEl = document.getElementById('bench-nodes');
        const fEl = document.getElementById('bench-files');
        const rEl = document.getElementById('bench-rounds');

        const nodeCount = nEl ? parseInt(nEl.value, 10) : 100;
        const fileCount = fEl ? parseInt(fEl.value, 10) : 20;
        const rounds = rEl ? parseInt(rEl.value, 10) : 5;

        const btn = document.getElementById('btn-run-benchmark');
        this._setButtonLoading(btn, true, 'Benchmarking...');

        this.logEvent('churn', `Starting DAA benchmark: ${nodeCount} nodes, ${fileCount} files, ${rounds} churn rounds...`);

        try {
            const res = await fetch('/api/benchmark/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    node_count: nodeCount,
                    file_count: fileCount,
                    churn_rounds: rounds,
                    churn_add: 10,
                    churn_remove: 5
                })
            });
            const data = await res.json();
            if (data.error) throw new Error(data.error);

            // Update all 4 metrics charts with empirical benchmark data!
            if (this.metrics) {
                this.metrics.updateFromBenchmark(data);
            }

            // Sync visualizer with post-benchmark state
            await this.fetchInitialState();

            this.logEvent('lookup', `Benchmark COMPLETE: Avg Hops: ${data.overall_avg_hops} (Theoretical log2 N: ${data.theoretical_log2n}), Success: ${(data.overall_success_rate * 100).toFixed(1)}%`);
        } catch (err) {
            alert(`Benchmark failed: ${err.message}`);
            this.logEvent('remove', `Benchmark error: ${err.message}`);
        } finally {
            this._setButtonLoading(btn, false, 'Run Benchmark');
        }
    }

    async inspectNode(nodeId) {
        try {
            const res = await fetch(`/api/node/${nodeId}/details`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();

            const emptyState = document.getElementById('node-details-empty');
            const content = document.getElementById('node-details-content');
            if (emptyState) emptyState.style.display = 'none';
            if (content) content.style.display = 'block';

            // Set text details
            const setText = (id, txt) => {
                const el = document.getElementById(id);
                if (el) el.textContent = txt;
            };

            setText('detail-node-id', data.id.value);
            setText('detail-node-hex', data.id.hex);
            setText('detail-node-binary', data.id.binary);
            setText('detail-node-status', data.is_alive ? 'Alive (Active Peer)' : 'Dead / Stale');
            setText('detail-node-connections', `${data.routing_table_size || 0} peers`);

            // Render Routing Table Buckets Mini Bar Chart
            const chartEl = document.getElementById('detail-bucket-chart');
            if (chartEl && Array.isArray(data.buckets)) {
                chartEl.innerHTML = '';
                data.buckets.forEach((b) => {
                    const bar = document.createElement('div');
                    bar.className = 'bucket-bar' + (b.size === 0 ? ' bucket-bar--empty' : '');
                    const heightPercent = b.size > 0 ? Math.max((b.size / b.capacity) * 100, 20) : 10;
                    bar.style.height = `${heightPercent}%`;
                    bar.title = `Bucket ${b.index}: ${b.size}/${b.capacity} contacts`;
                    chartEl.appendChild(bar);
                });
            }

            // Render Stored Keys list
            const keysContainer = document.getElementById('detail-stored-keys');
            if (keysContainer) {
                keysContainer.innerHTML = '';
                const storageKeys = Object.keys(data.storage || {});
                if (storageKeys.length === 0) {
                    keysContainer.innerHTML = '<p class="text-muted">No stored keys</p>';
                } else {
                    storageKeys.forEach(k => {
                        const item = document.createElement('div');
                        item.className = 'stored-key-item';
                        item.textContent = `Key ${k}: "${data.storage[k]}"`;
                        keysContainer.appendChild(item);
                    });
                }
            }

            this.logEvent('info', `Inspecting Node ${data.id.hex} (${data.routing_table_size} routing contacts).`);
        } catch (err) {
            console.error("Inspect node error:", err);
        }
    }

    hideNodeDetails() {
        const emptyState = document.getElementById('node-details-empty');
        const content = document.getElementById('node-details-content');
        if (emptyState) emptyState.style.display = 'block';
        if (content) content.style.display = 'none';
    }

    showLookupTrace(info) {
        const emptyState = document.getElementById('lookup-trace-empty');
        const content = document.getElementById('lookup-trace-content');
        if (emptyState) emptyState.style.display = 'none';
        if (content) content.style.display = 'block';

        const summaryEl = document.getElementById('trace-summary');
        if (summaryEl) {
            summaryEl.innerHTML = `<strong>${info.title}</strong><br>${info.target} • ${info.hops} total hops`;
        }

        const hopsEl = document.getElementById('trace-hops');
        if (hopsEl) {
            hopsEl.innerHTML = '';
            if (Array.isArray(info.path)) {
                info.path.forEach((nodeId, idx) => {
                    const hex = `0x${nodeId.toString(16).padStart(4, '0')}`;
                    const row = document.createElement('div');
                    row.className = 'trace-hop';
                    row.innerHTML = `
                        <span class="trace-hop__number">${idx === 0 ? 'START' : `HOP ${idx}`}</span>
                        <span class="trace-hop__arrow">→</span>
                        <span class="trace-hop__node">Node ${hex} (${nodeId})</span>
                    `;
                    hopsEl.appendChild(row);
                });
            }
        }

        const resultEl = document.getElementById('trace-result');
        if (resultEl) {
            if (info.found) {
                resultEl.className = 'trace-result trace-result--found';
                resultEl.innerHTML = `✓ FOUND: "${info.value}"`;
            } else {
                resultEl.className = 'trace-result trace-result--not-found';
                resultEl.innerHTML = `✗ NOT FOUND: Target key absent in closest k-neighborhood`;
            }
        }
    }

    hideLookupTrace() {
        const emptyState = document.getElementById('lookup-trace-empty');
        const content = document.getElementById('lookup-trace-content');
        if (emptyState) emptyState.style.display = 'block';
        if (content) content.style.display = 'none';
    }

    async refreshStats() {
        try {
            const res = await fetch('/api/stats');
            if (res.ok) {
                const stats = await res.json();
                this.updateHeaderStats(stats);
            }
        } catch (e) {
            // silent ignore
        }
    }

    async refreshHeatmap() {
        if (!this.currentSnapshot || !this.currentSnapshot.nodes || !this.metrics) return;

        // Sample up to 10 nodes to build heatmap
        const sampleNodes = this.currentSnapshot.nodes.slice(0, 10);
        const heatmapRows = [];

        for (const n of sampleNodes) {
            try {
                const res = await fetch(`/api/node/${n.id}/details`);
                if (res.ok) {
                    const data = await res.json();
                    const bucketsArray = (data.buckets || []).map(b => b.size);
                    heatmapRows.push({
                        node_hex: n.hex,
                        buckets: bucketsArray
                    });
                }
            } catch (err) {
                // ignore
            }
        }

        if (heatmapRows.length > 0) {
            this.metrics.updateHeatmap(heatmapRows);
        }
    }

    logEvent(type, text) {
        const logContainer = document.getElementById('event-log');
        if (!logContainer) return;

        const now = new Date();
        const timeStr = [
            now.getHours().toString().padStart(2, '0'),
            now.getMinutes().toString().padStart(2, '0'),
            now.getSeconds().toString().padStart(2, '0')
        ].join(':');

        const entry = document.createElement('div');
        entry.className = `event-entry event-entry--${type}`;
        entry.innerHTML = `
            <span class="event-dot"></span>
            <span class="event-time">${timeStr}</span>
            <span class="event-text">${text}</span>
        `;

        logContainer.appendChild(entry);
        logContainer.scrollTop = logContainer.scrollHeight;

        // Keep maximum 80 entries to prevent memory growth
        while (logContainer.children.length > 80) {
            logContainer.removeChild(logContainer.firstChild);
        }
    }

    _setButtonLoading(btn, isLoading, loadingText = '') {
        if (!btn) return;
        if (isLoading) {
            btn.dataset.originalHtml = btn.innerHTML;
            btn.disabled = true;
            btn.style.opacity = '0.7';
            if (loadingText) btn.textContent = loadingText;
        } else {
            btn.disabled = false;
            btn.style.opacity = '1';
            if (btn.dataset.originalHtml) {
                btn.innerHTML = btn.dataset.originalHtml;
            }
        }
    }
}

// Bootstrap on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    window.pingwise = new PingwiseApp();
    window.pingwise.init();
});
