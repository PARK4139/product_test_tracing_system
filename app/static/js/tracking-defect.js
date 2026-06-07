// tracking-defect.js -- defect image popup, defect col resize

function bindDefectImages(root) {
    const popup = document.getElementById("trk_img_popup") || (() => {
        const el = document.createElement("div"); el.id = "trk_img_popup";
        el.innerHTML = `<img id="trk_popup_img" src="">`;
        document.body.appendChild(el); return el;
    })();
    const popupImg = document.getElementById("trk_popup_img");
    root.querySelectorAll(".trk_defect_thumb").forEach(img => {
        img.addEventListener("mouseenter", () => {
            popupImg.src = img.dataset.src;
            popup.style.display = "flex";
        });
        img.addEventListener("mouseleave", () => { popup.style.display = "none"; });
    });
    root.querySelectorAll(".trk_img_file_input").forEach(input => {
        input.addEventListener("change", async e => {
            e.stopPropagation();
            const file = input.files[0]; if (!file) return;
            const defectId = input.dataset.defectId;
            const imgType  = input.dataset.imgType || "other_device";
            const formData = new FormData();
            formData.append("file", file); formData.append("img_type", imgType);
            try {
                const resp = await fetch(`/admin/api/defect/${encodeURIComponent(defectId)}/image`, { method:"POST", body:formData });
                if (!resp.ok) throw new Error(await resp.text());
                document.getElementById("trk_refresh_btn").click();
            } catch(err) { alert("upload failed: " + err.message); }
        });
    });
}

const DEFECT_COL_KEY = "trk_defect_col_widths";

function initDefectColResize(root) {
    const table = root.querySelector(".trk_defect_table");
    if (!table) return;
    const cols = Array.from(table.querySelectorAll("col.trk_col_resizable"));
    try {
        const saved = JSON.parse(uiStateGetItem(DEFECT_COL_KEY) || "[]");
        saved.forEach((w, i) => { if (cols[i] && w > 20) cols[i].style.width = w + "px"; });
    } catch(e) {}

    table.querySelectorAll("thead th .trk_col_handle").forEach((handle, idx) => {
        let startX, startW;
        handle.addEventListener("mousedown", e => {
            e.preventDefault();
            startX = e.clientX;
            startW = cols[idx] ? parseInt(cols[idx].style.width) || 80 : 80;
            document.body.style.cursor = "col-resize";
            document.body.style.userSelect = "none";
            const onMove = mv => {
                const w = Math.max(30, startW + (mv.clientX - startX));
                if (cols[idx]) cols[idx].style.width = w + "px";
            };
            const onUp = () => {
                document.body.style.cursor = "";
                document.body.style.userSelect = "";
                const widths = cols.map(c => parseInt(c.style.width) || 0);
                uiStateSetItem(DEFECT_COL_KEY, JSON.stringify(widths));
                document.removeEventListener("mousemove", onMove);
                document.removeEventListener("mouseup", onUp);
            };
            document.addEventListener("mousemove", onMove);
            document.addEventListener("mouseup", onUp);
        });
    });
}
