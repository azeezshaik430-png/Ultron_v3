/**
 * ULTRON V3 - Conversation Panel Component
 * Displays user voice transcriptions and ULTRON assistant responses.
 */

class ConversationPanel {
    constructor(feedId) {
        this.feed = document.getElementById(feedId);
    }

    addMessage(sender, text, type = 'assistant') {
        if (!this.feed) return;
        const msgDiv = document.createElement('div');
        msgDiv.className = `chat-message ${type === 'user' ? 'user-msg' : 'assistant-msg'}`;

        const senderSpan = document.createElement('span');
        senderSpan.className = 'msg-sender';
        senderSpan.textContent = sender;

        const textP = document.createElement('p');
        textP.textContent = text;

        const timeSpan = document.createElement('span');
        timeSpan.className = 'msg-time';
        timeSpan.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        msgDiv.appendChild(senderSpan);
        msgDiv.appendChild(textP);
        msgDiv.appendChild(timeSpan);

        this.feed.appendChild(msgDiv);
        this.feed.scrollTop = this.feed.scrollHeight;
    }
}

window.ConversationPanel = ConversationPanel;
