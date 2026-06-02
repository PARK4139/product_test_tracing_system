// tracking-render.js — renderTracking: builds full HTML from API data
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

            html += `<tr data-release-id="${d.release_id}" data-parent-release-id="${d.parent_release_id || ''}" data-defect-id="${d.id}">
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
