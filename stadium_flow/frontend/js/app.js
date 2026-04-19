/**
 * StadiumFlow AI — Main Application Orchestrator
 *
 * Initializes all modules, connects WebSocket events to
 * dashboard updates, and manages the application lifecycle.
 */

const App = (() => {
    'use strict';

    function init() {
        console.log('🏟️ StadiumFlow AI v1.0.0 initializing...');

        // Initialize modules
        Dashboard.init();
        Chat.init();

        // Connect WebSocket and wire event handlers
        WSClient.on('connected', onConnected);
        WSClient.on('disconnected', onDisconnected);
        WSClient.on('initial_state', onInitialState);
        WSClient.on('state_update', onStateUpdate);

        // Start WebSocket connection
        WSClient.connect();

        // Fetch initial stats
        fetchInitialData();

        console.log('✅ StadiumFlow AI ready');
    }

    // ── WebSocket Event Handlers ─────────────────────────────
    function onConnected() {
        Dashboard.addFeedItem({
            event_type: 'system_status',
            severity: 'info',
            title: 'Connected to StadiumFlow AI backend',
        });
        Accessibility.announce('Connected to real-time venue data');
    }

    function onDisconnected(data) {
        Dashboard.addFeedItem({
            event_type: 'system_status',
            severity: 'warning',
            title: 'Connection lost — reconnecting...',
        });
    }

    function onInitialState(state) {
        if (!state) return;

        // Render the venue map with initial zone data
        VenueMap.renderStadium(state.zones);

        // Update dashboard
        Dashboard.handleStateUpdate(state);

        Dashboard.addFeedItem({
            event_type: 'system_status',
            severity: 'info',
            title: `Simulation active — tracking ${state.metrics.total_attendees.toLocaleString()} attendees`,
        });
    }

    function onStateUpdate(state) {
        if (!state) return;
        Dashboard.handleStateUpdate(state);
    }

    // ── Initial Data Fetch ───────────────────────────────────
    async function fetchInitialData() {
        try {
            // Fetch venue stats for wait time
            const statsRes = await fetch('/api/v1/venues/stats');
            if (statsRes.ok) {
                const stats = await statsRes.json();
                Dashboard.updateWaitTime(stats.avg_wait_time_minutes || 0);
            }
        } catch (e) {
            console.warn('Failed to fetch initial data:', e);
        }
    }

    // ── Start on DOM Ready ───────────────────────────────────
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    return { init };
})();
