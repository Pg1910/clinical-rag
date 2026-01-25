/**
 * API Client for Clinical RAG System
 * Handles all network requests and error parsing.
 */
export class ApiClient {
    constructor(baseUrl = '/api') {
        this.baseUrl = baseUrl;
    }

    async getCases() {
        return this._get('/cases');
    }

    async globalRetrieve(caseId, question, useSoap) {
        return this._post('/retrieve/global', { case_id: caseId, question, use_soap: useSoap });
    }

    async localRetrieve(caseId, question, useHybrid) {
        return this._post('/retrieve/local', { case_id: caseId, question, use_hybrid: useHybrid });
    }

    async llmAnswer(caseId, question, config) {
        return this._post('/llm/answer', { case_id: caseId, question, config });
    }

    async getEvidence(evidenceId) {
        return this._get(`/evidence/${evidenceId}`);
    }

    async computeBleu(reference, generated) {
        return this._post('/metrics/bleu', { reference, generated });
    }

    async _get(endpoint) {
        try {
            const res = await fetch(`${this.baseUrl}${endpoint}`);
            if (!res.ok) throw new Error(`API Error: ${res.statusText}`);
            return await res.json();
        } catch (e) {
            console.error(`GET ${endpoint} failed:`, e);
            throw e;
        }
    }

    async _post(endpoint, body) {
        try {
            const res = await fetch(`${this.baseUrl}${endpoint}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            if (!res.ok) throw new Error(`API Error: ${res.statusText}`);
            return await res.json();
        } catch (e) {
            console.error(`POST ${endpoint} failed:`, e);
            throw e;
        }
    }
}
