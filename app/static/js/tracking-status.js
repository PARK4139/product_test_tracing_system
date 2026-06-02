// tracking-status.js — inline status dropdown + stat summary clickable
/* ── 상태 인라인 드롭다운 ───────────────────────────────────────── */
const STATUS_OPTIONS = [
    { value: "TESTING",          label: "QI Team 시험중"   },
    { value: "QI_TEAM_RELEASED", label: "QI Team 시험합격판정" },
    { value: "QI_TEAM_REVIEWED", label: "QI Team 시험완료" },
    { value: "BLOCKED",          label: "QI Team 시험중단판정"   },
    { value: "DRAFT",            label: "QI Team 초안"     },
];
let _dropdown = null;
function closeDropdown() { if (_dropdown) { _dropdown.remove(); _dropdown = null; } }
document.addEventListener("click", e => { if (_dropdown && !_dropdown.contains(e.target)) closeDropdown(); });
function openStatusDropdown(trigger, releaseId, currentStatus) {
    closeDropdown();
    const rect = trigger.getBoundingClientRect();
    const dd = document.createElement("div");
    dd.className = "trk_status_dropdown";
    dd.style.top  = (rect.bottom + window.scrollY + 4) + "px";
    dd.style.left = rect.left + "px";
    STATUS_OPTIONS.forEach(opt => {
        const item = document.createElement("div");
        item.className = "trk_status_dropdown_item" + (opt.value === currentStatus ? " active" : "");
        item.innerHTML = statusBadge(opt.value) + ` <span>${opt.label}</span>`;
        item.addEventListener("click", async e => {
            e.stopPropagation(); closeDropdown();
            if (opt.value === currentStatus) return;
            try {
                const res = await fetch(`/admin/api/release/${encodeURIComponent(releaseId)}/status`, { method:"PATCH", headers:{"Content-Type":"application/json"}, body:JSON.stringify({status:opt.value}) });
                if (!res.ok) throw new Error("HTTP " + res.status);
                trigger.dataset.status = opt.value;
                trigger.innerHTML = statusBadge(opt.value);
            } catch(err) { alert("상태 변경 실패: " + err.message); }
        });
        dd.appendChild(item);
    });
    document.body.appendChild(dd); _dropdown = dd;
}
function bindStatusEditable(root) {
    root.querySelectorAll(".trk_status_editable").forEach(el => {
        el.addEventListener("click", e => { e.stopPropagation(); openStatusDropdown(el, el.dataset.releaseId, el.dataset.status); });
    });
}

function initStatClickable(root) {
    let _popup = null;
    root.querySelectorAll(".trk_stat_clickable").forEach(el => {
        el.addEventListener("click", e => {
            e.stopPropagation();
            if (_popup) { _popup.remove(); _popup = null; return; }
            const detail = el.dataset.detail;
            let rows = "";
            try {
                const data = JSON.parse(el.dataset.json || "[]");
                if (detail === "pass") {
                    rows = data.map(r => `<tr><td>${r.alias}</td><td>${r.passed}/${r.total}</td><td style="color:${r.total>0&&r.passed/r.total>=0.8?'#22c55e':'#f59e0b'};font-weight:700">${r.total>0?Math.round(r.passed/r.total*100):0}%</td></tr>`).join("");
                    rows = `<table class="trk_popup_table"><thead><tr><th>배포명</th><th>통과/전체</th><th>통과율</th></tr></thead><tbody>${rows}</tbody></table>`;
                } else if (detail === "block") {
                    rows = data.map(r => `<tr><td>${r.alias}</td><td style="color:${r.blocked>0?'#f59e0b':'#22c55e'};font-weight:700">${r.blocked}건</td></tr>`).join("");
                    rows = `<table class="trk_popup_table"><thead><tr><th>배포명</th><th>블록</th></tr></thead><tbody>${rows}</tbody></table>`;
                } else if (detail === "defect") {
                    rows = data.map(r => `<tr><td>${r.id}</td><td>${r.title}</td><td>${r.severity}</td></tr>`).join("");
                    rows = `<table class="trk_popup_table"><thead><tr><th>결함 ID</th><th>제목</th><th>심각도</th></tr></thead><tbody>${rows}</tbody></table>`;
                }
            } catch(err) { rows = "데이터 없음"; }
            const popup = document.createElement("div");
            popup.style.cssText = "position:fixed;z-index:9999;background:#fff;border:1px solid #e4e4e7;border-radius:8px;box-shadow:0 4px 16px rgba(0,0,0,0.12);padding:12px;max-width:480px;max-height:320px;overflow:auto;font-size:0.8rem";
            popup.innerHTML = rows;
            const rect = el.getBoundingClientRect();
            popup.style.top  = (rect.bottom + 6) + "px";
            popup.style.left = Math.min(rect.left, window.innerWidth - 490) + "px";
            document.body.appendChild(popup);
            _popup = popup;
            const close = ev => { if (!popup.contains(ev.target) && ev.target !== el) { popup.remove(); _popup = null; document.removeEventListener("click", close); } };
            setTimeout(() => document.addEventListener("click", close), 0);
        });
    });
}

