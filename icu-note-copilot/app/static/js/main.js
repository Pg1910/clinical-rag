import { ApiClient } from './modules/api.js';
import { Store } from './modules/store.js';
import { ControlsComponent } from './components/ControlsComponent.js';
import { ChatComponent } from './components/ChatComponent.js';
import { TraceComponent } from './components/TraceComponent.js';

document.addEventListener('DOMContentLoaded', () => {
    // Initialize Core
    const api = new ApiClient();
    const store = new Store();

    // Initialize Components
    const controls = new ControlsComponent(store, api);
    const chat = new ChatComponent(store);
    const trace = new TraceComponent(store, api);

    console.log("Clinical RAG System (Modular) Initialized");
});
