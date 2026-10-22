/**
 * pingwise-metrics.js — Canvas-based Metrics Dashboard for Pingwise DHT.
 *
 * Renders real-time computational analytics without heavy chart dependencies:
 * 1. Hop Count Distribution (Bar Chart)
 * 2. Success Rate Over Time / Rounds (Line Chart)
 * 3. Network Size vs Theoretical log2(N) (Area Chart)
 * 4. Routing Table Heatmap (16-bit Bucket Occupancy Grid)
 */

class MetricsDashboard {
    constructor(hopCanvas, successCanvas, networkSizeCanvas, heatmapCanvas) {
        this.canvases = {
            hops: hopCanvas,
            success: successCanvas,
            networkSize: networkSizeCanvas,
            heatmap: heatmapCanvas
        };
        this.ctxs = {
            hops: hopCanvas ? hopCanvas.getContext('2d') : null,
            success: successCanvas ? successCanvas.getContext('2d') : null,
            networkSize: networkSizeCanvas ? networkSizeCanvas.getContext('2d') : null,
            heatmap: heatmapCanvas ? heatmapCanvas.getContext('2d') : null
        };
        this.dpi = window.devicePixelRatio || 1;

        this._setupCanvases();
        this.renderPlaceholders();

        window.addEventListener('resize', () => {
            this._setupCanvases();
            this._reRenderCurrent();
        });
    }

    _setupCanvases() {
        this.dpi = window.devicePixelRatio || 1;
        Object.keys(this.canvases).forEach((key) => {
            const canvas = this.canvases[key];
            if (!canvas) return;
            const rect = canvas.getBoundingClientRect();
            const w = Math.max(rect.width, 240);
            const h = Math.max(rect.height, 160);

            canvas.width = w * this.dpi;
            canvas.height = h * this.dpi;
            const ctx = this.ctxs[key];
            ctx.setTransform(this.dpi, 0, 0, this.dpi, 0, 0);
        });
    }

    renderPlaceholders() {
        this._drawEmpty(this.ctxs.hops, this.canvases.hops, 'Hop Distribution', 'Run lookups or benchmark');
        this._drawEmpty(this.ctxs.success, this.canvases.success, 'Success Rate', 'Awaiting benchmark run');
        this._drawEmpty(this.ctxs.networkSize, this.canvases.networkSize, 'Network Scale & O(log N)', 'Awaiting data');
        this._drawEmpty(this.ctxs.heatmap, this.canvases.heatmap, 'Routing Table Heatmap', 'Click node or init network');
    }

    _drawEmpty(ctx, canvas, title, subtitle) {
        if (!ctx || !canvas) return;
        const w = canvas.width / this.dpi;
        const h = canvas.height / this.dpi;

        ctx.clearRect(0, 0, w, h);
        ctx.fillStyle = '#0d1322';
        ctx.fillRect(0, 0, w, h);

        ctx.fillStyle = '#64748b';
        ctx.font = '600 12px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(title, w / 2, h / 2 - 8);

        ctx.font = '400 10px "JetBrains Mono", monospace';
        ctx.fillStyle = '#475569';
        ctx.fillText(subtitle, w / 2, h / 2 + 12);
    }

    _reRenderCurrent() {
        if (this._lastHopData) this.updateHopDistribution(this._lastHopData);
        if (this._lastRoundsData) {
            this.updateSuccessRate(this._lastRoundsData);
            this.updateNetworkSize(this._lastRoundsData);
        }
        if (this._lastHeatmapData) this.updateHeatmap(this._lastHeatmapData);
    }

    /**
     * 1. Hop Count Distribution (Bar Chart)
     * hopData: { "1": count, "2": count, ... }
     */
    updateHopDistribution(hopData) {
        this._lastHopData = hopData;
        const ctx = this.ctxs.hops;
        const canvas = this.canvases.hops;
        if (!ctx || !canvas || !hopData) return;

        const w = canvas.width / this.dpi;
        const h = canvas.height / this.dpi;
        ctx.clearRect(0, 0, w, h);

        // Dark background
        ctx.fillStyle = '#0d1322';
        ctx.fillRect(0, 0, w, h);

        const keys = Object.keys(hopData).sort((a, b) => parseInt(a) - parseInt(b));
        if (keys.length === 0) {
            this._drawEmpty(ctx, canvas, 'Hop Distribution', 'No lookups recorded yet');
            return;
        }

        const values = keys.map(k => hopData[k]);
        const maxVal = Math.max(...values, 1);

        const padLeft = 36;
        const padRight = 16;
        const padTop = 30;
        const padBottom = 28;
        const chartW = w - padLeft - padRight;
        const chartH = h - padTop - padBottom;

        // Title
        ctx.font = '600 11px Inter, sans-serif';
        ctx.fillStyle = '#94a3b8';
        ctx.textAlign = 'left';
        ctx.fillText('HOP COUNT DISTRIBUTION', padLeft, 18);

        // Y-axis gridlines
        ctx.font = '500 9px "JetBrains Mono", monospace';
        ctx.fillStyle = '#475569';
        ctx.textAlign = 'right';
        const gridSteps = 3;
        for (let i = 0; i <= gridSteps; i++) {
            const y = padTop + chartH - (i / gridSteps) * chartH;
            const labelVal = Math.round((i / gridSteps) * maxVal);
            ctx.fillText(labelVal.toString(), padLeft - 6, y + 3);

            ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
            ctx.beginPath();
            ctx.moveTo(padLeft, y);
            ctx.lineTo(w - padRight, y);
            ctx.stroke();
        }

        // Bars
        const barWidth = Math.max(Math.min(chartW / keys.length - 8, 36), 8);
        const slotWidth = chartW / keys.length;

        keys.forEach((key, idx) => {
            const count = hopData[key];
            const barH = (count / maxVal) * chartH;
            const x = padLeft + idx * slotWidth + (slotWidth - barWidth) / 2;
            const y = padTop + chartH - barH;

            // Bar Gradient
            const grad = ctx.createLinearGradient(0, y, 0, y + barH);
            grad.addColorStop(0, '#00f0ff');
            grad.addColorStop(1, 'rgba(0, 240, 255, 0.15)');

            ctx.fillStyle = grad;
            ctx.beginPath();
            ctx.roundRect ? ctx.roundRect(x, y, barWidth, barH, [3, 3, 0, 0]) : ctx.rect(x, y, barWidth, barH);
            ctx.fill();

            // Value text above bar
            if (barH > 14) {
                ctx.fillStyle = '#ffffff';
                ctx.font = '600 9px "JetBrains Mono", monospace';
                ctx.textAlign = 'center';
                ctx.fillText(count.toString(), x + barWidth / 2, y - 4);
            }

            // X label
            ctx.fillStyle = '#94a3b8';
            ctx.font = '500 9px "JetBrains Mono", monospace';
            ctx.textAlign = 'center';
            ctx.fillText(`${key}h`, x + barWidth / 2, h - 10);
        });
    }

    /**
     * 2. Success Rate Over Time / Rounds (Line Chart)
     * rounds: [{ round: 0, success_rate: 1.0 }, ...]
     */
    updateSuccessRate(rounds) {
        this._lastRoundsData = rounds;
        const ctx = this.ctxs.success;
        const canvas = this.canvases.success;
        if (!ctx || !canvas || !Array.isArray(rounds)) return;

        const w = canvas.width / this.dpi;
        const h = canvas.height / this.dpi;
        ctx.clearRect(0, 0, w, h);

        ctx.fillStyle = '#0d1322';
        ctx.fillRect(0, 0, w, h);

        if (rounds.length === 0) {
            this._drawEmpty(ctx, canvas, 'Success Rate', 'Awaiting benchmark run');
            return;
        }

        const padLeft = 40;
        const padRight = 16;
        const padTop = 30;
        const padBottom = 28;
        const chartW = w - padLeft - padRight;
        const chartH = h - padTop - padBottom;

        // Title
        ctx.font = '600 11px Inter, sans-serif';
        ctx.fillStyle = '#94a3b8';
        ctx.textAlign = 'left';
        ctx.fillText('LOOKUP SUCCESS RATE (CHURN RESILIENCE)', padLeft, 18);

        // 100% reference line (dashed green)
        const y100 = padTop;
        ctx.save();
        ctx.strokeStyle = 'rgba(16, 185, 129, 0.4)';
        ctx.lineWidth = 1;
        ctx.setLineDash([3, 4]);
        ctx.beginPath();
        ctx.moveTo(padLeft, y100);
        ctx.lineTo(w - padRight, y100);
        ctx.stroke();
        ctx.restore();

        // Y-axis labels
        ctx.font = '500 9px "JetBrains Mono", monospace';
        ctx.fillStyle = '#475569';
        ctx.textAlign = 'right';
        ctx.fillText('100%', padLeft - 6, y100 + 3);
        ctx.fillText('50%', padLeft - 6, padTop + chartH / 2 + 3);
        ctx.fillText('0%', padLeft - 6, padTop + chartH + 3);

        // Plot points
        const points = rounds.map((r, i) => {
            const x = padLeft + (rounds.length > 1 ? (i / (rounds.length - 1)) * chartW : chartW / 2);
            const rate = Math.min(Math.max(r.success_rate !== undefined ? r.success_rate : 1, 0), 1);
            const y = padTop + (1 - rate) * chartH;
            return { x, y, rate, round: r.round !== undefined ? r.round : i };
        });

        // Area fill
        if (points.length > 0) {
            ctx.beginPath();
            ctx.moveTo(points[0].x, padTop + chartH);
            points.forEach(p => ctx.lineTo(p.x, p.y));
            ctx.lineTo(points[points.length - 1].x, padTop + chartH);
            ctx.closePath();

            const grad = ctx.createLinearGradient(0, padTop, 0, padTop + chartH);
            grad.addColorStop(0, 'rgba(16, 185, 129, 0.35)');
            grad.addColorStop(1, 'rgba(16, 185, 129, 0.02)');
            ctx.fillStyle = grad;
            ctx.fill();

            // Line stroke
            ctx.beginPath();
            points.forEach((p, i) => {
                if (i === 0) ctx.moveTo(p.x, p.y);
                else ctx.lineTo(p.x, p.y);
            });
            ctx.strokeStyle = '#10b981';
            ctx.lineWidth = 2.5;
            ctx.stroke();

            // Dots
            points.forEach(p => {
                ctx.beginPath();
                ctx.arc(p.x, p.y, 3.5, 0, 2 * Math.PI);
                ctx.fillStyle = '#ffffff';
                ctx.fill();
                ctx.strokeStyle = '#10b981';
                ctx.lineWidth = 2;
                ctx.stroke();

                // Round label
                ctx.fillStyle = '#94a3b8';
                ctx.font = '500 8px "JetBrains Mono", monospace';
                ctx.textAlign = 'center';
                ctx.fillText(`R${p.round}`, p.x, h - 10);
            });
        }
    }

    /**
     * 3. Network Size vs Theoretical log2(N) (Area Chart)
     * rounds: [{ round: 0, network_size: 100, theoretical_max: 6.64, avg_hops: 3.2 }, ...]
     */
    updateNetworkSize(rounds) {
        const ctx = this.ctxs.networkSize;
        const canvas = this.canvases.networkSize;
        if (!ctx || !canvas || !Array.isArray(rounds)) return;

        const w = canvas.width / this.dpi;
        const h = canvas.height / this.dpi;
        ctx.clearRect(0, 0, w, h);

        ctx.fillStyle = '#0d1322';
        ctx.fillRect(0, 0, w, h);

        if (rounds.length === 0) {
            this._drawEmpty(ctx, canvas, 'Network Scale & O(log N)', 'Awaiting benchmark run');
            return;
        }

        const padLeft = 40;
        const padRight = 16;
        const padTop = 30;
        const padBottom = 28;
        const chartW = w - padLeft - padRight;
        const chartH = h - padTop - padBottom;

        // Title
        ctx.font = '600 11px Inter, sans-serif';
        ctx.fillStyle = '#94a3b8';
        ctx.textAlign = 'left';
        ctx.fillText('HOPS VS THEORETICAL O(log2 N)', padLeft, 18);

        const maxHops = Math.max(...rounds.map(r => Math.max(r.theoretical_max || 0, r.avg_hops || 0)), 4);

        // Y-axis grid
        ctx.font = '500 9px "JetBrains Mono", monospace';
        ctx.fillStyle = '#475569';
        ctx.textAlign = 'right';
        for (let i = 0; i <= 3; i++) {
            const y = padTop + chartH - (i / 3) * chartH;
            const val = ((i / 3) * maxHops).toFixed(1);
            ctx.fillText(val, padLeft - 6, y + 3);

            ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
            ctx.beginPath();
            ctx.moveTo(padLeft, y);
            ctx.lineTo(w - padRight, y);
            ctx.stroke();
        }

        // Plot theoretical curve (cyan dashed) and empirical avg hops (violet line)
        const getX = (idx) => padLeft + (rounds.length > 1 ? (idx / (rounds.length - 1)) * chartW : chartW / 2);

        // 1. Theoretical log2(N) line
        ctx.save();
        ctx.strokeStyle = '#00f0ff';
        ctx.lineWidth = 1.8;
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        rounds.forEach((r, idx) => {
            const x = getX(idx);
            const val = r.theoretical_max || (r.network_size ? Math.log2(r.network_size) : 0);
            const y = padTop + chartH - (val / maxHops) * chartH;
            if (idx === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        });
        ctx.stroke();
        ctx.restore();

        // 2. Empirical Avg Hops line with points
        ctx.beginPath();
        rounds.forEach((r, idx) => {
            const x = getX(idx);
            const val = r.avg_hops || 0;
            const y = padTop + chartH - (val / maxHops) * chartH;
            if (idx === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        });
        ctx.strokeStyle = '#a855f7';
        ctx.lineWidth = 2.5;
        ctx.stroke();

        rounds.forEach((r, idx) => {
            const x = getX(idx);
            const val = r.avg_hops || 0;
            const y = padTop + chartH - (val / maxHops) * chartH;

            ctx.beginPath();
            ctx.arc(x, y, 3.5, 0, 2 * Math.PI);
            ctx.fillStyle = '#ffffff';
            ctx.fill();
            ctx.strokeStyle = '#a855f7';
            ctx.lineWidth = 2;
            ctx.stroke();

            // Round label below
            ctx.fillStyle = '#94a3b8';
            ctx.font = '500 8px "JetBrains Mono", monospace';
            ctx.textAlign = 'center';
            ctx.fillText(`R${r.round !== undefined ? r.round : idx}`, x, h - 10);
        });

        // Legend top right
        ctx.font = '500 9px "JetBrains Mono", monospace';
        ctx.fillStyle = '#00f0ff';
        ctx.textAlign = 'right';
        ctx.fillText('-- log2(N)', w - padRight - 60, 18);
        ctx.fillStyle = '#a855f7';
        ctx.fillText('— Avg Hops', w - padRight, 18);
    }

    /**
     * 4. Routing Table Heatmap (16-bit K-Bucket Grid)
     * bucketStats: [{ node_hex: "0xABCD", buckets: [0, 1, 4, 2, ...] }]
     */
    updateHeatmap(bucketStats) {
        this._lastHeatmapData = bucketStats;
        const ctx = this.ctxs.heatmap;
        const canvas = this.canvases.heatmap;
        if (!ctx || !canvas) return;

        const w = canvas.width / this.dpi;
        const h = canvas.height / this.dpi;
        ctx.clearRect(0, 0, w, h);

        ctx.fillStyle = '#0d1322';
        ctx.fillRect(0, 0, w, h);

        if (!Array.isArray(bucketStats) || bucketStats.length === 0) {
            this._drawEmpty(ctx, canvas, 'Routing Table Heatmap', 'Initialize network to view');
            return;
        }

        const padLeft = 44;
        const padRight = 16;
        const padTop = 30;
        const padBottom = 22;
        const chartW = w - padLeft - padRight;
        const chartH = h - padTop - padBottom;

        // Title
        ctx.font = '600 11px Inter, sans-serif';
        ctx.fillStyle = '#94a3b8';
        ctx.textAlign = 'left';
        ctx.fillText('K-BUCKET OCCUPANCY HEATMAP (16 BITS)', padLeft, 18);

        const rows = Math.min(bucketStats.length, 12); // up to 12 sampled nodes
        const cols = 16; // 16 buckets
        const cellW = (chartW - (cols - 1) * 2) / cols;
        const cellH = (chartH - (rows - 1) * 2) / rows;

        for (let r = 0; r < rows; r++) {
            const node = bucketStats[r];
            const y = padTop + r * (cellH + 2);

            // Node hex label
            ctx.font = '500 8px "JetBrains Mono", monospace';
            ctx.fillStyle = '#64748b';
            ctx.textAlign = 'right';
            ctx.fillText(node.node_hex || `N${r}`, padLeft - 6, y + cellH * 0.75);

            for (let c = 0; c < cols; c++) {
                const count = (node.buckets && node.buckets[c]) || 0;
                const capacity = 4;
                const ratio = Math.min(count / capacity, 1);
                const x = padLeft + c * (cellW + 2);

                // Cell color: dark blue to bright cyan
                if (ratio === 0) {
                    ctx.fillStyle = 'rgba(255, 255, 255, 0.03)';
                } else {
                    const alpha = 0.25 + ratio * 0.75;
                    ctx.fillStyle = `rgba(0, 240, 255, ${alpha.toFixed(2)})`;
                }

                ctx.fillRect(x, y, cellW, cellH);
            }
        }

        // X-axis bucket index labels at bottom
        ctx.font = '400 8px "JetBrains Mono", monospace';
        ctx.fillStyle = '#475569';
        ctx.textAlign = 'center';
        for (let c = 0; c < cols; c += 2) {
            const x = padLeft + c * (cellW + 2) + cellW / 2;
            ctx.fillText(c.toString(), x, h - 8);
        }
    }

    updateFromBenchmark(benchmarkData) {
        if (!benchmarkData) return;
        if (benchmarkData.hop_distribution) {
            this.updateHopDistribution(benchmarkData.hop_distribution);
        }
        if (benchmarkData.rounds) {
            this.updateSuccessRate(benchmarkData.rounds);
            this.updateNetworkSize(benchmarkData.rounds);
        }
    }

    clear() {
        this.renderPlaceholders();
    }
}
