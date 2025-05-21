# MRHA Trading System Fix Guide

이 문서는 MRHA 트레이딩 시스템에서 발생한 Notion 상태 업데이트 오류와 관련 수정 방법에 대해 설명합니다.

## 발견된 문제

1. **BUY/SELL 주문 상태 업데이트 실패**
   - BUY/SELL 주문은 실행되었지만 Notion에서 상태가 PENDING에서 DONE으로 업데이트되지 않음
   - 오류 메시지: `Order_ID is not a property that exists`, `Amount is not a property that exists`, `Execution_Price is not a property that exists`, `Transaction_Value is not a property that exists`

2. **거래 실행 요약 불완전**
   - 거래 실행 요약이 정확하게 표시되지 않음
   - 실행된 거래 로그가 완전히 표시되지 않음

3. **최종 계정 잔액 업데이트 미완료**
   - 거래 후 계정 잔액 업데이트가 완료되지 않음

## 해결 방법

### 1. 속성 체크 및 수정 스크립트 실행

```bash
python enhanced_notion_property_checker.py
```

이 스크립트는 다음을 수행합니다:
- Notion 데이터베이스의 필수 속성 존재 여부 확인
- 누락된 속성에 대한 보고
- 필요한 경우 속성 추가 옵션 제공

### 2. Notion 속성 수정 스크립트 실행

```bash
python fix_notion_properties.py
```

이 스크립트는 다음을 수행합니다:
- 누락된 속성 자동 추가 (Order_ID, Amount, Execution_Price, Transaction_Value 등)
- IN_PROGRESS 상태에 멈춘 시그널 복구
- 포트폴리오 데이터베이스 업데이트

### 3. 거래 요약 업데이트 스크립트 실행

```bash
python update_trade_summary.py
```

이 스크립트는 다음을 수행합니다:
- 최신 포트폴리오 정보 수집
- 거래 실행 요약 업데이트 및 Slack 알림 전송
- 포트폴리오 상태 업데이트 및 Slack 알림 전송

### 4. 긴급 복구 스크립트 실행 (필요한 경우)

```bash
python fix_now.py
```

이 스크립트는 다음을 수행합니다:
- 모든 PENDING 시그널을 DONE으로 강제 변경
- 포트폴리오 DB를 현재 잔고 상태로 업데이트

## 해결 방안 설명

1. **BUY/SELL 주문 상태 업데이트 실패**
   - 원인: Notion 데이터베이스에 BUY/SELL 주문 상태 업데이트에 필요한 속성(Order_ID, Amount, Execution_Price, Transaction_Value)이 누락됨
   - 해결책: fix_notion_properties.py를 사용하여 필요한 속성을 데이터베이스에 추가

2. **거래 실행 요약 불완전**
   - 원인: 일부 신호 상태 업데이트 실패로 인해 거래 요약이 정확하지 않음
   - 해결책: update_trade_summary.py를 사용하여 최신 데이터로 요약 다시 생성

3. **최종 계정 잔액 업데이트 미완료**
   - 원인: 포트폴리오 업데이트 부분에서 속성 불일치로 인한 오류
   - 해결책: 포트폴리오 DB 스키마 확인 및 수정, 최신 데이터로 강제 업데이트

## 예방 방법

1. **fixed_notion_manager.py 사용**
   - enhanced_realtime_trader.py는 이미 fixed_notion_manager.py를 사용하도록 업데이트됨
   - 이 관리자는 속성이 없는 경우에도 오류를 잘 처리함

2. **정기적인 DB 속성 확인**
   - enhanced_notion_property_checker.py를 정기적으로 실행하여 DB 속성 확인
   - 필요한 경우 속성 업데이트

3. **테스트 모드에서 충분한 검증**
   - 테스트 모드에서 BUY, SELL, HOLD 각각에 대한 시나리오 테스트
   - 모든 상태 업데이트 확인 후 프로덕션 모드 실행

## 결론

Notion 데이터베이스 속성 불일치는 시스템 오류의 주요 원인이었습니다. 제공된 스크립트를 사용하여 속성을 수정하고, fixed_notion_manager.py를 사용하면 향후 유사한 문제를 방지할 수 있습니다. 테스트 모드와 프로덕션 모드는 동일한 방식으로 작동하므로, 테스트 모드에서 확인된 모든 기능은 프로덕션 모드에서도 동일하게 작동해야 합니다.