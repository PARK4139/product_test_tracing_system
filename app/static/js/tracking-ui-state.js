// tracking-ui-state.js — DB 또는 localStorage 에 화면 UI 상태(탭 순서/접기/활성탭/라벨/뷰모드 등)를 저장하는 동기 캐시 래퍼
// 기본 모드: "db"    → 서버 DB(ui_state_pref)에 저장. 같은 DB를 다른 PC에서 clone 해도 화면 상태가 유지된다.
// 옵션 모드: "local" → 이 브라우저의 localStorage 에만 저장(기존 동작과 동일, 공유 안 됨).
//
// 사용법: 기존의 localStorage.getItem/setItem/removeItem 호출을
//        uiStateGetItem/uiStateSetItem/uiStateRemoveItem 으로 교체하면 된다.
// 내부적으로는 항상 localStorage 를 "동기 캐시"로 그대로 사용한다(호출부의 동기 흐름이 깨지지 않도록).
// DB 모드에서는 값이 바뀔 때마다 디바운스된 백그라운드 PUT/DELETE 로 서버에도 반영한다.
// 부팅 시 hydrateUiStateFromServer() 를 한 번 호출해 서버 값으로 localStorage 를 먼저 덮어써서,
// 다른 PC에서 같은 DB로 열어도 동일한 화면 상태로 시작하도록 한다.
(function () {
    var UI_STATE_MODE_KEY = "trk_ui_state_mode"; // localStorage 에 저장되는 모드 키: "db" | "local"
    var UI_STATE_API_BASE = "/admin/api/ui-state";
    var SAVE_DEBOUNCE_MS = 500;
    var saveTimers = Object.create(null);

    function getUiStateMode() {
        try {
            var m = window.localStorage.getItem(UI_STATE_MODE_KEY);
            return m === "local" ? "local" : "db"; // 기본값 = db
        } catch (e) {
            return "db";
        }
    }

    function setUiStateMode(mode) {
        var v = (mode === "local") ? "local" : "db";
        try { window.localStorage.setItem(UI_STATE_MODE_KEY, v); } catch (e) {}
        return v;
    }

    function isUiStateDbMode() {
        return getUiStateMode() !== "local";
    }

    function uiStateGetItem(key) {
        try { return window.localStorage.getItem(key); } catch (e) { return null; }
    }

    function uiStateSetItem(key, value) {
        try { window.localStorage.setItem(key, value); } catch (e) {}
        if (key !== UI_STATE_MODE_KEY && isUiStateDbMode()) {
            scheduleUiStateSave(key, value);
        }
    }

    function uiStateRemoveItem(key) {
        try { window.localStorage.removeItem(key); } catch (e) {}
        if (key !== UI_STATE_MODE_KEY && isUiStateDbMode()) {
            scheduleUiStateDelete(key);
        }
    }

    // value(문자열)를 JSON 으로 파싱해서 보내되, JSON 이 아니면 원본 문자열 그대로 보낸다.
    // hydrateUiStateFromServer() 에서 동일한 규칙으로 역변환하므로 값이 그대로 왕복된다.
    function scheduleUiStateSave(key, value) {
        if (saveTimers[key] && saveTimers[key].timer) {
            clearTimeout(saveTimers[key].timer);
        }
        saveTimers[key] = { timer: setTimeout(function () {
            delete saveTimers[key];
            var parsed;
            try { parsed = JSON.parse(value); } catch (e) { parsed = value; }
            fetch(UI_STATE_API_BASE + "/" + encodeURIComponent(key), {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ value: parsed }),
            }).catch(function (err) {
                if (window.clientLog) window.clientLog("uiState save failed: " + key, String(err), "warn");
            });
        }, SAVE_DEBOUNCE_MS) };
    }

    function scheduleUiStateDelete(key) {
        if (saveTimers[key] && saveTimers[key].timer) {
            clearTimeout(saveTimers[key].timer);
            delete saveTimers[key];
        }
        fetch(UI_STATE_API_BASE + "/" + encodeURIComponent(key), { method: "DELETE" })
            .catch(function (err) {
                if (window.clientLog) window.clientLog("uiState delete failed: " + key, String(err), "warn");
            });
    }

    var hydratePromise = null;
    // 서버(DB)에 저장된 값으로 localStorage 를 덮어쓴다. DOMContentLoaded 의 가장 앞에서
    // await 로 호출해, 이후의 모든 복원 로직(탭 순서/접기/활성탭 등)이 최신 서버 값을 보도록 한다.
    function hydrateUiStateFromServer() {
        if (hydratePromise) return hydratePromise;
        if (!isUiStateDbMode()) {
            hydratePromise = Promise.resolve();
            return hydratePromise;
        }
        hydratePromise = fetch(UI_STATE_API_BASE, { method: "GET" })
            .then(function (res) {
                if (!res.ok) throw new Error("HTTP " + res.status);
                return res.json();
            })
            .then(function (data) {
                var values = (data && data.values) || {};
                Object.keys(values).forEach(function (key) {
                    if (key === UI_STATE_MODE_KEY) return; // 저장 모드 자체는 이 브라우저의 선택을 유지
                    var v = values[key];
                    var s = (typeof v === "string") ? v : JSON.stringify(v);
                    try { window.localStorage.setItem(key, s); } catch (e) {}
                });
            })
            .catch(function (err) {
                if (window.clientLog) window.clientLog("uiState hydrate failed", String(err), "warn");
            });
        return hydratePromise;
    }

    // 스크립트 로드 시점에 바로 백그라운드로 fetch 를 시작해둔다(이후 tracking.js 의
    // DOMContentLoaded 핸들러가 같은 promise 를 await 해서, 네트워크 왕복 시간을 다른
    // 스크립트 파싱/실행 시간과 겹치게 만든다 → 체감 지연 최소화).
    hydrateUiStateFromServer();

    // 저장 모드 토글 버튼: "DB에 저장(기본, 다른 PC와 공유)" ↔ "이 브라우저에만 저장(로컬)"
    // 모드를 바꾸면 해당 모드 기준으로 화면 상태를 다시 읽어야 하므로 새로고침한다.
    function renderUiStateModeToggleButton(btn) {
        const mode = getUiStateMode();
        if (mode === "local") {
            btn.textContent = "화면 설정 저장: 이 브라우저만(로컬)";
            btn.title = "현재 이 브라우저의 localStorage 에만 저장됩니다(다른 PC와 공유 안 됨).\n클릭하면 서버 DB 저장 모드로 전환하고 새로고침합니다.";
        } else {
            btn.textContent = "화면 설정 저장: DB(다른 PC와 공유)";
            btn.title = "탭 순서·접기 상태 등 화면 설정이 서버 DB에 저장됩니다(같은 DB를 다른 PC에서 열어도 동일).\n클릭하면 이 브라우저에만 저장하는 로컬 모드로 전환하고 새로고침합니다.";
        }
    }

    function initUiStateModeToggleButton() {
        const btn = document.getElementById("trk_ui_state_mode_btn");
        if (!btn || btn.dataset.uiStateModeBound === "1") return;
        btn.dataset.uiStateModeBound = "1";
        renderUiStateModeToggleButton(btn);
        btn.addEventListener("click", function () {
            const next = isUiStateDbMode() ? "local" : "db";
            setUiStateMode(next);
            window.location.reload();
        });
    }
    document.addEventListener("DOMContentLoaded", initUiStateModeToggleButton);
    window.initUiStateModeToggleButton = initUiStateModeToggleButton;

    window.getUiStateMode = getUiStateMode;
    window.setUiStateMode = setUiStateMode;
    window.isUiStateDbMode = isUiStateDbMode;
    window.uiStateGetItem = uiStateGetItem;
    window.uiStateSetItem = uiStateSetItem;
    window.uiStateRemoveItem = uiStateRemoveItem;
    window.hydrateUiStateFromServer = hydrateUiStateFromServer;
})();
