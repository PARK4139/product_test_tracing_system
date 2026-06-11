// tracking-render.js — renderTracking: builds full HTML from API data
/* ── defect table builder ─────────────────────────────────────── */
function buildDefectTable(defects) {
    const isHidden = uiStateGetItem("trk_active_defects_hidden") === "1";
    const toggleLabel = isHidden ? "보기모드: VIEW 보이기" : "보기모드: VIEW 숨기기";
    let html = `<div class="trk_sub_header">미결 결함 현황 (진행 중 배포)
        <button type="button" class="trk_view_mode_btn"
            onclick="var n=uiStateGetItem('trk_active_defects_hidden')==='1'?'0':'1';uiStateSetItem('trk_active_defects_hidden',n);var b=document.getElementById('trk_refresh_btn');if(b){b.dataset.preserveScroll='1';b.click();}">
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
        html += `<tr data-entity-type="product_test_defect" data-entity-id="${d.id}" data-release-id="${d.release_id}" data-parent-release-id="${d.parent_release_id || ''}" data-defect-id="${d.id}" data-run-id="${d.run_id || ''}">
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
function buildSimpleDataTableSection(title, className, columns, rows, options) {
    const opts = options || {};
    if (!rows || rows.length === 0) return "";
    function escapeHtml(value) {
        return String(value == null ? "" : value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }
    let html = `<div class="trk_sub_header">${title}</div>`;
    html += `<div class="trk_timeline_wrap"><table class="${className}"><thead><tr>`;
    columns.forEach(col => {
        const width = col.width ? ` style="width:${col.width}"` : "";
        html += `<th${width}>${col.label}</th>`;
    });
    html += `</tr></thead><tbody>`;
    rows.forEach(row => {
        const entityType = row.entity_type || opts.entityType || "";
        const entityId = row.entity_id || (opts.entityIdKey ? row[opts.entityIdKey] : row.id) || "";
        const rowAttrs = entityType && entityId
            ? ` data-entity-type="${escapeHtml(entityType)}" data-entity-id="${escapeHtml(entityId)}"`
            : "";
        html += `<tr${rowAttrs} style="cursor:pointer">`;
        columns.forEach(col => {
            const raw = row[col.key] == null ? "" : String(row[col.key]);
            const display = col.transform ? col.transform(raw) : raw;
            const text = display || "-";
            const field = col.field || "";
            const fieldAttr = field ? ` data-field="${escapeHtml(field)}"` : "";
            html += `<td${fieldAttr} title="${escapeHtml(raw)}">${escapeHtml(text)}</td>`;
        });
        html += `</tr>`;
    });
    html += `</tbody></table></div>`;
    return html;
}

function buildMasterDataSections(data, releases) {
    let html = "";
    html += buildSimpleDataTableSection("Test Round", "trk_test_release_table", [
        { key: "id", label: "Round ID", width: "280px" },
        { key: "upstream_id", label: "Upstream", width: "220px", field: "test_round_name" },
        { key: "stage", label: "Stage", width: "110px" },
        { key: "status", label: "Status", width: "130px", field: "product_test_round_status" },
        { key: "workday", label: "Workday", width: "90px" },
        { key: "start_date", label: "Start", width: "100px" },
        { key: "end_date", label: "End", width: "100px" },
        { key: "run_count", label: "Runs", width: "70px" },
        { key: "open_defects", label: "Open Defects", width: "100px" },
        { key: "remark", label: "Remark", width: "300px", field: "remark" }
    ], data.test_rounds || releases || [], { entityType: "product_test_round" });

    html += buildSimpleDataTableSection("Test Targets", "trk_test_target_table", [
        { key: "id", label: "Target ID", width: "300px" },
        { key: "round_id", label: "Timeline Round", width: "300px" },
        { key: "physical_target_id", label: "Physical Target", width: "240px" },
        { key: "product_code", label: "Product Code", width: "120px" },
        { key: "model_name", label: "Model", width: "140px" },
        { key: "hardware_revision", label: "HW Rev", width: "80px" },
        { key: "serial_number", label: "Serial", width: "140px", field: "serial_number" },
        { key: "software_version", label: "SW", width: "100px", field: "software_version" },
        { key: "firmware_version", label: "FW", width: "100px", field: "firmware_version" },
        { key: "manufacture_lot", label: "Lot", width: "110px", field: "manufacture_lot" },
        { key: "status", label: "Status", width: "100px", field: "product_test_target_status" },
        { key: "remark", label: "Remark", width: "260px", field: "remark" }
    ], data.test_targets || []);

    html += buildSimpleDataTableSection("Test Configs", "trk_test_environment_table", [
        { key: "id", label: "Config ID", width: "330px", transform: v => stripConfigPrefix(v) },
        { key: "definition_id", label: "Definition ID", width: "360px" },
        { key: "name", label: "Name", width: "200px", field: "product_test_environment_name" },
        { key: "country", label: "Country", width: "90px" },
        { key: "city", label: "City", width: "90px" },
        { key: "company", label: "Company", width: "120px" },
        { key: "room", label: "Room", width: "140px" },
        { key: "network_type", label: "Network", width: "140px", field: "network_type" },
        { key: "computer_name", label: "Computer", width: "150px", field: "test_computer_name" },
        { key: "os_version", label: "OS", width: "160px", field: "operating_system_version" },
        { key: "tool_version", label: "Tool Ver.", width: "110px", field: "test_tool_version" },
        { key: "power_voltage", label: "Voltage", width: "90px", field: "power_voltage" },
        { key: "power_frequency", label: "Freq.", width: "80px", field: "power_frequency" },
        { key: "captured_at", label: "Captured", width: "120px", field: "captured_at" },
        { key: "status", label: "Status", width: "100px", field: "product_test_environment_status" },
        { key: "remark", label: "Remark", width: "260px", field: "remark" }
    ], data.test_environments || [], { entityType: "product_test_environment" });

    html += buildSimpleDataTableSection("Test Case", "trk_test_case_master_table", [
        { key: "id", label: "Case ID", width: "330px" },
        { key: "title", label: "Title", width: "260px", field: "product_test_case_title" },
        { key: "category", label: "Category", width: "130px", field: "test_category" },
        { key: "objective", label: "Objective", width: "260px", field: "test_objective" },
        { key: "precondition", label: "Precondition", width: "260px", field: "precondition" },
        { key: "expected_result", label: "Expected Result", width: "260px", field: "expected_result" },
        { key: "status", label: "Status", width: "100px", field: "product_test_case_status" },
        { key: "remark", label: "Remark", width: "260px", field: "remark" }
    ], data.test_cases || [], { entityType: "product_test_case" });

    html += buildSimpleDataTableSection("Test Procedure", "trk_test_procedure_master_table", [
        { key: "id", label: "Procedure ID", width: "360px" },
        { key: "case_id", label: "Case ID", width: "330px" },
        { key: "sequence", label: "Seq", width: "60px" },
        { key: "action", label: "Action", width: "300px", field: "procedure_action" },
        { key: "acceptance_criteria", label: "Acceptance", width: "260px", field: "acceptance_criteria" },
        { key: "required_evidence_type", label: "Evidence", width: "120px", field: "required_evidence_type" },
        { key: "status", label: "Status", width: "100px", field: "product_test_procedure_status" },
        { key: "used_releases", label: "Used In", width: "260px" },
        { key: "remark", label: "Remark", width: "260px", field: "remark" }
    ], data.test_procedures || [], { entityType: "product_test_procedure" });

    return html;
}

function renderTracking(data) {
    const releases = data.releases || [];

    let html = "";
    const viewLabels = ['보기모드: 전체','보기모드: 시험중','보기모드: 중단판정','보기모드: 최상위'];
    const curView = parseInt(uiStateGetItem('trk_view_mode') || '0', 10);
    const sortLabels = ['정렬: 기본','정렬: 시험종료일자별'];
    const curSort = parseInt(uiStateGetItem('trk_sort_mode') || '0', 10);
    html += `<div class="trk_sub_header">Round Timeline
        <button type="button" id="trk_view_toggle_btn" class="trk_view_mode_btn"
            onclick="var l=['보기모드: 전체','보기모드: 시험중','보기모드: 중단판정','보기모드: 최상위'];var c=parseInt(uiStateGetItem('trk_view_mode')||'0',10);var n=(c+1)%4;uiStateSetItem('trk_view_mode',n);this.textContent=l[n];var b=document.getElementById('trk_refresh_btn');if(b){b.dataset.preserveScroll='1';b.click();}">
            ${viewLabels[curView] || viewLabels[0]}
        </button>
        <button type="button" id="trk_sort_toggle_btn" class="trk_view_mode_btn"
            onclick="var l=['정렬: 기본','정렬: 시험종료일자별'];var c=parseInt(uiStateGetItem('trk_sort_mode')||'0',10);var n=(c+1)%2;uiStateSetItem('trk_sort_mode',n);this.textContent=l[n];var b=document.getElementById('trk_refresh_btn');if(b){b.dataset.preserveScroll='1';b.click();}">
            ${sortLabels[curSort] || sortLabels[0]}
        </button>
    </div>`;
    html += buildGantt(releases.filter(r => !r.id.includes("FALLBACK")), data.runs || []);
    return html;
}
