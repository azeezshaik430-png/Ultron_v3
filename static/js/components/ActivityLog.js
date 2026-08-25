/**
 * ULTRON V3 — Activity Log Component
 * Security and activity event log with auto-scrolling.
 */

class ActivityLog {
    constructor() {
        this.feed = document.getElementById('activityFeed');
        this.entries = [];
    }

    addEntry(text, type = 'info') {
        if (!this.feed) return;

        const now = new Date();
        const time = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

        const entry = document.createElement('div');
        entry.className = `activity-entry ${type}`;

        const timeSpan = document.createElement('span');
        timeSpan.className = 'act-time';
        timeSpan.textContent = time;

        const textSpan = document.createElement('span');
        textSpan.className = 'act-text';
        textSpan.textContent = text;

        entry.appendChild(timeSpan);
        entry.appendChild(textSpan);

        this.feed.prepend(entry);
        this.entries.push(entry);

        // Keep last 50 entries
        while (this.entries.length > 50) {
            const old = this.entries.shift();
            if (old.parentNode) old.parentNode.removeChild(old);
        }
    }

    addSecurityEvent(text) {
        this.addEntry(text, 'security');
    }

    addSuccessEvent(text) {
        this.addEntry(text, 'success');
    }
}

window.ActivityLog = ActivityLog;
