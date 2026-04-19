/**
 * StadiumFlow AI — Accessibility Utilities
 *
 * Provides focus management, keyboard shortcuts, high-contrast
 * mode toggle, and ARIA live region announcements.
 */

const Accessibility = (() => {
    'use strict';

    // ── State ────────────────────────────────────────────────
    let currentTheme = 'dark';

    // ── Live Region Announcements ────────────────────────────
    function announce(message, priority = 'polite') {
        const region = document.getElementById('a11y-announcements');
        if (!region) return;

        region.setAttribute('aria-live', priority);
        region.textContent = '';
        // Brief delay to ensure screen readers pick up the change
        requestAnimationFrame(() => {
            region.textContent = message;
        });
    }

    // ── Theme Management ─────────────────────────────────
    function setTheme(theme) {
        currentTheme = theme;
        document.documentElement.setAttribute('data-theme', theme);
        
        // Update icons
        const iconMoon = document.getElementById('icon-moon');
        const iconSun = document.getElementById('icon-sun');
        if (iconMoon && iconSun) {
            if (theme === 'light') {
                iconMoon.style.display = 'none';
                iconSun.style.display = 'block';
            } else {
                iconMoon.style.display = 'block';
                iconSun.style.display = 'none';
            }
        }
        
        announce(`Theme set to ${theme}`);

        try {
            localStorage.setItem('stadiumflow-theme', theme);
        } catch (e) {}
    }

    function toggleTheme() {
        if (currentTheme === 'dark' || currentTheme === 'high-contrast') {
            setTheme('light');
        } else {
            setTheme('dark');
        }
    }

    function toggleHighContrast() {
        if (currentTheme === 'high-contrast') {
            setTheme('dark');
        } else {
            setTheme('high-contrast');
        }
    }

    // ── Keyboard Shortcuts ───────────────────────────────────
    function setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Alt+H: Toggle high contrast
            if (e.altKey && e.key === 'h') {
                e.preventDefault();
                toggleHighContrast();
            }

            // Alt+C: Focus chat input
            if (e.altKey && e.key === 'c') {
                e.preventDefault();
                const chatInput = document.getElementById('chat-input-field');
                if (chatInput) {
                    chatInput.focus();
                    announce('Chat input focused');
                }
            }

            // Alt+M: Focus map
            if (e.altKey && e.key === 'm') {
                e.preventDefault();
                const map = document.getElementById('venue-map');
                if (map) {
                    map.focus();
                    announce('Venue map focused');
                }
            }

            // Escape: Close tooltips/modals
            if (e.key === 'Escape') {
                const tooltip = document.getElementById('map-tooltip');
                if (tooltip) {
                    tooltip.classList.remove('map-tooltip--visible');
                    tooltip.setAttribute('aria-hidden', 'true');
                }
            }
        });
    }

    // ── Focus Management ─────────────────────────────────────
    function trapFocus(element) {
        const focusable = element.querySelectorAll(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        const first = focusable[0];
        const last = focusable[focusable.length - 1];

        element.addEventListener('keydown', (e) => {
            if (e.key !== 'Tab') return;

            if (e.shiftKey) {
                if (document.activeElement === first) {
                    e.preventDefault();
                    last.focus();
                }
            } else {
                if (document.activeElement === last) {
                    e.preventDefault();
                    first.focus();
                }
            }
        });
    }

    // ── Initialization ───────────────────────────────────────
    function init() {
        // Restore theme preference
        try {
            const savedTheme = localStorage.getItem('stadiumflow-theme');
            if (savedTheme) {
                setTheme(savedTheme);
            }
            // Migrate legacy
            const legacyHC = localStorage.getItem('stadiumflow-high-contrast');
            if (legacyHC === 'true' && !savedTheme) {
                setTheme('high-contrast');
            }
        } catch (e) {}

        // Wire up theme toggle button
        const themeBtn = document.getElementById('btn-theme-toggle');
        if (themeBtn) {
            themeBtn.addEventListener('click', toggleTheme);
        }

        // Wire up high contrast button
        const hcBtn = document.getElementById('btn-high-contrast');
        if (hcBtn) {
            hcBtn.addEventListener('click', toggleHighContrast);
        }

        // Wire up fullscreen button
        const fsBtn = document.getElementById('btn-fullscreen');
        if (fsBtn) {
            fsBtn.addEventListener('click', () => {
                if (!document.fullscreenElement) {
                    document.documentElement.requestFullscreen().catch(() => {});
                    announce('Fullscreen mode enabled');
                } else {
                    document.exitFullscreen().catch(() => {});
                    announce('Fullscreen mode disabled');
                }
            });
        }

        setupKeyboardShortcuts();
    }

    // Run on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    return { announce, toggleHighContrast, toggleTheme, trapFocus };
})();
