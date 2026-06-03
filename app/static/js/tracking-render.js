// tracking-render.js — renderTracking: builds full HTML from API data
/* ── defect table builder ─────────────────────────────────────── */
function buildDefectTable(defects) {
    let html = `<div class="trk_sub_header">미결 결함 현황 (진행 중 배포)</div>`;
    if (defects.length === 0) {
        html += `<div style="color:var(--color-text-muted,#71717a);font-size:0.85rem;padding:12px 0">진행 중 배포에 미결 결함이 없습니다.</div>`;
        return html;
    }
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
            ? `<span class="${dCls}">${d.expected_resolution_date}${dCls === "trk_date_overdue" ? " !" : ""}</span>`
            : `<span style="color:#94a3b8">미정</span>`;
        const imgs = d.images || {};
        function imgCell(type) {
            const urls = [...(imgs[type] || []), ...(type === 'other_device' ? (imgs.general || []) : [])];
            const thumbs = urls.map(url =>
                `<img src="${url}" class="trk_defect_thumb" data-src="${url}" title="click to zoom">`
            ).join("");
            return `<td class="trk_defect_img_cell">
                ${thumbs}
                <label class="trk_img_upload_btn" title="add image">+
                    <input type="file" accept="image/*" style="display:none"
                        data-defect-id="${d.id}" data-img-type="${type}" class="trk_img_file_input">
                </label>
            </td>`;
        }
        html += `<tr data-release-id="${d.release_id}" data-parent-release-id="${d.parent_release_id || ''}" data-defect-id="${d.id}" data-run-id="${d.run_id || ''}">
            <td style="font-size:0.75rem;color:#64748b">${d.id}</td>
            <td>${sevBadge(d.severity)}</td>
            <td>${prioBadge(d.priority, d.severity)}</td>
            <td style="max-width:280px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${d.title}">${d.title}</td>
            <td>${d.assigned_to}</td>
            <td>${expDate}</td>
            <td style="font-size:0.75rem;color:#64748b">${(d.created_at||"").slice(0,10)}</td>
            <td style="font-size:0.75rem">${d.release_id}</td>
            ${imgCell('other_device')}
            ${imgCell('hdr_screen')}
        </tr>`;
    });
    html += `</tbody></table></div>`;
    return html;
}

/* ── render ──────────────────────────────────────────────────── */
function renderTracking(data) {
    const releases = data.releases || [];
    const defects  = data.active_defects || [];

    const testing    = releases.filter(r => r.status === "TESTING" && !r.id.includes("FALLBACK"));
    const totalResults = testing.reduce((a, r) => a + r.total_results, 0);
    const totalPass    = testing.reduce((a, r) => a + r.passed,       0);
    const totalBlock   = testing.reduce((a, r) => a + r.blocked,      0);
    const totalOpen    = defects.length;

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
                    <th>미결 결함</th>
                </tr></thead>
                <tbody><tr>
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
    html += buildDefectTable(defects);

    /* ── 4. Run table ─────────────────────────────────────── */
    const runs = data.runs || [];
    if (runs.length > 0) {
        html += `<div class="trk_sub_header">Run 현황</div>`;
        html += `<div class="trk_timeline_wrap"><table class="trk_run_table">
            <thead><tr>
                <th style="width:220px">Run ID</th>
                <th style="width:200px">구성</th>
                <th style="width:70px">상태</th>
                <th style="width:50px">전체</th>
                <th style="width:50px">합격</th>
                <th style="width:50px">차단</th>
                <th style="width:50px">시험중</th>
            </tr></thead><tbody>`;
        runs.forEach(r => {
            const runSt = r.blocked>0?"BLOCKED":r.testing>0?"TESTING":"PASSED";
            html += `<tr data-run-id="${r.id}" data-parent-release-id="${r.parent_release_id}" data-status="${runSt}" style="cursor:pointer">
                <td style="font-size:0.72rem;color:#64748b" title="${r.id}">${r.id}</td>
                <td style="font-size:0.78rem">${extractTopo(r.parent_release_id)}</td>
                <td>${statusBadge(r.status)}</td>
                <td style="text-align:center">${r.total_results}</td>
                <td style="text-align:center;color:#16a34a;font-weight:600">${r.passed}</td>
                <td style="text-align:center;color:${r.blocked>0?"#dc2626":"#94a3b8"};font-weight:${r.blocked>0?"600":"400"}">${r.blocked}</td>
                <td style="text-align:center;color:${r.testing>0?"#2563eb":"#94a3b8"}">${r.testing}</td>
            </tr>`;
        });
        html += `</tbody></table></div>`;
    }

    /* ── 4. Result summary (case level) ───────────────────── */
    const resultsSummary = data.results_summary || [];
    if (resultsSummary.length > 0) {
        html += `<div class="trk_sub_header">Result 요약 (Case 단위)</div>`;
        html += `<div class="trk_timeline_wrap"><table class="trk_result_table">
            <thead><tr>
                <th style="width:360px">Test Case</th>
                <th style="width:50px">전체</th>
                <th style="width:50px">합격</th>
                <th style="width:50px">차단</th>
                <th style="width:50px">시험중</th>
                <th style="width:50px">결함</th>
            </tr></thead><tbody>`;
        resultsSummary.forEach(r => {
            const hd = r.defect_ids && r.defect_ids.length > 0;
            const resSt = r.blocked>0?"BLOCKED":r.testing>0?"TESTING":"PASSED";
            const caseDisplay = extractTopo(r.parent_release_id) + "-" + (r.case_id||"").replace(/^(TEST_CASE|DEPRECATED_TEST_CASE)-[^-]+-/,"");
            html += `<tr data-parent-release-id="${r.parent_release_id}"
                         data-case-id="${r.case_id}"
                         data-result-ids='${JSON.stringify(r.result_ids||[])}'
                         data-defect-ids='${JSON.stringify(r.defect_ids||[])}'
                         data-status="${resSt}"
                         style="cursor:pointer">
                <td style="font-size:0.75rem;max-width:360px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${caseDisplay}">${caseDisplay}</td>
                <td style="text-align:center">${r.total}</td>
                <td style="text-align:center;color:#16a34a;font-weight:600">${r.passed}</td>
                <td style="text-align:center;color:${r.blocked>0?"#dc2626":"#94a3b8"};font-weight:${r.blocked>0?"600":"400"}">${r.blocked}</td>
                <td style="text-align:center;color:${r.testing>0?"#2563eb":"#94a3b8"}">${r.testing}</td>
                <td style="text-align:center;color:${hd?"#dc2626":"#94a3b8"};font-weight:${hd?"700":"400"}">${hd?r.defect_ids.length:"-"}</td>
            </tr>`;
        });
        html += `</tbody></table></div>`;
    }

    /* ── 5. Procedure Results ─────────────────────────────── */
    const procResults = data.procedure_results || [];
    if (procResults.length > 0) {
        html += `<div class="trk_sub_header">Procedure Result 현황</div>`;
        html += `<div class="trk_timeline_wrap"><table class="trk_proc_result_table">
            <thead><tr>
                <th style="width:180px">구성</th>
                <th style="width:200px">Test Case</th>
                <th style="width:30px">Seq</th>
                <th style="width:250px">Action</th>
                <th style="width:70px">상태</th>
                <th style="width:120px">판정자</th>
                <th style="width:100px">판정일</th>
            </tr></thead><tbody>`;
        procResults.forEach(pr => {
            const topoShort = (pr.parent_release_id||"").replace("TEST_RELEASE-","");
            const caseShort = (pr.case_id||"").replace("TEST_CASE-","");
            html += `<tr data-parent-release-id="${pr.parent_release_id}"
                         data-result-id="${pr.result_id}"
                         data-procedure-result-id="${pr.id}"
                         style="cursor:pointer">
                <td style="font-size:0.75rem;color:#64748b">${topoShort}</td>
                <td style="font-size:0.75rem" title="${pr.case_id}">${caseShort}</td>
                <td style="text-align:center">${pr.sequence}</td>
                <td style="font-size:0.75rem;max-width:250px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${pr.action}">${pr.action}</td>
                <td>${statusBadge(pr.status)}</td>
                <td style="font-size:0.75rem">${pr.judged_by}</td>
                <td style="font-size:0.75rem;color:#64748b">${(pr.judged_at||"").slice(0,10)}</td>
            </tr>`;
        });
        html += `</tbody></table></div>`;
    }

    /* ── 7. Evidence ──────────────────────────────────────── */
    const evidenceList = data.evidence || [];
    if (evidenceList.length > 0) {
        html += `<div class="trk_sub_header">Evidence 현황</div>`;
        html += `<div class="trk_timeline_wrap"><table class="trk_evidence_table">
            <thead><tr>
                <th style="width:180px">구성</th>
                <th style="width:80px">유형</th>
                <th style="width:200px">파일명</th>
                <th style="width:100px">연결 대상</th>
                <th style="width:120px">수집자</th>
                <th style="width:100px">수집일</th>
            </tr></thead><tbody>`;
        evidenceList.forEach(ev => {
            const topoShort = (ev.parent_release_id||"").replace("TEST_RELEASE-","");
            const linked = ev.defect_id ? ("defect: "+ev.defect_id) : ev.procedure_result_id ? ("proc: "+ev.procedure_result_id) : ev.result_id ? ("result: "+ev.result_id) : "-";
            html += `<tr data-parent-release-id="${ev.parent_release_id}"
                         data-result-id="${ev.result_id}"
                         data-defect-id="${ev.defect_id}"
                         data-evidence-id="${ev.id}"
                         style="cursor:pointer">
                <td style="font-size:0.75rem;color:#64748b">${topoShort}</td>
                <td style="font-size:0.78rem">${ev.type}</td>
                <td style="font-size:0.75rem;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${ev.file_name}">${ev.file_name}</td>
                <td style="font-size:0.7rem;color:#64748b;max-width:100px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${linked}">${linked}</td>
                <td style="font-size:0.75rem">${ev.captured_by}</td>
                <td style="font-size:0.75rem;color:#64748b">${(ev.captured_at||"").slice(0,10)}</td>
            </tr>`;
        });
        html += `</tbody></table></div>`;
    }

    return html;
}
