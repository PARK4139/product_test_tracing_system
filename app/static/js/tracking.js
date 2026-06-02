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
            S: ["#ef4444", "즉시수정"],
            A: ["#f97316", "높음"],
            B: ["#f59e0b", "보통"],
            C: ["#84cc16", "낮음"],
        };
        const [color, label] = map[norm] || ["#94a3b8", raw || "-"];
        const sevNorm = (sev || "").toUpperCase();
        const mustTag = ["S","A"].includes(sevNorm)
            ? `<span class="trk_sev_must">필수수정</span> ` : "";
        return `${mustTag}<span style="display:inline-block;padding:2px 7px;border-radius:4px;font-size:0.72rem;font-weight:700;background:${color};color:#fff">${label}</span>`;
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
            html += `<div class="trk_timeline_wrap trk_defect_wrap"><table class="trk_defect_table">
                <colgroup>
                    <col class="trk_col_resizable" style="width:130px">
                    <col class="trk_col_resizable" style="width:60px">
                    <col class="trk_col_resizable" style="width:110px">
                    <col class="trk_col_resizable" style="width:260px">
                    <col class="trk_col_resizable" style="width:80px">
                    <col class="trk_col_resizable" style="width:90px">
                    <col class="trk_col_resizable" style="width:80px">
                    <col class="trk_col_resizable" style="width:130px">
                    <col class="trk_col_resizable" style="width:70px">
                    <col class="trk_col_resizable" style="width:70px">
                </colgroup>
                <thead><tr>
                    <th><span>결함 ID</span><div class="trk_col_handle"></div></th>
                    <th><span>심각도</span><div class="trk_col_handle"></div></th>
                    <th><span>수정 우선순위</span><div class="trk_col_handle"></div></th>
                    <th><span>제목</span><div class="trk_col_handle"></div></th>
                    <th><span>담당자</span><div class="trk_col_handle"></div></th>
                    <th><span>예상 해결일</span><div class="trk_col_handle"></div></th>
                    <th><span>등록일</span><div class="trk_col_handle"></div></th>
                    <th><span>시험 배포 ID</span><div class="trk_col_handle"></div></th>
                    <th><span>결함의심사진(HDR외)</span><div class="trk_col_handle"></div></th>
                    <th><span>결함의심사진(HDR)</span></th>
                </tr></thead><tbody>`;

            defects.forEach(d => {
                const dCls = dateCls(d.expected_resolution_date);
                const expDate = d.expected_resolution_date
                    ? `<span class="${dCls}">${d.expected_resolution_date}${dCls === "trk_date_overdue" ? " ⚠️" : ""}</span>`
                    : `<span style="color:#94a3b8">미정</span>`;

                const imgs = d.images || {};
                function imgCell(type) {
                    const urls = [...(imgs[type] || []), ...(type === 'other_device' ? (imgs.general || []) : [])];
                    const thumbs = urls.map(url =>
                        `<img src="${url}" class="trk_defect_thumb" data-src="${url}" title="클릭하여 확대">`
                    ).join("");
                    return `<td class="trk_defect_img_cell">
                        ${thumbs}
                        <label class="trk_img_upload_btn" title="이미지 추가">+
                            <input type="file" accept="image/*" style="display:none"
                                data-defect-id="${d.id}" data-img-type="${type}" class="trk_img_file_input">
                        </label>
                    </td>`;
                }

                html += `<tr data-release-id="${d.release_id}" data-wifi-release-id="${d.wifi_release_id || ''}" data-defect-id="${d.id}">
                    <td style="font-size:0.75rem;color:#64748b">${d.id}</td>
                    <td>${sevBadge(d.severity)}</td>
                    <td>${prioBadge(d.priority, d.severity)}</td>
                    <td style="max-width:280px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"
                        title="${d.title}">${d.title}</td>
                    <td>${d.assigned_to}</td>
                    <td>${expDate}</td>
                    <td style="font-size:0.75rem;color:#64748b">${(d.created_at||"").slice(0,10)}</td>
                    <td style="font-size:0.75rem">${d.release_id}</td>
                    ${imgCell('other_device')}
                    ${imgCell('hdr_screen')}
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
        // 뷰 모드: 0=전체, 1=시험중(TESTING+BLOCKED), 2=저장상태복구
        const viewMode = parseInt(localStorage.getItem('trk_view_mode') || '0', 10);
        const IN_PROGRESS = new Set(['TESTING','BLOCKED']);
        const visibleReleases = (viewMode === 1
            ? releases.filter(r => IN_PROGRESS.has(r.status))
            : releases
        ).filter(r => !isContainer(r));

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

        let html = `<div class="gantt_wrap">
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
                bindDefectImages(root);
                initDefectColResize(root);
                if (typeof initTableColumnFeatures === "function") initTableColumnFeatures(root);
            })
            .catch(err => {
                root.innerHTML = `<div class="trk_loading" style="color:#ef4444">
                    데이터 로드 실패: ${err.message}
                </div>`;
            });
    }

    /* ── 결함 이미지 업로드 + 라이트박스 ────────────────────────── */
    /* ── 결함 테이블 컬럼 리사이즈 ──────────────────────────── */
    const DEFECT_COL_KEY = "trk_defect_col_widths";
    function initDefectColResize(root) {
        const table = root.querySelector(".trk_defect_table");
        if (!table) return;
        const cols = table.querySelectorAll("col.trk_col_resizable");
        const handles = table.querySelectorAll("th .trk_col_handle");

        // 저장된 폭 복원
        try {
            const saved = JSON.parse(localStorage.getItem(DEFECT_COL_KEY) || "[]");
            saved.forEach((w, i) => { if (cols[i] && w > 20) cols[i].style.width = w + "px"; });
        } catch(e) {}

        handles.forEach((handle, idx) => {
            let startX, startW;
            handle.addEventListener("mousedown", e => {
                e.preventDefault();
                startX = e.clientX;
                startW = cols[idx] ? parseInt(cols[idx].style.width) || 80 : 80;
                const onMove = mv => {
                    const w = Math.max(30, startW + mv.clientX - startX);
                    if (cols[idx]) cols[idx].style.width = w + "px";
                };
                const onUp = () => {
                    document.removeEventListener("mousemove", onMove);
                    document.removeEventListener("mouseup", onUp);
                    const widths = Array.from(cols).map(c => parseInt(c.style.width) || 80);
                    localStorage.setItem(DEFECT_COL_KEY, JSON.stringify(widths));
                };
                document.addEventListener("mousemove", onMove);
                document.addEventListener("mouseup", onUp);
            });
        });
    }

    /* ── 간트 접기/펼치기 ───────────────────────────────────── */
    const GANTT_FOLD_KEY = "trk_gantt_fold";

    function getFoldState(id) {
        try { return JSON.parse(localStorage.getItem(GANTT_FOLD_KEY) || "{}")[id] === true; }
        catch(e) { return false; }
    }
    function saveFoldState(id, folded) {
        try {
            const s = JSON.parse(localStorage.getItem(GANTT_FOLD_KEY) || "{}");
            s[id] = folded;
            localStorage.setItem(GANTT_FOLD_KEY, JSON.stringify(s));
        } catch(e) {}
    }
    function _applyFold(root, id, folded) {
        root.querySelectorAll(`[data-parent-id="${id}"]`).forEach(row => {
            row.style.display = folded ? "none" : "";
        });
    }
    function bindGanttFold(root) {
        const viewMode = parseInt(localStorage.getItem('trk_view_mode') || '0', 10);
        root.querySelectorAll(".gantt_fold_btn").forEach(btn => {
            const id = btn.dataset.foldId;
            // 모드 2(저장상태복구)만 저장된 상태 적용, 나머지는 모두 펼침
            if (viewMode === 2 && getFoldState(id)) {
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

    function bindDefectImages(root) {
        // 썸네일 hover → 확대 팝업
        const popup = document.getElementById("trk_img_popup") || (() => {
            const el = document.createElement("div");
            el.id = "trk_img_popup";
            el.innerHTML = `<img id="trk_popup_img" src="">`;
            document.body.appendChild(el);
            return el;
        })();
        const popupImg = document.getElementById("trk_popup_img");

        root.querySelectorAll(".trk_defect_thumb").forEach(img => {
            img.addEventListener("mouseenter", e => {
                popupImg.src = img.dataset.src;
                popup.style.display = "block";
                const rect = img.getBoundingClientRect();
                const pw = window.innerWidth  * 0.7 + 12;
                const ph = window.innerHeight * 0.7 + 12;
                let left = rect.right + 10;
                let top  = rect.top;
                if (left + pw > window.innerWidth)  left = Math.max(8, rect.left - pw - 10);
                if (top  + ph > window.innerHeight) top  = Math.max(8, window.innerHeight - ph - 8);
                popup.style.left = left + "px";
                popup.style.top  = top  + "px";
            });
            img.addEventListener("mouseleave", () => { popup.style.display = "none"; });
        });

        // 파일 입력 → 업로드
        root.querySelectorAll(".trk_img_file_input").forEach(input => {
            input.addEventListener("change", async e => {
                e.stopPropagation();
                const file = input.files[0];
                if (!file) return;
                const defectId = input.dataset.defectId;
                const imgType = input.dataset.imgType || "other_device";
                const formData = new FormData();
                formData.append("file", file);
                formData.append("img_type", imgType);
                try {
                    const resp = await fetch(`/admin/api/defect/${encodeURIComponent(defectId)}/image`, {
                        method: "POST", body: formData
                    });
                    if (!resp.ok) throw new Error(await resp.text());
                    document.getElementById("trk_refresh_btn").click();
                } catch(err) {
                    alert("업로드 실패: " + err.message);
                }
            });
        });
    }

    const VIEW_MODE_LABELS = ['전체 보기', '시험중 보기', '저장상태 복구'];
    function updateToggleLabel() {
        const btn = document.getElementById("trk_view_toggle_btn");
        if (!btn) return;
        const mode = parseInt(localStorage.getItem('trk_view_mode') || '0', 10);
        // 다음 클릭 시 이동할 상태 안내
        btn.textContent = VIEW_MODE_LABELS[(mode + 1) % 3];
        btn.title = `현재: ${VIEW_MODE_LABELS[mode]} → 클릭하면: ${VIEW_MODE_LABELS[(mode + 1) % 3]}`;
    }

    document.addEventListener("DOMContentLoaded", () => { updateToggleLabel(); loadTracking(); });
    document.getElementById("trk_refresh_btn")
        && document.getElementById("trk_refresh_btn").addEventListener("click", () => { updateToggleLabel(); loadTracking(); });
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
    // 상태별 하이라이트 클래스 결정
    function statusHighlightClass(status) {
        if (!status) return "hl-default";
        const s = status.toUpperCase();
        if (["PASSED","QI_TEAM_RELEASED","APPROVED"].includes(s)) return "hl-passed";
        if (["BLOCKED"].includes(s)) return "hl-blocked";
        if (["TESTING"].includes(s)) return "hl-testing";
        return "hl-default";
    }

    function clearAllHighlights() {
        document.querySelectorAll("tr.trk_row_highlighted").forEach(r => {
            r.classList.remove("trk_row_highlighted","hl-passed","hl-blocked","hl-testing","hl-default");
        });
        root.querySelectorAll(".gantt_row.gantt_hl").forEach(r => {
            r.classList.remove("gantt_hl","hl-passed","hl-blocked","hl-testing","hl-default");
        });
    }

    root.querySelectorAll(".gantt_row_child").forEach(row => {
        row.addEventListener("click", e => {
            if (e.target.closest(".trk_status_editable, .trk_status_readonly")) return;
            const releaseId = row.dataset.rowId;
            const isSelected = row.classList.contains("gantt_hl");

            clearAllHighlights();
            if (!isSelected && releaseId) {
                const hlCls = statusHighlightClass(row.dataset.status);
                row.classList.add("gantt_hl", hlCls);
                const matched = document.querySelectorAll(`tr[data-release-id="${releaseId}"]`);
                matched.forEach(r => r.classList.add("trk_row_highlighted", hlCls));
                if (matched.length > 0) matched[0].scrollIntoView({ behavior: "smooth", block: "nearest" });
            }
        });
    });

    // 결함 행 클릭 → 연관 데이터 하이라이트
    root.querySelectorAll(".trk_defect_table tbody tr").forEach(tr => {
        tr.style.cursor = "pointer";
        tr.addEventListener("click", () => {
            const isSelected = tr.classList.contains("trk_row_highlighted");
            clearAllHighlights();
            if (isSelected) return;

            const wifiRelease = tr.dataset.wifiReleaseId || "";
            // 결함 행 자체는 blocked 색상
            tr.classList.add("trk_row_highlighted", "hl-blocked");

            if (wifiRelease) {
                const parentRow = root.querySelector(`.gantt_row[data-row-id="${wifiRelease}"]`);
                if (parentRow) {
                    const hlCls = statusHighlightClass(parentRow.dataset.status);
                    parentRow.classList.add("gantt_hl", hlCls);
                    parentRow.scrollIntoView({ behavior: "smooth", block: "nearest" });
                }
                root.querySelectorAll(`.gantt_row_child[data-parent-id="${wifiRelease}"]`).forEach(c => {
                    c.classList.add("gantt_hl", statusHighlightClass(c.dataset.status));
                });
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
