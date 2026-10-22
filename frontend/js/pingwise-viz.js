/**
 * pingwise-viz.js — D3 Force & Canvas Visualization for Pingwise DHT.
 *
 * Visualizes the Kademlia P2P network using HTML5 Canvas powered by D3.js physics.
 * Supports:
 * - Dynamic Force-Directed and Ring (Circular ID space) layouts
 * - Real-time lookup hop animation with glowing particle trails
 * - Interactive node selection, dragging, and hover effects
 * - High-DPI (Retina) canvas scaling
 */

class PingwiseVisualizer {
    constructor(canvasElement) {
        this.canvas = canvasElement;
        this.ctx = canvasElement.getContext('2d');
        this.nodes = [];
        this.links = [];
        this.nodeMap = new Map(); // id -> node object
        this.simulation = null;
        this.selectedNodeId = null;
        this.hoveredNodeId = null;
        this.highlightedPath = []; // array of node IDs in lookup path
        this.layout = 'force'; // 'force' or 'ring'
        this.onNodeClick = null; // callback(nodeId)
        this.particles = []; // animated flow particles along lookup path
        this.animationFrameId = null;
        this.width = 800;
        this.height = 600;
        this.dpi = window.devicePixelRatio || 1;

        this._setupCanvas();
        this._setupInteraction();
        this._startLoop();
    }

    _setupCanvas() {
        const resize = () => {
            const rect = this.canvas.getBoundingClientRect();
            this.width = Math.max(rect.width, 300);
            this.height = Math.max(rect.height, 300);
            this.dpi = window.devicePixelRatio || 1;

            this.canvas.width = this.width * this.dpi;
            this.canvas.height = this.height * this.dpi;
            this.ctx.setTransform(this.dpi, 0, 0, this.dpi, 0, 0);

            if (this.simulation && this.layout === 'force') {
                this.simulation.force('center', d3.forceCenter(this.width / 2, this.height / 2));
                this.simulation.alpha(0.3).restart();
            } else if (this.layout === 'ring') {
                this._applyRingLayout();
            }
        };

        window.addEventListener('resize', resize);
        // Observe container size changes
        if (window.ResizeObserver && this.canvas.parentElement) {
            new ResizeObserver(resize).observe(this.canvas.parentElement);
        }
        resize();
    }

    _setupInteraction() {
        const getCanvasPos = (evt) => {
            const rect = this.canvas.getBoundingClientRect();
            return {
                x: evt.clientX - rect.left,
                y: evt.clientY - rect.top
            };
        };

        this.canvas.addEventListener('mousemove', (evt) => {
            const pos = getCanvasPos(evt);
            const found = this._findNode(pos.x, pos.y, 16);
            if (found) {
                this.hoveredNodeId = found.id;
                this.canvas.style.cursor = 'pointer';
            } else {
                this.hoveredNodeId = null;
                this.canvas.style.cursor = 'crosshair';
            }
        });

        this.canvas.addEventListener('click', (evt) => {
            const pos = getCanvasPos(evt);
            const found = this._findNode(pos.x, pos.y, 16);
            if (found) {
                this.selectedNodeId = found.id;
                if (typeof this.onNodeClick === 'function') {
                    this.onNodeClick(found.id);
                }
            } else {
                this.selectedNodeId = null;
            }
        });

        // D3 Dragging support on canvas
        d3.select(this.canvas).call(
            d3.drag()
                .container(this.canvas)
                .subject((event) => {
                    const rect = this.canvas.getBoundingClientRect();
                    const x = event.x;
                    const y = event.y;
                    return this._findNode(x, y, 20);
                })
                .on('start', (event) => {
                    if (this.layout !== 'force') return;
                    if (!event.active && this.simulation) this.simulation.alphaTarget(0.3).restart();
                    event.subject.fx = event.subject.x;
                    event.subject.fy = event.subject.y;
                })
                .on('drag', (event) => {
                    if (this.layout !== 'force') return;
                    event.subject.fx = event.x;
                    event.subject.fy = event.y;
                })
                .on('end', (event) => {
                    if (this.layout !== 'force') return;
                    if (!event.active && this.simulation) this.simulation.alphaTarget(0);
                    event.subject.fx = null;
                    event.subject.fy = null;
                })
        );
    }

    _findNode(x, y, radius = 16) {
        let best = null;
        let minDist = radius * radius;
        for (const n of this.nodes) {
            const dx = n.x - x;
            const dy = n.y - y;
            const d2 = dx * dx + dy * dy;
            if (d2 < minDist) {
                minDist = d2;
                best = n;
            }
        }
        return best;
    }

    updateGraph(snapshot) {
        if (!snapshot || !snapshot.nodes) return;

        // Hide watermark if nodes exist
        const watermark = document.querySelector('.canvas-watermark');
        if (watermark) {
            watermark.style.display = snapshot.nodes.length > 0 ? 'none' : 'block';
        }

        const oldMap = this.nodeMap;
        const newNodes = [];
        const newMap = new Map();

        snapshot.nodes.forEach((n) => {
            const old = oldMap.get(n.id);
            const nodeObj = {
                id: n.id,
                hex: n.hex,
                is_alive: n.is_alive !== false,
                storage_count: n.storage_count || 0,
                routing_table_size: n.routing_table_size || 0,
                x: old ? old.x : (this.width / 2 + (Math.random() - 0.5) * 200),
                y: old ? old.y : (this.height / 2 + (Math.random() - 0.5) * 200),
                vx: old ? old.vx : 0,
                vy: old ? old.vy : 0
            };
            newNodes.push(nodeObj);
            newMap.set(n.id, nodeObj);
        });

        // Filter and build links (references to node objects for d3)
        const newLinks = [];
        if (snapshot.links) {
            snapshot.links.forEach((l) => {
                const s = typeof l.source === 'object' ? l.source.id : l.source;
                const t = typeof l.target === 'object' ? l.target.id : l.target;
                if (newMap.has(s) && newMap.has(t)) {
                    newLinks.push({
                        source: newMap.get(s),
                        target: newMap.get(t)
                    });
                }
            });
        }

        this.nodes = newNodes;
        this.links = newLinks;
        this.nodeMap = newMap;

        if (this.layout === 'force') {
            this._setupForceSimulation();
        } else {
            this._applyRingLayout();
        }
    }

    _setupForceSimulation() {
        if (this.simulation) {
            this.simulation.stop();
        }

        const chargeStrength = this.nodes.length > 150 ? -60 : (this.nodes.length > 60 ? -120 : -220);
        const linkDistance = this.nodes.length > 150 ? 45 : (this.nodes.length > 60 ? 70 : 100);

        this.simulation = d3.forceSimulation(this.nodes)
            .force('link', d3.forceLink(this.links).distance(linkDistance).strength(0.35))
            .force('charge', d3.forceManyBody().strength(chargeStrength).distanceMax(400))
            .force('center', d3.forceCenter(this.width / 2, this.height / 2))
            .force('collide', d3.forceCollide().radius(d => 10 + Math.min(d.routing_table_size, 8)).strength(0.7))
            .alpha(0.6)
            .restart();
    }

    _applyRingLayout() {
        if (this.simulation) {
            this.simulation.stop();
        }
        if (this.nodes.length === 0) return;

        // Sort nodes by integer ID to reflect XOR distance ring
        const sorted = [...this.nodes].sort((a, b) => a.id - b.id);
        const centerX = this.width / 2;
        const centerY = this.height / 2;
        const radius = Math.min(this.width, this.height) * 0.40;

        const total = sorted.length;
        sorted.forEach((n, idx) => {
            const angle = (idx / total) * 2 * Math.PI - Math.PI / 2;
            n.x = centerX + radius * Math.cos(angle);
            n.y = centerY + radius * Math.sin(angle);
            n.fx = n.x;
            n.fy = n.y;
        });
    }

    setLayout(mode) {
        if (this.layout === mode) return;
        this.layout = mode;

        if (mode === 'ring') {
            this._applyRingLayout();
        } else {
            // Clear fixed coordinates
            this.nodes.forEach(n => {
                n.fx = null;
                n.fy = null;
            });
            this._setupForceSimulation();
        }
    }

    highlightLookup(path) {
        if (!Array.isArray(path) || path.length === 0) {
            this.highlightedPath = [];
            this.particles = [];
            return;
        }

        this.highlightedPath = [...path];
        this.particles = [];

        // Generate glowing trail particles along each step in the path
        for (let i = 0; i < path.length - 1; i++) {
            const fromId = path[i];
            const toId = path[i + 1];
            // Multiple particles per segment with staggered offsets
            for (let p = 0; p < 3; p++) {
                this.particles.push({
                    fromId,
                    toId,
                    t: (p / 3) + Math.random() * 0.1,
                    speed: 0.015 + Math.random() * 0.005,
                    size: 3 + Math.random() * 2
                });
            }
        }
    }

    clearHighlight() {
        this.highlightedPath = [];
        this.particles = [];
    }

    selectNode(nodeId) {
        this.selectedNodeId = nodeId;
    }

    _startLoop() {
        const tick = () => {
            this._render();
            this._updateParticles();
            this.animationFrameId = requestAnimationFrame(tick);
        };
        this.animationFrameId = requestAnimationFrame(tick);
    }

    _updateParticles() {
        if (this.particles.length === 0) return;

        this.particles.forEach(p => {
            p.t += p.speed;
            if (p.t > 1) {
                p.t = 0;
            }
        });
    }

    _render() {
        const ctx = this.ctx;
        ctx.clearRect(0, 0, this.width, this.height);

        // 1. Subtle background grid dots
        this._renderGrid(ctx);

        // 2. Ring backdrop when in ring mode
        if (this.layout === 'ring' && this.nodes.length > 0) {
            const centerX = this.width / 2;
            const centerY = this.height / 2;
            const radius = Math.min(this.width, this.height) * 0.40;
            ctx.save();
            ctx.beginPath();
            ctx.arc(centerX, centerY, radius, 0, 2 * Math.PI);
            ctx.strokeStyle = 'rgba(0, 240, 255, 0.08)';
            ctx.lineWidth = 1.5;
            ctx.setLineDash([4, 6]);
            ctx.stroke();
            ctx.restore();
        }

        // 3. Render Links
        this._renderLinks(ctx);

        // 4. Render Highlighted Lookup Path
        this._renderHighlightedPath(ctx);

        // 5. Render Moving Particles
        this._renderParticles(ctx);

        // 6. Render Nodes
        this._renderNodes(ctx);
    }

    _renderGrid(ctx) {
        ctx.save();
        ctx.fillStyle = 'rgba(255, 255, 255, 0.025)';
        const step = 40;
        for (let x = 20; x < this.width; x += step) {
            for (let y = 20; y < this.height; y += step) {
                ctx.beginPath();
                ctx.arc(x, y, 1, 0, 2 * Math.PI);
                ctx.fill();
            }
        }
        ctx.restore();
    }

    _renderLinks(ctx) {
        if (this.links.length === 0) return;

        ctx.save();
        ctx.strokeStyle = 'rgba(100, 160, 255, 0.12)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        for (const l of this.links) {
            const s = l.source;
            const t = l.target;
            if (s && t && s.x !== undefined && t.x !== undefined) {
                ctx.moveTo(s.x, s.y);
                ctx.lineTo(t.x, t.y);
            }
        }
        ctx.stroke();
        ctx.restore();
    }

    _renderHighlightedPath(ctx) {
        if (this.highlightedPath.length < 2) return;

        ctx.save();
        // Thick neon glow
        ctx.shadowColor = '#00f0ff';
        ctx.shadowBlur = 12;
        ctx.strokeStyle = '#00f0ff';
        ctx.lineWidth = 3;
        ctx.beginPath();

        for (let i = 0; i < this.highlightedPath.length - 1; i++) {
            const s = this.nodeMap.get(this.highlightedPath[i]);
            const t = this.nodeMap.get(this.highlightedPath[i + 1]);
            if (s && t) {
                ctx.moveTo(s.x, s.y);
                ctx.lineTo(t.x, t.y);
            }
        }
        ctx.stroke();

        // Second pass: bright core line
        ctx.shadowBlur = 0;
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 1.2;
        ctx.stroke();
        ctx.restore();
    }

    _renderParticles(ctx) {
        if (this.particles.length === 0) return;

        ctx.save();
        ctx.shadowColor = '#00f0ff';
        ctx.shadowBlur = 8;
        ctx.fillStyle = '#ffffff';

        for (const p of this.particles) {
            const s = this.nodeMap.get(p.fromId);
            const t = this.nodeMap.get(p.toId);
            if (s && t) {
                const px = s.x + (t.x - s.x) * p.t;
                const py = s.y + (t.y - s.y) * p.t;
                ctx.beginPath();
                ctx.arc(px, py, p.size, 0, 2 * Math.PI);
                ctx.fill();
            }
        }
        ctx.restore();
    }

    _renderNodes(ctx) {
        const pathSet = new Set(this.highlightedPath);

        for (const n of this.nodes) {
            if (n.x === undefined || n.y === undefined) continue;

            const isSelected = n.id === this.selectedNodeId;
            const isHovered = n.id === this.hoveredNodeId;
            const isPathNode = pathSet.has(n.id);
            const isPathStart = this.highlightedPath.length > 0 && this.highlightedPath[0] === n.id;
            const isPathEnd = this.highlightedPath.length > 0 && this.highlightedPath[this.highlightedPath.length - 1] === n.id;

            // Radius scales slightly with routing table size
            let radius = 6 + Math.min(n.routing_table_size || 0, 8);
            if (isSelected || isPathNode) radius += 3;

            ctx.save();

            // Glow effects
            if (isPathStart) {
                ctx.shadowColor = '#10b981'; // Emerald for initiator
                ctx.shadowBlur = 18;
            } else if (isPathEnd) {
                ctx.shadowColor = '#f59e0b'; // Amber for destination
                ctx.shadowBlur = 18;
            } else if (isPathNode) {
                ctx.shadowColor = '#00f0ff'; // Cyan for path
                ctx.shadowBlur = 15;
            } else if (isSelected) {
                ctx.shadowColor = '#a855f7'; // Violet for selected
                ctx.shadowBlur = 20;
            } else if (isHovered) {
                ctx.shadowColor = '#00f0ff';
                ctx.shadowBlur = 12;
            } else {
                ctx.shadowColor = 'rgba(0, 240, 255, 0.2)';
                ctx.shadowBlur = 4;
            }

            // Radial gradient fill
            const grad = ctx.createRadialGradient(n.x - radius * 0.3, n.y - radius * 0.3, 1, n.x, n.y, radius);
            if (isPathStart) {
                grad.addColorStop(0, '#ffffff');
                grad.addColorStop(0.4, '#10b981');
                grad.addColorStop(1, '#065f46');
            } else if (isPathEnd) {
                grad.addColorStop(0, '#ffffff');
                grad.addColorStop(0.4, '#f59e0b');
                grad.addColorStop(1, '#92400e');
            } else if (isPathNode) {
                grad.addColorStop(0, '#ffffff');
                grad.addColorStop(0.4, '#00f0ff');
                grad.addColorStop(1, '#0369a1');
            } else if (isSelected) {
                grad.addColorStop(0, '#ffffff');
                grad.addColorStop(0.4, '#c084fc');
                grad.addColorStop(1, '#581c87');
            } else {
                grad.addColorStop(0, '#38bdf8');
                grad.addColorStop(0.6, '#0284c7');
                grad.addColorStop(1, '#0f172a');
            }

            ctx.fillStyle = grad;
            ctx.beginPath();
            ctx.arc(n.x, n.y, radius, 0, 2 * Math.PI);
            ctx.fill();

            // Node border ring
            ctx.shadowBlur = 0;
            if (isSelected) {
                ctx.strokeStyle = '#ffffff';
                ctx.lineWidth = 2.5;
            } else if (isPathNode) {
                ctx.strokeStyle = '#ffffff';
                ctx.lineWidth = 1.8;
            } else {
                ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
                ctx.lineWidth = 1;
            }
            ctx.stroke();

            // Hex label below node (show for all if node count < 75, or for active/selected/path)
            const showLabel = this.nodes.length <= 75 || isSelected || isHovered || isPathNode;
            if (showLabel) {
                ctx.font = '500 10px "JetBrains Mono", monospace';
                ctx.fillStyle = isSelected ? '#a855f7' : (isPathNode ? '#00f0ff' : 'rgba(241, 245, 249, 0.85)');
                ctx.textAlign = 'center';
                ctx.textBaseline = 'top';
                ctx.fillText(n.hex || `0x${n.id.toString(16).padStart(4, '0')}`, n.x, n.y + radius + 4);
            }

            ctx.restore();
        }
    }

    destroy() {
        if (this.animationFrameId) {
            cancelAnimationFrame(this.animationFrameId);
        }
        if (this.simulation) {
            this.simulation.stop();
        }
    }
}
