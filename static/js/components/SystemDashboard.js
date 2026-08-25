/**
 * ULTRON V3 — System Diagnostics Dashboard Component
 * Displays CPU, RAM, GPU, network, temperature, and power metrics.
 */

class SystemDashboard {
    constructor() {
        this.cpuVal = document.getElementById('cpuVal');
        this.ramVal = document.getElementById('ramVal');
        this.gpuVal = document.getElementById('gpuVal');
        this.netVal = document.getElementById('netVal');
        this.tempVal = document.getElementById('tempVal');
        this.powerVal = document.getElementById('powerVal');
    }

    updateMetrics(metrics) {
        if (!metrics) return;
        if (this.cpuVal && metrics.cpu_percent !== undefined) {
            this.cpuVal.textContent = `${Math.round(metrics.cpu_percent)}%`;
        }
        if (this.ramVal && metrics.ram_percent !== undefined) {
            this.ramVal.textContent = `${Math.round(metrics.ram_percent)}%`;
        }
        if (this.powerVal && metrics.platform) {
            this.powerVal.textContent = metrics.platform;
        }
    }
}

window.SystemDashboard = SystemDashboard;
