/**
 * Centralized State Store (Pub/Sub)
 */
export class Store {
    constructor() {
        this.state = {
            cases: [],
            selectedCase: localStorage.getItem('selectedCase') || '',
            userQuestion: '',
            isLoading: false,
            globalTrace: null,
            localTrace: null,
            evidence: null,
            latestReport: null,
            metrics: null,
            reportsCache: {}
        };
        this.listeners = new Map();
    }

    /**
     * Subscribe to state changes for a specific key
     * @param {string} key - State key
     * @param {function} callback - Function to call on change
     */
    subscribe(key, callback) {
        if (!this.listeners.has(key)) {
            this.listeners.set(key, new Set());
        }
        this.listeners.get(key).add(callback);
        // Initial call
        callback(this.state[key]);

        return () => this.listeners.get(key).delete(callback);
    }

    /**
     * Update state and notify listeners
     * @param {string} key 
     * @param {any} value 
     */
    setState(key, value) {
        if (this.state[key] === value) return;

        this.state[key] = value;

        if (key === 'selectedCase') {
            localStorage.setItem('selectedCase', value);
        }

        if (this.listeners.has(key)) {
            this.listeners.get(key).forEach(cb => cb(value));
        }
    }

    getState(key) {
        return this.state[key];
    }
}
