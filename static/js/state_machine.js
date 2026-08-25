/**
 * ULTRON V3 — UI State Machine
 * Manages deterministic state transitions for the cinematic interface.
 */

const UIState = Object.freeze({
    IDLE:               'IDLE',
    LISTENING:          'LISTENING',
    THINKING:           'THINKING',
    PROCESSING:         'PROCESSING',
    SPEAKING:           'SPEAKING',
    EXECUTING:          'EXECUTING',
    WAITING_CONFIRMATION: 'WAITING_CONFIRMATION',
    SUCCESS:            'SUCCESS',
    ERROR:              'ERROR',
    OFFLINE:            'OFFLINE'
});

class UIStateMachine {
    constructor() {
        this.currentState = UIState.OFFLINE;
        this.listeners = [];
    }

    getState() {
        return this.currentState;
    }

    setState(newState) {
        if (this.currentState === newState) return;
        console.log(`[UIStateMachine] ${this.currentState} → ${newState}`);
        const old = this.currentState;
        this.currentState = newState;
        for (const fn of this.listeners) {
            try { fn(newState, old); } catch (e) { console.error('[UIStateMachine] Listener error:', e); }
        }
    }

    subscribe(fn) {
        this.listeners.push(fn);
    }
}

window.UIState = UIState;
window.uiStateMachine = new UIStateMachine();
