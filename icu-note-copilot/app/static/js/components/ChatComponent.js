export class ChatComponent {
    constructor(store) {
        this.store = store;
        this.container = document.getElementById('chatContainer');
        this.loading = document.getElementById('loadingIndicator');

        this.init();
    }

    init() {
        // Listen for global chat events (decoupled from Controls)
        document.addEventListener('chat-message', (e) => {
            this.addMessage(e.detail.role, e.detail.text, e.detail.isHtml);
        });

        this.store.subscribe('isLoading', (val) => {
            if (val) this.loading.classList.remove('hidden');
            else this.loading.classList.add('hidden');
        });
    }

    addMessage(role, text, isHtml = false) {
        const div = document.createElement('div');
        div.className = `chat-message ${role}`;

        if (isHtml) {
            div.innerHTML = this.processEvidenceLinks(text);
            // Re-attach listeners for evidence links
            div.querySelectorAll('.evidence-link').forEach(link => {
                link.onclick = () => {
                    const id = link.dataset.id;
                    document.dispatchEvent(new CustomEvent('view-evidence', { detail: id }));
                };
            });

            // Toggle buttons for trace sections
            div.querySelectorAll('.btn-toggle-trace').forEach(btn => {
                btn.onclick = () => {
                    const targetId = btn.dataset.target;
                    const target = document.getElementById(targetId);
                    if (target) {
                        target.classList.toggle('expanded');
                        btn.textContent = target.classList.contains('expanded') ? '▲ Collapse' : '▼ Expand';
                    }
                };
            });

            // Export buttons for individual evidence items
            div.querySelectorAll('.btn-export-evidence').forEach(btn => {
                btn.onclick = () => {
                    const idx = parseInt(btn.dataset.idx);
                    if (window._evidenceData && window._evidenceData[idx]) {
                        const evidence = window._evidenceData[idx];
                        const blob = new Blob([JSON.stringify(evidence, null, 2)], { type: 'application/json' });
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = `evidence_${evidence.id || idx + 1}.json`;
                        a.click();
                        URL.revokeObjectURL(url);
                    }
                };
            });
        } else {
            div.textContent = text;
        }

        this.container.appendChild(div);
        this.container.scrollTop = this.container.scrollHeight;
    }

    processEvidenceLinks(text) {
        // Regex to find [doc_id] patterns
        return text.replace(/\[(\w+)\]/g, (match, id) => {
            return `<span class="evidence-link" data-id="${id}">[${id}]</span>`;
        });
    }
}
