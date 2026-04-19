/**
 * StadiumFlow AI — Interactive Venue Map
 *
 * Renders an SVG representation of the Narendra Modi Stadium
 * with interactive zones, color-coded congestion, tooltips,
 * click-to-route navigation, and facility icons.
 */

const VenueMap = (() => {
    'use strict';

    const svgEl = document.getElementById('stadium-svg');
    const tooltipEl = document.getElementById('map-tooltip');
    let zones = {};

    // ── Click-to-Route State ─────────────────────────────────
    let routeOrigin = null;
    let routeDestination = null;
    let routePathEl = null;
    let routeMarkersGroup = null;

    // Facility definitions with emoji icons and positions near concourses
    const FACILITIES = [
        { id: 'restroom-n1', type: 'restroom', label: '\uD83D\uDEBB', x: 350, y: 195, name: 'Restroom (North)' },
        { id: 'restroom-n2', type: 'restroom', label: '\uD83D\uDEBB', x: 450, y: 195, name: 'Restroom (North)' },
        { id: 'restroom-s1', type: 'restroom', label: '\uD83D\uDEBB', x: 350, y: 500, name: 'Restroom (South)' },
        { id: 'restroom-s2', type: 'restroom', label: '\uD83D\uDEBB', x: 450, y: 500, name: 'Restroom (South)' },
        { id: 'food-n', type: 'food', label: '\uD83C\uDF54', x: 400, y: 205, name: 'Food Court (North)' },
        { id: 'food-s', type: 'food', label: '\uD83C\uDF54', x: 400, y: 490, name: 'Food Court (South)' },
        { id: 'food-e', type: 'food', label: '\uD83C\uDF54', x: 680, y: 300, name: 'Food Stall (East)' },
        { id: 'food-w', type: 'food', label: '\uD83C\uDF54', x: 120, y: 300, name: 'Food Stall (West)' },
        { id: 'medical-1', type: 'medical', label: '\u2795', x: 310, y: 210, name: 'First Aid (North)' },
        { id: 'medical-2', type: 'medical', label: '\u2795', x: 620, y: 440, name: 'First Aid (East)' },
        { id: 'atm-1', type: 'atm', label: '\uD83C\uDFE7', x: 160, y: 210, name: 'ATM (Gate 6)' },
        { id: 'atm-2', type: 'atm', label: '\uD83C\uDFE7', x: 640, y: 210, name: 'ATM (Gate 5)' },
        { id: 'info-1', type: 'info', label: '\u2139\uFE0F', x: 260, y: 180, name: 'Info Desk (North)' },
        { id: 'merch-1', type: 'merchandise', label: '\uD83D\uDC55', x: 540, y: 195, name: 'Merchandise (North)' },
        { id: 'merch-2', type: 'merchandise', label: '\uD83D\uDC55', x: 260, y: 500, name: 'Merchandise (South)' },
    ];

    // ── Stadium Geometry ─────────────────────────────────────
    function renderStadium(zoneData) {
        if (!svgEl) return;
        svgEl.innerHTML = '';
        zones = zoneData;

        // Background field (cricket pitch)
        const defs = createSVGElement('defs');
        defs.innerHTML = `
            <radialGradient id="field-glow" cx="50%" cy="50%" r="50%">
                <stop offset="0%" stop-color="#10b981" stop-opacity="0.08"/>
                <stop offset="100%" stop-color="#10b981" stop-opacity="0"/>
            </radialGradient>
            <filter id="glow">
                <feGaussianBlur stdDeviation="3" result="blur"/>
                <feMerge>
                    <feMergeNode in="blur"/>
                    <feMergeNode in="SourceGraphic"/>
                </feMerge>
            </filter>
        `;
        svgEl.appendChild(defs);

        // Outer stadium ring
        const outerRing = createSVGElement('ellipse');
        setAttributes(outerRing, {
            cx: 400, cy: 300, rx: 290, ry: 260,
            fill: 'none',
            stroke: 'rgba(99, 102, 241, 0.1)',
            'stroke-width': 1,
        });
        svgEl.appendChild(outerRing);

        // Inner field
        const field = createSVGElement('ellipse');
        setAttributes(field, {
            cx: 400, cy: 300, rx: 120, ry: 100,
            fill: 'url(#field-glow)',
            stroke: 'rgba(16, 185, 129, 0.2)',
            'stroke-width': 1,
            'stroke-dasharray': '4 4',
        });
        svgEl.appendChild(field);

        // Pitch rectangle
        const pitch = createSVGElement('rect');
        setAttributes(pitch, {
            x: 380, y: 275, width: 40, height: 50,
            rx: 4,
            fill: 'rgba(16, 185, 129, 0.1)',
            stroke: 'rgba(16, 185, 129, 0.3)',
            'stroke-width': 0.5,
        });
        svgEl.appendChild(pitch);

        // Field label
        const fieldLabel = createSVGElement('text');
        setAttributes(fieldLabel, {
            x: 400, y: 303,
            'text-anchor': 'middle',
            fill: 'rgba(16, 185, 129, 0.4)',
            'font-size': 11,
            'font-family': 'Inter, sans-serif',
            'font-weight': 600,
        });
        fieldLabel.textContent = 'PLAYING FIELD';
        svgEl.appendChild(fieldLabel);

        // Render each zone
        const zoneEntries = Object.entries(zoneData);

        // Sort: gates first, then concourses, then blocks
        const typeOrder = { entry_gate: 0, concourse: 1, vip: 2, hospitality: 2, seating: 3 };
        zoneEntries.sort((a, b) => {
            return (typeOrder[a[1].zone_type] || 9) - (typeOrder[b[1].zone_type] || 9);
        });

        for (const [id, zone] of zoneEntries) {
            renderZone(id, zone);
        }

        // Render facility icons on the map
        renderFacilities();

        // Initialize routing controls
        initRouting(zoneData);

        // Route instruction line
        renderRouteInstruction();
    }

    function renderZone(id, zone) {
        const group = createSVGElement('g');
        group.setAttribute('data-zone-id', id);
        group.setAttribute('role', 'button');
        group.setAttribute('tabindex', '0');
        group.setAttribute('aria-label', `${zone.name}: ${Math.round(zone.occupancy_ratio * 100)}% capacity, status ${zone.status}`);

        let shape;
        const statusClass = `zone-shape--${zone.status}`;
        const x = zone.map_x || 400;
        const y = zone.map_y || 300;

        if (zone.zone_type === 'entry_gate') {
            // Gates: diamonds
            shape = createSVGElement('rect');
            setAttributes(shape, {
                x: x - 14, y: y - 14, width: 28, height: 28,
                rx: 4,
                transform: `rotate(45 ${x} ${y})`,
            });
        } else if (zone.zone_type === 'concourse') {
            // Concourses: rounded rectangles
            shape = createSVGElement('rect');
            const isHorizontal = id.includes('north') || id.includes('south');
            if (isHorizontal) {
                setAttributes(shape, {
                    x: x - 80, y: y - 15, width: 160, height: 30, rx: 8,
                });
            } else {
                setAttributes(shape, {
                    x: x - 15, y: y - 60, width: 30, height: 120, rx: 8,
                });
            }
        } else if (zone.zone_type === 'vip' || zone.zone_type === 'hospitality') {
            shape = createSVGElement('rect');
            setAttributes(shape, {
                x: x - 30, y: y - 14, width: 60, height: 28, rx: 14,
            });
        } else {
            // Seating blocks: circles
            const radius = 22 + (zone.occupancy_ratio * 8);
            shape = createSVGElement('circle');
            setAttributes(shape, { cx: x, cy: y, r: radius });
        }

        shape.classList.add('zone-shape', statusClass);
        group.appendChild(shape);

        // Label
        const label = createSVGElement('text');
        label.classList.add('zone-label');
        setAttributes(label, { x: x, y: y });

        if (id.startsWith('block-')) {
            label.textContent = id.replace('block-', '').toUpperCase();
        } else if (id.startsWith('gate-')) {
            label.textContent = `G${id.replace('gate-', '')}`;
        } else if (id === 'presidential-suite') {
            label.textContent = 'VIP';
        } else if (id === 'premium-gallery') {
            label.textContent = 'PRE';
        } else if (id.startsWith('concourse-')) {
            label.textContent = id.replace('concourse-', '')[0].toUpperCase();
            setAttributes(label, { 'font-size': 9 });
        }

        group.appendChild(label);

        // Hover events
        group.addEventListener('mouseenter', (e) => showTooltip(e, zone));
        group.addEventListener('mouseleave', hideTooltip);
        group.addEventListener('focus', (e) => showTooltip(e, zone));
        group.addEventListener('blur', hideTooltip);

        // CLICK to set origin/destination
        group.addEventListener('click', () => handleZoneClick(id, zone));
        group.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                handleZoneClick(id, zone);
            }
        });

        svgEl.appendChild(group);
    }

    // ── Facility Icons ──────────────────────────────────────
    function renderFacilities() {
        const facilityGroup = createSVGElement('g');
        facilityGroup.setAttribute('id', 'facility-icons');

        FACILITIES.forEach(fac => {
            const g = createSVGElement('g');
            g.setAttribute('class', 'facility-marker');
            g.setAttribute('data-facility-type', fac.type);

            // Background circle
            const bg = createSVGElement('circle');
            setAttributes(bg, {
                cx: fac.x, cy: fac.y, r: 10,
                fill: 'rgba(15, 19, 53, 0.85)',
                stroke: 'rgba(99, 102, 241, 0.4)',
                'stroke-width': 1,
            });
            g.appendChild(bg);

            // Icon text
            const icon = createSVGElement('text');
            setAttributes(icon, {
                x: fac.x, y: fac.y + 1,
                'text-anchor': 'middle',
                'dominant-baseline': 'central',
                'font-size': 11,
                'pointer-events': 'none',
            });
            icon.textContent = fac.label;
            g.appendChild(icon);

            // Tooltip on hover
            g.addEventListener('mouseenter', (e) => {
                if (!tooltipEl) return;
                tooltipEl.innerHTML = `
                    <div style="font-weight:600;">${fac.name}</div>
                    <div style="font-size:0.7rem;color:#94a3b8;margin-top:2px;">
                        ${fac.type.charAt(0).toUpperCase() + fac.type.slice(1)} Facility
                    </div>
                `;
                const mapRect = svgEl.parentElement.getBoundingClientRect();
                tooltipEl.style.left = `${e.clientX - mapRect.left + 15}px`;
                tooltipEl.style.top = `${e.clientY - mapRect.top - 10}px`;
                tooltipEl.classList.add('map-tooltip--visible');
            });
            g.addEventListener('mouseleave', hideTooltip);

            facilityGroup.appendChild(g);
        });

        svgEl.appendChild(facilityGroup);
    }

    // ── Click-to-Route ──────────────────────────────────────
    function handleZoneClick(zoneId, zone) {
        if (!routeOrigin) {
            // First click: set origin
            routeOrigin = zoneId;
            highlightSelectedZone(zoneId, 'origin');
            updateRouteInstruction(`Origin: ${zone.name} — Click another zone as destination`);

            // Sync dropdowns
            const originSel = document.getElementById('route-origin');
            if (originSel) originSel.value = zoneId;

        } else if (!routeDestination && zoneId !== routeOrigin) {
            // Second click: set destination and auto-route
            routeDestination = zoneId;
            highlightSelectedZone(zoneId, 'destination');

            // Sync dropdowns
            const destSel = document.getElementById('route-dest');
            if (destSel) destSel.value = zoneId;

            updateRouteInstruction(`Routing: ${getZoneName(routeOrigin)} \u2192 ${zone.name}...`);
            executeRoute(routeOrigin, routeDestination);

        } else {
            // Third click or same zone: reset and start new selection
            clearRoute();
            routeOrigin = zoneId;
            highlightSelectedZone(zoneId, 'origin');
            updateRouteInstruction(`Origin: ${zone.name} — Click another zone as destination`);

            const originSel = document.getElementById('route-origin');
            if (originSel) originSel.value = zoneId;
        }
    }

    function getZoneName(zoneId) {
        const z = zones[zoneId];
        return z ? z.name : zoneId;
    }

    function highlightSelectedZone(zoneId, role) {
        const group = svgEl.querySelector(`[data-zone-id="${zoneId}"]`);
        if (!group) return;
        const shape = group.querySelector('.zone-shape');
        if (!shape) return;

        if (role === 'origin') {
            shape.style.stroke = '#06b6d4';
            shape.style.strokeWidth = '3';
            shape.style.filter = 'drop-shadow(0 0 6px rgba(6,182,212,0.6))';
        } else {
            shape.style.stroke = '#f59e0b';
            shape.style.strokeWidth = '3';
            shape.style.filter = 'drop-shadow(0 0 6px rgba(245,158,11,0.6))';
        }
    }

    function clearZoneHighlights() {
        svgEl.querySelectorAll('.zone-shape').forEach(shape => {
            shape.style.stroke = '';
            shape.style.strokeWidth = '';
            shape.style.filter = '';
        });
    }

    function renderRouteInstruction() {
        // Add a text instruction bar below the map header
        let instrEl = document.getElementById('route-instruction');
        if (!instrEl) {
            instrEl = document.createElement('div');
            instrEl.id = 'route-instruction';
            instrEl.style.cssText = 'padding:6px 16px;font-size:0.78rem;color:var(--text-secondary);background:var(--surface-1);border-bottom:1px solid var(--glass-border);min-height:28px;display:flex;align-items:center;gap:8px;';
            instrEl.innerHTML = '<span>\uD83D\uDCCD Click any zone on the map to set it as <strong>Origin</strong>, then click another for <strong>Destination</strong></span>';
            const mapContainer = document.getElementById('venue-map');
            if (mapContainer) mapContainer.parentElement.insertBefore(instrEl, mapContainer);
        }
    }

    function updateRouteInstruction(text) {
        const instrEl = document.getElementById('route-instruction');
        if (instrEl) instrEl.innerHTML = `<span>${text}</span>`;
    }

    // ── Routing API ─────────────────────────────────────────
    async function executeRoute(originId, destId) {
        try {
            const res = await fetch(`/api/v1/routing/find?start_zone_id=${originId}&end_zone_id=${destId}`);
            if (res.ok) {
                const data = await res.json();
                // Extract the zone_id path from the steps array
                const pathIds = data.steps.map(s => s.zone_id);
                if (pathIds.length >= 2) {
                    drawRoute(pathIds);
                    const mins = data.estimated_time_minutes || 0;
                    const dist = data.total_distance_meters || 0;
                    updateRouteInstruction(
                        `\u2705 Route: ${getZoneName(originId)} \u2192 ${getZoneName(destId)} | ` +
                        `${pathIds.length} zones | ${Math.round(dist)}m | ~${mins} min`
                    );
                }
            } else {
                updateRouteInstruction('\u274C No route found between these zones. Try different locations.');
            }
        } catch (e) {
            console.error('Routing failed:', e);
            updateRouteInstruction('\u274C Routing error. Please try again.');
        }
    }

    // ── Routing Dropdowns ───────────────────────────────────
    function initRouting(zoneData) {
        const originSelect = document.getElementById('route-origin');
        const destSelect = document.getElementById('route-dest');
        if (!originSelect || !destSelect) return;

        originSelect.innerHTML = '<option value="">Origin...</option>';
        destSelect.innerHTML = '<option value="">Destination...</option>';

        const sortedZones = Object.values(zoneData).sort((a, b) => a.name.localeCompare(b.name));

        sortedZones.forEach(z => {
            const opt1 = document.createElement('option');
            opt1.value = z.id;
            opt1.textContent = z.name;
            originSelect.appendChild(opt1);

            const opt2 = document.createElement('option');
            opt2.value = z.id;
            opt2.textContent = z.name;
            destSelect.appendChild(opt2);
        });

        // Wire up button (use fresh clones to avoid duplicate listeners)
        const btnFind = document.getElementById('btn-find-route');
        const btnClear = document.getElementById('btn-clear-route');

        if (btnFind) {
            const newBtn = btnFind.cloneNode(true);
            btnFind.parentNode.replaceChild(newBtn, btnFind);
            newBtn.addEventListener('click', () => {
                const o = originSelect.value;
                const d = destSelect.value;
                if (!o || !d || o === d) return;
                routeOrigin = o;
                routeDestination = d;
                clearZoneHighlights();
                highlightSelectedZone(o, 'origin');
                highlightSelectedZone(d, 'destination');
                executeRoute(o, d);
            });
        }

        if (btnClear) {
            const newBtn = btnClear.cloneNode(true);
            btnClear.parentNode.replaceChild(newBtn, btnClear);
            newBtn.addEventListener('click', clearRoute);
        }
    }

    // ── Draw / Clear Routes ─────────────────────────────────
    function drawRoute(pathIds) {
        // Remove any existing route
        const existing = svgEl.querySelector('.route-path');
        if (existing) existing.remove();
        if (routeMarkersGroup) routeMarkersGroup.remove();

        if (!svgEl || pathIds.length < 2) return;

        const coords = pathIds.map(id => {
            const z = zones[id];
            return z ? { x: z.map_x, y: z.map_y } : null;
        }).filter(Boolean);

        if (coords.length < 2) return;

        // Draw animated polyline
        const points = coords.map(c => `${c.x},${c.y}`).join(' ');
        routePathEl = createSVGElement('polyline');
        setAttributes(routePathEl, { points, class: 'route-path' });
        svgEl.appendChild(routePathEl);

        // Draw waypoint markers
        routeMarkersGroup = createSVGElement('g');
        routeMarkersGroup.setAttribute('class', 'route-markers');

        coords.forEach((c, i) => {
            const marker = createSVGElement('circle');
            const isEndpoint = i === 0 || i === coords.length - 1;
            setAttributes(marker, {
                cx: c.x, cy: c.y,
                r: isEndpoint ? 6 : 3,
                fill: i === 0 ? '#06b6d4' : (i === coords.length - 1 ? '#f59e0b' : '#8b5cf6'),
                stroke: '#fff',
                'stroke-width': isEndpoint ? 2 : 1,
            });
            routeMarkersGroup.appendChild(marker);
        });

        svgEl.appendChild(routeMarkersGroup);

        const btnClear = document.getElementById('btn-clear-route');
        if (btnClear) btnClear.style.display = 'inline-flex';
    }

    function clearRoute() {
        // Remove SVG route elements
        const existing = svgEl.querySelector('.route-path');
        if (existing) existing.remove();
        if (routeMarkersGroup) { routeMarkersGroup.remove(); routeMarkersGroup = null; }
        routePathEl = null;

        // Reset state
        routeOrigin = null;
        routeDestination = null;
        clearZoneHighlights();

        // Reset dropdowns
        const originSel = document.getElementById('route-origin');
        const destSel = document.getElementById('route-dest');
        if (originSel) originSel.value = '';
        if (destSel) destSel.value = '';

        const btnClear = document.getElementById('btn-clear-route');
        if (btnClear) btnClear.style.display = 'none';

        updateRouteInstruction('\uD83D\uDCCD Click any zone on the map to set it as <strong>Origin</strong>, then click another for <strong>Destination</strong>');
    }

    // ── Update Zone States ───────────────────────────────────
    function updateZones(zoneData) {
        zones = zoneData;

        for (const [id, zone] of Object.entries(zoneData)) {
            const group = svgEl.querySelector(`[data-zone-id="${id}"]`);
            if (!group) continue;

            const shape = group.querySelector('.zone-shape');
            if (!shape) continue;

            // Update class (but preserve any route highlight)
            const hasHighlight = shape.style.strokeWidth === '3';
            shape.className.baseVal = `zone-shape zone-shape--${zone.status}`;
            if (hasHighlight) {
                // Re-apply the highlight after class reset
            }

            // Update circle radius for seating blocks
            if (zone.zone_type === 'seating' && shape.tagName === 'circle') {
                const newRadius = 22 + (zone.occupancy_ratio * 8);
                shape.setAttribute('r', newRadius);
            }

            group.setAttribute('aria-label',
                `${zone.name}: ${Math.round(zone.occupancy_ratio * 100)}% capacity, status ${zone.status}`
            );
        }
    }

    // ── Tooltip ──────────────────────────────────────────────
    function showTooltip(event, zone) {
        if (!tooltipEl) return;

        const pct = Math.round(zone.occupancy_ratio * 100);
        const statusColors = {
            clear: '#10b981', moderate: '#f59e0b',
            busy: '#f97316', critical: '#f43f5e', closed: '#64748b',
        };
        const color = statusColors[zone.status] || '#94a3b8';

        tooltipEl.innerHTML = `
            <div style="margin-bottom:4px;font-weight:600;">${zone.name}</div>
            <div style="font-size:0.75rem;color:#94a3b8;">
                <span style="color:${color};">\u25CF</span>
                ${zone.current_occupancy.toLocaleString()} / ${zone.capacity.toLocaleString()}
                (${pct}%)
            </div>
            <div style="font-size:0.7rem;color:#64748b;margin-top:2px;">
                Status: <span style="color:${color};text-transform:uppercase;">${zone.status}</span>
            </div>
            <div style="font-size:0.65rem;color:#6366f1;margin-top:3px;">
                \uD83D\uDCCD Click to set as route point
            </div>
        `;

        const mapRect = svgEl.parentElement.getBoundingClientRect();

        let posX, posY;
        if (event.type === 'focus') {
            const groupRect = event.target.getBoundingClientRect();
            posX = groupRect.left - mapRect.left + groupRect.width / 2;
            posY = groupRect.top - mapRect.top - 10;
        } else {
            posX = event.clientX - mapRect.left + 15;
            posY = event.clientY - mapRect.top - 10;
        }

        tooltipEl.style.left = `${posX}px`;
        tooltipEl.style.top = `${posY}px`;
        tooltipEl.classList.add('map-tooltip--visible');
        tooltipEl.setAttribute('aria-hidden', 'false');
    }

    function hideTooltip() {
        if (!tooltipEl) return;
        tooltipEl.classList.remove('map-tooltip--visible');
        tooltipEl.setAttribute('aria-hidden', 'true');
    }

    // ── SVG Helpers ──────────────────────────────────────────
    function createSVGElement(tag) {
        return document.createElementNS('http://www.w3.org/2000/svg', tag);
    }

    function setAttributes(el, attrs) {
        for (const [key, value] of Object.entries(attrs)) {
            el.setAttribute(key, value);
        }
    }

    return { renderStadium, updateZones };
})();
