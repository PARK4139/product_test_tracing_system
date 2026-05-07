_________________________________________________ Plan : May  
# 화수목 야근상신
 

# 물품 신청
☑️지퍼팩 30 🔳 25cm : 20매 Connectivity AP 부속자재 및 정리보관용
🔳 3M VHB? TAPE : Connectivity AP 전선정리용
🔳 소독용 에탄올 : Connectivity AP 자재청소용


# 자재이동 2층 to 6층 Connectivity Room
🔳 Cable Tie 소 : 



# 라벨프린팅 예정 목록
🔳 Router PASSWORD
🔳 Router Power Adapter별로 Serial Number
🔳 Router MODEL NAME, PASSWORD

 

# 필요정보
제품별 UI 화면설계 용어표준 : ex> UI 화면 및 UI Component 정의 정보위치. 



# 용어 범례
*TBD : To Be Determind 추후결정사항

 





# Connectivity Room 네트워크 작업 보고서 작성 및 공유
받는이 : 조영수, 김용순
참조 : 김선웅, 이민혁

# Connectivity Room 네트워크 증설작업 진행현황
☑️ Connectivity Room 미국발 AP 추가입고 및 임시배치(Rack, Router, Router Power Adapter, 4단 Black Rack). 2026-05-06
    ☑️ 부속자재 및 정리보관용 분류 및 저장(지퍼팩, 라벨프린팅) - 2026-05-07
    ☑️ Rack(7단, 아이보리) 설치 - 2026-05-07
    ☑️ Router Model명, Serial Number, SSID, SSID Password 전산화 - 2026-05-07
    🔳 Router Power Adapter별로 Serial Number 주기(라벨프린팅).
    🔳 Rack 멀티탭 단의 천장에 부착.
    🔳 Router 배선정리(Cable Tie, Cutting Plier).
    🔳 Router MODEL NAME, PASSWORD 라벨프린팅 및 부착.
    🔳 Router 110V TRANS 설치.
    🔳 Router AP 동작 테스트
🔳 현지 네트워크 환경 모의를 위한 유럽발(독일|) AP 추가입고 및 배치

# Connectivity Room 제품별 네트워크시험 Test Case 작성 
☑️ Connectivity Room 제품별 네트워크시험 Test Case 초안작성 - 2026-04-30
    Operating 중심(:server=1:1).
    5GHz 제외
    Static 제외
    HISS 제외
    MATE 제외
    Server 재연결 시 복구 Test Case(AP 컷오프 건) 일부미포함 
    산출물 : "WIFI Connectivity 테스트 시나리오.xlsx - Google Sheets" 
☑️ Connectivity Room 제품별 네트워크시험 Test Case v1 작성
    ☑️ Defect(Bug, 결함) 및 특이사항은 Smart Phone활용 촬영 - 2026-05-07
        "HRK-9000A SETUP 버튼 간헐적 미인식 건 - 2026-05-07.mp4" 영상첨부
    ☑️ Server 재연결 시 복구 Test Case(AP 컷오프 건) 추가 - 2026-05-07
    ☑️ Test Case 작성검증(TBD, 특이사항, 이슈 중심)
🔳 Connectivity Room 제품별 네트워크시험 Test Case v2 작성
    🔳 HISS 장비 기본조작 및 셋팅 배우기
        MATE 등의 화면 기본조작 및 각 이미지 데이터 시현결과 확인법   
    🔳 5GHz Case Config 추가
    🔳 Static Case Config 추가
    🔳 Static/DHCP 별 Test Case 추가 
    🔳 5GHz Test Case 추가 
    🔳 절전모드 복구 Test Case 추가 : 절전모드 > 하루대기
    🔳 Defect(Bug, 결함) 및 특이사항은 Chest Cam활용 촬영

# Connectivity Room 제품별 네트워크시험 Test Report 작성
🔳 Connectivity Room 제품별 네트워크시험 Test Report 초안작성
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

# Connectivity Room 제품별 네트워크시험 Test Scenario와 Test Case 간 정합성 검토
🔳 Test 시나리오(TEST 요구사항 정의)과 Test Case 간 정합성 검토 회의 - 금요일예정
    (QI > 제품담당자)
    🔳 Connectivity Room 제품별 네트워크시험 환경 정의
        🔳 AP와 장비 간 물리적 거리 정의
            🔳 Connectivity Network 환경 컨셉 아트(AI 이미지 생성 및 첨부)
            🔳 현재 1M 내외 수준 실배치
        🔳 안테나 방향 정의
        🔳 산출물 작업방식 제안(기존:google docs > 제안:엑셀파일) 
        🔳 Etherent Cable(LAN CABLE) CATEGORY 규격 정의

# Connectivity Room 제품별 네트워크시험 Test Report 및 이슈 전달
(QI >연구소)  
Operating 중심(:server=1:1).

5GHz 제외
Static 제외
HISS 제외
MATE 제외
5GHz, Static, HISS 연동, MATE 연동결과 에 대한 Test Case 추가정의 및 Test 필요 




# Test Data Tracing system 설계(Test Senario, Test Data Full Life Cycle 관리)  
🔳 Test Data Tracing system Export 기능활용 엑셀화 하여 공유
시스템 설계가 필요...











# pk TBD
🔳 Connectivity Room 제품별 네트워크시험 환경 품평(랙 및 실제테스트 사진)



# LM-100 누수Test 보고
받는이 : 차석길
# T3 Hall Sensor Abnormal 시현 - 2026-05-06
_________________________________________________ TODO: e2e flow 정합성 검토 
# 문의 to 제품 시나리오 작성 담당자별 
🔳 장비별 Serial Number/Software version, Firmware version 취득방법
🔳 여러대 연결 시나리오 조금 더 구체적인 샘플
🔳 특이사항 확인
🔳 TBD 확인.
🔳 User(검안사|안경사)별 e2e Flow 확인
🔳 내가 작성한 Test Case가 담당자 검증 의도에 맞는지 정합성 검토.
pk 임의 우선 작성한 뒤 > flow 정합성 검토
_________________________________________________ TODO: 문의 to 현철 프로님께
🔳 내가 작성한 Test Case 작성 구조 검토


STR(Step to Reproducing)

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
7/X  2달 연장 계약 만료일



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



________________________________________________________ TBD
HRK 테스트 시트는 테스트케이스 작성에 도움이 된 BEST Test Senario가 작성된 시트 


# Test Case 작성을 위한 필요조건 요청사항



Test변수 통제 필요성 검토
1. xxx-000 필요함, Setting 할 수 있는 모든 UI 설정사항(버튼)에 대한 Default를 열려줘야함.
Software Setup에 있는 각종 mode 상태 요청



HDC 테스트 속도 개선안
확인필요 : HDC-XXX 에서 XXX 가 의미하는 것.
        단순 테스트 순번? 다른 관리 아키텍쳐? 
        단순 테스트 순번이라면 순서 재배열 제안
제안 : Test항목 간 종속성에 따른 테스트 순번 재배열 
         기존 (DHCP > Static) 
        신규 (Static > DHCP)
제안 기대효과 : HDC-005, HDC-007의 테스트 속도 개선






0. 테스트대상 및 테스트환경 테스트시작상태 정의 필요(모든 모드, 모든 버튼 위치 및 네트워크 연결 캐시 초기화)
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
________________________________________________________ HTR-000
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


# 2. AP 연결 성공
OP/QC Settings 화면/commnunication/connection/AP Password/Verify/Connecting to the access point.








WIFI Test 관련 상태에 대한 Test Config의 수 = "장비 단품연동 기준 Test Config 의 수" * (2*1)*(4*1) *(etc_options*1)        (2: DHCP/Static,  4: 연동서버의 수)
1개 Test Case는 n 개의 Step 을 가짐
> 경우의 수가 매우 많다.



# 절차_재현판단기준 정의
