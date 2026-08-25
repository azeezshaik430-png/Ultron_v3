/**
 * ULTRON V3 — Security Confirmation Overlay Modal
 * Handles high-priority confirmation requests for dangerous operations.
 */

class SecurityModal {
    constructor(modalId) {
        this.modal = document.getElementById(modalId);
        this.actionLabel = document.getElementById('secActionLabel');
        this.targetLabel = document.getElementById('secTargetLabel');
        this.timerVal = document.getElementById('secTimerVal');
        this.btnApprove = document.getElementById('btnSecApprove');
        this.btnDeny = document.getElementById('btnSecDeny');
        this.currentTokenId = null;
        this.timerInterval = null;

        if (this.btnApprove) this.btnApprove.addEventListener('click', () => this.respond(true));
        if (this.btnDeny) this.btnDeny.addEventListener('click', () => this.respond(false));
    }

    showPrompt(tokenId, action, target, expiresSec = 15) {
        if (!this.modal) return;
        this.currentTokenId = tokenId;
        if (this.actionLabel) this.actionLabel.textContent = `ACTION: ${action}`;
        if (this.targetLabel) this.targetLabel.textContent = `TARGET: ${target}`;

        let remaining = expiresSec;
        if (this.timerVal) this.timerVal.textContent = remaining;

        this.modal.classList.remove('hidden');
        if (window.uiStateMachine) window.uiStateMachine.setState(UIState.WAITING_CONFIRMATION);

        clearInterval(this.timerInterval);
        this.timerInterval = setInterval(() => {
            remaining--;
            if (this.timerVal) this.timerVal.textContent = remaining;
            if (remaining <= 0) {
                clearInterval(this.timerInterval);
                this.respond(false);
            }
        }, 1000);
    }

    async respond(approved) {
        clearInterval(this.timerInterval);
        if (this.modal) this.modal.classList.add('hidden');

        if (this.currentTokenId) {
            try {
                await fetch('/api/security/confirm', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ token_id: this.currentTokenId, approved: approved }),
                });
            } catch (e) {
                console.error('[SecurityModal] Failed to send response:', e);
            }
        }
        if (window.uiStateMachine) window.uiStateMachine.setState(UIState.IDLE);
    }
}

window.SecurityModal = SecurityModal;
