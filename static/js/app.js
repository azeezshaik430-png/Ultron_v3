/**
 * ULTRON V3 — Main Frontend Application Controller
 * Connects all cinematic UI components to the FastAPI WebSocket gateway.
 */

document.addEventListener('DOMContentLoaded', () => {
    console.log('ULTRON V3 Cinematic Interface initializing...');

    /* ── Initialize Components ── */
    const avatar = new window.ULTRONAvatar('avatarCanvas');
    const voice = new window.VoiceInterface();
    const conversation = new window.ConversationPanel('conversationFeed');
    const agentPanel = new window.AgentPanel('agentFeed');
    const securityModal = new window.SecurityModal('securityModal');
    const dashboard = new window.SystemDashboard();
    const memoryPanel = new window.MemoryPanel('memoryFeed');
    const cmdInput = new window.CommandInput();
    const quickAccess = new window.QuickAccess();
    const activityLog = new window.ActivityLog();

    /* ── UI State Badge ── */
    const stateBadge = document.getElementById('stateText');
    if (window.uiStateMachine) {
        window.uiStateMachine.subscribe((newState) => {
            if (stateBadge) stateBadge.textContent = newState;
        });
    }

    /* ── Settings Drawer ── */
    const btnToggle = document.getElementById('btnToggleSettings');
    const btnClose = document.getElementById('btnCloseSettings');
    const drawer = document.getElementById('settingsDrawer');
    if (btnToggle && drawer) btnToggle.addEventListener('click', () => drawer.classList.remove('hidden'));
    if (btnClose && drawer) btnClose.addEventListener('click', () => drawer.classList.add('hidden'));

    /* ── Uptime Counter ── */
    const startTime = Date.now();
    const uptimeLabel = document.getElementById('uptimeLabel');
    setInterval(() => {
        if (!uptimeLabel) return;
        const elapsed = Math.floor((Date.now() - startTime) / 1000);
        const m = Math.floor(elapsed / 60);
        const s = elapsed % 60;
        uptimeLabel.textContent = `UPTIME: ${m}:${String(s).padStart(2, '0')}`;
    }, 1000);

    /* ── Command Counter ── */
    let cmdCount = 0;
    const cmdCountLabel = document.getElementById('cmdCountLabel');

    /* ── WebSocket Connection ── */
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/ui`;
    const wsDot = document.getElementById('wsDot');
    const wsLabel = document.getElementById('wsLabel');

    function connectWebSocket() {
        if (wsLabel) wsLabel.textContent = 'WS: CONNECTING';

        const socket = new WebSocket(wsUrl);

        socket.onopen = () => {
            console.log('[WebSocket] Connected to ULTRON V3 gateway.');
            if (window.uiStateMachine) window.uiStateMachine.setState(UIState.IDLE);
            if (wsDot) wsDot.className = 'strip-dot green';
            if (wsLabel) wsLabel.textContent = 'WS: CONNECTED';
            activityLog.addSuccessEvent('WebSocket gateway connected');
        };

        socket.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                handleGatewayEvent(msg);
            } catch (e) {
                console.error('[WebSocket] Parse error:', e);
            }
        };

        socket.onclose = () => {
            console.warn('[WebSocket] Disconnected. Reconnecting in 3s...');
            if (window.uiStateMachine) window.uiStateMachine.setState(UIState.OFFLINE);
            if (wsDot) wsDot.className = 'strip-dot red';
            if (wsLabel) wsLabel.textContent = 'WS: RECONNECTING';
            activityLog.addEntry('WebSocket disconnected, reconnecting...');
            setTimeout(connectWebSocket, 3000);
        };

        socket.onerror = (err) => {
            console.error('[WebSocket] Error:', err);
        };
    }

    /* ── Gateway Event Router ── */
    function handleGatewayEvent(msg) {
        const { event, payload } = msg;
        switch (event) {
            case 'voice_state':
                if (payload && payload.state && window.uiStateMachine) {
                    window.uiStateMachine.setState(payload.state);
                }
                break;

            case 'audio_level':
                if (payload && voice) {
                    voice.updateLevels(payload.amplitude || 0.1);
                }
                break;

            case 'speech_recognized':
                if (payload && payload.text && conversation) {
                    conversation.addMessage('BOSS', payload.text, 'user');
                    activityLog.addEntry(`Voice: "${payload.text}"`);
                }
                break;

            case 'assistant_response':
                if (payload && payload.text && conversation) {
                    conversation.addMessage('ULTRON', payload.text, 'assistant');
                    activityLog.addSuccessEvent(`Response sent (${payload.agent || 'Core'})`);
                }
                break;

            case 'agent_progress':
                if (payload && agentPanel) {
                    agentPanel.updateAgentProgress(payload.agent_name, payload.step, payload.progress);
                }
                break;

            case 'security_confirmation_required':
                if (payload && securityModal) {
                    securityModal.showPrompt(payload.token_id, payload.action, payload.target, payload.expires_in);
                    activityLog.addSecurityEvent(`Security: ${payload.action} required`);
                }
                break;

            case 'system_metrics':
                if (payload && dashboard) {
                    dashboard.updateMetrics(payload);
                }
                break;

            case 'memory_updated':
                if (payload && memoryPanel) {
                    memoryPanel.addOrUpdateMemory(payload.key, payload.value, payload.action || 'REMEMBERED');
                    activityLog.addEntry(`Memory: ${payload.action} "${payload.key}"`);
                }
                break;
        }
    }

    /* ── Command Submission ── */
    function sendCommand(text) {
        if (!text || !text.trim()) return;
        cmdCount++;
        if (cmdCountLabel) cmdCountLabel.textContent = `CMD: ${cmdCount}`;

        conversation.addMessage('BOSS', text, 'user');
        activityLog.addEntry(`Command: "${text}"`);

        if (window.uiStateMachine) window.uiStateMachine.setState(UIState.THINKING);

        fetch('/api/command', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ command: text }),
        })
            .then(res => res.json())
            .then(data => {
                if (data.result) {
                    conversation.addMessage('ULTRON', data.result, 'assistant');
                }
                if (window.uiStateMachine) window.uiStateMachine.setState(UIState.IDLE);
            })
            .catch(err => {
                console.error('[Command] Error:', err);
                conversation.addMessage('ULTRON', 'Error processing command.', 'assistant');
                if (window.uiStateMachine) window.uiStateMachine.setState(UIState.ERROR);
            });
    }

    /* ── Wire Command Input ── */
    if (cmdInput) cmdInput.onCommand = sendCommand;

    /* ── Wire Quick Access ── */
    if (quickAccess) quickAccess.onCommand = sendCommand;

    /* ── Wire Mic Button ── */
    if (voice && voice.micBtn) {
        voice.micBtn.addEventListener('click', () => {
            if (window.uiStateMachine) {
                const current = window.uiStateMachine.getState();
                if (current === UIState.IDLE || current === UIState.OFFLINE) {
                    window.uiStateMachine.setState(UIState.LISTENING);
                } else {
                    window.uiStateMachine.setState(UIState.IDLE);
                }
            }
        });
    }

    /* ── Start WebSocket ── */
    connectWebSocket();
});
