/**
 * StadiumFlow AI — Dashboard Components
 *
 * Manages stats bar, zone list, and activity feed with
 * animated updates and real-time data binding.
 */

const Dashboard = (() => {
    'use strict';

    // ── State ────────────────────────────────────────────────
    let currentFilter = 'all';
    let lastState = null;
    let feedItems = [];
    const MAX_FEED_ITEMS = 30;

    // ── Stats Bar ────────────────────────────────────────────
    function updateStats(metrics) {
        // Animate number transitions
        animateValue('total-occupancy', metrics.total_attendees);
        animateValue('capacity-pct', `${metrics.occupancy_percentage}%`);
        animateValue('active-alerts', metrics.critical_zones);

        // Capacity ring
        const ring = document.getElementById('capacity-ring');
        if (ring) {
            const pct = Math.min(metrics.occupancy_percentage, 100);
            ring.setAttribute('stroke-dasharray', `${pct}, 100`);
        }
    }

    function updateWaitTime(avgWait) {
        const el = document.getElementById('avg-wait');
        if (el) {
            el.textContent = `${avgWait} min`;
        }
    }

    function animateValue(elementId, value) {
        const el = document.getElementById(elementId);
        if (!el) return;

        const displayValue = typeof value === 'number'
            ? value.toLocaleString()
            : value;

        if (el.textContent !== displayValue) {
            el.style.transform = 'scale(1.05)';
            el.textContent = displayValue;
            setTimeout(() => { el.style.transform = 'scale(1)'; }, 200);
        }
    }

    // ── Zone List ────────────────────────────────────────────
    function updateZoneList(zones) {
        const container = document.getElementById('zone-list');
        if (!container) return;

        // Convert zones object to sorted array
        let zoneArray = Object.entries(zones).map(([id, z]) => ({ id, ...z }));

        // Apply filter
        if (currentFilter !== 'all') {
            zoneArray = zoneArray.filter(z => z.status === currentFilter);
        }

        // Sort: critical first, then by occupancy ratio descending
        const statusPriority = { critical: 0, busy: 1, moderate: 2, clear: 3, closed: 4 };
        zoneArray.sort((a, b) => {
            const pa = statusPriority[a.status] ?? 9;
            const pb = statusPriority[b.status] ?? 9;
            if (pa !== pb) return pa - pb;
            return b.occupancy_ratio - a.occupancy_ratio;
        });

        // Build zone items HTML
        container.innerHTML = zoneArray.map(zone => {
            const pct = Math.round(zone.occupancy_ratio * 100);
            const statusColor = getStatusColor(zone.status);

            return `
                <div class="zone-item" role="listitem" aria-label="${zone.name}: ${pct}% capacity">
                    <span class="zone-item__status" style="background:${statusColor}" aria-hidden="true"></span>
                    <span class="zone-item__name">${zone.name}</span>
                    <span class="zone-item__occupancy">${pct}%</span>
                    <div class="zone-item__bar" aria-hidden="true">
                        <div class="zone-item__bar-fill"
                             style="width:${pct}%;background:${statusColor}"></div>
                    </div>
                </div>
            `;
        }).join('');
    }

    // ── Activity Feed ────────────────────────────────────────
    function addFeedItem(event) {
        const icons = {
            crowd_alert: '⚠️',
            staff_dispatch: '👮',
            route_change: '🔀',
            system_status: 'ℹ️',
            wait_time_update: '⏱️',
        };

        const severityClass = {
            info: 'feed-item--info',
            warning: 'feed-item--warning',
            critical: 'feed-item--critical',
            emergency: 'feed-item--critical',
        };

        const item = {
            icon: icons[event.event_type] || '📌',
            title: event.title || event.message || 'System event',
            time: new Date().toLocaleTimeString(),
            severity: event.severity || 'info',
            cssClass: severityClass[event.severity] || 'feed-item--info',
        };

        feedItems.unshift(item);
        if (feedItems.length > MAX_FEED_ITEMS) {
            feedItems = feedItems.slice(0, MAX_FEED_ITEMS);
        }

        renderFeed();
    }

    function addSimulationFeedItem(metrics) {
        // Add periodic status updates to the feed
        if (metrics.critical_zones > 0) {
            addFeedItem({
                event_type: 'crowd_alert',
                severity: 'warning',
                title: `${metrics.critical_zones} zone(s) at critical capacity`,
            });
        }
    }

    function renderFeed() {
        const container = document.getElementById('feed-list');
        const countEl = document.getElementById('feed-count');
        if (!container) return;

        if (feedItems.length === 0) {
            container.innerHTML = '<div class="feed-empty"><p>Monitoring venue activity...</p></div>';
            if (countEl) countEl.textContent = '0 events';
            return;
        }

        container.innerHTML = feedItems.slice(0, 15).map(item => `
            <div class="feed-item ${item.cssClass}" role="listitem">
                <span class="feed-item__icon" aria-hidden="true">${item.icon}</span>
                <div class="feed-item__content">
                    <div class="feed-item__title">${item.title}</div>
                    <div class="feed-item__time">${item.time}</div>
                </div>
            </div>
        `).join('');

        if (countEl) countEl.textContent = `${feedItems.length} events`;
    }

    // ── Filter ───────────────────────────────────────────────
    function setupFilter() {
        const filterEl = document.getElementById('zone-filter');
        if (!filterEl) return;

        filterEl.addEventListener('change', (e) => {
            currentFilter = e.target.value;
            if (lastState) {
                updateZoneList(lastState.zones);
            }
        });
    }

    // ── Helpers ──────────────────────────────────────────────
    function getStatusColor(status) {
        const colors = {
            clear: '#10b981',
            moderate: '#f59e0b',
            busy: '#f97316',
            critical: '#f43f5e',
            closed: '#64748b',
        };
        return colors[status] || '#94a3b8';
    }

    // ── Public API ───────────────────────────────────────────
    function handleStateUpdate(state) {
        lastState = state;
        updateStats(state.metrics);
        updateZoneList(state.zones);
        VenueMap.updateZones(state.zones);
        
        if (state.metrics.avg_wait_time_minutes !== undefined) {
            updateWaitTime(state.metrics.avg_wait_time_minutes);
        }
        
        const badge = document.getElementById('match-phase-badge');
        if (badge && state.match_phase) {
            badge.textContent = state.match_phase;
        }

        // Periodic feed updates (every 10th tick)
        if (state.tick % 10 === 0) {
            addSimulationFeedItem(state.metrics);
        }
    }

    function init() {
        setupFilter();
        renderFeed();
    }

    return {
        init,
        handleStateUpdate,
        addFeedItem,
        updateWaitTime,
    };
})();
