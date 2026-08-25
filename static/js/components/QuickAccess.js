/**
 * ULTRON V3 — Quick Access Controls Component
 * Quick-action buttons that send preset commands.
 */

class QuickAccess {
    constructor() {
        this.container = document.getElementById('quickAccess');
        this.onCommand = null;
        this._bind();
    }

    _bind() {
        if (!this.container) return;
        const buttons = this.container.querySelectorAll('.quick-btn');
        buttons.forEach((btn) => {
            btn.addEventListener('click', () => {
                const cmd = btn.getAttribute('data-cmd');
                if (cmd && this.onCommand) this.onCommand(cmd);
            });
        });
    }
}

window.QuickAccess = QuickAccess;
