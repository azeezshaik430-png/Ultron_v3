/**
 * ULTRON V3 — Voice Interface Component
 * Dynamic audio waveform visualization with mic control and state awareness.
 */

class VoiceInterface {
    constructor() {
        this.canvas = document.getElementById('waveformCanvas');
        this.micBtn = document.getElementById('micBtn');
        this.stateText = document.getElementById('voiceStateText');
        this.isActive = false;
        this.amplitude = 0.1;
        this.targetAmplitude = 0.1;

        if (this.canvas) {
            this.ctx = this.canvas.getContext('2d');
            this._resize();
            window.addEventListener('resize', () => this._resize());
            this._animate();
        }

        if (this.micBtn) {
            this.micBtn.addEventListener('click', () => this._toggleMic());
        }

        if (window.uiStateMachine) {
            window.uiStateMachine.subscribe((state) => this._onState(state));
        }
    }

    _resize() {
        if (!this.canvas) return;
        const parent = this.canvas.parentElement;
        if (parent) {
            this.canvas.width = parent.clientWidth;
            this.canvas.height = 40;
        }
    }

    _toggleMic() {
        this.isActive = !this.isActive;
        if (this.micBtn) {
            this.micBtn.classList.toggle('listening', this.isActive);
        }
    }

    _onState(state) {
        const stateLabels = {
            IDLE: 'IDLE',
            LISTENING: 'LISTENING',
            THINKING: 'THINKING',
            PROCESSING: 'PROCESSING',
            SPEAKING: 'SPEAKING',
            EXECUTING: 'EXECUTING',
            WAITING_CONFIRMATION: 'AWAITING CONFIRM',
            SUCCESS: 'COMPLETE',
            ERROR: 'ERROR',
            OFFLINE: 'OFFLINE',
        };
        if (this.stateText) {
            this.stateText.textContent = stateLabels[state] || state;
        }

        // Update mic button class
        if (this.micBtn) {
            this.micBtn.classList.remove('listening', 'processing');
            if (state === 'LISTENING') this.micBtn.classList.add('listening');
            else if (state === 'THINKING' || state === 'PROCESSING' || state === 'EXECUTING') this.micBtn.classList.add('processing');
        }

        // Set target amplitude based on state
        const ampMap = {
            IDLE: 0.05,
            LISTENING: 0.6,
            THINKING: 0.15,
            PROCESSING: 0.2,
            SPEAKING: 0.7,
            EXECUTING: 0.3,
            WAITING_CONFIRMATION: 0.1,
            SUCCESS: 0.4,
            ERROR: 0.5,
            OFFLINE: 0.02,
        };
        this.targetAmplitude = ampMap[state] || 0.1;
    }

    updateLevels(amplitude) {
        this.targetAmplitude = Math.min(1.0, amplitude);
    }

    _animate() {
        requestAnimationFrame(() => this._animate());
        if (!this.ctx) return;

        const w = this.canvas.width;
        const h = this.canvas.height;
        this.ctx.clearRect(0, 0, w, h);

        // Smooth amplitude transition
        this.amplitude += (this.targetAmplitude - this.amplitude) * 0.08;

        const barCount = Math.floor(w / 4);
        const barWidth = 2;
        const gap = (w - barCount * barWidth) / (barCount - 1);

        for (let i = 0; i < barCount; i++) {
            const freq = Math.sin(i * 0.15 + Date.now() * 0.003) * 0.3 + 0.7;
            const noise = Math.random() * 0.2 + 0.8;
            const barH = Math.max(2, (this.amplitude * freq * noise) * (h * 0.8));
            const x = i * (barWidth + gap);
            const y = (h - barH) / 2;

            const alpha = 0.3 + this.amplitude * 0.5;
            this.ctx.fillStyle = `rgba(212, 168, 67, ${alpha})`;
            this.ctx.fillRect(x, y, barWidth, barH);
        }
    }
}

window.VoiceInterface = VoiceInterface;
