/**
 * ULTRON V3 — Command Input Component
 * Text command submission with enter-key and send button support.
 */

class CommandInput {
    constructor() {
        this.input = document.getElementById('commandInput');
        this.sendBtn = document.getElementById('commandSendBtn');
        this.onCommand = null;

        if (this.sendBtn) {
            this.sendBtn.addEventListener('click', () => this._submit());
        }
        if (this.input) {
            this.input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') this._submit();
            });
        }
    }

    _submit() {
        if (!this.input) return;
        const text = this.input.value.trim();
        if (!text) return;
        this.input.value = '';
        if (this.onCommand) this.onCommand(text);
    }

    getCommand() {
        return this.input ? this.input.value.trim() : '';
    }
}

window.CommandInput = CommandInput;
