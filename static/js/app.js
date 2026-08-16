/**
 * ULTRON V3 - Main Frontend Application Controller & WebSocket Gateway Client
 */

document.addEventListener('DOMContentLoaded', () => {
    console.log('Initializing ULTRON V3 Futuristic HUD...');

    // Initialize UI Components
    const avatar = new window.AvatarRenderer('avatarCanvas');
    const visualizer = new window.VoiceVisualizer('spectrumCanvas');
    const conversation = new window.ConversationPanel('conversationFeed');
    const agentPanel = new window.AgentPanel('agentFeed');
    const securityModal = new window.SecurityModal('securityModal');
    const dashboard = new window.SystemDashboard();

    // UI State Badge Listener
    const stateBadge = document.getElementById('stateText');
    if (window.uiStateMachine) {
        window.uiStateMachine.subscribe((newState) => {
            if (stateBadge) stateBadge.textContent = newState;
        });
    }

    // Settings Drawer Toggle
    const btnToggleSettings = document.getElementById('btnToggleSettings');
    const btnCloseSettings = document.getElementById('btnCloseSettings');
    const settingsDrawer = document.getElementById('settingsDrawer');

    if (btnToggleSettings && settingsDrawer) {
        btnToggleSettings.addEventListener('click', () => settingsDrawer.classList.remove('hidden'));
    }
    if (btnCloseSettings && settingsDrawer) {
        btnCloseSettings.addEventListener('click', () => settingsDrawer.classList.add('hidden'));
    }

    // Connect to WebSocket Gateway
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/ui`;

    function connectWebSocket() {
        const socket = new WebSocket(wsUrl);

        socket.onopen = () => {
            console.log('[WebSocket] Connected to ULTRON V3 Real-Time Gateway.');
            if (window.uiStateMachine) window.uiStateMachine.setState(UIState.IDLE);
        };

        socket.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                handleGatewayEvent(msg);
            } catch (e) {
                console.error('[WebSocket] Parsing error:', e);
            }
        };

        socket.onclose = () => {
            console.warn('[WebSocket] Disconnected from Gateway. Reconnecting in 3s...');
            if (window.uiStateMachine) window.uiStateMachine.setState(UIState.OFFLINE);
            setTimeout(connectWebSocket, 3000);
        };

        socket.onerror = (err) => {
            console.error('[WebSocket] Socket error:', err);
        };
    }

    function handleGatewayEvent(msg) {
        const { event, payload } = msg;
        switch (event) {
            case 'voice_state':
                if (payload && payload.state && window.uiStateMachine) {
                    window.uiStateMachine.setState(payload.state);
                }
                break;
            case 'audio_level':
                if (payload && visualizer) {
                    visualizer.updateLevels(payload.amplitude || 0.1);
                }
                break;
            case 'speech_recognized':
                if (payload && payload.text && conversation) {
                    conversation.addMessage('USER', payload.text, 'user');
                }
                break;
            case 'assistant_response':
                if (payload && payload.text && conversation) {
                    conversation.addMessage('ULTRON', payload.text, 'assistant');
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
                }
                break;
            case 'system_metrics':
                if (payload && dashboard) {
                    dashboard.updateMetrics(payload);
                }
                break;
        }
    }

    connectWebSocket();
});
