/**
 * StadiumFlow AI — AI Concierge Chat
 *
 * Chat widget for interacting with the Gemini AI-powered
 * venue assistant. Supports quick actions, typing indicators,
 * and message history.
 */

const Chat = (() => {
    'use strict';

    // ── State ────────────────────────────────────────────────
    let sessionId = null;
    let isLoading = false;

    // ── DOM References ───────────────────────────────────────
    const messagesEl = document.getElementById('chat-messages');
    const formEl = document.getElementById('chat-form');
    const inputEl = document.getElementById('chat-input-field');
    const sendBtn = document.getElementById('chat-send-btn');
    const quickActionsEl = document.getElementById('chat-quick-actions');

    // ── Send Message ─────────────────────────────────────────
    async function sendMessage(message) {
        if (!message.trim() || isLoading) return;

        // Add user message to UI
        appendMessage(message, 'user');

        // Show typing indicator
        showTyping();
        isLoading = true;
        setSendButtonState(false);

        try {
            const response = await fetch('/api/v1/chat/message', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: message,
                    session_id: sessionId,
                    user_zone: null,
                }),
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            sessionId = data.session_id;

            // Remove typing indicator and show response
            removeTyping();
            appendMessage(data.response, 'ai');

            // Update suggested actions if available
            if (data.suggested_actions && data.suggested_actions.length > 0) {
                updateSuggestedActions(data.suggested_actions);
            }

            // Announce for screen readers
            Accessibility.announce('New response from AI Concierge');

        } catch (error) {
            removeTyping();
            appendMessage(
                '⚠️ Connection issue. Please try again in a moment.',
                'ai'
            );
        } finally {
            isLoading = false;
            setSendButtonState(true);
        }
    }

    // ── Message Rendering ────────────────────────────────────
    function appendMessage(content, sender) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `chat-message chat-message--${sender}`;

        const avatar = document.createElement('div');
        avatar.className = 'chat-message__avatar';
        avatar.setAttribute('aria-hidden', 'true');
        avatar.textContent = sender === 'ai' ? '🤖' : '👤';

        const contentDiv = document.createElement('div');
        contentDiv.className = 'chat-message__content';

        // Parse markdown-like formatting
        const formattedContent = formatMessage(content);
        contentDiv.innerHTML = formattedContent;

        msgDiv.appendChild(avatar);
        msgDiv.appendChild(contentDiv);
        messagesEl.appendChild(msgDiv);

        // Scroll to bottom
        messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function formatMessage(text) {
        // Convert markdown-like syntax to HTML
        let html = text
            // Bold
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            // Line breaks
            .replace(/\n\n/g, '</p><p>')
            .replace(/\n/g, '<br>')
            // Bullet lists
            .replace(/^[•\-]\s(.+)/gm, '<li>$1</li>');

        // Wrap list items in <ul>
        if (html.includes('<li>')) {
            html = html.replace(/(<li>.*?<\/li>)+/gs, (match) => `<ul>${match}</ul>`);
        }

        return `<p>${html}</p>`.replace('<p></p>', '');
    }

    // ── Typing Indicator ─────────────────────────────────────
    function showTyping() {
        const typingDiv = document.createElement('div');
        typingDiv.className = 'chat-message chat-message--ai';
        typingDiv.id = 'typing-indicator';

        typingDiv.innerHTML = `
            <div class="chat-message__avatar" aria-hidden="true">🤖</div>
            <div class="chat-message__content">
                <div class="typing-indicator" aria-label="AI is thinking">
                    <div class="typing-indicator__dot"></div>
                    <div class="typing-indicator__dot"></div>
                    <div class="typing-indicator__dot"></div>
                </div>
            </div>
        `;

        messagesEl.appendChild(typingDiv);
        messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function removeTyping() {
        const typing = document.getElementById('typing-indicator');
        if (typing) typing.remove();
    }

    // ── Suggested Actions ────────────────────────────────────
    function updateSuggestedActions(actions) {
        if (!quickActionsEl) return;

        // Keep the default quick actions but add new ones
        const existingPrompts = new Set(
            [...quickActionsEl.querySelectorAll('.quick-action')]
                .map(el => el.dataset.prompt)
        );

        actions.forEach(action => {
            if (!existingPrompts.has(action)) {
                const btn = document.createElement('button');
                btn.className = 'quick-action';
                btn.dataset.prompt = action;
                btn.textContent = action.length > 30 ? action.substring(0, 30) + '...' : action;
                btn.addEventListener('click', () => sendMessage(action));
                quickActionsEl.appendChild(btn);
            }
        });
    }

    // ── UI State ─────────────────────────────────────────────
    function setSendButtonState(enabled) {
        if (sendBtn) {
            sendBtn.disabled = !enabled;
            sendBtn.style.opacity = enabled ? '1' : '0.5';
        }
    }

    // ── Initialization ───────────────────────────────────────
    function init() {
        // Form submission
        if (formEl) {
            formEl.addEventListener('submit', (e) => {
                e.preventDefault();
                const message = inputEl.value.trim();
                if (message) {
                    sendMessage(message);
                    inputEl.value = '';
                }
            });
        }

        // Quick action buttons
        if (quickActionsEl) {
            quickActionsEl.addEventListener('click', (e) => {
                const btn = e.target.closest('.quick-action');
                if (btn && btn.dataset.prompt) {
                    sendMessage(btn.dataset.prompt);
                }
            });
        }

        // Generate session ID
        sessionId = `sess-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
    }

    return { init, sendMessage };
})();
