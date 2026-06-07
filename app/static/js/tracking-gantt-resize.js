// tracking-gantt-resize.js -- column resize + deadline drag
function initGanttResize(wrap) {
    const handle = wrap.querySelector("#gantt_resize_handle");
    if (!handle) return;
    const saved = parseInt(uiStateGetItem(GANTT_COL_W_KEY), 10);
    if (saved && saved > 80) wrap.style.setProperty("--gantt-label-w", saved + "px");

    let startX, startW;
    handle.addEventListener("mousedown", e => {
        e.preventDefault();
        startX = e.clientX;
        startW = parseInt(getComputedStyle(wrap).getPropertyValue("--gantt-label-w")) || 260;
        handle.classList.add("dragging");
        document.body.style.cursor = "col-resize";
        document.body.style.userSelect = "none";

        function onMove(e) {
            const w = Math.max(80, Math.min(600, startW + (e.clientX - startX)));
            wrap.style.setProperty("--gantt-label-w", w + "px");
        }
        function onUp() {
            handle.classList.remove("dragging");
            document.body.style.cursor = "";
            document.body.style.userSelect = "";
            const w = parseInt(wrap.style.getPropertyValue("--gantt-label-w"), 10);
            if (w) uiStateSetItem(GANTT_COL_W_KEY, w);
            document.removeEventListener("mousemove", onMove);
            document.removeEventListener("mouseup", onUp);
        }
        document.addEventListener("mousemove", onMove);
        document.addEventListener("mouseup", onUp);
    });
}

const DEADLINE_KEY = "gantt_deadline_pct";

function calcDateFromPct(chartCol, p) {
    const wrap = chartCol.closest(".gantt_wrap");
    const minDateRaw = wrap ? wrap.dataset.minDate : "";
    const totalMs = wrap ? parseFloat(wrap.dataset.totalMs || "0") : 0;
    const minD = minDateRaw ? new Date(minDateRaw) : null;
    if (!minD || Number.isNaN(minD.getTime()) || !totalMs) return "";
    const d = new Date(minD.getTime() + (p / 100) * totalMs);
    return isNaN(d) ? "" : d.toLocaleDateString('ko-KR', {year:'numeric', month:'2-digit', day:'2-digit'});
}

function initDeadlineDrag(wrap) {
    const line = wrap.querySelector("#gantt_deadline_line");
    if (!line) return;
    const chartCol = wrap.querySelector(".gantt_header .gantt_chart_col");
    if (!chartCol) return;

    line.addEventListener("mousedown", e => {
        e.preventDefault();
        const onMove = mv => {
            const rect = chartCol.getBoundingClientRect();
            const p = Math.max(0, Math.min(100, (mv.clientX - rect.left) / rect.width * 100));
            const dateStr = calcDateFromPct(chartCol, p);
            line.style.left = p + "%";
            line.classList.remove("gantt_deadline_hidden");
            const lbl = line.querySelector(".gantt_deadline_label");
            if (lbl) lbl.innerHTML = "deadline<br>" + dateStr;
            uiStateSetItem(DEADLINE_KEY, JSON.stringify({pct: p, date: dateStr}));
        };
        const onUp = () => {
            document.removeEventListener("mousemove", onMove);
            document.removeEventListener("mouseup", onUp);
        };
        document.addEventListener("mousemove", onMove);
        document.addEventListener("mouseup", onUp);
    });
}

const GANTT_FOLD_KEY = "trk_gantt_fold";
