// tracking-defect.js — defect image popup, defect col resize
/* ── 결함 이미지 업로드 + hover 팝업 ───────────────────── */
function bindDefectImages(root) {
    const popup = document.getElementById("trk_img_popup") || (() => {
        const el = document.createElement("div"); el.id = "trk_img_popup";
        el.innerHTML = `<img id="trk_popup_img" src="">`;
        document.body.appendChild(el); return el;
    })();
    const popupImg = document.getElementById("trk_popup_img");
    root.querySelectorAll(".trk_defect_thumb").forEach(img => {
        img.addEventListener("mouseenter", () => {
            popupImg.src = img.dataset.src; popup.style.display = "block";
            const rect = img.getBoundingClientRect();
            const pw = window.innerWidth * 0.7 + 12, ph = window.innerHeight * 0.7 + 12;
            let left = rect.right + 10, top = rect.top;
            if (left + pw > window.innerWidth)  left = Math.max(8, rect.left - pw - 10);
            if (top  + ph > window.innerHeight) top  = Math.max(8, window.innerHeight - ph - 8);
            popup.style.left = left + "px"; popup.style.top = top + "px";
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
            } catch(err) { alert("업로드 실패: " + err.message); }
        });
    });
}

/* ── 결함 테이블 컬럼 리사이즈 ──────────────────────────── */
