/**
 * ULTRON V3 - UI State Machine Client Controller
 * Manages deterministic UI state transitions across all components.
 */

const UIState = Object.freeze({
    IDLE: 'IDLE',
    LISTENING: 'LISTENING',
    PROCESSING: 'PROCESSING',
    SPEAKING: 'SPEAKING',
    EXECUTING: 'EXECUTING',
    WAITING_CONFIRMATION: 'WAITING_CONFIRMATION',
    SUCCESS: 'SUCCESS',
    ERROR: 'ERROR',
    OFFLINE: 'OFFLINE'
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
        console.log(`[UI State Machine] Transition: ${this.currentState} -> ${newState}`);
        const oldState = this.currentState;
        this.currentState = newState;
        this.notify(newState, oldState);
    }

    subscribe(listener) {
        this.listeners.push(listener);
    }

    notify(newState, oldState) {
        for (const listener of this.listeners) {
            try {
                listener(newState, oldState);
            } catch (e) {
                console.error('[UI State Machine] Listener error:', e);
            }
        }
    }
}

window.uiStateMachine = new UIStateMachine();
