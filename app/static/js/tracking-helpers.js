// tracking-helpers.js — badge & date helpers
/* ── helpers ─────────────────────────────────────────────────── */
function stageBadge(stage) {
    const cls = {
        RC:  "trk_stage_rc",
        TEST:"trk_stage_test",
        PVT: "trk_stage_pvt",
        DVT: "trk_stage_dvt",
    }[stage] || "trk_stage_other";
    return `<span class="trk_stage_badge ${cls}">${stage || "-"}</span>`;
}

function sevBadge(sev) {
    const raw = (sev || "").toUpperCase();
    const norm = {
        CRITICAL: "S", BLOCKER: "S",
        HIGH: "A", MAJOR: "A",
        MEDIUM: "B", NORMAL: "B", MODERATE: "B",
        LOW: "C", MINOR: "C", TRIVIAL: "C",
    }[raw] || raw;
    const s = ["S","A","B","C"].includes(norm) ? norm : norm;
    const cls = ["S","A","B","C"].includes(s) ? `trk_sev_${s}` : "trk_sev_x";
    return `<span class="trk_sev_wrap"><span class="trk_sev ${cls}">${s || "?"}</span></span>`;
}

function prioBadge(prio, sev) {
    const raw = (prio || "").toUpperCase();
    const norm = {
        CRITICAL: "S", BLOCKER: "S",
        HIGH: "A", MAJOR: "A",
        MEDIUM: "B", NORMAL: "B", MODERATE: "B",
        LOW: "C", MINOR: "C", TRIVIAL: "C",
    }[raw] || raw;
    const map = {
        S: ["#ef4444", "선순위"],
        A: ["#f97316", "선순위"],
        B: ["#f59e0b", "차순위"],
        C: ["#84cc16", "후순위"],
    };
    const [color, label] = map[norm] || ["#94a3b8", raw || "-"];
    const sevNorm = (sev || "").toUpperCase();
    const isMust = ["S","A"].includes(sevNorm);
    if (isMust) return `<span class="trk_sev_must">필수수정</span>`;
    return `<span style="display:inline-block;padding:2px 7px;border-radius:4px;font-size:0.72rem;font-weight:700;background:${color};color:#fff">${label}</span>`;
}

function statusBadge(st, short = false) {
    const map = {
        TESTING:          ["status-testing",  "QI Team 시험중"],
        DONE:             ["status-done",     "QI Team 완료"],
        DRAFT:            ["status-draft",    "QI Team 초안"],
        BLOCKED:          ["status-blocked",  "QI Team 시험중단판정"],
        FAILED:           ["status-failed",   "QI Team 시험실패판정"],
        PASSED:           ["status-passed",   "QI Team 시험합격판정"],
        SKIPPED:          ["status-skipped",  "QI Team 시험제외"],
        CANCELLED:        ["status-cancelled", "QI Team 시험취소"],
        QI_TEAM_RELEASED: ["status-approved",  "QI Team 시험합격판정"],
        QI_TEAM_REVIEWED: ["status-reviewed",  "QI Team 시험완료"],
        APPROVED:         ["status-approved",  "QI Team 시험합격판정"],
        TBD:      ["status-tbd",       "TBD"],
        TODO:     ["status-todo",      "TODO"],
    };
    const [cls, label] = map[st] || ["status-draft", st || "-"];
    const displayLabel = short ? label.replace(/^QI Team /, "") : label;
    return `<span class="status_badge ${cls}">${displayLabel}</span>`;
}

function normalizeDate(raw) {
    if (!raw || raw === "None" || raw === "?") return "-";
    // "2026 04 22" → "2026-04-22"
    // "2026_05_26_0000" → "2026-05-26"
    const s = raw.trim().replace(/_/g, "-").replace(/\s+/g, "-");
    // YYYY-MM-DD 앞 10자리만
    const m = s.match(/(\d{4}-\d{2}-\d{2})/);
    return m ? m[1] : s.slice(0, 10);
}

    function dateCls(dateStr) {
    if (!dateStr) return "";
    const today = new Date(); today.setHours(0,0,0,0);
    const d = new Date(dateStr); d.setHours(0,0,0,0);
    const diff = (d - today) / 86400000;
    if (diff < 0) return "trk_date_overdue";
    if (diff <= 3) return "trk_date_soon";
    return "trk_date_ok";
}

function extractTopo(releaseId) {
    const m = (releaseId || "").match(/(\d+AP[_A-Za-z0-9]*|UNCLASSIFIED)$/);
    return m ? m[1] : (releaseId || "").replace("TEST_RELEASE-","");
}
