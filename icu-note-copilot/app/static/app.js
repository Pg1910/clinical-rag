// --- UI helpers ---
function $(id) { return document.getElementById(id); }
function showTab(tab) {
    ["global-trace","local-trace","evidence-viewer","metrics"].forEach(t => {
        $(t).style.display = (t === tab+"-trace" || t === tab) ? "block" : "none";
    });
}
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.onclick = () => showTab(btn.dataset.tab);
});

// --- Load cases ---
fetch('/api/cases').then(r => r.json()).then(data => {
    let sel = $("case-selector");
    data.cases.forEach(c => {
        let opt = document.createElement("option");
        opt.value = c.case_id; opt.textContent = c.label;
        sel.appendChild(opt);
    });
});

// --- Chat UI ---
function appendChat(role, msg) {
    let div = document.createElement("div");
    div.className = "chat-bubble " + role;
    div.innerHTML = msg;
    $("chat-ui").appendChild(div);
}

// --- Retrieval buttons ---
$("btn-global").onclick = () => {
    let case_id = $("case-selector").value;
    let question = $("user-question").value;
    appendChat("user", question);
    fetch('/api/retrieve/global', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({case_id, question})
    }).then(r => r.json()).then(data => {
        let msg = `<b>Global Retrieval:</b><br>` + JSON.stringify(data.soap_queries) + `<br>`;
        appendChat("assistant", msg);
        renderGlobalTrace(data);
    });
};
$("btn-local").onclick = () => {
    let case_id = $("case-selector").value;
    let question = $("user-question").value;
    appendChat("user", question);
    fetch('/api/retrieve/local', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({case_id, question})
    }).then(r => r.json()).then(data => {
        let msg = `<b>Local Retrieval:</b><br>` + JSON.stringify(data.derived_queries) + `<br>`;
        appendChat("assistant", msg);
        renderLocalTrace(data);
    });
};
$("btn-full").onclick = () => {
    let case_id = $("case-selector").value;
    let question = $("user-question").value;
    appendChat("user", question);
    fetch('/api/llm/answer', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({case_id, question, use_global:true, use_local:true})
    }).then(r => r.json()).then(data => {
        let msg = `<b>LLM Report:</b><br>` + (data.assistant_message || "") + `<br>`;
        appendChat("assistant", msg);
        if(data.report && data.report.summary) {
            msg += `<ul>` + data.report.summary.map(b => `<li>${b}</li>`).join("") + `</ul>`;
        }
        renderGlobalTrace(data.trace.global);
        renderLocalTrace(data.trace.local);
        window.latestReport = data.report;
    });
};
$("btn-latest").onclick = () => {
    // Load latest report
    fetch('/api/llm/answer', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({case_id: "latest", question: "Summarize case", use_global:true, use_local:true})
    }).then(r => r.json()).then(data => {
        appendChat("assistant", `<b>Latest Report:</b><br>` + (data.assistant_message || ""));
        window.latestReport = data.report;
    });
};
$("btn-export").onclick = () => {
    if(window.latestReport) {
        let blob = new Blob([JSON.stringify(window.latestReport, null, 2)], {type:'application/json'});
        let a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'report.json';
        a.click();
    }
};

// --- Evidence ID click ---
function renderGlobalTrace(data) {
    let el = $("global-trace");
    el.innerHTML = "<h3>Global Retrieval Trace</h3>";
    if(!data || !data.results) return;
    for(let s of ["S","O","A","P"]) {
        el.innerHTML += `<b>${s}:</b><ul>`;
        (data.results[s]||[]).forEach(e => {
            el.innerHTML += `<li>${e.evidence_id} <button onclick="viewEvidence('${e.evidence_id}')">View</button> Score: ${e.hybrid||""}</li>`;
        });
        el.innerHTML += `</ul>`;
    }
}
function renderLocalTrace(data) {
    let el = $("local-trace");
    el.innerHTML = "<h3>Local Retrieval Trace</h3>";
    if(!data || !data.results) return;
    for(let s of ["S","O","A","P"]) {
        el.innerHTML += `<b>${s}:</b><ul>`;
        (data.results[s]||[]).forEach(e => {
            el.innerHTML += `<li>${e.evidence_id} <button onclick="viewEvidence('${e.evidence_id}')">View</button> Score: ${e.hybrid||""}</li>`;
        });
        el.innerHTML += `</ul>`;
    }
}
window.viewEvidence = function(evidence_id) {
    fetch(`/api/evidence/${evidence_id}`).then(r => r.json()).then(data => {
        let el = $("evidence-viewer");
        el.innerHTML = `<h3>Evidence ${evidence_id}</h3><pre>${data.raw_text}</pre><div>Meta: ${JSON.stringify(data.meta||{})}</div>`;
        showTab("evidence");
    });
};

// --- BLEU ---
$("btn-bleu").onclick = () => {
    let generated = window.latestReport ? window.latestReport.summary.join(" ") : "";
    let reference = $("reference-summary").value;
    fetch('/api/metrics/bleu', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({generated, reference})
    }).then(r => r.json()).then(data => {
        $("bleu-results").innerHTML = `BLEU-1: ${data.bleu1.toFixed(2)} BLEU-2: ${data.bleu2.toFixed(2)} BLEU-3: ${data.bleu3.toFixed(2)} BLEU-4: ${data.bleu4.toFixed(2)} Cumulative: ${data.bleu.toFixed(2)}`;
    });
};
