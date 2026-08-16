/**
 * ULTRON V3 - Multi-Agent & Task Execution Monitor
 */

class AgentPanel {
    constructor(feedId) {
        this.feed = document.getElementById(feedId);
    }

    updateAgentProgress(agentName, step, progress = 0.5) {
        if (!this.feed) return;
        let item = document.getElementById(`agent-${agentName}`);
        if (!item) {
            item = document.createElement('div');
            item.id = `agent-${agentName}`;
            item.className = 'agent-item active';
            this.feed.appendChild(item);
        }

        const pct = Math.round(progress * 100);
        item.innerHTML = `
            <span class="agent-name">${agentName}</span>
            <span class="agent-step">${step}</span>
            <div class="progress-bar"><div class="fill" style="width: ${pct}%;"></div></div>
        `;
    }
}

window.AgentPanel = AgentPanel;
