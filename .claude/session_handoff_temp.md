`product_test_tracing_system`이 마운트 안 됨. bash로 접근 불가.

에러 내용만 보면 진단은 가능:

**원인**: `product_test_run_service/__init__.py` line 104에서 `get_test_round_id_by_run_id`를 `_trace.py`에서 import하려는데, 그 함수가 `_trace.py`에 없음.

**가능한 원인 2가지**:
1. `_trace.py`에서 함수가 다른 이름으로 정의됨 (리팩토링 후 이름 변경)
2. 함수가 `_trace.py`에서 삭제됨

**확인 필요**: `product_test_tracing_system/app/services/product_test_run_service/_trace.py` 열어서 실제 함수명 확인.

직접 고치려면 그 디렉토리를 세션에 연결해야 함. 아니면 사용자가 직접 `_trace.py`에 `get_test_round_id_by_run_id` 함수 이름 확인 후 `__init__.py`의 import명을 맞춰주면 됨.

`product_test_tracing_system` 폴더도 연결해드릴까요?