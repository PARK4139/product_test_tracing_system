// tracking-gantt-chart.js — buildGantt (bar rendering)
// tracking-gantt.js — buildGantt, resize, deadline drag, fold
/* ── 간트차트 ────────────────────────────────────────────────── */
function buildGantt(releases) {
    if (!releases.length) return `<div class="trk_empty">데이터 없음</div>`;

    const STATUS_COLOR = {
        TESTING:          "#3b82f6",
        QI_TEAM_RELEASED: "#22c55e",
        QI_TEAM_REVIEWED: "#8b5cf6",
        APPROVED:         "#22c55e",
        BLOCKED:          "#ef4444",
        DRAFT:            "#94a3b8",
    };

    function toDate(raw) {
        const s = normalizeDate(raw);
        return s !== "-" ? new Date(s) : null;
    }

    const today = new Date(); today.setHours(0,0,0,0);

    // 부모 / 자식 분리 (upstream_id가 다른 배포 ID면 자식)
    // 뷰 필터: 기본은 시험중(TESTING)만, 토글 시 전체
    // TEST_REPORT_*, TBD_REPORT_* 는 간트에서 항상 숨김 (보고서 컨테이너)
    const isContainer = r => r.id.includes("TEST_REPORT_") || r.id.includes("TBD_REPORT_");
    // 뷰 모드: 0=전체, 1=시험중(TESTING+BLOCKED), 2=중단판정(BLOCKED만)
    const viewMode = parseInt(localStorage.getItem('trk_view_mode') || '0', 10);
    const IN_PROGRESS = new Set(['TESTING','BLOCKED']);
    const BLOCKED_ONLY = new Set(['BLOCKED']);
    const visibleReleases = (viewMode === 1
        ? releases.filter(r => IN_PROGRESS.has(r.status))
        : viewMode === 2
        ? releases.filter(r => BLOCKED_ONLY.has(r.status))
        : releases
    ).filter(r => !isContainer(r) && r.visible !== false);

    const releaseIds = new Set(visibleReleases.map(r => r.id));
    const parents = visibleReleases.filter(r => !releaseIds.has(r.upstream_id));
    const childrenMap = {};
    visibleReleases.filter(r => releaseIds.has(r.upstream_id)).forEach(r => {
        if (!childrenMap[r.upstream_id]) childrenMap[r.upstream_id] = [];
        childrenMap[r.upstream_id].push(r);
    });

    // 날짜 범위
    let minD = null, maxD = null;
    releases.forEach(r => {
        const sd = toDate(r.start_date), ed = toDate(r.end_date);
        if (sd && (!minD || sd < minD)) minD = sd;
        if (ed && (!maxD || ed > maxD)) maxD = ed;
    });
    if (!minD) minD = new Date(today.getTime() - 30*86400000);
    if (!maxD) maxD = new Date(today.getTime() + 14*86400000);
    minD = new Date(minD.getTime() - 3*86400000);
    maxD = new Date(maxD.getTime() + 7*86400000);
    const totalMs = maxD - minD;

    function pct(d) { return Math.max(0, Math.min(100, (d - minD) / totalMs * 100)); }
    const todayPct = pct(today);

    function monthLabels() {
        let html = "";
        let d = new Date(minD.getFullYear(), minD.getMonth(), 1);
        while (d <= maxD) {
            const left = pct(d);
            html += `<div class="gantt_month_label" style="left:${left}%">${d.getFullYear()}.${String(d.getMonth()+1).padStart(2,"0")}</div>`;
            d = new Date(d.getFullYear(), d.getMonth()+1, 1);
        }
        return html;
    }

    function renderBar(r, indent) {
        const color   = STATUS_COLOR[r.status] || "#94a3b8";
        const alias   = (r.alias && r.alias !== r.upstream_id) ? r.alias : (r.upstream_system || r.id);
        const sd      = toDate(r.start_date);
        const ed      = toDate(r.end_date) || today;
        const total   = r.total_results || 0;
        const passed  = r.passed || 0;
        const pctVal  = total > 0 ? Math.round(passed/total*100) : 0;
        const open    = r.open_defects || 0;

        const isCompleted = ["APPROVED","QI_TEAM_RELEASED","DONE"].includes(r.status);
        const sdStr = normalizeDate(r.start_date);
        const edStr = normalizeDate(r.end_date);
        const endLabel = edStr !== "-"
            ? (isCompleted ? `실종료: ${edStr}` : `예상종료: ${edStr}`)
            : (isCompleted ? "종료" : "진행중");
        const barTitle = r.workday
            ? `${r.workday} (${sdStr !== "-" ? sdStr : "?"} ~ ${endLabel})`
            : `${sdStr !== "-" ? sdStr : "?"} ~ ${endLabel}`;
        const barDisplayLabel = r.workday
            ? `${r.workday} (${sdStr !== "-" ? sdStr : "?"} ~ ${edStr !== "-" ? edStr : "?"})`
            : "";

        let barHtml = "";
        if (indent === 0) {
            // 부모 행만 간트 바 표시
            if (sd) {
                const left  = pct(sd);
                const width = Math.max(0.5, pct(ed) - left);
                barHtml = `<div class="gantt_bar" style="left:${left}%;width:${width}%;background:${color}"
                    title="${barTitle}">
                    <span class="gantt_bar_label">${barDisplayLabel}</span>
                </div>`;
            } else {
                barHtml = `<div class="gantt_bar gantt_bar_nodate" style="left:${todayPct}%;width:1%" title="${barTitle}"></div>`;
            }
        }
        // 자식 행은 바 없음 — 추후 run 기록 기반으로 계산 예정

        const indentPx = indent * 20;
        const hasChildren = indent === 0 && (childrenMap[r.id] || []).length > 0;
        return `<div class="gantt_row${r.status === 'TESTING' ? ' gantt_row_active' : ''}${indent > 0 ? ' gantt_row_child' : ''}"
            data-row-id="${r.id}" data-status="${r.status}" ${indent > 0 ? `data-parent-id="${r.upstream_id}"` : ''}>
            <div class="gantt_label_col" style="padding-left:${10 + indentPx}px">
                ${hasChildren ? `<button class="gantt_fold_btn" data-fold-id="${r.id}" title="접기/펼치기">▼</button>` : (indent > 0 ? '<span class="gantt_child_icon">└</span>' : '<span style="width:18px;display:inline-block"></span>')}
                <div class="gantt_label_main">
                    <span class="gantt_label_name" title="${alias}">${alias}</span>
                    ${total > 0 ? `<span class="gantt_meta_chip">${pctVal}%</span>` : ""}
                    ${open > 0 ? `<span class="gantt_meta_chip gantt_chip_red">결함 ${open}</span>` : ""}
                </div>
            </div>
            <div class="gantt_status_col">
                <span class="${hasChildren ? 'trk_status_readonly' : 'trk_status_editable'}" data-release-id="${r.id}" data-status="${r.status}" ${hasChildren ? 'title="자식 상태에 의해 자동 결정됨"' : ''}>${statusBadge(r.status)}</span>
            </div>
            <div class="gantt_chart_col">
                <div class="gantt_today_line" style="left:${todayPct}%"></div>
                ${barHtml}
            </div>
        </div>`;
    }

    let html = `<div class="gantt_wrap" data-min-date="${minD.toISOString()}" data-total-ms="${totalMs}">
        <div class="gantt_header">
            <div class="gantt_label_col">시험명<div class="gantt_resize_handle" id="gantt_resize_handle"></div></div>
            <div class="gantt_status_col" style="font-weight:600;font-size:0.8rem;border-right:1px solid var(--color-border,#e4e4e7)">상태</div>
            <div class="gantt_chart_col" style="position:relative">
                ${monthLabels()}
                <div class="gantt_today_line" style="left:${todayPct}%"></div>
            </div>
        </div>`;

    // 장비 나열 순서: HRK > HTR > HLM > HDR > HDC > HIIS
    const DEVICE_ORDER = ["HRK", "HTR", "HLM", "HDR", "HDC", "HIIS"];
    function deviceSortKey(id) {
        const upper = id.toUpperCase();
        const idx = DEVICE_ORDER.findIndex(d => upper.includes(d));
        return idx === -1 ? 99 : idx;
    }

    parents.forEach(p => {
        html += renderBar(p, 0);
        const children = (childrenMap[p.id] || []).slice().sort((a, b) => deviceSortKey(a.id) - deviceSortKey(b.id));
        children.forEach(c => {
            html += renderBar(c, 1);
        });
    });


    html += `</div>`;
    return html;
}

/* ── 간트 시험명 컬럼 폭 드래그 리사이즈 ──────────────────────── */
const GANTT_COL_W_KEY = "gantt_label_col_width";
