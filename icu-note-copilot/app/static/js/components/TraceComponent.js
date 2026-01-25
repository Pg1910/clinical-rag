export class TraceComponent {
    constructor(store, api) {
        this.store = store;
        this.api = api;

        this.els = {
            tabs: document.querySelectorAll('.tab-btn'),
            contents: document.querySelectorAll('.tab-content'),
            summaryContent: document.getElementById('summaryContent'),
            differentialContent: document.getElementById('differentialContent'),
            rightPanel: document.querySelector('.right-panel'),
            bleuResult: document.getElementById('bleuResult')
        };

        this.init();
    }

    init() {
        // Tabs Logic
        this.els.tabs.forEach(tab => {
            tab.onclick = () => {
                this.els.tabs.forEach(t => t.classList.remove('active'));
                this.els.contents.forEach(c => c.classList.add('hidden'));

                tab.classList.add('active');
                document.getElementById(tab.dataset.tab).classList.remove('hidden');
            };
        });

        // Wide View Toggle Logic
        const wideBtn = document.createElement('button');
        wideBtn.className = 'btn-wide-toggle';
        wideBtn.innerHTML = '⬌ Wide View';
        wideBtn.title = 'Toggle Wide/Narrow View';
        document.querySelector('.tabs').appendChild(wideBtn);

        wideBtn.onclick = () => {
            this.els.rightPanel.classList.toggle('wide');
            wideBtn.classList.toggle('active');
            wideBtn.innerHTML = this.els.rightPanel.classList.contains('wide') ? '⬌ Narrow View' : '⬌ Wide View';
        };

        // Logout Button
        const logoutBtn = document.createElement('button');
        logoutBtn.className = 'btn-logout';
        logoutBtn.innerHTML = 'Logout';
        logoutBtn.onclick = () => window.location.href = '/logout';
        document.querySelector('.tabs').appendChild(logoutBtn);

        // Listen for Metrics calculation results (BLEU + Others)
        document.addEventListener('bleu-calculated', (e) => {
            const data = e.detail;
            if (this.els.bleuResult) {
                // Determine if we have extended metrics or just BLEU
                const isExtended = !!data.rouge_1;

                let html = `<div class="metrics-grid">`;

                if (isExtended) {
                    html += `
                        <div class="metric-group">
                            <strong>Validation Metrics (Qwen 3:4B)</strong>
                            <div class="metric-row">BLEU: <span>${data.bleu.toFixed(4)}</span></div>
                            <div class="metric-row">ROUGE-1: <span>${data.rouge_1.toFixed(4)}</span></div>
                            <div class="metric-row">ROUGE-2: <span>${data.rouge_2.toFixed(4)}</span></div>
                            <div class="metric-row">ROUGE-L: <span>${data.rouge_l.toFixed(4)}</span></div>
                            <div class="metric-row">Semantic Similarity: <span>${data.semantic_similarity.toFixed(4)}</span></div>
                            <div class="metric-row">SOAP Sections: <span>${data.soap_sections}</span></div>
                        </div>
                    `;
                } else {
                    html += `
                        <div class="bleu-scores">
                            <strong>Combined BLEU: ${data.bleu.toFixed(4)}</strong>
                            <div class="bleu-breakdown">
                                <span>B1: ${data.bleu1.toFixed(3)}</span> | 
                                <span>B2: ${data.bleu2.toFixed(3)}</span> | 
                                <span>B3: ${data.bleu3.toFixed(3)}</span> | 
                                <span>B4: ${data.bleu4.toFixed(3)}</span>
                            </div>
                        </div>
                    `;
                }
                html += `</div>`;
                this.els.bleuResult.innerHTML = html;
            }
        });

        // Subscribe to latestReport to render Summary and Differential
        this.store.subscribe('latestReport', (data) => {
            if (data && data.report) {
                this.renderSummary(data.report.summary);
                this.renderDifferential(data.report.differential);
            }
        });
    }

    renderSummary(summaryData) {
        if (!summaryData || (Array.isArray(summaryData) && summaryData.length === 0)) {
            this.els.summaryContent.innerHTML = '<p class="placeholder-text">No summary available.</p>';
            return;
        }

        let html = '<div class="summary-list"><h4>Clinical Summary</h4><ul>';
        if (Array.isArray(summaryData)) {
            summaryData.forEach(point => {
                html += `<li>${point}</li>`;
            });
        } else {
            html += `<li>${summaryData}</li>`;
        }
        html += '</ul></div>';
        this.els.summaryContent.innerHTML = html;
    }

    renderDifferential(diffData) {
        if (!diffData) {
            this.els.differentialContent.innerHTML = '<p class="placeholder-text">No differential diagnosis available.</p>';
            return;
        }

        let html = '<div class="differential-list"><h4>Differential Diagnosis</h4>';

        if (diffData.support && Array.isArray(diffData.support) && diffData.support.length > 0) {
            html += '<div class="diff-section"><strong>Supporting:</strong><ul>';
            diffData.support.forEach(item => {
                html += `<li class="support-item">${item}</li>`;
            });
            html += '</ul></div>';
        }

        if (diffData.against && Array.isArray(diffData.against) && diffData.against.length > 0) {
            html += '<div class="diff-section"><strong>Against:</strong><ul>';
            diffData.against.forEach(item => {
                html += `<li class="against-item">${item}</li>`;
            });
            html += '</ul></div>';
        }

        if (diffData.missing && Array.isArray(diffData.missing) && diffData.missing.length > 0) {
            html += '<div class="diff-section"><strong>Missing Info:</strong><ul>';
            diffData.missing.forEach(item => {
                html += `<li class="missing-item">${item}</li>`;
            });
            html += '</ul></div>';
        }

        if (html === '<div class="differential-list"><h4>Differential Diagnosis</h4>') {
            html += '<p class="placeholder-text">Differential diagnosis was not specifically structured by the model. Check the Clinical Summary or Raw Data Staging for details.</p>';
        }

        html += '</div>';
        this.els.differentialContent.innerHTML = html;
    }
}
