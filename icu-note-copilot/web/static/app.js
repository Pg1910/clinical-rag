document.addEventListener('DOMContentLoaded', function() {
    // Inject chat UI
    fetch('/static/report-preview.html')
        .then(res => res.text())
        .then(html => {
            document.getElementById('main-ui').innerHTML = html;
            setupChatUI();
        });
});

function setupChatUI() {
    const rowSelect = document.getElementById('row-select');
    const runBtn = document.getElementById('run-btn');
    const chatBody = document.getElementById('chat-body');

    // Fetch available rows
    fetch('/api/rows')
        .then(res => res.json())
        .then(data => {
            data.rows.forEach(row => {
                const opt = document.createElement('option');
                opt.value = row;
                opt.textContent = row;
                rowSelect.appendChild(opt);
            });
        });

    runBtn.onclick = function() {
        const rowId = rowSelect.value;
        addUserMessage(`Show me the report for case ${rowId}`);
        addBotMessage('Running SOAP pipeline...');
        fetch(`/api/case/${rowId}`)
            .then(res => res.json())
            .then(data => {
                // Clear loading
                chatBody.innerHTML = '';
                addUserMessage(`Show me the report for case ${rowId}`);
                addBotMessage(`<b>SOAP Summary</b><br><pre>${data.soap_summary}</pre>`);
                addBotMessage(`<b>Differential Diagnosis</b><br><pre>${formatDifferential(data.differential)}</pre>`);
                addBotMessage(`<b>Evidence Used</b><br><pre>${data.evidence_used.join(', ')}</pre>`);
            })
            .catch(err => {
                addBotMessage(`<span style='color:red'>Error: ${err}</span>`);
            });
    };

    function addUserMessage(text) {
        const msg = document.createElement('div');
        msg.className = 'chat-message user';
        msg.innerHTML = `<div class='chat-bubble'>${text}</div>`;
        chatBody.appendChild(msg);
        chatBody.scrollTop = chatBody.scrollHeight;
    }
    function addBotMessage(html) {
        const msg = document.createElement('div');
        msg.className = 'chat-message bot';
        msg.innerHTML = `<div class='chat-bubble'>${html}</div>`;
        chatBody.appendChild(msg);
        chatBody.scrollTop = chatBody.scrollHeight;
    }
    function formatDifferential(diff) {
        if (!Array.isArray(diff)) return '';
        return diff.map((d, i) => {
            let s = `<b>${i+1}. ${d.diagnosis}</b> (${d.confidence} confidence)`;
            if (d.support && d.support.length) {
                s += '<br>Supporting evidence:';
                s += '<ul>' + d.support.slice(0,5).map(e => `<li>${e.label}: ${e.value} [${(e.evidence_ids||[]).join(', ')}]</li>`).join('') + '</ul>';
            }
            if (d.missing && d.missing.length) {
                s += `<br><i>Missing:</i> ${d.missing.slice(0,3).join(', ')}`;
            }
            return s;
        }).join('<hr>');
    }
}
