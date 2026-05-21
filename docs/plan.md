_________________________________________________ TODO
🔳 2026 사내 필수강의 5월 중으로 수강
🔳 Tracer 테스트 : 아침30분, 저녁30분 수치입력 by 오대영 프로.
🔳 테스터는 조건 이해하기 쉽도록 작성해야한다. 재현절차..
🔳 chatGPT 유료/Business  공유    팀내 사용규칙확인  

# 물품 구매예정
🔳 지퍼팩 30 🔳 25cm : 20매 Connectivity AP 부속자재 및 정리보관용
🔳 3M VHB? TAPE : Connectivity AP 전선정리용
🔳 소독용 에탄올 : Connectivity AP 자재청소용
1자 드라이버 소형(TEST 작업용)
🔳 Cable Tie 소 : 자재이동 2층 to 6층 Connectivity Room

# 라벨프린팅 예정 목록
🔳 Router PASSWORD
🔳 Router Power Adapter별로 Serial Number
🔳 Router MODEL NAME, PASSWORD
 
🔳 용어 필요정보
제품별 UI 화면설계 용어표준 : ex> UI 화면 및 UI Component 정의 정보위치. 

☑️ 특근관리
2026.04.22 수 휴가 승인
2026.05.06 수 특근근무 승인
2026.05.07 목 특근근무 승인
2026.05.11 월 특근근무 승인
2026.05.12 화 특근근무 승인
2026.05.13 수 특근근무 승인
2026.05.14 목 특근근무 승인
2026.05.18 월 특근근무 승인
2026.05.19 화 특근근무 승인
2026.05.20 수 특근근무 신청
WIFI Connectivity 제품별 네트워크시험 수행
- Wi-Fi Connectivity Test 2차(5G, 다수AP환경) 검토 회의결과 정리
- Connectivity Room Router 스티커 라벨링 및 배선 정리 작업
- Connectivity Room Router 현황 업데이트


# 시험 Config 경우의 수 산출(실제로는 시험조건 추가가 되며, 시험조건 추가 시, 계속 증식되는 환경에서 수행해야함)
    # "WIFI Test 관련" 경우의 수
    WIFI Test 관련 상태에 대한 Test Config의 수 = "장비 단품연동 기준 Test Config 의 수" * (2*1)*(4*1) *(etc_options*1)        (2: DHCP/Static,  4: 연동서버의 수)
    1개 Test Case는 n 개의 Step 을 가짐
    > 경우의 수가 매우 많다. 유효한 것들을 우선순위로 필터하여 선작업.
    유효한 경우의 수를 필터(중요도를 이산화하여 경우의 수에 대해서 분류한다) 
    유효한 경우의 수를 시험
    모든 경우의 수는 

    Cases 
    제품별 Test Case 수
    = (2.4GHz/5GHz) * (Static/DHCP) * (단독HDR연동/다수HDR연동) * (미공간분리/공간분리) * (한국향/미국향/유럽향(독일향|etc))


    2*2*2*2*(제품별 Test Case 수) = 16*(제품별 Test Case 수)

    ex  (2.4GHz/공간미분리/DHCP/단독HDR연동/한국향)


    # 한국향
    2.4GHz/공간미분리/DHCP/단독HDR연동/한국향
    2.4GHz/공간미분리/Static/단독HDR연동/한국향
    2.4GHz/공간미분리/DHCP/다수HDR연동/한국향
    2.4GHz/공간미분리/Static/다수HDR연동/한국향
    2.4GHz/공간분리/DHCP/단독HDR연동/한국향
    2.4GHz/공간분리/Static/단독HDR연동/한국향
    2.4GHz/공간분리/DHCP/다수HDR연동/한국향
    2.4GHz/공간분리/Static/다수HDR연동/한국향
    5GHz/공간미분리/DHCP/단독HDR연동/한국향
    5GHz/공간미분리/Static/단독HDR연동/한국향
    5GHz/공간미분리/DHCP/다수HDR연동/한국향
    5GHz/공간미분리/Static/다수HDR연동/한국향
    5GHz/공간분리/DHCP/단독HDR연동/한국향
    5GHz/공간분리/Static/단독HDR연동/한국향
    5GHz/공간분리/DHCP/다수HDR연동/한국향
    5GHz/공간분리/Static/다수HDR연동/한국향

    # 미국향
    2.4GHz/공간미분리/DHCP/단독HDR연동/미국향
    2.4GHz/공간미분리/Static/단독HDR연동/미국향
    2.4GHz/공간미분리/DHCP/다수HDR연동/미국향
    2.4GHz/공간미분리/Static/다수HDR연동/미국향
    2.4GHz/공간분리/DHCP/단독HDR연동/미국향
    2.4GHz/공간분리/Static/단독HDR연동/미국향
    2.4GHz/공간분리/DHCP/다수HDR연동/미국향
    2.4GHz/공간분리/Static/다수HDR연동/미국향
    5GHz/공간미분리/DHCP/단독HDR연동/미국향
    5GHz/공간미분리/Static/단독HDR연동/미국향
    5GHz/공간미분리/DHCP/다수HDR연동/미국향
    5GHz/공간미분리/Static/다수HDR연동/미국향
    5GHz/공간분리/DHCP/단독HDR연동/미국향
    5GHz/공간분리/Static/단독HDR연동/미국향
    5GHz/공간분리/DHCP/다수HDR연동/미국향
    5GHz/공간분리/Static/다수HDR연동/미국향

    # 유럽향
    2.4GHz/공간미분리/DHCP/단독HDR연동/유럽향(독일향)
    2.4GHz/공간미분리/Static/단독HDR연동/유럽향(독일향)
    2.4GHz/공간미분리/DHCP/다수HDR연동/유럽향(독일향)
    2.4GHz/공간미분리/Static/다수HDR연동/유럽향(독일향)
    2.4GHz/공간분리/DHCP/단독HDR연동/유럽향(독일향)
    2.4GHz/공간분리/Static/단독HDR연동/유럽향(독일향)
    2.4GHz/공간분리/DHCP/다수HDR연동/유럽향(독일향)
    2.4GHz/공간분리/Static/다수HDR연동/유럽향(독일향)
    5GHz/공간미분리/DHCP/단독HDR연동/유럽향(독일향)
    5GHz/공간미분리/Static/단독HDR연동/유럽향(독일향)
    5GHz/공간미분리/DHCP/다수HDR연동/유럽향(독일향)
    5GHz/공간미분리/Static/다수HDR연동/유럽향(독일향)
    5GHz/공간분리/DHCP/단독HDR연동/유럽향(독일향)
    5GHz/공간분리/Static/단독HDR연동/유럽향(독일향)
    5GHz/공간분리/DHCP/다수HDR연동/유럽향(독일향)
    5GHz/공간분리/Static/다수HDR연동/유럽향(독일향)
_________________________________________________ TBD
# Test Case 기능추가 검토필요
ex) 베타적으로 장비 전원 OFF 시 하나씩 연결하는 경우에 대한 Test Case 를 별도로 추가"

🔳 HRK 테스트 시트는 테스트케이스 작성에 도움이 된 BEST Test Senario가 작성된 시트 


🔳 Test Case 작성을 위한 필요조건 요청사항

🔳 Test변수 통제 필요성 검토
1. xxx-000 필요함, Setting 할 수 있는 모든 UI 설정사항(버튼)에 대한 Default를 열려줘야함.
Software Setup에 있는 각종 mode 상태 요청


🔳 HDC 테스트 속도 개선안
확인필요 : HDC-XXX 에서 XXX 가 의미하는 것.
        단순 테스트 순번? 다른 관리 아키텍쳐? 
        단순 테스트 순번이라면 순서 재배열 제안
제안 : Test항목 간 종속성에 따른 테스트 순번 재배열 
         기존 (DHCP > Static) 
        신규 (Static > DHCP)
제안 기대효과 : HDC-005, HDC-007의 테스트 속도 개선


🔳 테스트대상 및 테스트환경 테스트시작상태 정의 필요(모든 모드, 모든 버튼 위치 및 네트워크 연결 캐시 초기화)


TBD : 동글 활성화 상태 확인 정의, Refraction exam 생성 방법 정의
🔳 구매필요
🔳 라우터용 선반 1개
🔳 220V 6구 멀티탭 1개
🔳 110V 6구 멀티탭 2개
🔳 220V TO 110V 변환기 플러그 1개
🔳 스마트플러그(P110m) 2개 다른공간 라우터 원격제어용
🔳 3M VHB 초강력 양면테이프



🔳 연결할AP 송출출력 통제방법 수립
_________________________________________________ SQA Process 개선 회의  
제품 표준서?
UI 불편 > 브랜드 가치 하락
동일 내용   랭귀지 차이 L10n 다국어지원 수준

# 송출출력(Router Tx Power) Low 설정
http://192.168.1.1/
ADVANCED
Wireless/Wireless Settings/Transmit Power:High > Low/Save 
무용.

# Mature SQA > SQA

# AS-IS
SRS 사양서 부재(권장해상도, ..)
VMV 레포트?
VNV 레포트?

# HW 검증( QC )

# SW 검증( SQA )

# heavy process sys 도입
낮은 성숙도
내부반발 

# Shift Left ?
# SQA Team 전략
# risk based testing(치명 영역 집중) 기반
# 경량검증


# SQA Team 휴비츠형 전략
# 실행 로드맵
\\ 고도화 전략
JIRA 
JIRA Dashboard 공유
bug level 정의
테스트 정량화 
개발/테스터 이해관계 (자료 공유, 문서화 공유)


# IDEA
소프트웨어 자동화(개발QA) 
Smoke Test 자동화 주고


# 문제부각
실질적CRITICAL 케이스들을 수집해서 발표. TC 정합성 조정
E2E 를 제공해서 연구소에서 테스트 먼저하도록 하자는 건데...



# Windows장비 Web 자동화테스트
# Windows 장비 테스트
# 임베디드 장비 테스트
HTG
OCT
BM?



# VOC
대형병원 : (층분리+Ethernet)


 
# ?
크렘리스?



# TEST IDEA
Test용 장비는 재현성 확보 및 VOC 대응을 위해 Reference별 Serial별로 별도 구비 희망. 장비가 비싸면, 케이블과 부속품이라도.
_________________________________________________ WIFI Connectivity 제품별 네트워크 시험 및 Connectivity Room 네트워크 증설 현황 중간보고

받는이 : 조영수, 김용순
참조 : 김선웅, 이민혁

안녕하세요. 제품 Wi-Fi 테스트 중인 박정훈 사원입니다.

아래의 두 작업에 대해서 현황 보고 드립니다
WIFI Connectivity 제품별 네트워크 시험 
Connectivity Room 네트워크 증설 현황


1. Test Report 작업
- 완료내용
    Test Report 에 대한 Draft 작성을 완료하였으며. 지금까지의 결과는 PASSED 입니다.
    연구소에서 요청하신 온전한 Test 시나리오는 Test Case 정합성 검토가 필요하여, 완전히 테스트하지는 못한 상태이며  
    5GHz, DHCP/Static, HISS, MATE, 다수서버연동에 대해서는 제외되었으며
    단품과의 연결에 대한 Operating 중심으로. 핵심기능을 2.4GHz, DHCP 설정으로 빠르게 Smoke Test 검증하였습니다. 

- 산출물 : 
    위치: 
        https://docs.google.com/spreadsheets/d/1CphfBg6d6mOVyiOOxpAZ-HzReFmZTyB_/edit?gid=1074338896#gid=1074338896
    요점 위치 :
        "문제점 관리" 시트의 
            "파란색 폰트적용 항목" : 문제판정 검토필요 항목
            "주황색 폰트적용 항목" : TEST 관련 기타 검토필요 항목

- 추후계획
    1. Tester 장비 숙달(HIIS, MATE, 다수서버연동 등)
    2. Test 시나리오와 Test Config, Test Case와의 정합성 검토, 
    3. 5GHz, Static, HISS 연동, MATE 연동결과 등에 대한 세부 Test Case 추가정의 및 Test 가 필요합니다. 
    4. WIFI Connectivity 제품별 네트워크시험 환경 정의
    5. Test 프로세스 시스템 정의 및 타부서 협업 연동. 
    6. Test System 도입 제안





2. Connectivity Room 네트워크 증설작업

- 완료내용
    Test Report 에 대한 Draft 작성을 완료하였으며. 지금까지의 결과는 PASSED 입니다.
    연구소에서 요청하신 온전한 Test 시나리오는 Test Case 정합성 검토가 필요하여, 완전히 테스트하지는 못한 상태이며  
    5GHz, DHCP/Static, HISS, MATE, 다수서버연동에 대해서는 제외되었으며
    단품과의 연결에 대한 Operating 중심으로. 핵심기능을 2.4GHz, DHCP 설정으로 빠르게 Smoke Test 검증하였습니다. 

- 산출물 : https://docs.google.com/spreadsheets/d/1CphfBg6d6mOVyiOOxpAZ-HzReFmZTyB_/edit?gid=1074338896#gid=1074338896

- 추후계획
    1. Tester 장비 숙달(HIIS, MATE, 다수서버연동 등)
    2. Test 시나리오와 Test Config, Test Case와의 정합성 검토, 
    3. 5GHz, Static, HISS 연동, MATE 연동결과 등에 대한 세부 Test Case 추가정의 및 Test 가 필요합니다. 
    4. WIFI Connectivity 제품별 네트워크시험 환경 정의
    5. Test 프로세스 시스템 정의 및 타부서 협업 연동. 
    6. Test System 도입 제안
    7. 사용자별(검안사|) e2e 프로세스 이해 및 Test Case 추가.


아래는 업무별 진행현황 및 계획 구조 입니다.

# 작업상태 
☑️ : DONE
🔳 : PLAN 


# 현재작업 진행현황 (mkr, ing)
🔳 2026-05-12 작업
🔳 HIIS 설치 PC에 KEY(PK7579) 주기 
🔳 Connectivity Room Doorlock KEY(PK9999) 주기 by 김선웅
🔳 Test 현황 업데이트
    frame 생성하고 TC 채우기
🔳 Connectivity Room 입고 Routers 목록 업데이트
🔳 입고 Routers 전원 테스트
🔳 입고 Routers Wi-Fi 통신 테스트
🔳 작업현황 공유(메일링) 
☑️ 오피스디포 주문 물품 사무실앞 수령
🔳 시험늦어짐 사유 취합
    OP 부팅시간, 
    장비 부팅시간(재부팅 AP 영향 시험), 
    장비/케이블 빌려오는 시간, 
    이슈발생 시 고장탐구시간
    주변장비 셋업 


# Connectivity Room 네트워크 증설작업 진행현황
☑️ Connectivity Room 미국발 AP 추가입고 및 임시배치(Rack, Router, Router Power Adapter, 4단 Black Rack). 2026-05-06
    ☑️ 부속자재 및 정리보관용 분류 및 저장(지퍼팩, 라벨프린팅) - 2026-05-07
    ☑️ Rack(7단, 아이보리) 설치 - 2026-05-07
    ☑️ Router Model명, Serial Number, SSID, SSID Password 전산화 - 2026-05-07
    🔳 Router Power Adapter별로 Serial Number 주기(라벨프린팅).
    🔳 Rack 멀티탭 단의 천장에 부착.
    🔳 Router 배선정리(Cable Tie, Cutting Plier).
    🔳 Router MODEL NAME, PASSWORD 라벨프린팅 및 부착.
    🔳 Router 110V TRANS 설치
    🔳 Router AP 동작 테스트
☑️ 현지 네트워크 환경 모의를 위한 유럽발(독일|) AP 추가입고 및 배치
 🔳 콘센트 14A 넘는지 21 Routers 입력전원 예측해서 전원증설 검토



# WIFI Connectivity 제품별 네트워크시험 Tester 교육 
☑️ 교육기간: 5일 (2026-04-20~2026-04-24)



# WIFI Connectivity 제품별 네트워크시험 Test 
☑️ 실투입기간: 7일 (2026-04-22~2026-04~30)        



# WIFI Connectivity 제품별 네트워크시험 Test Report 작성
☑️ WIFI Connectivity 제품별 네트워크시험 Test Case 작성 
    ☑️ WIFI Connectivity 제품별 네트워크시험 Test Case 초안작성 - 2026-04-30
        Operating 중심(server=1:1).
        5GHz 제외
        Static 제외
        HISS 제외
        MATE 제외
        Server 재연결 시 복구 Test Case(AP 컷오프 건) 일부미포함 
        산출물 : "WIFI Connectivity 테스트 시나리오.xlsx - Google Sheets" 
    ☑️ WIFI Connectivity 제품별 네트워크시험 Test Case v1 작성
        ☑️ Defect(Bug, 결함) 및 특이사항은 Smart Phone활용 촬영 - 2026-05-07
            "HRK-9000A SETUP 버튼 간헐적 미인식 건 - 2026-05-07.mp4" 영상첨부
        ☑️ Server 재연결 시 복구 Test Case(AP 컷오프 건) 추가 - 2026-05-07
        ☑️ Test Case 작성검증(TBD, 특이사항, 이슈 중심)
    🔳 WIFI Connectivity 제품별 네트워크시험 Test Case v2 작성 
        2.4GHz HDR 4대 - 서버여러대
        🔳 Static Case Config 추가
        🔳 Static/DHCP 별 Test Case 추가 
        🔳 Defect(Bug, 결함) 및 특이사항은 Chest Cam활용 촬영
        🔳 공간미분리 
        🔳 공간분리
        🔳 5GHz Case Config 추가
        🔳 5GHz Test Case 추가 
        🔳 절전모드 복구 Test Case 추가 : 절전모드 > 하루대기 > 복구시험

🔳 WIFI Connectivity 제품별 네트워크시험 Test Report 초안작성
    🔳 시험대상 및 환경 및 Serial Number/Model Name/Software Version 수집
        외관 부착스티커 및, 부팅시 화면으로도 알수 없는 장비들이 있었음. 명시적인 Version 확인방법 필요.
        도움필요.
    🔳 시험대상 및 환경 및 Serial Number/Model Name/Software Version을 Test Report 에 기입 
    ☑️ Test Config/Test Case 임시ID 부여
        ☑️ Test Report 관리용 데이터 관계규칙 설계(Caveman Style)
            Test Report ID, Test Release ID, Test Config ID, Test Case ID : 	 
            
            관리용 데이터 관계 규칙:
                Test Report 1건
                    └─ Test Release N건
                            └─ Test Config N건
                                    └─ Test Case N건
                                            └─ Test Result N건
            관리용 데이터 ID 작성규칙: 
                SQA_TEST_REPORT_ID-{YYMMDD}
                SQA_TEST_RELEASE_ID_{MODEL_NAME}-{SW_VERSION}_{RELEASE_STAGE}
                SQA_TEST_CONFIG-{MODEL_NAME}-{TEST_SCOPE}-{CONFIG_TARGET}-{SEQUENCE}
                SQA_TEST_CONFIG-{MODEL_NAME}-{TEST_SCOPE}-{CONFIG_TARGET}-{CONNECTED_TARGET}-{SEQUENCE}
                SQA_TEST_CASE-{MODEL_NAME}-{TEST_CHARACTER_DESCRIPTION}-{IDENTICAL_SEQUENCE}
                SQA_TEST_RESULT-{MODEL_NAME}-{YYMMDD}-{RESULT_SEQUENCE}

            관리용 데이터 ID 예시: 
                Test Report ID  : SQA_TEST_REPORT_ID-260507
                Test Release ID : SQA_TEST_RELEASE_ID_HRK-9000A-1.01.01A_GA
                Test Config ID  : SQA_TEST_CONFIG-HRK-9000A-WIFI-ROUTER_2_4G-HDR-9000-001
                Test Case ID    : SQA_TEST_CASE-HRK-9000A-WIFI_AP_AUTH-001
                Test Result ID  : SQA_TEST_RESULT-HRK-9000A-260507-001
    중간산출물 : https://docs.google.com/spreadsheets/d/1CphfBg6d6mOVyiOOxpAZ-HzReFmZTyB_/edit?gid=1074338896#gid=1074338896
    🔳 Tester 장비 숙달(HIIS, MATE, 다수서버연동 등)
    🔳 Defect ID 작성규칙 추가
    🔳 HISS 장비 기본조작 및 셋팅 배우기
        MATE 등의 화면 기본조작 및 각 이미지 데이터 시현결과 확인법  
    🔳 Test 시나리오와 Test Config, Test Case와의 정합성 검토
    🔳 5GHz, Static, HISS 연동, MATE 연동결과 등에 대한 세부 Test Case 추가정의 및 Test 
    🔳 WIFI Connectivity 제품별 네트워크시험 환경 정의
    🔳 Test 프로세스 시스템 정의 및 타부서 협업 연동 
    🔳 Test System 도입 제안
    🔳 사용자별(검안사|) e2e 프로세스 이해 및 Test Case 추가.


# WIFI Connectivity 제품별 네트워크시험 Test Scenario와 Test Case 간 정합성 검토
🔳 Test 시나리오(TEST 요구사항 정의)과 Test Case 간 정합성 검토 회의 - 오늘 중 수행 예정
    (QI > 제품담당자)
    🔳 재현 시현을 위해 케이블 및 장비 준비
    🔳 WIFI Connectivity 제품별 네트워크시험 환경 정의
        🔳 AP와 장비 간 물리적 거리 정의
            🔳 Connectivity Network 환경 컨셉 아트(AI 이미지 생성 및 첨부)
            🔳 Connectivity Room n x n meter 공간 내
            🔳 현재 1M 내외 수준 실배치
        🔳 안테나 방향 정의
            ex> 최대한 수직방향
        🔳 산출물 작업방식 제안(기존:google docs > 제안:엑셀파일 or System 도입) 
        🔳 Etherent Cable(LAN CABLE) CATEGORY 규격 정의


이상입니다.
감사합니다.



# Test Data Tracing system 설계(Test Senario, Test Data Full Life Cycle 관리)  
🔳 Test Data Tracing system Export 기능활용 엑셀화 하여 공유
(현재) 문서 악성노동 증가 > 문서 완성도 떨어짐.
(제안) 시스템 설계
꼭 만들면 좋겠어.
왜 이렇게 안했어?



# TBD : 용순 프로가 비슷하게 진행 중 인듯. 검토 불필요 해보임.
🔳 WIFI Connectivity 제품별 네트워크시험 환경 품평(랙 및 실제테스트 사진)




_________________________________________________ TODO: e2e flow 정합성 검토 
# 문의 to 제품 시나리오 작성 담당자별 
🔳 장비별 Serial Number/Software version, Firmware version 취득방법
🔳 여러대 연결 시나리오 조금 더 구체적인 샘플
🔳 특이사항 확인
🔳 TBD 확인.
🔳 User(검안사|안경사)별 e2e Flow 확인
🔳 내가 작성한 Test Case가 담당자 검증 의도에 맞는지 정합성 검토.
pk 임의 우선 작성한 뒤 > flow 정합성 검토

STR(Step to Reproducing)



________________________________________________________ 시험 소요시간 산출
장비별 TC별 delta time (오늘 중) 
HRK 12 Test Cases (141*0.5 Mins)  70분 * 0.8  
HLM 7 Test Cases (61*0.5 Mins)   30분 * 0.8  
HTR 12 Test Cases (91*0.5 Mins)   45분 * 0.8 
HDR 9 Test Cases ((92+TBD)*0.5 Mins)  (46분 + HIIS_TBD×0.5분) * 0.8 
HDC 8 Test Cases (69*0.5 Mins)   34.5분 * 0.8 
	SQA_TEST_CASE-HDC-9100-WIFI_DR_CONNECT_ON_DHCP-001 TestProcedure*14
	SQA_TEST_CASE-HDC-9100-WIFI_DR_CONNECT_ON_DHCP-002 TestProcedure*14
	SQA_TEST_CASE-HDC-9100-WIFI_DR_CONNECT_OFF-001 TestProcedure*8
	SQA_TEST_CASE-HDC-9100-WIFI_DR_CONNECT_ON_STATIC-001 TestProcedure*11

# 결론 (장비별 소요시간)
HRK 12 Test Cases (141*0.5 Mins)  70분 * 0.8  
HLM 7 Test Cases (61*0.5 Mins)   30분 * 0.8
HTR 12 Test Cases (91*0.5 Mins)   45분 * 0.8
HDR 9 Test Cases ((92+TBD)*0.5 Mins)  (46분 + HIIS_TBD×0.5분) * 0.8
HDC 8 Test Cases (69*0.5 Mins)   34.5분 * 0.8
HIIS_TBD = 10 : *HIIS 연동 별도측정필요, 지금까지의 평균 Test Procedure는 9.45로 10으로 가정함
1 TestProcedure = 0.5 Mins 로 가정하였음.	
0.8 : 장비 사용 숙련이 되면 대략 20% 정도는 빠르게 끝날 수 있어보여 20%를 감축하였음.
전장비 시험 소요시간= 184.4분 (2.4GHz/공간미분리/DHCP/단독HDR연동/한국향 기준)


# 요약
"예상시험소요시간(분)
(Test Case 작성 시간 미포함)"
56분
24분
36분
41분
28분
전장비 시험 소요시간= 184.4분 (2.4GHz/공간미분리/DHCP/단독HDR연동/한국향 기준)





_________________________________________________________ STEP 회의(품질회의) PPT
Wi-Fi Connectivity Test 계획 및 진행현황


데드라인 : 
이번달 남은 워킹데이
13일(5/12~5/29)
10(1 항목 / 1일)  +  3(2 항목 1 일)
________________________________________________________ working
실확인결과(Actual Result), PASSED 판단 근거
STR Completion Criteria (Test Case PASSED 판단 근거)


________________________________________________________ 필요한것 
사용자(검안사|안과)별 e2e Test Senario
- 근시 안경도수 처방가정 e2e Test Senario 
- 원시 안경도수 처방가정 e2e Test Senario 
- 난시 안경도수 처방가정 e2e Test Senario 
(flow 이해 필요, 특히 Eye, Lens 파라미터(Sphere, Cylinder, Axis 등의) 관점)




테스트환경 구성(장비 대수, Device Identifier, 장비필수특성) : 
- Router(1대, 2232318003141 ,2.4GHz Band) 1대

________________________________________________________ TBD
# 제품 TEST 관리 전략(Testcollab.io 도입)
궁극적으로, PLM의 ID DATA들과의 연결도모(실제 PLM 데이터와의 데이터관계성, 작업자/관리자 사용성 확인 필요)
제품 TRACE ID 관리
제품 TEST 관리 ARCHITECTURE 설계
TRACE DEFECT LIFECYCLE 개선 > Test version > Release version  



# SQA 업무프로세스 관리 전략(몇 가지 업무 flow 가 나눠질 필요가 있다. 신규테스트시나리오추가)
## ROLE AND WORK TASKS ALLOCATION
REQ : 타조직(고객|영업조직|시장조사조직|제품연구조직)
IMPLEMENTATION : 타조직(제품연구조직 개발조직)
SENARIO 생성 : 타조직(제품연구조직 개발조직)
SENARIO ID 부여 : SQA TEAM  
TEST : SQA TEAM
DEFECT : SQA TEAM
DEFECT 보고 : SQA TEAM to 타조직(제품연구조직 개발조직) 
조치 : 타조직(제품연구조직 개발조직)
Test Version : VAL 및 회귀 테스트 결과 보고.  
Release : 
## Test 산출물 : 
XXX Release TEST REPORT






TRACE ID 관리 전략
TEST Schema 설계 

TRACE ID 관리 전략
Traceability Flow 예시 설계 : 문제점 관리 시트 참고, 일련번호별로 추적가능.
MANAGEMENT MAP
TEST_SENARIO_REQ/-TC
                 -DEFECT
                 -VAL
Test항목 별 delta 측정(미숙련자|숙련자 기준)
Test항목 별 delta 합산 통계 




추적 예시.(Wi-Fi DEFECT 추적)
 




SENARIO, TEST CASE 정합성 검토회의 
1. 정하고 싶은것



# 제품 TEST Data 입력 관리 전략
용어 정규화/표준화 > 데이터입력 제약 필요
SERIAL 별로 TEST CASE 나오고 PASSED/FAILED



# 제품 Display 터치 자동화 Test지그 설계
1. HUMAN : 제품 및 테스트 환경 구성
2. HUMAN : TEST FLOW 선택
4. MACHI : UI COMPONENT 요소 객체인식 # 화면촬영
5. MACHI : 클릭 
FIRMWARE DESIGN(박정훈)
2차원 기구설계 (박정훈)




현철 프로님께 검토 요청
________________________________________________________ SQA TEAM 내부용 제품 TEST 문맥작성 표준.md
# 바이브코딩 : 문서용어 정규화/표준화 자동치환기
작성규칙위반 = 작성규칙 검사기() # ai 활용
________________________________________________________ PLAN
# ANUAL
야근 : 주3일 아근, 2달 빡시게하고
5/15 끝내는 게 매우 중요.
5/22 늦으면.
5/29 양산적용 Release
7/3?  2달 연장 계약 만료일



# DAILY
# 일간 업무보고서 작성
정규근무시간: 
시간외: 



# MANDANTORY
제품 S/W AND SERIAL 기록
추후 사이클 부터는 chest camera 촬영
TEST CASE 관련 업무메일 참조 : 김선웅



# 도입 전환 
# WIFI Connectivity 테스트 시나리오.xlsx - Google Sheets
Notion, Jira, Testcollab.io 도입 관리 환경조사
이현철 프로님 기술자문 요청.






________________________________________________________ SQA Test 실무흐름 이해
# basic senario == e2e senario



# function test
Lillivis-works 프로그램/검색기능/column filter 없이 like 검색 # filter 기준 없음.
________________________________________________________ 제품 Wi-Fi Test 환경 구성
# OBJECT
Router
HTR 
HDR
HDC # 모니터 처럼 생긴 Digial Chart
HDC Remote Controller 
OP : Operation Panel 
Junction Box
모델아이
측정렌즈 or 검안테
________________________________________________________ 제품 Wi-Fi Test  환경 및 제품 정의 TBD
배경 : Wi-Fi 끊김 이슈 > Wi-Fi 끊김 이슈 개선 > 개선 적용 제품에 대한 개선 유효성 확인
기존 : 장비들(네트워크 노드들) 1 meter 이내에서 Wi-Fi Test 수행
제안 : X meter 떨어져서 Test 필요성

Router WiFi 체크리스트 점검 상세절차
________________________________________________________ 제품 기본조작
# HDR/Chat Row 삭제
HDR/Claer/Clear 


# OP/QC Settings 화면 진입
HDR/shift + Menu(keyboard) or Settings(touch) 누른 상태에서 1초 대기
두 버튼 동시에 Release 


# OP IP Setup
OP/QC Settings 화면/commnunication/connection/on
OP/QC Settings 화면/commnunication/connection/AP Name(SSID)/MER****{SSID Example}
OP/QC Settings 화면/commnunication/connection/AP Password/*******{password Example}
OP/QC Settings 화면/commnunication/connection/AP Password/Verify/Connecting to the access point.
OP/QC Settings 화면/commnunication/connection/IP Address/192.168.1.***{IP Address Example}
________________________________________________________ Test 환경 구성
# phsical environment setting
HRK/Power 스위치 OFF (| > o)
HRK 높이 노브 운영상태로 셋팅
locate 모델아이

# Wiring
Power Calbe > Junction box > OP Cable > OP
Power Calbe > Junction box > HDR Cable > HDR

# Network
MER***********

# OP AP OFF 설정
OP/QC Settings 화면/OFF/OK #OK 까지 해야함.

HRK/Power on(o>|)

# software setting
AP Link 제거
HTR/RK

# logical flow
HRK Data 전송
________________________________________________________  
# OP IP 설정 및 확인
OP/QC Settings 화면/commnunication/connection/on
OP/QC Settings 화면/commnunication/connection/AP Name(SSID)/MER****{SSID Example}
OP/QC Settings 화면/commnunication/connection/AP Password/*******{password Example}
OP/QC Settings 화면/commnunication/connection/AP Password/Verify/Connecting to the access point.
OP/QC Settings 화면/commnunication/connection/IP Address/192.168.1.***{IP Address Example}


# 네트워크 구성 설정(HDR & OP)
HDR/Setup/IP ADDRESS/HDR9000_1{IP Address Nickname Example}/192.168.1.***{IP Address Example}
Activate IP Address to communicate by using V mark


OP/QC Settings 화면/commnunication/connection/on


# 스캔
OP/QC Settings 화면/commnunication/connection/AP Name(SSID)/돋보기 아이콘


# 1. 연결 가능한 AP 목록 (SSID/RSSI 순서)
OP/QC Settings 화면/commnunication/connection/AP Name(SSID)/연결가능 AP 목록 모달/MER****{AP SSID Example}/OK
연결 가능한 AP 목록이 "연결가능 AP 목록 모달"에 출력. 
RSSI 강도가 강 한것이 약한 것보다 우선 출력.
SSID  # "-" 가 " " 보다 우선 출력.  " " 가 "_" 보다 우선 출력. 
위의 3가지를 충족하면 기대결과 충족
_________________________________________________ ETC
# 텍스트 템플릿
TBD(To Be Determined, 협의사항)
협의사항(TBD, To Be Determined)
🔳 절차_재현판단기준 정의
🔳 LM-100 Spindle 시험 관련 물품들 이관 및 반납
SQA_TEST_CASE-HRK-9000A
SQA_TEST_CASE-HLM-9000
SQA_TEST_CASE-HTR-1A
SQA_TEST_CASE-HDR-9000
SQA_TEST_CASE-HDC-9100
