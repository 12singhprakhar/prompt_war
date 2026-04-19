/**
 * StadiumFlow AI — WebSocket Client
 *
 * Manages real-time connection to the backend with auto-reconnect,
 * heartbeat keep-alive, and message routing to registered handlers.
 */

const WSClient = (() => {
    'use strict';

    // ── Configuration ────────────────────────────────────────
    const CONFIG = {
        reconnectDelay: 2000,
        maxReconnectDelay: 30000,
        heartbeatInterval: 25000,
        maxRetries: 50,
    };

    // ── State ────────────────────────────────────────────────
    let socket = null;
    let reconnectAttempts = 0;
    let heartbeatTimer = null;
    let reconnectTimer = null;
    let isConnected = false;
    const handlers = {};

    // ── URL Construction ─────────────────────────────────────
    function getWSUrl() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        return `${protocol}//${window.location.host}/ws/dashboard`;
    }

    // ── Connection Management ────────────────────────────────
    function connect() {
        if (socket && socket.readyState === WebSocket.OPEN) return;

        const url = getWSUrl();
        socket = new WebSocket(url);

        socket.onopen = () => {
            isConnected = true;
            reconnectAttempts = 0;
            startHeartbeat();
            updateStatus(true);
            dispatch('connected', {});
        };

        socket.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                handleMessage(message);
            } catch (e) {
                console.warn('[WS] Parse error:', e);
            }
        };

        socket.onclose = (event) => {
            isConnected = false;
            stopHeartbeat();
            updateStatus(false);
            dispatch('disconnected', { code: event.code });

            // Auto-reconnect
            if (reconnectAttempts < CONFIG.maxRetries) {
                const delay = Math.min(
                    CONFIG.reconnectDelay * Math.pow(1.5, reconnectAttempts),
                    CONFIG.maxReconnectDelay
                );
                reconnectTimer = setTimeout(() => {
                    reconnectAttempts++;
                    connect();
                }, delay);
            }
        };

        socket.onerror = () => {
            // Error handling is done via onclose
        };
    }

    function disconnect() {
        if (reconnectTimer) clearTimeout(reconnectTimer);
        stopHeartbeat();
        if (socket) {
            socket.close(1000, 'Client disconnect');
            socket = null;
        }
        isConnected = false;
    }

    // ── Heartbeat ────────────────────────────────────────────
    function startHeartbeat() {
        stopHeartbeat();
        heartbeatTimer = setInterval(() => {
            send({ type: 'ping' });
        }, CONFIG.heartbeatInterval);
    }

    function stopHeartbeat() {
        if (heartbeatTimer) {
            clearInterval(heartbeatTimer);
            heartbeatTimer = null;
        }
    }

    // ── Message Handling ─────────────────────────────────────
    function handleMessage(message) {
        const type = message.type;

        if (type === 'heartbeat' || type === 'pong') return;

        dispatch(type, message.data || message);
    }

    function send(data) {
        if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify(data));
        }
    }

    // ── Event System ─────────────────────────────────────────
    function on(eventType, callback) {
        if (!handlers[eventType]) handlers[eventType] = [];
        handlers[eventType].push(callback);
    }

    function off(eventType, callback) {
        if (!handlers[eventType]) return;
        handlers[eventType] = handlers[eventType].filter(cb => cb !== callback);
    }

    function dispatch(eventType, data) {
        const callbacks = handlers[eventType] || [];
        callbacks.forEach(cb => {
            try {
                cb(data);
            } catch (e) {
                console.error(`[WS] Handler error for "${eventType}":`, e);
            }
        });
    }

    // ── Status UI ────────────────────────────────────────────
    function updateStatus(connected) {
        const statusEl = document.getElementById('system-status');
        const dotEl = document.querySelector('.status-dot');

        if (statusEl) {
            statusEl.textContent = connected ? 'System Active' : 'Reconnecting...';
        }
        if (dotEl) {
            dotEl.classList.toggle('status-dot--active', connected);
        }
    }

    return {
        connect,
        disconnect,
        send,
        on,
        off,
        get isConnected() { return isConnected; },
    };
})();
