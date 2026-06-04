// tracking-gantt-chart.js — buildGantt (bar rendering)
// tracking-gantt.js — buildGantt, resize, deadline drag, fold
/* ── 간트차트 ────────────────────────────────────────────────── */
function buildGantt(releases, runs) {
    if (!releases.length) return `<div class="trk_empty">데이터 없음</div>`;
    runs = runs || [];

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
    const baseReleases = releases.filter(r => !isContainer(r) && r.visible !== false);

    // 필터 적용: 자식이 통과하면 부모도 반드시 포함
    let visibleReleases;
    if (viewMode === 0) {
        visibleReleases = baseReleases;
    } else {
        const filterSet = viewMode === 2 ? BLOCKED_ONLY : IN_PROGRESS;
        const passIds = new Set();
        // 1단계: 필터 통과하는 release 수집
        baseReleases.forEach(r => { if (filterSet.has(r.status)) passIds.add(r.id); });
        // 2단계: 자식이 통과하면 부모(upstream)도 포함
        baseReleases.forEach(r => {
            if (passIds.has(r.id) && r.upstream_id) passIds.add(r.upstream_id);
        });
        visibleReleases = baseReleases.filter(r => passIds.has(r.id));
    }

    const releaseIds = new Set(visibleReleases.map(r => r.id));
    const parents = visibleReleases.filter(r => !releaseIds.has(r.upstream_id));
    const childrenMap = {};
    visibleReleases.filter(r => releaseIds.has(r.upstream_id)).forEach(r => {
        if (!childrenMap[r.upstream_id]) childrenMap[r.upstream_id] = [];
        childrenMap[r.upstream_id].push(r);
    });
    const runsByParent = {};
    runs.forEach(run => {
        const parentId = run.parent_release_id || run.release_id || "";
        if (!parentId) return;
        if (!runsByParent[parentId]) runsByParent[parentId] = [];
        runsByParent[parentId].push(run);
    });

    // 날짜 범위
    let minD = null, maxD = null;
    releases.forEach(r => {
        const sd = toDate(r.start_date), ed = toDate(r.end_date);
        if (sd && (!minD || sd < minD)) minD = sd;
        if (ed && (!maxD || ed > maxD)) maxD = ed;
    });
    runs.forEach(r => {
        const sd = toDate(r.started_at), ed = toDate(r.finished_at);
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

    function renderBar(r, indent, parentIdOverride) {
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
        let deltaLabel = "";
        if (sd && ed) {
            const diffMs = ed - sd;
            const diffDays = Math.round(diffMs / 86400000);
            deltaLabel = diffDays + "d";
        }
        const barDisplayLabel = r.workday
            ? `${r.workday} (${sdStr !== "-" ? sdStr : "?"} ~ ${edStr !== "-" ? edStr : "?"})`
            : (sd && ed ? `${deltaLabel} (${sdStr} ~ ${edStr})` : "");

        let barHtml = "";
        if (indent === 0 || r.stage === 'run_session') {
            // 라운드/세션 행에 간트 바 표시
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

        const indentPx = indent * 18;
        // indent: 0=round, 1=test item/session, 2=run/topology child
        const isRound   = indent === 0;
        const isSession = r.stage === 'run_session';
        const isTopo    = !isRound && !isSession;
        const hasChildren = ((childrenMap[r.id] || []).length > 0) || ((runsByParent[r.id] || []).length > 0);
        const rowClass = isRound ? "gantt_row gantt_row_round"
            : isSession ? "gantt_row gantt_row_session"
            : "gantt_row gantt_row_child";
        const dataParentId = parentIdOverride || r.upstream_id;
        const dataParent = !isRound ? `data-parent-id="${dataParentId}"` : "";
        const icon = hasChildren
            ? `<button class="gantt_fold_btn" data-fold-id="${r.id}" title="접기/펼치기">▼</button>`
            : isTopo ? '<span class="gantt_child_icon">└</span>'
            : isSession ? '<span class="gantt_child_icon" style="opacity:0.4">└</span>'
            : '<span style="width:18px;display:inline-block"></span>';
        return `<div class="${rowClass}${r.status === 'TESTING' ? ' gantt_row_active' : ''}"
            data-row-id="${r.id}" data-status="${r.status}" ${dataParent}>
            <div class="gantt_label_col" style="padding-left:${8 + indentPx}px">
                ${icon}
                <div class="gantt_label_main">
                    <span class="gantt_label_name" title="${r.id}">${alias}</span>
                    ${total > 0 ? `<span class="gantt_meta_chip">${pctVal}%</span>` : ""}
                    ${open > 0 ? `<span class="gantt_meta_chip gantt_chip_red">결함 ${open}</span>` : ""}
                </div>
            </div>
            <div class="gantt_status_col">
                <span class="trk_status_readonly" data-release-id="${r.id}" data-status="${r.status}" title="하위 시험 결과로부터 자동 결정">${statusBadge(r.status)}</span>
            </div>
            <div class="gantt_chart_col">
                <div class="gantt_today_line" style="left:${todayPct}%"></div>
                ${barHtml}
            </div>
        </div>`;
    }

    function renderRunRow(run, indent, parentId) {
        const color = STATUS_COLOR[run.status] || "#64748b";
        const sd = toDate(run.started_at);
        const ed = toDate(run.finished_at) || today;
        const total = run.total_results || 0;
        const passed = run.passed || 0;
        const pctVal = total > 0 ? Math.round(passed / total * 100) : 0;
        const sdStr = normalizeDate(run.started_at);
        const edStr = normalizeDate(run.finished_at);
        const title = `${run.id} (${sdStr !== "-" ? sdStr : "?"} ~ ${edStr !== "-" ? edStr : "?"})`;
        let barHtml = "";
        if (sd) {
            const left = pct(sd);
            const width = Math.max(0.5, pct(ed) - left);
            barHtml = `<div class="gantt_bar gantt_run_bar" style="left:${left}%;width:${width}%;background:${color}" title="${title}">
                <span class="gantt_bar_label">${sdStr}${edStr !== "-" ? " ~ " + edStr : ""}</span>
            </div>`;
        } else {
            barHtml = `<div class="gantt_bar gantt_bar_nodate gantt_run_bar" style="left:${todayPct}%;width:1%" title="${title}"></div>`;
        }
        return `<div class="gantt_row gantt_row_run${run.status === 'TESTING' ? ' gantt_row_active' : ''}"
            data-row-id="${run.id}" data-parent-id="${parentId}" data-status="${run.status}" data-run-id="${run.id}">
            <div class="gantt_label_col" style="padding-left:${8 + indent * 18}px">
                <span class="gantt_child_icon">RUN</span>
                <div class="gantt_label_main">
                    <span class="gantt_label_name" title="${run.id}">${run.id}</span>
                    ${total > 0 ? `<span class="gantt_meta_chip">${pctVal}%</span>` : ""}
                    ${(run.blocked || 0) > 0 ? `<span class="gantt_meta_chip gantt_chip_red">blocked ${run.blocked}</span>` : ""}
                </div>
            </div>
            <div class="gantt_status_col">${statusBadge(run.status)}</div>
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
        const sessions = (childrenMap[p.id] || []).slice().sort((a, b) => (a.sequence||0) - (b.sequence||0));
        if (sessions.length === 0) return;
        // RunSession이 있으면 3단계, 없으면 직접 topology(구 구조 호환)
        const firstStage = sessions[0] && sessions[0].stage;
        if (firstStage === 'run_session') {
            sessions.forEach(sess => {
                const topos = (childrenMap[sess.id] || []).slice().sort((a, b) => deviceSortKey(a.id) - deviceSortKey(b.id));
                topos.forEach(t => {
                    html += renderBar(t, 1, p.id);
                    (runsByParent[t.id] || []).slice().sort((a, b) => String(a.started_at || "").localeCompare(String(b.started_at || ""))).forEach(run => {
                        html += renderRunRow(run, 2, t.id);
                    });
                });
            });
        } else {
            // 구 구조: topology 직접 표시
            sessions.forEach(c => {
                html += renderBar(c, 1);
                (runsByParent[c.id] || []).slice().sort((a, b) => String(a.started_at || "").localeCompare(String(b.started_at || ""))).forEach(run => {
                    html += renderRunRow(run, 2, c.id);
                });
            });
        }
    });


    html += `</div>`;
    return html;
}

/* ── 간트 시험명 컬럼 폭 드래그 리사이즈 ──────────────────────── */
const GANTT_COL_W_KEY = "gantt_label_col_width";
