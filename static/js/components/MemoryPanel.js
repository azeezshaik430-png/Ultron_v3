/**
 * ULTRON V3 — Memory Recall UI Component Controller
 * Hydrates and live-updates real persistent & semantic memory feed.
 */

class MemoryPanel {
    constructor(containerId = 'memoryFeed') {
        this.container = document.getElementById(containerId);
        this.memoriesMap = new Map();
        this.init();
    }

    async init() {
        if (!this.container) return;
        try {
            const response = await fetch('/api/memory?limit=20');
            if (response.ok) {
                const data = await response.json();
                if (data.memories && Array.isArray(data.memories)) {
                    this.container.innerHTML = '';
                    data.memories.forEach(mem => {
                        this.addOrUpdateMemory(mem.key, mem.value, mem.tag);
                    });
                }
            }
        } catch (err) {
            console.warn('[MemoryPanel] Initial hydration notice:', err);
        }
    }

    addOrUpdateMemory(key, value, tag = 'REMEMBERED') {
        if (!this.container) return;
        const text = `${key}: ${value}`;
        const existing = this.memoriesMap.get(key);

        if (existing) {
            const p = existing.querySelector('.mem-text');
            if (p) p.textContent = text;
            const t = existing.querySelector('.mem-tag');
            if (t) t.textContent = tag.toUpperCase();
        } else {
            const item = document.createElement('div');
            item.className = 'memory-item';
            item.setAttribute('data-key', key);

            const spanTag = document.createElement('span');
            spanTag.className = 'mem-tag';
            spanTag.textContent = tag.toUpperCase();

            const pText = document.createElement('p');
            pText.className = 'mem-text';
            pText.textContent = text;

            item.appendChild(spanTag);
            item.appendChild(pText);

            this.container.prepend(item);
            this.memoriesMap.set(key, item);
        }
    }
}

window.MemoryPanel = MemoryPanel;
