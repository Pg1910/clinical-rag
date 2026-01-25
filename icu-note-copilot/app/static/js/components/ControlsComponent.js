export class ControlsComponent {
    constructor(store, api) {
        this.store = store;
        this.api = api;

        this.els = {
            caseSelector: document.getElementById('caseSelector'),
            userQuestion: document.getElementById('userQuestion'),
            btnGlobal: document.getElementById('btnGlobal'),
            btnLocal: document.getElementById('btnLocal'),
            btnFull: document.getElementById('btnFull'),
            btnLoadReport: document.getElementById('btnLoadReport'),
            btnExport: document.getElementById('btnExport'),
            toggleSoap: document.getElementById('toggleSoap'),
            toggleHybrid: document.getElementById('toggleHybrid'),
            toggleEvidenceIds: document.getElementById('toggleEvidenceIds'),
            toggleJson: document.getElementById('toggleJson')
        };

        this.init();
    }

    init() {
        // Load Cases
        this.loadCases();

        // Subscriptions
        this.store.subscribe('selectedCase', (val) => {
            if (this.els.caseSelector.value !== val) {
                this.els.caseSelector.value = val;
            }
        });

        // Event Listeners
        this.els.caseSelector.addEventListener('change', (e) => {
            const caseId = e.target.value;
            this.store.setState('selectedCase', caseId);

            // AUTOMATED PROMPT for Multi-stage Orchestrator
            if (caseId) {
                const defaultPrompt = "Analyze the provided ICU clinical notes for Case ID " + caseId + ". \n" +
                    "1. Provide a detailed summary of the patient status (5-8 bullet points).\n" +
                    "2. Identify potential differential diagnoses with supporting evidence.";
                this.store.setState('userQuestion', defaultPrompt);
                this.els.userQuestion.value = defaultPrompt;
            } else {
                this.store.setState('userQuestion', '');
                this.els.userQuestion.value = '';
            }
        });

        this.els.userQuestion.addEventListener('input', (e) => {
            this.store.setState('userQuestion', e.target.value);
        });

        this.els.btnGlobal.onclick = () => this.handleGlobal();
        this.els.btnLocal.onclick = () => this.handleLocal();
        this.els.btnFull.onclick = () => this.handleFull();
        this.els.btnExport.onclick = () => this.handleExport();

        // BLEU Computation listener
        const btnBleu = document.getElementById('btnBleu');
        if (btnBleu) {
            btnBleu.onclick = () => this.handleBleu();
        }
    }

    async handleBleu() {
        const refSummary = document.getElementById('refSummary').value;
        const report = this.store.getState('latestReport');

        if (!refSummary) return alert("Please paste a reference summary first");
        if (!report || !report.report || !report.report.summary) return alert("Run the pipeline first to get a generated summary");

        const generated = Array.isArray(report.report.summary) ? report.report.summary.join(" ") : report.report.summary;

        try {
            const res = await this.api.computeBleu(refSummary, generated);
            document.dispatchEvent(new CustomEvent('bleu-calculated', { detail: res }));
        } catch (e) {
            alert("Bleu calculation failed: " + e.message);
        }
    }

    async loadCases() {
        try {
            const data = await this.api.getCases();
            // Expected { cases: [{case_id, label}, ...] }
            const cases = data.cases || [];

            this.els.caseSelector.innerHTML = '<option value="">Select a case...</option>';
            cases.forEach(c => {
                const opt = document.createElement('option');
                // FIX: Ensure textContent is readable label, value is ID
                opt.value = c.case_id;
                opt.textContent = c.label || `Case ${c.case_id}`;
                this.els.caseSelector.appendChild(opt);
            });

            // Restore selection
            const saved = this.store.getState('selectedCase');
            if (saved) this.els.caseSelector.value = saved;

            this.store.setState('cases', cases);
        } catch (e) {
            console.error(e);
            alert("Failed to load cases");
        }
    }

    validate() {
        const caseId = this.store.getState('selectedCase');
        const question = this.store.getState('userQuestion');
        if (!caseId) { alert('Select a case'); return false; }
        if (!question) { alert('Enter a question'); return false; }
        return { caseId, question };
    }

    async handleGlobal() {
        const input = this.validate();
        if (!input) return;

        this.store.setState('isLoading', true);
        try {
            const res = await this.api.globalRetrieve(
                input.caseId, input.question, this.els.toggleSoap.checked
            );
            this.store.setState('globalTrace', res);
            // Switch tab logic handled by TraceComponent ideally, 
            // but we can trigger it or just let data flow.
            document.querySelector('[data-tab="tab-global"]').click();
        } catch (e) {
            console.error(e);
        }
        this.store.setState('isLoading', false);
    }

    async handleLocal() {
        const input = this.validate();
        if (!input) return;

        this.store.setState('isLoading', true);
        try {
            const res = await this.api.localRetrieve(
                input.caseId, input.question, this.els.toggleHybrid.checked
            );
            this.store.setState('localTrace', res);
            document.querySelector('[data-tab="tab-local"]').click();
        } catch (e) {
            console.error(e);
        }
        this.store.setState('isLoading', false);
    }

    async handleFull() {
        const input = this.validate();
        if (!input) return;

        this.store.setState('isLoading', true);

        const msg = { role: 'user', text: input.question };
        document.dispatchEvent(new CustomEvent('chat-message', { detail: msg }));

        try {
            const res = await this.api.llmAnswer(input.caseId, input.question, {
                use_soap: this.els.toggleSoap.checked,
                json_mode: this.els.toggleJson.checked
            });

            // Store the full report (TraceComponent will pick up summary/differential)
            this.store.setState('latestReport', res);

            // Build chat message with traces and evidence (instead of summary)
            let html = '';

            // Add Global Trace to chat - FULL OUTPUT
            if (res.trace && res.trace.global_run) {
                html += `<div class="trace-section">
                    <div class="trace-header">
                        <strong>Global Retrieval:</strong>
                        <button class="btn-toggle-trace" data-target="global-trace-details">▼ Expand</button>
                    </div>`;
                const globalData = res.trace.global_run;

                // Show SOAP queries
                if (globalData.soap_queries) {
                    html += `<div class="soap-queries"><em>SOAP Queries:</em>`;
                    for (const [section, queries] of Object.entries(globalData.soap_queries)) {
                        html += `<div class="query-item"><strong>${section}:</strong> ${queries.join(', ')}</div>`;
                    }
                    html += `</div>`;
                }

                // Show full results in expandable section
                html += `<div class="trace-details" id="global-trace-details">`;
                if (globalData.results) {
                    html += `<div class="results-section"><em>Retrieved Results:</em>`;
                    for (const [section, items] of Object.entries(globalData.results)) {
                        if (items && items.length > 0) {
                            html += `<div class="result-category"><strong>${section}:</strong>`;
                            items.forEach(item => {
                                html += `<div class="result-item">${item.text || JSON.stringify(item)}</div>`;
                            });
                            html += `</div>`;
                        }
                    }
                    html += `</div>`;
                }
                if (globalData.evidence_count) {
                    html += `<div class="evidence-count">Evidence Count: ${globalData.evidence_count}</div>`;
                }
                html += `</div></div>`;
            }

            // Add Local Trace to chat - FULL OUTPUT
            if (res.trace && res.trace.local_run) {
                html += `<div class="trace-section">
                    <div class="trace-header">
                        <strong>Local Retrieval:</strong>
                        <button class="btn-toggle-trace" data-target="local-trace-details">▼ Expand</button>
                    </div>`;
                const localData = res.trace.local_run;

                // Show derived queries
                if (localData.derived_queries) {
                    html += `<div class="derived-queries"><em>Derived Queries:</em>`;
                    localData.derived_queries.forEach(q => {
                        html += `<div class="query-item"><strong>${q.section}:</strong> ${q.query}</div>`;
                    });
                    html += `</div>`;
                }

                // Show full results in expandable section
                html += `<div class="trace-details" id="local-trace-details">`;
                if (localData.results) {
                    html += `<div class="results-section"><em>Retrieved Results:</em>`;
                    for (const [section, items] of Object.entries(localData.results)) {
                        if (items && items.length > 0) {
                            html += `<div class="result-category"><strong>${section}:</strong>`;
                            items.forEach(item => {
                                html += `<div class="result-item">${item.text || JSON.stringify(item)}</div>`;
                            });
                            html += `</div>`;
                        }
                    }
                    html += `</div>`;
                }
                html += `</div></div>`;
            }

            // Add Evidence to chat with ID and Export buttons
            if (res.evidence && res.evidence.length > 0) {
                // Store evidence globally for export
                window._evidenceData = res.evidence;

                html += `<div class="evidence-section">
                    <div class="evidence-header">
                        <strong>Evidence Used (${res.evidence.length} items):</strong>
                    </div>`;
                html += `<div class="evidence-cards">`;
                res.evidence.forEach((item, idx) => {
                    const evidenceId = item.id || (idx + 1);
                    html += `<div class="evidence-chip" data-evidence-idx="${idx}">
                        <div class="evidence-chip-header">
                            <span class="evidence-id-badge">ID: ${evidenceId}</span>
                            <button class="btn-export-evidence" data-idx="${idx}" title="Export this evidence">📥 Export</button>
                        </div>
                        <div class="evidence-text-full">${item.text || 'No text available'}</div>
                    </div>`;
                });
                html += `</div></div>`;
            }

            if (html) {
                document.dispatchEvent(new CustomEvent('chat-message', {
                    detail: { role: 'assistant', text: html, isHtml: true }
                }));
            }

        } catch (e) {
            alert(e.message);
        }
        this.store.setState('isLoading', false);
    }

    handleExport() {
        const report = this.store.getState('latestReport');
        if (!report) return alert("No report to export");
        const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `report.json`;
        a.click();
    }
}
