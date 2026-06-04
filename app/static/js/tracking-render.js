// tracking-render.js — renderTracking: builds full HTML from API data
/* ── defect table builder ─────────────────────────────────────── */
function buildDefectTable(defects) {
    const isHidden = localStorage.getItem("trk_active_defects_hidden") === "1";
    const toggleLabel = isHidden ? "보기모드: VIEW 보이기" : "보기모드: VIEW 숨기기";
    let html = `<div class="trk_sub_header">미결 결함 현황 (진행 중 배포)
        <button type="button" class="trk_view_mode_btn"
            onclick="var n=localStorage.getItem('trk_active_defects_hidden')==='1'?'0':'1';localStorage.setItem('trk_active_defects_hidden',n);var b=document.getElementById('trk_refresh_btn');if(b){b.dataset.preserveScroll='1';b.click();}">
            ${toggleLabel}
        </button>
    </div>`;
    if (isHidden) return html;
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
    const allRuns = data.runs || [];
    const sumResults = allRuns.reduce((a,r) => a + r.total_results, 0);
    const sumPassed  = allRuns.reduce((a,r) => a + r.passed, 0);
    const sumBlocked = allRuns.reduce((a,r) => a + r.blocked, 0);
    const sumTesting = allRuns.reduce((a,r) => a + r.testing, 0);
    const passRate   = sumResults > 0 ? Math.round(sumPassed / sumResults * 100) : 0;

    const passColor  = passRate >= 80 ? "#22c55e" : passRate >= 50 ? "#f59e0b" : "#ef4444";
    const blockColor = sumBlocked > 0 ? "#ef4444" : "#22c55e";
    const openColor  = totalOpen  > 0 ? "#ef4444" : "#22c55e";

    html += `<div class="trk_stat_table_wrap">
        <table class="trk_stat_table">
            <thead><tr>
                <th>미결 결함</th>
                <th>전체 Result</th>
                <th>통과율</th>
                <th>차단</th>
                <th>시험중</th>
            </tr></thead>
            <tbody><tr>
                <td>
                    <span class="trk_stat_num" style="color:${openColor};font-weight:700">${totalOpen}건</span>
                    <div class="trk_stat_sub">opened</div>
                </td>
                <td>
                    <span class="trk_stat_num" style="font-weight:700">${sumResults}건</span>
                    <div class="trk_stat_sub">${allRuns.length} runs</div>
                </td>
                <td>
                    <span class="trk_stat_num" style="color:${passColor};font-weight:700">${passRate}%</span>
                    <div class="trk_stat_sub">${sumPassed}/${sumResults}</div>
                </td>
                <td>
                    <span class="trk_stat_num" style="color:${blockColor};font-weight:700">${sumBlocked}건</span>
                    <div class="trk_stat_sub">blocked</div>
                </td>
                <td>
                    <span class="trk_stat_num" style="color:${sumTesting>0?"#2563eb":"#94a3b8"};font-weight:700">${sumTesting}건</span>
                    <div class="trk_stat_sub">testing</div>
                </td>
            </tr></tbody>
        </table>
    </div>`;

    /* ── 2. Active defects ─────────────────────────────────── */
    html += buildDefectTable(defects);

    /* ── 3. Release timeline ───────────────────────────────── */
    const viewLabels = ['보기모드: 전체','보기모드: 시험중','보기모드: 중단판정','보기모드: 최상위'];
    const curView = parseInt(localStorage.getItem('trk_view_mode') || '0', 10);
    const sortLabels = ['정렬: 기본','정렬: 시험종료일자별'];
    const curSort = parseInt(localStorage.getItem('trk_sort_mode') || '0', 10);
    html += `<div class="trk_sub_header">배포 이력 타임라인
        <button type="button" id="trk_view_toggle_btn" class="trk_view_mode_btn"
            onclick="var l=['보기모드: 전체','보기모드: 시험중','보기모드: 중단판정','보기모드: 최상위'];var c=parseInt(localStorage.getItem('trk_view_mode')||'0',10);var n=(c+1)%4;localStorage.setItem('trk_view_mode',n);this.textContent=l[n];var b=document.getElementById('trk_refresh_btn');if(b){b.dataset.preserveScroll='1';b.click();}">
            ${viewLabels[curView] || viewLabels[0]}
        </button>
        <button type="button" id="trk_sort_toggle_btn" class="trk_view_mode_btn"
            onclick="var l=['정렬: 기본','정렬: 시험종료일자별'];var c=parseInt(localStorage.getItem('trk_sort_mode')||'0',10);var n=(c+1)%2;localStorage.setItem('trk_sort_mode',n);this.textContent=l[n];var b=document.getElementById('trk_refresh_btn');if(b){b.dataset.preserveScroll='1';b.click();}">
            ${sortLabels[curSort] || sortLabels[0]}
        </button>
    </div>`;
    html += buildGantt(releases.filter(r => !r.id.includes("FALLBACK")), data.runs || []);

    
    /* ── 3.5 Run 현황 ───────────────────────────────────────── */
    const runList = data.runs || [];
    // target/env 상세 조회용 맵
    const tgtMap = Object.fromEntries((data.targets||[]).map(t => [t.id, t]));
    const envMap = Object.fromEntries((data.environments||[]).map(e => [e.id, e]));
    if (runList.length > 0) {
        html += `<div class="trk_sub_header">Run 현황</div>`;
        html += `<div class="trk_timeline_wrap"><table class="trk_run_table">
            <thead><tr>
                <th style="width:300px">Run ID</th>
                <th style="width:70px">상태</th>
                <th style="width:160px">Target</th>
                <th style="width:200px">Environment</th>
                <th style="width:80px">시작일</th>
                <th style="width:80px">종료일</th>
                <th style="width:45px">전체</th>
                <th style="width:45px">통과</th>
                <th style="width:45px">차단</th>
                <th style="width:260px">Remark</th>
            </tr></thead><tbody>`;
        runList.forEach(r => {
            html += `<tr data-parent-release-id="${r.parent_release_id}" data-run-id="${r.id}" data-status="${r.status}" style="cursor:pointer">
                <td style="font-size:0.72rem;color:#64748b" title="${r.id}">${r.id}</td>
                <td>${statusBadge(r.status)}</td>
                <td style="font-size:0.72rem;color:#64748b" title="${r.target_id}">
                    ${tgtMap[r.target_id] ? `<span style="font-weight:600">${tgtMap[r.target_id].model_name}</span> <span style="color:#94a3b8">${tgtMap[r.target_id].sw_version}</span>` : (r.target_id || "-")}
                </td>
                <td style="font-size:0.72rem;color:#64748b" title="${r.environment_id}">
                    ${envMap[r.environment_id] ? envMap[r.environment_id].name : (r.environment_id || "-")}
                </td>
                <td style="font-size:0.75rem;color:#64748b">${(r.planned_start_date || r.started_at || "").slice(0, 10)}</td>
                <td style="font-size:0.75rem;color:#64748b">${(r.planned_end_date || r.finished_at || "").slice(0, 10) || "-"}</td>
                <td style="text-align:center">${r.total_results}</td>
                <td style="text-align:center;color:#22c55e;font-weight:${r.passed > 0 ? "700" : "400"}">${r.passed}</td>
                <td style="text-align:center;color:${r.blocked > 0 ? "#ef4444" : "#94a3b8"};font-weight:${r.blocked > 0 ? "700" : "400"}">${r.blocked}</td>
                <td style="font-size:0.72rem;color:#64748b;max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${r.remark || ""}">${r.remark || "-"}</td>
            </tr>`;
        });
        html += `</tbody></table></div>`;
    }

/* ── 5. Target / Environment ──────────────────────────── */
    const tgts = data.targets || [];
    const envs = data.environments || [];
    if (tgts.length > 0 || envs.length > 0) {
        html += `<div class="trk_sub_header">Target / Environment</div>`;
        if (tgts.length > 0) {
            // 자동완성용 datalist
            const tgtDatalistId = "trk_target_id_list";
            html += `<datalist id="${tgtDatalistId}">` +
                tgts.map(t => `<option value="${t.id}">${t.model_name} ${t.sw_version} (${t.serial_number})</option>`).join("") +
                `</datalist>`;
            html += `<div class="trk_timeline_wrap"><table class="trk_target_table">
                <thead><tr>
                    <th style="width:300px">Logical Target ID</th>
                    <th style="width:130px">모델명</th>
                    <th style="width:90px">SW 버전</th>
                    <th style="width:220px">Physical Target ID</th>
                </tr></thead><tbody>`;
            tgts.forEach(t => {
                html += `<tr style="cursor:pointer">
                    <td>
                        <input list="${tgtDatalistId}" value="${t.id}" readonly
                            style="font-size:0.72rem;color:#64748b;background:transparent;border:none;width:100%;cursor:pointer"
                            title="${t.id}">
                    </td>
                    <td style="font-size:0.78rem;font-weight:600">${t.model_name || "-"}</td>
                    <td style="font-size:0.78rem">${t.sw_version || "-"}</td>
                    <td style="font-size:0.75rem;color:#64748b">${t.physical_target_id || t.serial_number || "-"}</td>
                </tr>`;
            });
            html += `</tbody></table></div>`;
        }
        if (envs.length > 0) {
            const envDatalistId = "trk_env_id_list";
            html += `<datalist id="${envDatalistId}">` +
                envs.map(e => `<option value="${e.id}">${e.name}</option>`).join("") +
                `</datalist>`;
            html += `<div class="trk_timeline_wrap" style="margin-top:6px"><table class="trk_env_table">
                <thead><tr>
                    <th style="width:260px">Environment ID</th>
                    <th style="width:400px">환경 이름</th>
                </tr></thead><tbody>`;
            envs.forEach(e => {
                html += `<tr style="cursor:pointer">
                    <td>
                        <input list="${envDatalistId}" value="${e.id}" readonly
                            style="font-size:0.72rem;color:#64748b;background:transparent;border:none;width:100%;cursor:pointer"
                            title="${e.id}">
                    </td>
                    <td style="font-size:0.75rem" title="${e.name}">${e.name || "-"}</td>
                </tr>`;
            });
            html += `</tbody></table></div>`;
        }
    }

    
    /* ── 5.5 Result 요약 (케이스별) ─────────────────────────── */
    const resultsSummary = data.results_summary || [];
    if (resultsSummary.length > 0) {
        html += `<div class="trk_sub_header">Result 요약 (케이스별)</div>`;
        html += `<div class="trk_timeline_wrap"><table class="trk_result_table">
            <thead><tr>
                <th style="width:200px">구성</th>
                <th style="width:240px">Test Case ID</th>
                <th style="width:45px">전체</th>
                <th style="width:45px">통과</th>
                <th style="width:45px">차단</th>
                <th style="width:45px">시험중</th>
                <th style="width:45px">결함</th>
            </tr></thead><tbody>`;
        resultsSummary.forEach(r => {
            const caseShort = r.case_id || "";
            const defectCount = (r.defect_ids || []).length;
            const rowStyle = r.blocked > 0 ? "background:rgba(239,68,68,0.05);" : "";
            const rowStatus = r.blocked > 0 ? "BLOCKED" : r.testing > 0 ? "TESTING" : r.passed > 0 ? "PASSED" : "";
            html += `<tr data-parent-release-id="${r.parent_release_id}"
                         data-case-id="${r.case_id}"
                         data-defect-ids='${JSON.stringify(r.defect_ids || [])}'
                         data-status="${rowStatus}"
                         style="${rowStyle}cursor:pointer">
                <td style="font-size:0.75rem;color:#64748b">${(r.parent_release_id||"").replace("TEST_RELEASE-","")}</td>
                <td style="font-size:0.75rem" title="${r.case_id}">${caseShort}</td>
                <td style="text-align:center">${r.total}</td>
                <td style="text-align:center;color:#22c55e;font-weight:${r.passed > 0 ? "700" : "400"}">${r.passed}</td>
                <td style="text-align:center;color:${r.blocked > 0 ? "#ef4444" : "#94a3b8"};font-weight:${r.blocked > 0 ? "700" : "400"}">${r.blocked}</td>
                <td style="text-align:center;color:${r.testing > 0 ? "#2563eb" : "#94a3b8"}">${r.testing}</td>
                <td style="text-align:center;color:${defectCount > 0 ? "#ef4444" : "#94a3b8"};font-weight:${defectCount > 0 ? "700" : "400"}">${defectCount || "-"}</td>
            </tr>`;
        });
        html += `</tbody></table></div>`;
    }

    /* ── 6. Case / Procedure ──────────────────────────────── */
    const caseList = data.cases || [];
    const procList = data.procedures || [];
    if (caseList.length > 0) {
        html += `<div class="trk_sub_header">Test Case / Procedure</div>`;
        html += `<div class="trk_timeline_wrap"><table class="trk_case_table">
            <thead><tr>
                <th style="width:350px">Test Case</th>
                <th style="width:200px">제목</th>
            </tr></thead><tbody>`;
        caseList.forEach(c => {
            const caseDisplay = c.id || "";
            html += `<tr data-parent-release-id="${c.parent_release_id}" data-case-id="${c.id}" style="cursor:pointer">
                <td style="font-size:0.75rem" title="${c.id}">${caseDisplay}</td>
                <td style="font-size:0.72rem;color:#64748b;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${c.title}">${c.title}</td>
            </tr>`;
        });
        html += `</tbody></table></div>`;
        if (procList.length > 0) {
            html += `<div class="trk_timeline_wrap" style="margin-top:6px"><table class="trk_procedure_table">
                <thead><tr>
                    <th style="width:30px">Seq</th>
                    <th style="width:350px">Test Case</th>
                    <th style="width:300px">Action</th>
                </tr></thead><tbody>`;
            procList.forEach(p => {
                const caseDisplay = p.case_id || "";
                html += `<tr data-parent-release-id="${p.parent_release_id}" data-case-id="${p.case_id}" style="cursor:pointer">
                    <td style="text-align:center">${p.sequence}</td>
                    <td style="font-size:0.72rem;color:#64748b" title="${p.case_id}">${caseDisplay}</td>
                    <td style="font-size:0.72rem;max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${p.action}">${p.action}</td>
                </tr>`;
            });
            html += `</tbody></table></div>`;
        }
    }

    /* ── 7. Procedure Results ─────────────────────────────── */
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
            const caseShort = pr.case_id || "";
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
