/**
 * ULTRON V3 - System Diagnostics Dashboard Component
 */

class SystemDashboard {
    constructor() {
        this.cpuVal = document.getElementById('cpuVal');
        this.ramVal = document.getElementById('ramVal');
        this.osVal = document.getElementById('osVal');
    }

    updateMetrics(metrics) {
        if (!metrics) return;
        if (this.cpuVal && metrics.cpu_percent !== undefined) {
            this.cpuVal.textContent = `${Math.round(metrics.cpu_percent)}%`;
        }
        if (this.ramVal && metrics.ram_percent !== undefined) {
            this.ramVal.textContent = `${Math.round(metrics.ram_percent)}%`;
        }
        if (this.osVal && metrics.platform) {
            this.osVal.textContent = metrics.platform;
        }
    }
}

window.SystemDashboard = SystemDashboard;
