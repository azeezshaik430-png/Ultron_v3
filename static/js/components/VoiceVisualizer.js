/**
 * ULTRON V3 - Voice Audio Spectrum Visualizer
 * Renders 60 FPS audio spectrum bars on Canvas synced with voice level payloads.
 */

class VoiceVisualizer {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        this.bars = 32;
        this.amplitudes = new Array(this.bars).fill(5);
        this.animate();
    }

    updateLevels(amplitude) {
        const factor = Math.min(1.0, amplitude);
        for (let i = 0; i < this.bars; i++) {
            const target = 5 + Math.random() * factor * (this.canvas.height - 10);
            this.amplitudes[i] += (target - this.amplitudes[i]) * 0.3;
        }
    }

    animate() {
        requestAnimationFrame(() => this.animate());
        if (!this.ctx) return;

        const width = this.canvas.width;
        const height = this.canvas.height;
        this.ctx.clearRect(0, 0, width, height);

        const barWidth = (width / this.bars) - 2;
        for (let i = 0; i < this.bars; i++) {
            const h = this.amplitudes[i];
            const x = i * (barWidth + 2);
            const y = height - h;

            this.ctx.fillStyle = '#00f0ff';
            this.ctx.fillRect(x, y, barWidth, h);
        }
    }
}

window.VoiceVisualizer = VoiceVisualizer;
