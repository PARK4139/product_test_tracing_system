(function () {
    "use strict";

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
        const mustTag = ["S","A"].includes(s)
            ? `<span class="trk_sev_must">필수수정</span>` : "";
        return `<span class="trk_sev_wrap"><span class="trk_sev ${cls}">${s || "?"}</span>${mustTag}</span>`;
    }

    function prioBadge(prio) {
        const raw = (prio || "").toUpperCase();
        const norm = {
            CRITICAL: "S", BLOCKER: "S",
            HIGH: "A", MAJOR: "A",
            MEDIUM: "B", NORMAL: "B", MODERATE: "B",
            LOW: "C", MINOR: "C", TRIVIAL: "C",
        }[raw] || raw;
        const map = {
            S: ["#ef4444", "즉시수정"],
            A: ["#f97316", "높음"],
            B: ["#f59e0b", "보통"],
            C: ["#84cc16", "낮음"],
        };
        const [color, label] = map[norm] || ["#94a3b8", raw || "-"];
        return `<span style="display:inline-block;padding:2px 7px;border-radius:4px;font-size:0.72rem;font-weight:700;background:${color};color:#fff">${label}</span>`;
    }

    function statusBadge(st, short = false) {
        const map = {
            TESTING:          ["status-testing",  "QI Team 시험중"],
            DONE:             ["status-done",     "QI Team 완료"],
            DRAFT:            ["status-draft",    "QI Team 초안"],
            BLOCKED:          ["status-blocked",  "QI Team 시험중단판정"],
            PASSED:           ["status-passed",   "QI Team 시험합격판정"],
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

    /* ── render ──────────────────────────────────────────────────── */
    function renderTracking(data) {
        const releases = data.releases || [];
        const defects  = data.active_defects || [];

        const testing    = releases.filter(r => r.status === "TESTING" && !r.id.includes("FALLBACK"));
        const totalResults = testing.reduce((a, r) => a + r.total_results, 0);
        const totalPass    = testing.reduce((a, r) => a + r.passed,       0);
        const totalBlock   = testing.reduce((a, r) => a + r.blocked,      0);
        const totalOpen    = testing.reduce((a, r) => a + r.open_defects, 0);

        let html = "";

        /* ── 1. Active summary table ───────────────────────────── */
        if (testing.length > 0) {
            const passRate = totalResults > 0
                ? Math.round(totalPass / totalResults * 100) : 0;
            const activeNames = testing.map(r => r.alias || r.id).join(", ");

            const passColor  = passRate >= 80 ? "#22c55e" : passRate >= 50 ? "#f59e0b" : "#ef4444";
            const blockColor = totalBlock > 0 ? "#f59e0b" : "#22c55e";
            const openColor  = totalOpen  > 0 ? "#ef4444" : "#22c55e";

            // 상세 팝업용 데이터
            const detailData = {
                releases: JSON.stringify(testing.map(r => ({alias: r.alias || r.id, status: r.status, passed: r.passed, total: r.total_results, open: r.open_defects, blocked: r.blocked}))),
            };

            html += `<div class="trk_stat_table_wrap">
                <table class="trk_stat_table">
                    <thead><tr>
                        <th>통과율</th>
                        <th>블록된 항목</th>
                        <th>미결 결함</th>
                    </tr></thead>
                    <tbody><tr>
                        <td>
                            <span class="trk_stat_num trk_stat_clickable"
                                style="color:${passColor};font-weight:700"
                                data-detail="pass"
                                data-json='${detailData.releases}'>
                                ${passRate}%
                            </span>
                            <div class="trk_stat_sub">통과 ${totalPass} / 전체 ${totalResults}건</div>
                        </td>
                        <td>
                            <span class="trk_stat_num trk_stat_clickable"
                                style="color:${blockColor};font-weight:700"
                                data-detail="block"
                                data-json='${detailData.releases}'>
                                ${totalBlock}건
                            </span>
                            <div class="trk_stat_sub">진행 중 배포 합산</div>
                        </td>
                        <td>
                            <span class="trk_stat_num trk_stat_clickable"
                                style="color:${openColor};font-weight:700"
                                data-detail="defect"
                                data-json='${JSON.stringify(defects)}'>
                                ${totalOpen}건
                            </span>
                            <div class="trk_stat_sub">opened 상태 결함</div>
                        </td>
                    </tr></tbody>
                </table>
            </div>`;
        }

        /* ── 2. Release timeline ───────────────────────────────── */
        html += `<div class="trk_sub_header">배포 이력 타임라인</div>`;
        html += buildGantt(releases.filter(r => !r.id.includes("FALLBACK")));

        /* ── 3. Active defects ─────────────────────────────────── */
        html += `<div class="trk_sub_header">미결 결함 현황 (진행 중 배포)</div>`;

        if (defects.length === 0) {
            html += `<div style="color:var(--color-text-muted,#71717a);font-size:0.85rem;padding:12px 0">
                진행 중 배포에 미결 결함이 없습니다. ✅
            </div>`;
        } else {
            html += `<div class="trk_timeline_wrap"><table class="trk_defect_table">
                <thead><tr>
                    <th>결함 ID</th><th>심각도</th><th>수정 우선순위</th>
                    <th>제목</th><th>담당자</th>
                    <th>예상 해결일</th><th>등록일</th><th>시험 배포 ID</th>
                </tr></thead><tbody>`;

            defects.forEach(d => {
                const dCls = dateCls(d.expected_resolution_date);
                const expDate = d.expected_resolution_date
                    ? `<span class="${dCls}">${d.expected_resolution_date}${dCls === "trk_date_overdue" ? " ⚠️" : ""}</span>`
                    : `<span style="color:#94a3b8">미정</span>`;

                html += `<tr data-release-id="${d.release_id}" data-wifi-release-id="${d.wifi_release_id || ''}">
                    <td style="font-size:0.75rem;color:#64748b">${d.id}</td>
                    <td>${sevBadge(d.severity)}</td>
                    <td>${prioBadge(d.priority)}</td>
                    <td style="max-width:320px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"
                        title="${d.title}">${d.title}</td>
                    <td>${d.assigned_to}</td>
                    <td>${expDate}</td>
                    <td style="font-size:0.75rem;color:#64748b">${(d.created_at||"").slice(0,10)}</td>
                    <td style="font-size:0.75rem">${d.release_id}</td>
                </tr>`;
            });

            html += `</tbody></table></div>`;
        }

        return html;
    }


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
        const viewAll = localStorage.getItem('trk_view_all') === '1';
        const visibleReleases = (viewAll ? releases : releases.filter(r => r.status === 'TESTING'))
            .filter(r => !isContainer(r));

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
                data-row-id="${r.id}" ${indent > 0 ? `data-parent-id="${r.upstream_id}"` : ''}>
                <div class="gantt_label_col" style="padding-left:${10 + indentPx}px">
                    ${hasChildren ? `<button class="gantt_fold_btn" data-fold-id="${r.id}" title="접기/펼치기">▼</button>` : (indent > 0 ? '<span class="gantt_child_icon">└</span>' : '<span style="width:18px;display:inline-block"></span>')}
                    <div class="gantt_label_main">
                        <span class="gantt_label_name" title="${alias}">${alias}</span>
                        <span class="${hasChildren ? 'trk_status_readonly' : 'trk_status_editable'}" data-release-id="${r.id}" data-status="${r.status}" ${hasChildren ? 'title="자식 상태에 의해 자동 결정됨"' : ''}>${statusBadge(r.status)}</span>
                        ${total > 0 ? `<span class="gantt_meta_chip">${pctVal}%</span>` : ""}
                        ${open > 0 ? `<span class="gantt_meta_chip gantt_chip_red">결함 ${open}</span>` : ""}
                    </div>
                </div>
                <div class="gantt_chart_col">
                    <div class="gantt_today_line" style="left:${todayPct}%"></div>
                    ${barHtml}
                </div>
            </div>`;
        }

        let html = `<div class="gantt_wrap">
            <div class="gantt_header">
                <div class="gantt_label_col">시험명<div class="gantt_resize_handle" id="gantt_resize_handle"></div></div>
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

        html += `<div style="text-align:center;padding:10px">
            <button class="gantt_hidden_toggle" onclick="
                localStorage.setItem('trk_view_all', localStorage.getItem('trk_view_all') === '1' ? '0' : '1');
                document.getElementById('trk_refresh_btn').click();
            " style="font-size:0.78rem;padding:4px 12px;cursor:pointer;border:1px solid var(--color-border,#e4e4e7);border-radius:4px;background:var(--color-surface-2,#f4f4f5)">
                ${localStorage.getItem('trk_view_all') === '1' ? '전체 → 시험중' : '시험중 → 전체'}
            </button>
        </div>`;

        html += `</div>`;
        return html;
    }

    /* ── 간트 시험명 컬럼 폭 드래그 리사이즈 ──────────────────────── */
    const GANTT_COL_W_KEY = "gantt_label_col_width";
    function initGanttResize(wrap) {
        const handle = wrap.querySelector("#gantt_resize_handle");
        if (!handle) return;
        // 저장된 폭 복원
        const saved = parseInt(localStorage.getItem(GANTT_COL_W_KEY), 10);
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
                if (w) localStorage.setItem(GANTT_COL_W_KEY, w);
                document.removeEventListener("mousemove", onMove);
                document.removeEventListener("mouseup", onUp);
            }
            document.addEventListener("mousemove", onMove);
            document.addEventListener("mouseup", onUp);
        });
    }

    /* ── 컬럼 드래그 앤 드롭 + 위치 저장/복원 ──────────────────────── */
    const TRK_COL_KEY = "trk_col_order";
    function getColKey(table) {
        return table.classList.contains("trk_timeline_table") ? "timeline" : "defect";
    }
    function saveColOrder(table) {
        const key = getColKey(table);
        const order = Array.from(table.querySelectorAll("thead tr th")).map(th => th.textContent.trim());
        try { const s = JSON.parse(localStorage.getItem(TRK_COL_KEY)||"{}"); s[key]=order; localStorage.setItem(TRK_COL_KEY,JSON.stringify(s)); } catch(e) {}
    }
    function restoreColOrder(table) {
        const key = getColKey(table);
        try {
            const order = (JSON.parse(localStorage.getItem(TRK_COL_KEY)||"{}") )[key];
            if (!order || !Array.isArray(order)) return;
            order.forEach((label, targetIdx) => {
                const ths = Array.from(table.querySelectorAll("thead tr th"));
                const srcIdx = ths.findIndex(th => th.textContent.trim() === label);
                if (srcIdx === -1 || srcIdx === targetIdx) return;
                swapCols(table, srcIdx, targetIdx);
            });
        } catch(e) {}
    }
    function swapCols(table, srcIdx, dstIdx) {
        Array.from(table.querySelectorAll("tr")).forEach(row => {
            const cells = Array.from(row.children);
            if (cells.length <= Math.max(srcIdx, dstIdx)) return;
            const a = cells[srcIdx], b = cells[dstIdx];
            if (srcIdx < dstIdx) b.parentNode.insertBefore(a, b.nextSibling);
            else b.parentNode.insertBefore(a, b);
        });
    }
    function bindColumnDragDrop(root) {
        root.querySelectorAll(".trk_timeline_table, .trk_defect_table").forEach(table => {
            restoreColOrder(table);
            let dragSrcIdx = null;
            const rebind = () => {
                const ths = Array.from(table.querySelectorAll("thead tr th"));
                ths.forEach((th, idx) => {
                    th.draggable = true; th.style.cursor = "grab";
                    th.ondragstart = e => { dragSrcIdx = idx; th.style.opacity = "0.5"; e.dataTransfer.effectAllowed = "move"; };
                    th.ondragend = () => { th.style.opacity = ""; ths.forEach(t => t.classList.remove("trk_col_drag_over")); };
                    th.ondragover = e => { e.preventDefault(); ths.forEach(t => t.classList.remove("trk_col_drag_over")); th.classList.add("trk_col_drag_over"); };
                    th.ondrop = e => {
                        e.preventDefault();
                        const dstIdx = Array.from(table.querySelectorAll("thead tr th")).indexOf(th);
                        if (dragSrcIdx === null || dragSrcIdx === dstIdx) return;
                        swapCols(table, dragSrcIdx, dstIdx);
                        saveColOrder(table); dragSrcIdx = null; rebind();
                    };
                });
            };
            rebind();
        });
    }

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

    /* ── fetch & mount ───────────────────────────────────────────── */
    function loadTracking() {
        const root    = document.getElementById("trk_root");
        const loadMsg = document.getElementById("trk_loading_msg");
        if (loadMsg) loadMsg.style.display = "block";

        fetch("/admin/api/tracking/summary")
            .then(r => {
                if (!r.ok) throw new Error("HTTP " + r.status);
                return r.json();
            })
            .then(data => {
                root.innerHTML = renderTracking(data);
                bindStatusEditable(root);
                bindColumnDragDrop(root);
                initStatClickable(root);
                bindGanttFold(root);
                const ganttWrap = root.querySelector(".gantt_wrap");
                if (ganttWrap) initGanttResize(ganttWrap);
            })
            .catch(err => {
                root.innerHTML = `<div class="trk_loading" style="color:#ef4444">
                    데이터 로드 실패: ${err.message}
                </div>`;
            });
    }

    document.addEventListener("DOMContentLoaded", loadTracking);
    document.getElementById("trk_refresh_btn")
        && document.getElementById("trk_refresh_btn").addEventListener("click", loadTracking);
})();


/* ── 간트차트 접기/펼치기 ─────────────────────────────────────── */
const GANTT_FOLD_KEY = "trk_gantt_fold";
function saveFoldState(id, folded) {
    try {
        const s = JSON.parse(localStorage.getItem(GANTT_FOLD_KEY) || "{}");
        s[id] = folded;
        localStorage.setItem(GANTT_FOLD_KEY, JSON.stringify(s));
    } catch(e) {}
}
function getFoldState(id) {
    try {
        const s = JSON.parse(localStorage.getItem(GANTT_FOLD_KEY) || "{}");
        return s[id] === true; // 기본 펼침
    } catch(e) { return false; }
}
function bindGanttFold(root) {
    // 초기 상태 복원
    // 자식 행 클릭 → 해당 행 하이라이트 + 연관 테이블 rows 하이라이트
    root.querySelectorAll(".gantt_row_child").forEach(row => {
        row.addEventListener("click", e => {
            if (e.target.closest(".trk_status_editable, .trk_status_readonly")) return;
            const releaseId = row.dataset.rowId;
            const isSelected = row.classList.contains("gantt_row_selected");

            // 간트 행 하이라이트 초기화
            root.querySelectorAll(".gantt_row_child.gantt_row_selected").forEach(r => r.classList.remove("gantt_row_selected"));
            // 테이블 행 하이라이트 초기화
            document.querySelectorAll("tr.trk_row_highlighted").forEach(r => r.classList.remove("trk_row_highlighted"));

            if (!isSelected && releaseId) {
                row.classList.add("gantt_row_selected");
                // release_id 직접 매칭 또는 wifi_release_id로 상위 시험 매칭
                const parentId = row.dataset.parentId || "";
                const matched = document.querySelectorAll(
                    `tr[data-release-id="${releaseId}"], tr[data-wifi-release-id="${parentId}"]`
                );
                matched.forEach(r => r.classList.add("trk_row_highlighted"));
                if (matched.length > 0) {
                    matched[0].scrollIntoView({ behavior: "smooth", block: "nearest" });
                }
            }
        });
    });

    root.querySelectorAll(".gantt_fold_btn").forEach(btn => {
        const id = btn.dataset.foldId;
        if (getFoldState(id)) {
            _applyFold(root, id, true);
            btn.textContent = "▶";
        }
        btn.addEventListener("click", e => {
            e.stopPropagation();
            const folded = btn.textContent === "▼";
            _applyFold(root, id, folded);
            btn.textContent = folded ? "▶" : "▼";
            saveFoldState(id, folded);
        });
    });
}
function _applyFold(root, parentId, folded) {
    root.querySelectorAll(`[data-parent-id="${parentId}"]`).forEach(row => {
        row.style.display = folded ? "none" : "";
    });
}

/* ── 통계 테이블 클릭 상세 팝업 ───────────────────────────────── */
function initStatClickable(root) {
    let popup = null;
    function closePopup() { if (popup) { popup.remove(); popup = null; } }
    document.addEventListener("click", e => { if (popup && !popup.contains(e.target)) closePopup(); });

    root.querySelectorAll(".trk_stat_clickable").forEach(el => {
        el.addEventListener("click", e => {
            e.stopPropagation();
            closePopup();
            const detail = el.dataset.detail;
            const data = JSON.parse(el.dataset.json || "[]");
            let rows = "";

            if (detail === "releases") {
                rows = data.map(r => `<tr><td>${r.alias}</td><td>${statusBadge(r.status)}</td></tr>`).join("");
                rows = `<table class="trk_popup_table"><thead><tr><th>배포명</th><th>상태</th></tr></thead><tbody>${rows}</tbody></table>`;
            } else if (detail === "pass") {
                rows = data.map(r => {
                    const pct = r.total > 0 ? Math.round(r.passed/r.total*100) : 0;
                    return `<tr><td>${r.alias}</td><td>${r.passed}/${r.total}</td><td style="color:${pct>=80?'#22c55e':pct>=50?'#f59e0b':'#ef4444'};font-weight:700">${pct}%</td></tr>`;
                }).join("");
                rows = `<table class="trk_popup_table"><thead><tr><th>배포명</th><th>통과/전체</th><th>통과율</th></tr></thead><tbody>${rows}</tbody></table>`;
            } else if (detail === "block") {
                rows = data.map(r => `<tr><td>${r.alias}</td><td style="color:${r.blocked>0?'#f59e0b':'#22c55e'};font-weight:700">${r.blocked}건</td></tr>`).join("");
                rows = `<table class="trk_popup_table"><thead><tr><th>배포명</th><th>블록</th></tr></thead><tbody>${rows}</tbody></table>`;
            } else if (detail === "defect") {
                if (!data.length) {
                    rows = `<div style="padding:12px;color:#22c55e">미결 결함 없음 ✅</div>`;
                } else {
                    rows = data.map(d => `<tr><td>${sevBadge(d.severity)}</td><td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${d.title}">${d.title}</td><td>${d.assigned_to}</td></tr>`).join("");
                    rows = `<table class="trk_popup_table"><thead><tr><th>심각도</th><th>제목</th><th>담당</th></tr></thead><tbody>${rows}</tbody></table>`;
                }
            }

            const rect = el.getBoundingClientRect();
            popup = document.createElement("div");
            popup.className = "trk_stat_popup";
            popup.style.top  = (rect.bottom + window.scrollY + 6) + "px";
            popup.style.left = Math.min(rect.left, window.innerWidth - 320) + "px";
            popup.innerHTML = rows;
            document.body.appendChild(popup);
        });
    });
}
