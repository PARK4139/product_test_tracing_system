(() => {
    const openMessageModal = (message, options = {}) => {
        const overlay = document.getElementById("app_message_modal");
        const title = document.getElementById("app_message_modal_title");
        const body = document.getElementById("app_message_modal_body");
        const closeButton = document.getElementById("app_message_modal_close_button");
        const okButton = document.getElementById("app_message_modal_ok_button");
        if (!overlay || !title || !body || !closeButton || !okButton) {
            return;
        }
        const type_name = String(options.type || "info").toLowerCase();
        const title_text = String(options.title || "알림");
        const ok_text = String(options.ok_text || "확인");
        const close_text = String(options.close_text || "닫기");
        const on_ok = typeof options.on_ok === "function" ? options.on_ok : null;
        const on_close = typeof options.on_close === "function" ? options.on_close : null;

        title.textContent = title_text;
        body.textContent = String(message || "");
        okButton.textContent = ok_text;
        closeButton.textContent = close_text;

        overlay.classList.remove("message_modal_success");
        if (type_name === "success") {
            overlay.classList.add("message_modal_success");
        }
        overlay.style.display = "flex";
        overlay.classList.add("is_open");
        overlay.setAttribute("aria-hidden", "false");

        const close = (run_on_close = true) => {
            overlay.classList.remove("is_open");
            overlay.setAttribute("aria-hidden", "true");
            overlay.style.display = "none";
            if (run_on_close && on_close) {
                try {
                    on_close();
                } catch (_error) {
                    // ignore
                }
            }
        };

        closeButton.onclick = () => close(true);
        okButton.onclick = () => {
            close(false);
            if (on_ok) {
                try {
                    on_ok();
                } catch (_error) {
                    // ignore
                }
            }
        };
        overlay.onclick = (event) => {
            if (event.target === overlay) {
                close(true);
            }
        };
        document.addEventListener(
            "keydown",
            (event) => {
                if (event.key === "Escape") close(true);
            },
            { once: true }
        );
        try {
            okButton.focus();
        } catch (_e) {
            // ignore
        }
    };

    window.openMessageModal = openMessageModal;
    let global_green_non_modal_timer = null;
    window.showGreenNonModalV2 = (message_text) => {
        let toast = document.getElementById("green_non_modal_v2");
        if (!toast) {
            toast = document.createElement("div");
            toast.id = "green_non_modal_v2";
            toast.className = "green_non_modal_v2";
            document.body.appendChild(toast);
        }
        toast.textContent = String(message_text || "");
        toast.classList.add("is_open");
        if (global_green_non_modal_timer) {
            clearTimeout(global_green_non_modal_timer);
        }
        global_green_non_modal_timer = setTimeout(() => {
            toast.classList.remove("is_open");
            global_green_non_modal_timer = null;
        }, 1400);
    };
    let center_non_modal_v2_timer = null;
    window.showCenterNonModalV2 = (message_text, type_name = "info") => {
        let toast = document.getElementById("center_non_modal_v2");
        if (!toast) {
            toast = document.createElement("div");
            toast.id = "center_non_modal_v2";
            toast.className = "center_non_modal_v2";
            document.body.appendChild(toast);
        }
        const normalized_type = String(type_name || "info").toLowerCase();
        toast.classList.remove("success", "error", "info");
        toast.classList.add(normalized_type);
        toast.textContent = String(message_text || "");
        toast.classList.add("is_open");
        if (center_non_modal_v2_timer) {
            clearTimeout(center_non_modal_v2_timer);
        }
        center_non_modal_v2_timer = setTimeout(() => {
            toast.classList.remove("is_open");
            center_non_modal_v2_timer = null;
        }, 1600);
    };
    window.showBlueNonModalV2 = (message_text) => {
        window.showCenterNonModalV2(message_text, "info");
    };

    const read_cookie_value = (cookie_name) => {
        const all_cookies = String(document.cookie || "").split(";");
        for (const cookie_part of all_cookies) {
            const [name_part, ...value_parts] = cookie_part.trim().split("=");
            if (name_part !== cookie_name) {
                continue;
            }
            return decodeURIComponent(value_parts.join("=") || "");
        }
        return "";
    };
    const get_storage_user_suffix = () => {
        const role_name = (read_cookie_value("role_name") || "anon").trim() || "anon";
        const phone_number = (read_cookie_value("phone_number") || "anon").trim() || "anon";
        const normalize = (value) => String(value).replace(/[^a-zA-Z0-9_\-]/g, "_");
        return `${normalize(role_name)}:${normalize(phone_number)}`;
    };

    const init_resizable_basic_tables = () => {
        const all_basic_tables = Array.from(document.querySelectorAll("table.basic_table"));
        if (all_basic_tables.length === 0) {
            return;
        }

        all_basic_tables.forEach((table_element, table_index) => {
            if (!(table_element instanceof HTMLTableElement)) {
                return;
            }
            if (table_element.id === "admin_grid_table") {
                return;
            }
            if (table_element.dataset.resizableInitDone === "1") {
                return;
            }
            table_element.dataset.resizableInitDone = "1";

            const header_cells = Array.from(table_element.querySelectorAll("thead th"));
            if (header_cells.length === 0) {
                return;
            }

            const table_key = table_element.id
                ? `id:${table_element.id}`
                : `idx:${table_index}`;
            const storage_key = `basic_table_col_widths_v1:${get_storage_user_suffix()}:${window.location.pathname}:${table_key}`;
            let saved_widths = {};
            try {
                saved_widths = JSON.parse(localStorage.getItem(storage_key) || "{}");
            } catch (_error) {
                saved_widths = {};
            }

            let active_header_cell = null;
            let active_header_index = -1;
            const column_resize_min_width = 8;
            let active_min_width = column_resize_min_width;
            let start_x = 0;
            let start_width = 0;

            const measure_canvas = document.createElement("canvas");
            const measure_context = measure_canvas.getContext("2d");
            const measure_text_width = (text) => {
                const normalized = String(text || "").trim();
                if (!measure_context) {
                    return Math.max(column_resize_min_width, normalized.length * 10 + 16);
                }
                const table_style = getComputedStyle(table_element);
                measure_context.font =
                    table_style.font || `${table_style.fontWeight} ${table_style.fontSize} ${table_style.fontFamily}`;
                return Math.max(column_resize_min_width, Math.ceil(measure_context.measureText(normalized).width) + 14);
            };

            const save_widths = () => {
                const payload = {};
                header_cells.forEach((header_cell, index) => {
                    if (!(header_cell instanceof HTMLElement)) {
                        return;
                    }
                    if (header_cell.classList.contains("hidden_id_column") || header_cell.classList.contains("hidden_audit_column")) {
                        return;
                    }
                    const width_value = Math.ceil(header_cell.getBoundingClientRect().width);
                    if (width_value > 0) {
                        payload[String(index)] = width_value;
                    }
                });
                try {
                    localStorage.setItem(storage_key, JSON.stringify(payload));
                } catch (_error) {
                    // ignore storage errors
                }
            };

            const on_mouse_move = (event) => {
                if (!active_header_cell) {
                    return;
                }
                const delta_x = event.clientX - start_x;
                const next_width = Math.max(active_min_width, Math.ceil(start_width + delta_x));
                active_header_cell.style.width = `${next_width}px`;
                active_header_cell.style.minWidth = `${next_width}px`;
            };

            const on_mouse_up = () => {
                active_header_cell = null;
                active_header_index = -1;
                document.body.style.cursor = "";
                document.body.style.userSelect = "";
                window.removeEventListener("mousemove", on_mouse_move);
                window.removeEventListener("mouseup", on_mouse_up);
                save_widths();
            };

            header_cells.forEach((header_cell, index) => {
                if (!(header_cell instanceof HTMLElement)) {
                    return;
                }
                if (header_cell.classList.contains("hidden_id_column") || header_cell.classList.contains("hidden_audit_column")) {
                    return;
                }

                const text_min_width = measure_text_width(header_cell.textContent || "");
                const saved_width = Number(saved_widths[String(index)] || 0);
                const base_width = Math.ceil(header_cell.getBoundingClientRect().width || 0);
                const apply_width = Math.max(
                    column_resize_min_width,
                    saved_width || base_width || text_min_width
                );
                header_cell.style.width = `${apply_width}px`;
                header_cell.style.minWidth = `${apply_width}px`;

                if (header_cell.querySelector(".column_resize_handle")) {
                    return;
                }
                const handle = document.createElement("span");
                handle.className = "column_resize_handle";
                handle.addEventListener("mousedown", (event) => {
                    event.preventDefault();
                    active_header_cell = header_cell;
                    active_header_index = index;
                    active_min_width = column_resize_min_width;
                    start_x = event.clientX;
                    start_width = header_cell.getBoundingClientRect().width;
                    document.body.style.cursor = "col-resize";
                    document.body.style.userSelect = "none";
                    window.addEventListener("mousemove", on_mouse_move);
                    window.addEventListener("mouseup", on_mouse_up);
                });
                header_cell.appendChild(handle);
            });
        });
    };
    init_resizable_basic_tables();

    const init_short_value_cell_alignment = () => {
        const tables = Array.from(document.querySelectorAll("table.basic_table"));
        if (tables.length === 0) {
            return;
        }

        const get_cell_display_value = (cell) => {
            const input = cell.querySelector("input, textarea");
            if (input && "value" in input) {
                return String(input.value || "").trim();
            }
            const select = cell.querySelector("select");
            if (select && "selectedIndex" in select) {
                const selected_option = select.options[select.selectedIndex];
                if (selected_option) {
                    return String(selected_option.textContent || "").trim();
                }
            }
            return String(cell.textContent || "").trim();
        };

        const update_cell_alignment = (cell) => {
            if (!(cell instanceof HTMLTableCellElement)) {
                return;
            }
            const value_text = get_cell_display_value(cell);
            const value_length = value_text.length;
            if (value_length > 0 && value_length < 20) {
                cell.classList.add("short_value_center");
            } else {
                cell.classList.remove("short_value_center");
            }
        };

        const update_table_alignment = (table) => {
            table.querySelectorAll("td").forEach((cell) => update_cell_alignment(cell));
        };

        tables.forEach((table) => {
            update_table_alignment(table);
            table.addEventListener(
                "input",
                (event) => {
                    const target_cell = event.target && event.target.closest ? event.target.closest("td") : null;
                    if (target_cell) {
                        update_cell_alignment(target_cell);
                    }
                },
                true
            );
            table.addEventListener(
                "change",
                (event) => {
                    const target_cell = event.target && event.target.closest ? event.target.closest("td") : null;
                    if (target_cell) {
                        update_cell_alignment(target_cell);
                    }
                },
                true
            );

            const observer = new MutationObserver(() => {
                update_table_alignment(table);
            });
            observer.observe(table, {
                childList: true,
                subtree: true,
                characterData: true,
            });
        });
    };
    init_short_value_cell_alignment();

    const init_scroll_position_persistence = () => {
        const storage_key = `scroll_positions_v1:${window.location.pathname}`;
        let saved_positions = {};
        try {
            saved_positions = JSON.parse(localStorage.getItem(storage_key) || "{}");
        } catch (_error) {
            saved_positions = {};
        }

        const collect_scroll_targets = () => {
            const targets = [];
            const scrolling_root =
                document.scrollingElement || document.documentElement || document.body;
            if (scrolling_root) {
                targets.push(scrolling_root);
            }
            const all_elements = document.querySelectorAll("*");
            for (const element of all_elements) {
                if (!(element instanceof HTMLElement)) {
                    continue;
                }
                if (element === document.body || element === document.documentElement) {
                    continue;
                }
                const can_scroll_x = element.scrollWidth > element.clientWidth + 1;
                const can_scroll_y = element.scrollHeight > element.clientHeight + 1;
                if (can_scroll_x || can_scroll_y) {
                    targets.push(element);
                }
            }
            return targets;
        };

        const get_target_key = (target, index) => {
            const scrolling_root =
                document.scrollingElement || document.documentElement || document.body;
            if (target === scrolling_root) {
                return "__window__";
            }
            const id_value = String(target.id || "").trim();
            if (id_value) {
                return `id:${id_value}`;
            }
            return `idx:${index}:${target.tagName.toLowerCase()}`;
        };

        const restore_positions = () => {
            const targets = collect_scroll_targets();
            targets.forEach((target, index) => {
                const key = get_target_key(target, index);
                const position = saved_positions[key];
                if (!position) {
                    return;
                }
                const left = Number(position.left || 0);
                const top = Number(position.top || 0);
                if (key === "__window__") {
                    window.scrollTo(left, top);
                    return;
                }
                target.scrollLeft = left;
                target.scrollTop = top;
            });
        };

        let save_timer = null;
        const save_positions = () => {
            const next_positions = {};
            const targets = collect_scroll_targets();
            targets.forEach((target, index) => {
                const key = get_target_key(target, index);
                const left = Math.max(0, Math.floor(target.scrollLeft || 0));
                const top = Math.max(0, Math.floor(target.scrollTop || 0));
                if (!left && !top) {
                    return;
                }
                next_positions[key] = { left, top };
            });
            try {
                localStorage.setItem(storage_key, JSON.stringify(next_positions));
                saved_positions = next_positions;
            } catch (_error) {
                // ignore storage errors
            }
        };

        const queue_save = () => {
            if (save_timer) {
                clearTimeout(save_timer);
            }
            save_timer = setTimeout(() => {
                save_timer = null;
                save_positions();
            }, 120);
        };

        window.addEventListener("scroll", queue_save, { passive: true });
        document.addEventListener(
            "scroll",
            (event) => {
                if (event.target instanceof HTMLElement) {
                    queue_save();
                }
            },
            true
        );
        window.addEventListener("beforeunload", save_positions);

        const restore_with_stabilization = () => {
            restore_positions();
            requestAnimationFrame(() => restore_positions());
            setTimeout(() => restore_positions(), 260);
        };

        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", restore_with_stabilization, { once: true });
        } else {
            restore_with_stabilization();
        }
    };
    init_scroll_position_persistence();

    const tester_grid_body = document.getElementById("tester_grid_body");
    const col_fill_button = document.getElementById("col_fill_button");
    const add_row_button = document.getElementById("add_row_button");
    const select_all_rows_button = document.getElementById("select_all_rows_button");
    const delete_selected_rows_button = document.getElementById("delete_selected_rows_button");
    const save_all_rows_button = document.getElementById("save_all_rows_button");
    const tester_submit_submission_button = document.getElementById(
        "tester_submit_submission_button"
    );
    const save_validation_notice = document.getElementById("save_validation_notice");
    const tester_dropdown_options_json = document.getElementById("tester_dropdown_options_json");
    const pending_deleted_row_ids = new Set();

    if (!tester_grid_body || !save_validation_notice) {
        return;
    }
    const current_display_name = (tester_grid_body.dataset.currentDisplayName || "").trim();
    const current_company_name = (tester_grid_body.dataset.currentCompanyName || "").trim();
    const tester_submission_display = document.getElementById("tester_active_submission_display");
    const tester_form_submission_id_hidden = document.getElementById(
        "tester_form_submission_id_value"
    );
    const tester_submission_id_hidden = null;
    const tester_start_submission_button = document.getElementById("tester_start_submission_button");
    let updateSaveControlsState = () => {};
    let queueAutoSave = () => {};
    let is_submission_submitted = false;

    const is_placeholder_submission_text = (text) => {
        const value = (text || "").trim();
        return !value || value === "자동계산" || value === "양식 재발급 필요";
    };

    const getActiveFormSubmissionId = () => {
        const fromHidden = tester_form_submission_id_hidden
            ? (tester_form_submission_id_hidden.value || "").trim()
            : "";
        if (fromHidden) {
            return fromHidden;
        }
        return (tester_grid_body.dataset.activeFormSubmissionId || "").trim() || null;
    };

    const setActiveFormSubmissionId = (form_submission_id) => {
        const v = (form_submission_id || "").trim();
        if (v) {
            tester_grid_body.dataset.activeFormSubmissionId = v;
            if (tester_form_submission_id_hidden) {
                tester_form_submission_id_hidden.value = v;
            }
        } else {
            tester_grid_body.removeAttribute("data-active-form-submission-id");
            if (tester_form_submission_id_hidden) {
                tester_form_submission_id_hidden.value = "";
            }
        }
        if (tester_submission_display) {
            tester_submission_display.textContent = v || "없음";
        }
        if (!v) {
            is_submission_submitted = false;
        }
        updateSaveControlsState();
    };

    const read_submission_id_from_row = (row_element) => {
        const cell = row_element.querySelector(".submission_id_cell_value");
        if (!cell) {
            return null;
        }
        const raw = (cell.textContent || "").trim();
        if (is_placeholder_submission_text(raw)) {
            return null;
        }
        return raw;
    };

    const get_row_submission_id_for_save = (row_element) => {
        return read_submission_id_from_row(row_element) || getActiveFormSubmissionId();
    };

    const apply_active_submission_to_placeholder_rows = () => {
        const sid = getActiveFormSubmissionId();
        if (!sid) {
            return;
        }
        for (const row_element of list_editable_rows()) {
            const cell = row_element.querySelector(".submission_id_cell_value");
            if (!cell || !is_placeholder_submission_text(cell.textContent)) {
                continue;
            }
            cell.textContent = sid;
            cell.classList.remove("is_placeholder");
        }
    };

    if (tester_submission_display) {
        tester_submission_display.textContent = getActiveFormSubmissionId() || "없음";
    }

    let dropdown_options_map = {};
    if (tester_dropdown_options_json) {
        try {
            dropdown_options_map = JSON.parse(tester_dropdown_options_json.textContent || "{}");
        } catch (_error) {
            dropdown_options_map = {};
        }
    }

    // NOTE: field_names are optional fields that can be saved when present.
    // Only a small subset is required to allow autosave/submission flow.
    const field_names = [
        "field_01", // 월 (required)
        "field_02", // 검사대수 (required)
        "field_03", // PASS / FAIL1 (optional)
        "field_04", // PASS / FAIL2 (optional)
        "field_05", // 불량내용 (optional)
        "field_06", // 확인사항 (optional)
        "field_07", // 조치사항 (optional)
    ];
    const required_field_names = ["key_1", "key_2", "key_3", "key_4", "field_01", "field_02"];
    const field_label_map = {
        key_1: "업체명",
        key_2: "양식제출자",
        key_3: "모델명",
        key_4: "공정번호",
        field_01: "월",
        field_02: "검사대수",
        field_03: "PASS / FAIL1",
        field_04: "PASS / FAIL2",
        field_05: "불량내용",
        field_06: "확인사항",
        field_07: "조치사항",
    };
    const time_field_definitions = [
        { selector: ".low_test_started_at_cell", label: "저온 투입일" },
        { selector: ".low_test_ended_at_cell", label: "저온 완료일" },
        { selector: ".high_test_started_at_cell", label: "고온 투입일" },
        { selector: ".high_test_ended_at_cell", label: "고온 완료일" },
    ];
    const accepted_time_format_hint = "YYYY-MM-DD (요일) HH:mm:ss";

    const read_error_detail = async (response) => {
        try {
            const payload = await response.json();
            if (payload && payload.detail) {
                return payload.detail;
            }
            return "요청에 실패했습니다.";
        } catch (_error) {
            return "요청에 실패했습니다.";
        }
    };

    const set_action_buttons_disabled = (row_element, disabled) => {
        row_element.querySelector(".low_test_start_button").disabled = disabled;
        row_element.querySelector(".low_test_end_button").disabled = disabled;
        row_element.querySelector(".high_test_start_button").disabled = disabled;
        row_element.querySelector(".high_test_end_button").disabled = disabled;
    };

    const get_completion_flag = (row_element, dataset_key, input_selector) => {
        if (row_element.dataset[dataset_key] === "1") {
            return true;
        }
        if (row_element.dataset[dataset_key] === "0") {
            return false;
        }
        const has_initial_value = !!read_cell_value(row_element.querySelector(input_selector));
        row_element.dataset[dataset_key] = has_initial_value ? "1" : "0";
        return has_initial_value;
    };

    const set_completion_flag = (row_element, dataset_key, completed) => {
        row_element.dataset[dataset_key] = completed ? "1" : "0";
    };

    const is_row_review_locked = (row_element) => row_element.dataset.reviewLocked === "1";

    const lock_row_for_review_approved = (row_element) => {
        if (!row_element || is_row_review_locked(row_element)) {
            return;
        }
        row_element.dataset.reviewLocked = "1";
        row_element.classList.add("row_review_approved_lock");
        row_element.querySelectorAll("select[data-field], input[data-field], .test_timestamp_input, button, .row_select_checkbox").forEach((control) => {
            if ("disabled" in control) {
                control.disabled = true;
            }
        });
        row_element.querySelectorAll(".test_timestamp_input").forEach((input_element) => {
            if (!(input_element instanceof HTMLInputElement)) {
                return;
            }
            if (!(input_element.value || "").trim()) {
                input_element.placeholder = "입력승인 완료";
            }
        });
    };

    const update_test_action_buttons = (row_element) => {
        if (is_row_review_locked(row_element)) {
            const low_test_start_button = row_element.querySelector(".low_test_start_button");
            const low_test_end_button = row_element.querySelector(".low_test_end_button");
            const high_test_start_button = row_element.querySelector(".high_test_start_button");
            const high_test_end_button = row_element.querySelector(".high_test_end_button");
            if (low_test_start_button) low_test_start_button.style.display = "none";
            if (low_test_end_button) low_test_end_button.style.display = "none";
            if (high_test_start_button) high_test_start_button.style.display = "none";
            if (high_test_end_button) high_test_end_button.style.display = "none";
            return;
        }
        const low_test_started = get_completion_flag(
            row_element,
            "lowTestStartedDone",
            ".low_test_started_at_cell"
        );
        const low_test_ended = get_completion_flag(
            row_element,
            "lowTestEndedDone",
            ".low_test_ended_at_cell"
        );
        const high_test_started = get_completion_flag(
            row_element,
            "highTestStartedDone",
            ".high_test_started_at_cell"
        );
        const high_test_ended = get_completion_flag(
            row_element,
            "highTestEndedDone",
            ".high_test_ended_at_cell"
        );

        const low_test_started_input = row_element.querySelector(".low_test_started_at_cell");
        const low_test_ended_input = row_element.querySelector(".low_test_ended_at_cell");
        const high_test_started_input = row_element.querySelector(".high_test_started_at_cell");
        const high_test_ended_input = row_element.querySelector(".high_test_ended_at_cell");

        const low_test_start_button = row_element.querySelector(".low_test_start_button");
        const low_test_end_button = row_element.querySelector(".low_test_end_button");
        const high_test_start_button = row_element.querySelector(".high_test_start_button");
        const high_test_end_button = row_element.querySelector(".high_test_end_button");

        low_test_started_input.style.display = low_test_started ? "" : "none";
        low_test_ended_input.style.display = low_test_ended ? "" : "none";
        high_test_started_input.style.display = high_test_started ? "" : "none";
        high_test_ended_input.style.display = high_test_ended ? "" : "none";

        low_test_start_button.style.display = low_test_started ? "none" : "";
        low_test_end_button.style.display = low_test_ended ? "none" : "";
        high_test_start_button.style.display = high_test_started ? "none" : "";
        high_test_end_button.style.display = high_test_ended ? "none" : "";

        low_test_start_button.disabled = false;
        low_test_end_button.disabled = !low_test_started || low_test_ended;
        high_test_start_button.disabled = false;
        high_test_end_button.disabled = !high_test_started || high_test_ended;
    };

    const create_row_element = () => {
        const build_select_html = (field_name) => {
            const option_values = Array.isArray(dropdown_options_map[field_name])
                ? dropdown_options_map[field_name]
                : [];
            const option_html = option_values
                .map((option_value) => `<option value="${option_value}">${option_value}</option>`)
                .join("");
            return `<select data-field="${field_name}"><option value=""></option>${option_html}</select>`;
        };
        const build_pass_fail_select_html = (field_name) => {
            return `
                <select data-field="${field_name}">
                    <option value=""></option>
                    <option value="PASS">PASS</option>
                    <option value="FAIL">FAIL</option>
                </select>
            `.trim();
        };

        const active_sid = getActiveFormSubmissionId();
        const sub_text = active_sid || "자동계산";
        const sub_is_placeholder = !active_sid;

        const row_element = document.createElement("tr");
        row_element.className = "editable_row";
        row_element.dataset.id = "";
        row_element.innerHTML = `
            <td><input class="row_select_checkbox" type="checkbox"></td>
            <td class="id_cell hidden_id_column"></td>
            <td><span class="submission_id_cell_value delta_value${sub_is_placeholder ? " is_placeholder" : ""}">${sub_text}</span></td>
            <td>
                <input type="hidden" data-field="key_1" value="${current_company_name}">
                <span class="company_name_cell_value delta_value${current_company_name ? "" : " is_placeholder"}">${current_company_name || "자동계산"}</span>
            </td>
            <td>
                <input type="hidden" data-field="key_2" value="${current_display_name}">
                <span class="data_writer_name_cell_value delta_value${current_display_name ? "" : " is_placeholder"}">${current_display_name || "자동계산"}</span>
            </td>
            <td>${build_select_html("key_3")}</td>
            <td>${build_select_html("key_4")}</td>
            <td>${build_select_html("field_01")}</td>
            <td>${build_select_html("field_02")}</td>
            <td class="test_action_td">
                <div class="test_action_cell">
                    <input class="low_test_started_at_cell test_timestamp_input" value="">
                    <button type="button" class="low_test_start_button">저온시험 시작</button>
                </div>
            </td>
            <td class="test_action_td">
                <div class="test_action_cell">
                    <input class="low_test_ended_at_cell test_timestamp_input" value="">
                    <button type="button" class="low_test_end_button">저온시험 종료</button>
                </div>
            </td>
            <td class="low_test_delta_cell"><span class="delta_value is_placeholder">자동계산</span></td>
            <td>${build_pass_fail_select_html("field_03")}</td>
            <td class="test_action_td">
                <div class="test_action_cell">
                    <input class="high_test_started_at_cell test_timestamp_input" value="">
                    <button type="button" class="high_test_start_button">고온시험 시작</button>
                </div>
            </td>
            <td class="test_action_td">
                <div class="test_action_cell">
                    <input class="high_test_ended_at_cell test_timestamp_input" value="">
                    <button type="button" class="high_test_end_button">고온시험 종료</button>
                </div>
            </td>
            <td class="high_test_delta_cell"><span class="delta_value is_placeholder">자동계산</span></td>
            <td>${build_pass_fail_select_html("field_04")}</td>
            <td><input data-field="field_05" value=""></td>
            <td><input data-field="field_06" value=""></td>
            <td><input data-field="field_07" value=""></td>
        `;

        const month_select = row_element.querySelector('select[data-field="field_01"]');
        if (month_select) {
            const current_month_value = String(new Date().getMonth() + 1);
            const has_month_option = Array.from(month_select.options).some(
                (option) => String(option.value || "").trim() === current_month_value
            );
            if (!has_month_option) {
                const month_option = document.createElement("option");
                month_option.value = current_month_value;
                month_option.textContent = current_month_value;
                month_select.appendChild(month_option);
            }
            month_select.value = current_month_value;
        }

        const count_select = row_element.querySelector('select[data-field="field_02"]');
        if (count_select) {
            const default_count_value = "1";
            const has_count_option = Array.from(count_select.options).some(
                (option) => String(option.value || "").trim() === default_count_value
            );
            if (!has_count_option) {
                const count_option = document.createElement("option");
                count_option.value = default_count_value;
                count_option.textContent = default_count_value;
                count_select.appendChild(count_option);
            }
            count_select.value = default_count_value;
        }
        return row_element;
    };

    const read_trimmed_value = (row_element, field_name) => {
        const input = row_element.querySelector(`[data-field="${field_name}"]`);
        if (!input) {
            return "";
        }
        if ("value" in input) {
            return (input.value || "").trim();
        }
        return (input.textContent || "").trim();
    };

    const apply_compact_width_to_input = (input_element) => {
        return input_element;
    };

    const bind_compact_width_behavior = (row_element) => {
        const input_elements = row_element.querySelectorAll("input[data-field]");
        for (const input_element of input_elements) {
            apply_compact_width_to_input(input_element);
            input_element.addEventListener("input", () => {
                apply_compact_width_to_input(input_element);
            });
        }
    };

    const build_upsert_payload = (row_element) => {
        const payload = {
            key_1: read_trimmed_value(row_element, "key_1"),
            key_2: read_trimmed_value(row_element, "key_2"),
            key_3: read_trimmed_value(row_element, "key_3"),
            key_4: read_trimmed_value(row_element, "key_4"),
        };

        for (const field_name of field_names) {
            const input = row_element.querySelector(`[data-field="${field_name}"]`);
            payload[field_name] = input.value;
        }

        const low_test_started_at_text = read_cell_value(
            row_element.querySelector(".low_test_started_at_cell")
        );
        const low_test_ended_at_text = read_cell_value(
            row_element.querySelector(".low_test_ended_at_cell")
        );
        const high_test_started_at_text = read_cell_value(
            row_element.querySelector(".high_test_started_at_cell")
        );
        const high_test_ended_at_text = read_cell_value(
            row_element.querySelector(".high_test_ended_at_cell")
        );

        const parsed_low_started = low_test_started_at_text
            ? parse_datetime_text(low_test_started_at_text)
            : null;
        payload.low_test_started_at = parsed_low_started ? parsed_low_started.toISOString() : null;
        const parsed_low_ended = low_test_ended_at_text
            ? parse_datetime_text(low_test_ended_at_text)
            : null;
        payload.low_test_ended_at = parsed_low_ended ? parsed_low_ended.toISOString() : null;
        const parsed_high_started = high_test_started_at_text
            ? parse_datetime_text(high_test_started_at_text)
            : null;
        payload.high_test_started_at = parsed_high_started ? parsed_high_started.toISOString() : null;
        const parsed_high_ended = high_test_ended_at_text
            ? parse_datetime_text(high_test_ended_at_text)
            : null;
        payload.high_test_ended_at = parsed_high_ended ? parsed_high_ended.toISOString() : null;

        const low_delta_node = row_element.querySelector(".low_test_delta_cell .delta_value");
        const low_test_delta_text = ((low_delta_node && low_delta_node.textContent) || "").trim();
        const high_delta_node = row_element.querySelector(".high_test_delta_cell .delta_value");
        const high_test_delta_text = ((high_delta_node && high_delta_node.textContent) || "").trim();
        payload.low_test_delta = low_test_delta_text === "자동계산" ? null : low_test_delta_text;
        payload.high_test_delta = high_test_delta_text === "자동계산" ? null : high_test_delta_text;

        return payload;
    };

    const trim_timestamp_input = (input_element) => {
        const trimmed_value = (input_element.value || "").trim();
        input_element.value = trimmed_value;
        return trimmed_value;
    };

    const is_timestamp_format_valid = (value) => {
        if (!value) {
            return true;
        }
        const format_regex =
            /^\d{4}-\d{2}-\d{2}\s(?:\([일월화수목금토]\)\s)?\d{2}:\d{2}:\d{2}$/;
        if (!format_regex.test(value)) {
            return false;
        }
        return parse_datetime_text(value) !== null;
    };

    const parse_datetime_text = (value) => {
        if (!value) {
            return null;
        }
        const without_weekday = value.replace(/\s\([일월화수목금토]\)\s/, " ");
        const normalized_value = without_weekday.includes("T")
            ? without_weekday
            : without_weekday.replace(" ", "T");
        const parsed = new Date(normalized_value);
        if (Number.isNaN(parsed.getTime())) {
            return null;
        }
        return parsed;
    };

    const format_two_digits = (value) => String(value).padStart(2, "0");
    const weekday_names = ["일", "월", "화", "수", "목", "금", "토"];

    const format_datetime_display = (date_value) => {
        const year = date_value.getFullYear();
        const month = format_two_digits(date_value.getMonth() + 1);
        const day = format_two_digits(date_value.getDate());
        const hours = format_two_digits(date_value.getHours());
        const minutes = format_two_digits(date_value.getMinutes());
        const seconds = format_two_digits(date_value.getSeconds());
        const weekday = weekday_names[date_value.getDay()];
        return `${year}-${month}-${day} (${weekday}) ${hours}:${minutes}:${seconds}`;
    };

    const get_now_timestamp_info = () => {
        const now = new Date();
        return {
            iso: now.toISOString(),
            display: format_datetime_display(now),
        };
    };

    const set_timestamp_cell = (cell_element, timestamp_info) => {
        if ("value" in cell_element) {
            cell_element.value = timestamp_info.display;
        } else {
            cell_element.textContent = timestamp_info.display;
        }
        cell_element.dataset.iso = timestamp_info.iso;
    };

    const read_cell_value = (cell_element) => {
        if ("value" in cell_element) {
            return cell_element.value.trim();
        }
        return cell_element.textContent.trim();
    };

    const parse_datetime_from_cell = (cell_element) => {
        const raw_value = read_cell_value(cell_element);
        const parsed_from_raw = parse_datetime_text(raw_value);
        if (parsed_from_raw) {
            return parsed_from_raw;
        }
        const iso_value = cell_element.dataset.iso || "";
        if (iso_value) {
            return parse_datetime_text(iso_value);
        }
        return null;
    };

    const normalize_timestamp_cell_display = (cell_element) => {
        const parsed = parse_datetime_from_cell(cell_element);
        if (!parsed) {
            return;
        }
        set_timestamp_cell(cell_element, {
            iso: parsed.toISOString(),
            display: format_datetime_display(parsed),
        });
    };

    const format_duration = (milliseconds) => {
        const total_seconds = Math.floor(milliseconds / 1000);
        const hours = String(Math.floor(total_seconds / 3600)).padStart(2, "0");
        const minutes = String(Math.floor((total_seconds % 3600) / 60)).padStart(2, "0");
        const seconds = String(total_seconds % 60).padStart(2, "0");
        return `${hours}:${minutes}:${seconds}`;
    };

    const render_delta_from_timestamps = (row_element, test_type) => {
        const started_cell = row_element.querySelector(`.${test_type}_started_at_cell`);
        const ended_cell = row_element.querySelector(`.${test_type}_ended_at_cell`);
        const delta_cell = row_element.querySelector(`.${test_type}_delta_cell`);
        const delta_value = delta_cell.querySelector(".delta_value") || delta_cell;
        const started_at = parse_datetime_from_cell(started_cell);
        const ended_at = parse_datetime_from_cell(ended_cell);

        if (!started_at || !ended_at || ended_at < started_at) {
            delta_value.textContent = "자동계산";
            delta_value.classList.add("is_placeholder");
            return;
        }
        delta_value.textContent = format_duration(ended_at.getTime() - started_at.getTime());
        delta_value.classList.remove("is_placeholder");
    };

    const upsert_row = async (row_element, row_index_for_message) => {
        const payload = build_upsert_payload(row_element);
        const sid = get_row_submission_id_for_save(row_element);
        if (sid) {
            payload.form_submission_id = sid;
        }
        const has_any_value =
            !!payload.key_1 ||
            !!payload.key_2 ||
            !!payload.key_3 ||
            !!payload.key_4 ||
            field_names.some((field_name) => String(payload[field_name] || "").trim() !== "") ||
            !!payload.low_test_started_at ||
            !!payload.low_test_ended_at ||
            !!payload.high_test_started_at ||
            !!payload.high_test_ended_at ||
            !!payload.low_test_delta ||
            !!payload.high_test_delta;
        if (!has_any_value) {
            return true;
        }
        if (!payload.key_1 || !payload.key_2 || !payload.key_3 || !payload.key_4) {
            openMessageModal(
                `${row_index_for_message}번째 행: 업체명, 양식제출자, 모델명, 공정번호는 모두 필수입니다.`
            );
            return false;
        }

        try {
            const response = await fetch("/user/rows/upsert", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            if (!response.ok) {
                openMessageModal(await read_error_detail(response));
                return false;
            }

            const upsert_result = await response.json();
            row_element.dataset.id = String(upsert_result.id);
            row_element.querySelector(".id_cell").textContent = String(upsert_result.id);
            row_element.querySelector('[data-field="key_1"]').value = upsert_result.key_1;
            row_element.querySelector('[data-field="key_2"]').value = upsert_result.key_2;
            row_element.querySelector('[data-field="key_3"]').value = upsert_result.key_3;
            row_element.querySelector('[data-field="key_4"]').value = upsert_result.key_4;
            apply_compact_width_to_input(row_element.querySelector('[data-field="key_1"]'));
            apply_compact_width_to_input(row_element.querySelector('[data-field="key_2"]'));
            apply_compact_width_to_input(row_element.querySelector('[data-field="key_3"]'));
            apply_compact_width_to_input(row_element.querySelector('[data-field="key_4"]'));
            update_test_action_buttons(row_element);
            return true;
        } catch (_error) {
            openMessageModal("네트워크 오류가 발생했습니다.");
            return false;
        }
    };

    const list_editable_rows = () =>
        Array.from(tester_grid_body.querySelectorAll("tr.editable_row")).filter(
            (row_element) => !is_row_review_locked(row_element)
        );
    updateSaveControlsState = () => {
        let hasContext = !!getActiveFormSubmissionId();
        if (!hasContext) {
            for (const r of list_editable_rows()) {
                if (read_submission_id_from_row(r)) {
                    hasContext = true;
                    break;
                }
            }
        }
        const allow_edit = hasContext && !is_submission_submitted;
        if (tester_submit_submission_button) tester_submit_submission_button.disabled = !allow_edit;
        if (add_row_button) {
            add_row_button.disabled = !!is_submission_submitted;
        }
        for (const el of [col_fill_button, select_all_rows_button, delete_selected_rows_button]) {
            if (el) {
                el.disabled = !allow_edit;
            }
        }
    };
    const list_selected_rows = () =>
        list_editable_rows().filter((row_element) => {
            const checkbox = row_element.querySelector(".row_select_checkbox");
            return checkbox && checkbox.checked;
        });

    const update_select_all_button_label = () => {
        if (!select_all_rows_button) {
            return;
        }
        const editable_rows = list_editable_rows();
        if (editable_rows.length === 0) {
            select_all_rows_button.textContent = "모든 행 선택";
            return;
        }
        const all_selected = editable_rows.every((row_element) => {
            const checkbox = row_element.querySelector(".row_select_checkbox");
            return checkbox && checkbox.checked;
        });
        select_all_rows_button.textContent = all_selected ? "모든 행 해제" : "모든 행 선택";
    };

    const set_meta_auto_value = (row_element, selector, value_text) => {
        const cell_value = row_element.querySelector(selector);
        if (!cell_value) {
            return;
        }
        const normalized_text = String(value_text || "").trim();
        if (!normalized_text) {
            cell_value.textContent = "자동계산";
            cell_value.classList.add("is_placeholder");
            return;
        }
        cell_value.textContent = normalized_text;
        cell_value.classList.remove("is_placeholder");
    };

    const render_non_modal_notice = (message_lines, notice_type) => {
        save_validation_notice.className = `non_modal_notice ${notice_type}`;
        save_validation_notice.innerHTML = message_lines.map((line) => `<div>${line}</div>`).join("");
    };

    const clear_non_modal_notice = () => {
        save_validation_notice.className = "non_modal_notice";
        save_validation_notice.innerHTML = "";
    };

    let auto_save_timer = null;
    let auto_save_in_progress = false;
    let auto_save_requested_again = false;

    const run_auto_save = async () => {
        if (auto_save_in_progress) {
            auto_save_requested_again = true;
            return;
        }
        auto_save_in_progress = true;
        try {
            const save_ok = await save_all_rows_now(false);
            if (save_ok) {
                window.showGreenNonModalV2("자동저장 되었습니다.");
            }
        } finally {
            auto_save_in_progress = false;
            if (auto_save_requested_again) {
                auto_save_requested_again = false;
                queueAutoSave();
            }
        }
    };

    queueAutoSave = () => {
        if (is_submission_submitted) {
            return;
        }
        if (auto_save_timer) {
            clearTimeout(auto_save_timer);
        }
        auto_save_timer = setTimeout(() => {
            auto_save_timer = null;
            run_auto_save();
        }, 600);
    };

    const get_missing_column_descriptions = (row_element) =>
        required_field_names
            .map((field_name, index) => {
                const input_element = row_element.querySelector(`[data-field="${field_name}"]`);
                const value = input_element ? input_element.value.trim() : "";
                if (value) {
                    return null;
                }
                return `${index + 1}번(${field_label_map[field_name]})`;
            })
            .filter(Boolean);

    const has_any_user_entered_value = (row_element) => {
        for (const field_name of ["key_3", "key_4", ...field_names]) {
            const field_element = row_element.querySelector(`[data-field="${field_name}"]`);
            const value = field_element && "value" in field_element ? (field_element.value || "").trim() : "";
            if (value) {
                return true;
            }
        }
        for (const field of time_field_definitions) {
            const input_element = row_element.querySelector(field.selector);
            if (!input_element) {
                continue;
            }
            const value = (input_element.value || "").trim();
            if (value) {
                return true;
            }
        }
        return false;
    };

    if (col_fill_button) {
        col_fill_button.addEventListener("click", () => {
            clear_non_modal_notice();
            const editable_rows = list_editable_rows();
            if (editable_rows.length === 0) {
                openMessageModal("샘플 작성할 행이 없습니다.");
                return;
            }

            for (const row_element of editable_rows) {
                for (const field_name of required_field_names) {
                    const field_element = row_element.querySelector(`[data-field="${field_name}"]`);
                    if (!field_element) {
                        continue;
                    }
                    if (field_name === "key_2" && current_display_name && !field_element.value.trim()) {
                        field_element.value = current_display_name;
                        const writer_span = row_element.querySelector(".data_writer_name_cell_value");
                        if (writer_span) {
                            writer_span.textContent = current_display_name;
                            writer_span.classList.remove("is_placeholder");
                        }
                        continue;
                    }
                    if (!field_element.value.trim()) {
                        if (field_element.tagName === "SELECT") {
                            const first_option = Array.from(field_element.options).find(
                                (option) => (option.value || "").trim() !== ""
                            );
                            if (first_option) {
                                field_element.value = first_option.value;
                            }
                            continue;
                        }
                        field_element.value = "col_value";
                        apply_compact_width_to_input(field_element);
                    }
                }
            }
            queueAutoSave();
        });
    }

    const post_test_action = async (row_element, action_path) => {
        const low_test_started_cell = row_element.querySelector(".low_test_started_at_cell");
        const low_test_ended_cell = row_element.querySelector(".low_test_ended_at_cell");
        const high_test_started_cell = row_element.querySelector(".high_test_started_at_cell");
        const high_test_ended_cell = row_element.querySelector(".high_test_ended_at_cell");

        if (action_path === "low_test/end") {
            const started_at = parse_datetime_from_cell(low_test_started_cell);
            if (!started_at) {
                openMessageModal("저온 투입일이 없습니다. 먼저 저온 투입 버튼을 눌러주세요.");
                return;
            }
            if (new Date() < started_at) {
                openMessageModal(
                    "저온 완료일은 저온 투입일보다 빠를 수 없습니다. 투입일을 먼저 확인해 주세요."
                );
                return;
            }
        }
        if (action_path === "high_test/end") {
            const started_at = parse_datetime_from_cell(high_test_started_cell);
            if (!started_at) {
                openMessageModal("고온 투입일이 없습니다. 먼저 고온 투입 버튼을 눌러주세요.");
                return;
            }
            if (new Date() < started_at) {
                openMessageModal(
                    "고온 완료일은 고온 투입일보다 빠를 수 없습니다. 투입일을 먼저 확인해 주세요."
                );
                return;
            }
        }

        if (action_path === "low_test/start") {
            set_timestamp_cell(low_test_started_cell, get_now_timestamp_info());
            set_completion_flag(row_element, "lowTestStartedDone", true);
        } else if (action_path === "low_test/end") {
            set_timestamp_cell(low_test_ended_cell, get_now_timestamp_info());
            set_completion_flag(row_element, "lowTestEndedDone", true);
        } else if (action_path === "high_test/start") {
            set_timestamp_cell(high_test_started_cell, get_now_timestamp_info());
            set_completion_flag(row_element, "highTestStartedDone", true);
        } else if (action_path === "high_test/end") {
            set_timestamp_cell(high_test_ended_cell, get_now_timestamp_info());
            set_completion_flag(row_element, "highTestEndedDone", true);
        }
        render_delta_from_timestamps(row_element, "low_test");
        render_delta_from_timestamps(row_element, "high_test");
        update_test_action_buttons(row_element);
    };

    const bind_row_actions = (row_element) => {
        const row_select_checkbox = row_element.querySelector(".row_select_checkbox");
        if (row_select_checkbox) {
            row_select_checkbox.addEventListener("change", update_select_all_button_label);
        }

        const timestamp_inputs = row_element.querySelectorAll(".test_timestamp_input");
        for (const timestamp_input of timestamp_inputs) {
            normalize_timestamp_cell_display(timestamp_input);
            timestamp_input.addEventListener("input", () => {
                delete timestamp_input.dataset.iso;
                render_delta_from_timestamps(row_element, "low_test");
                render_delta_from_timestamps(row_element, "high_test");
                update_test_action_buttons(row_element);
                queueAutoSave();
            });
            timestamp_input.addEventListener("change", () => {
                queueAutoSave();
            });
        }

        const editable_fields = row_element.querySelectorAll("select[data-field], input[data-field]");
        for (const editable_field of editable_fields) {
            editable_field.addEventListener("change", () => {
                queueAutoSave();
            });
            editable_field.addEventListener("input", () => {
                queueAutoSave();
            });
        }

        render_delta_from_timestamps(row_element, "low_test");
        render_delta_from_timestamps(row_element, "high_test");
        update_test_action_buttons(row_element);

        row_element
            .querySelector(".low_test_start_button")
            .addEventListener("click", async () => {
                await post_test_action(row_element, "low_test/start");
                queueAutoSave();
            });
        row_element
            .querySelector(".low_test_end_button")
            .addEventListener("click", async () => {
                await post_test_action(row_element, "low_test/end");
                queueAutoSave();
            });
        row_element
            .querySelector(".high_test_start_button")
            .addEventListener("click", async () => {
                await post_test_action(row_element, "high_test/start");
                queueAutoSave();
            });
        row_element
            .querySelector(".high_test_end_button")
            .addEventListener("click", async () => {
                await post_test_action(row_element, "high_test/end");
                queueAutoSave();
            });
    };

    if (add_row_button) {
        add_row_button.addEventListener("click", () => {
            clear_non_modal_notice();
            const row_element = create_row_element();
            tester_grid_body.appendChild(row_element);
            bind_compact_width_behavior(row_element);
            bind_row_actions(row_element);
        });
    }

    if (delete_selected_rows_button) {
        delete_selected_rows_button.addEventListener("click", () => {
            clear_non_modal_notice();
            const selected_rows = list_selected_rows();
            if (selected_rows.length === 0) {
                openMessageModal("선택한 행이 없습니다.");
                return;
            }
            for (const row_element of selected_rows) {
                const existing_id = Number((row_element.dataset.id || "").trim());
                if (Number.isInteger(existing_id) && existing_id > 0) {
                    pending_deleted_row_ids.add(existing_id);
                }
                row_element.remove();
            }
            update_select_all_button_label();
            queueAutoSave();
        });
    }

    if (select_all_rows_button) {
        select_all_rows_button.addEventListener("click", () => {
            clear_non_modal_notice();
            const editable_rows = list_editable_rows();
            const all_selected = editable_rows.length > 0 && editable_rows.every((row_element) => {
                const checkbox = row_element.querySelector(".row_select_checkbox");
                return checkbox && checkbox.checked;
            });
            for (const row_element of editable_rows) {
                const checkbox = row_element.querySelector(".row_select_checkbox");
                if (checkbox) {
                    checkbox.checked = !all_selected;
                }
            }
            update_select_all_button_label();
        });
    }

    if (tester_start_submission_button) {
        tester_start_submission_button.addEventListener("click", async () => {
            clear_non_modal_notice();
            const created_submission_id = await create_submission_id_if_missing(true);
            if (created_submission_id) {
                render_non_modal_notice(
                    [`새로운 양식제출ID(${created_submission_id}) 가 발급되었습니다.`],
                    "success"
                );
            }
        });
    }

    const create_submission_id_if_missing = async (force_create = false) => {
        const existing_id = getActiveFormSubmissionId();
        if (existing_id && !force_create) {
            return existing_id;
        }
        try {
            const form = new FormData();
            form.set("company_name", current_company_name || "");
            form.set("display_name", current_display_name || "");
            const response = await fetch("/submission/create", {
                method: "POST",
                body: form,
            });
            if (!response.ok) {
                render_non_modal_notice(
                    [await read_error_detail(response) || "양식제출ID를 생성할 수 없습니다."],
                    "error"
                );
                updateSaveControlsState();
                return null;
            }
            const data = await response.json();
            const new_id = (data && data.form_submission_id) || "";
            if (!new_id) {
                render_non_modal_notice(["서버 응답에 form_submission_id가 없습니다."], "error");
                updateSaveControlsState();
                return null;
            }
            setActiveFormSubmissionId(new_id);
            apply_active_submission_to_placeholder_rows();
            return new_id;
        } catch (_error) {
            render_non_modal_notice(
                ["네트워크 오류로 양식제출ID를 생성하지 못했습니다. 잠시 후 다시 시도하세요."],
                "error"
            );
            updateSaveControlsState();
            return null;
        }
    };

    if (tester_submit_submission_button) {
        tester_submit_submission_button.addEventListener("click", async () => {
            clear_non_modal_notice();
            const sid = getActiveFormSubmissionId();
            if (!sid) {
                render_non_modal_notice(
                    ["양식제출ID가 없습니다. 먼저 양식 저장을 진행해 주세요."],
                    "error"
                );
                updateSaveControlsState();
                return;
            }
            try {
                const form = new FormData();
                form.set("form_submission_id", sid);
                const response = await fetch("/submission/submit", {
                    method: "POST",
                    body: form,
                });
                if (!response.ok) {
                    render_non_modal_notice(
                        [await read_error_detail(response) || "제출 완료에 실패했습니다."],
                        "error"
                    );
                    updateSaveControlsState();
                    return;
                }
                const data = await response.json();
                if (data && data.status === "submitted") {
                    is_submission_submitted = true;
                }
                render_non_modal_notice(["제출 완료되었습니다. 관리자 승인 대기 중입니다."], "success");
                updateSaveControlsState();
            } catch (_error) {
                render_non_modal_notice(
                    ["네트워크 오류로 제출 완료에 실패했습니다. 잠시 후 다시 시도하세요."],
                    "error"
                );
                updateSaveControlsState();
            }
        });
    }

    const flush_pending_deleted_rows = async () => {
        const delete_row_ids = Array.from(pending_deleted_row_ids).filter(
            (row_id) => Number.isInteger(Number(row_id)) && Number(row_id) > 0
        );
        if (delete_row_ids.length === 0) {
            return true;
        }
        try {
            const response = await fetch("/user/rows/delete", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ row_ids: delete_row_ids }),
            });
            if (!response.ok) {
                openMessageModal(await read_error_detail(response));
                return false;
            }
            pending_deleted_row_ids.clear();
            return true;
        } catch (_error) {
            openMessageModal("행 삭제 중 네트워크 오류가 발생했습니다.");
            return false;
        }
    };

    const save_all_rows_now = async (show_success_modal = false) => {
        const editable_rows = list_editable_rows();
        const has_any_row_input = editable_rows.some((row_element) =>
            has_any_user_entered_value(row_element)
        );
        let active_submission_id = getActiveFormSubmissionId();
        if (!active_submission_id && has_any_row_input) {
            active_submission_id = await create_submission_id_if_missing(false);
            if (!active_submission_id) {
                return false;
            }
        }

        const validation_messages = [];
        for (let index = 0; index < editable_rows.length; index += 1) {
            const row_element = editable_rows[index];
            for (const field of time_field_definitions) {
                const input_element = row_element.querySelector(field.selector);
                const trimmed_value = trim_timestamp_input(input_element);
                if (!is_timestamp_format_valid(trimmed_value)) {
                    await flush_pending_deleted_rows();
                    return false;
                }
                if (trimmed_value) {
                    normalize_timestamp_cell_display(input_element);
                }
            }
        }

        for (let index = 0; index < editable_rows.length; index += 1) {
            const missing_columns = get_missing_column_descriptions(editable_rows[index]);
            if (missing_columns.length > 0) {
                validation_messages.push(`${index + 1}행: ${missing_columns.join(", ")} 입력을 완료해 주세요.`);
            }
        }

        if (validation_messages.length > 0) {
            await flush_pending_deleted_rows();
            clear_non_modal_notice();
            if (window.showBlueNonModalV2) {
                window.showBlueNonModalV2(`자동저장 안내: ${validation_messages[0]}`);
            } else if (window.showCenterNonModalV2) {
                window.showCenterNonModalV2(`자동저장 안내: ${validation_messages[0]}`, "info");
            }
            return false;
        }

        const rows_payload = [];
        for (let index = 0; index < editable_rows.length; index += 1) {
            const row_element = editable_rows[index];
            const row_payload = build_upsert_payload(row_element);
            const has_any_value =
                !!row_payload.key_1 ||
                !!row_payload.key_2 ||
                !!row_payload.key_3 ||
                !!row_payload.key_4 ||
                field_names.some((field_name) => String(row_payload[field_name] || "").trim() !== "") ||
                !!row_payload.low_test_started_at ||
                !!row_payload.low_test_ended_at ||
                !!row_payload.high_test_started_at ||
                !!row_payload.high_test_ended_at ||
                !!row_payload.low_test_delta ||
                !!row_payload.high_test_delta;
            if (!has_any_value) {
                continue;
            }
            const row_submission = get_row_submission_id_for_save(row_element) || active_submission_id;
            if (!row_submission) {
                return false;
            }
            row_payload.form_submission_id = row_submission;
            rows_payload.push(row_payload);
        }

        try {
            const response = await fetch("/user/rows/save_all", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    rows: rows_payload,
                    delete_row_ids: Array.from(pending_deleted_row_ids),
                }),
            });
            if (!response.ok) {
                openMessageModal(await read_error_detail(response));
                return false;
            }
            pending_deleted_row_ids.clear();
            for (const row_element of editable_rows) {
                const row_payload = build_upsert_payload(row_element);
                const has_any_value =
                    !!row_payload.key_1 ||
                    !!row_payload.key_2 ||
                    !!row_payload.key_3 ||
                    !!row_payload.key_4 ||
                    field_names.some((field_name) => String(row_payload[field_name] || "").trim() !== "") ||
                    !!row_payload.low_test_started_at ||
                    !!row_payload.low_test_ended_at ||
                    !!row_payload.high_test_started_at ||
                    !!row_payload.high_test_ended_at ||
                    !!row_payload.low_test_delta ||
                    !!row_payload.high_test_delta;
                if (!has_any_value) {
                    continue;
                }
                const after_sid = get_row_submission_id_for_save(row_element);
                if (after_sid) {
                    set_meta_auto_value(row_element, ".submission_id_cell_value", after_sid);
                }
                set_meta_auto_value(row_element, ".company_name_cell_value", row_payload.key_1 || current_company_name);
                set_meta_auto_value(row_element, ".data_writer_name_cell_value", row_payload.key_2 || current_display_name);
            }
        } catch (_error) {
            openMessageModal("모든 행 저장 중 네트워크 오류가 발생했습니다.");
            return false;
        }
        if (show_success_modal) {
            openMessageModal("양식 저장이 완료되었습니다.", {
                type: "success",
                title: "양식 저장 완료",
                ok_text: "확인",
            });
        }
        return true;
    };

    if (save_all_rows_button) {
        save_all_rows_button.addEventListener("click", async () => {
            clear_non_modal_notice();
            await save_all_rows_now(true);
        });
    }

    const existing_rows = tester_grid_body.querySelectorAll("tr.editable_row");
    for (const row_element of existing_rows) {
        bind_compact_width_behavior(row_element);
        bind_row_actions(row_element);
    }
    const lock_reviewed_rows_from_server = async () => {
        const all_rows = Array.from(tester_grid_body.querySelectorAll("tr.editable_row"));
        const target_ids = all_rows
            .map((row_element) => Number((row_element.dataset.id || "").trim()))
            .filter((row_id) => Number.isInteger(row_id) && row_id > 0);
        if (target_ids.length === 0) {
            return;
        }
        const query = new URLSearchParams();
        target_ids.forEach((row_id) => query.append("row_ids", String(row_id)));
        try {
            const response = await fetch(`/user/rows/review_status?${query.toString()}`);
            if (!response.ok) {
                return;
            }
            const payload = await response.json();
            const reviewed_row_id_set = new Set(
                (Array.isArray(payload && payload.reviewed_row_ids) ? payload.reviewed_row_ids : [])
                    .map((row_id) => Number(row_id))
                    .filter((row_id) => Number.isInteger(row_id) && row_id > 0)
            );
            let newly_locked_count = 0;
            all_rows.forEach((row_element) => {
                const row_id = Number((row_element.dataset.id || "").trim());
                if (!Number.isInteger(row_id) || row_id <= 0) {
                    return;
                }
                if (!reviewed_row_id_set.has(row_id)) {
                    return;
                }
                if (!is_row_review_locked(row_element)) {
                    newly_locked_count += 1;
                }
                lock_row_for_review_approved(row_element);
                update_test_action_buttons(row_element);
            });
            if (newly_locked_count > 0) {
                if (window.showBlueNonModalV2) {
                    window.showBlueNonModalV2("입력승인이 되어 수정할수 없는 데이터가 생겼습니다.");
                } else if (window.showCenterNonModalV2) {
                    window.showCenterNonModalV2("입력승인이 되어 수정할수 없는 데이터가 생겼습니다.", "info");
                }
            }
        } catch (_error) {
            // ignore polling errors
        }
    };
    lock_reviewed_rows_from_server();
    window.setInterval(lock_reviewed_rows_from_server, 3000);
    update_select_all_button_label();
    updateSaveControlsState();

    // 양식제출ID는 페이지 진입 시 자동 생성하지 않고, 양식 저장(자동저장 포함) 시 생성한다.
})();

(() => {
    const procedure_forms = Array.from(
        document.querySelectorAll(".product_test_procedure_result_form")
    );
    if (procedure_forms.length === 0) {
        return;
    }

    const render_reason_hint = (status_select, reason_input, hint_node) => {
        const selected_status = String(status_select.value || "").trim();
        const skipped_reasons = String(reason_input.dataset.skippedReasons || "").trim();
        const blocked_reasons = String(reason_input.dataset.blockedReasons || "").trim();
        const requires_reason = ["failed", "blocked", "skipped"].includes(selected_status);

        reason_input.required = requires_reason;

        if (!hint_node) {
            return;
        }
        if (selected_status === "skipped" && skipped_reasons) {
            hint_node.textContent = `예시: ${skipped_reasons}`;
            return;
        }
        if (selected_status === "blocked" && blocked_reasons) {
            hint_node.textContent = `예시: ${blocked_reasons}`;
            return;
        }
        if (selected_status === "failed") {
            hint_node.textContent = "실패 원인을 구체적으로 입력해 주세요.";
            return;
        }
        hint_node.textContent = "";
    };

    procedure_forms.forEach((form_element) => {
        const status_select = form_element.querySelector(
            ".product_test_procedure_result_status_select"
        );
        const reason_input = form_element.querySelector(
            ".product_test_judgement_reason_input"
        );
        const hint_node = form_element.querySelector(".product_test_reason_hint");
        if (
            !(status_select instanceof HTMLSelectElement) ||
            !(reason_input instanceof HTMLInputElement)
        ) {
            return;
        }

        const refresh = () => render_reason_hint(status_select, reason_input, hint_node);
        status_select.addEventListener("change", refresh);
        refresh();
    });
})();
