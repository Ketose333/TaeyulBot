# Engineering Decisions (single source)

## 원칙
- 서버 authoritative 유지
- 코어 로직은 외부 서비스 의존 없이 단독 실행 가능
- 문서 단일본 유지(중복 금지)
- 파괴적 변경은 사전 확인 후 실행

## 운영 결정
- 기능 추가보다 안정성/회귀 방지를 우선
- API 엔트리는 가능한 통합하고 action 분기로 확장
- 오류 문구는 사용자 기준으로 일관되게 노출
- UI 토큰은 시각 통일과 동작 의미 분리를 함께 유지

## TCG 현재 고정값
- overlay 의미: loading=blocking, card=modal, grave=drawer
- deck-codec: v2 only
- chip/signature: 재도입 금지

## 변경 규칙
- 구현 전에 결정 문서 먼저 갱신
- 변경 후 QA 체크리스트로 회귀 확인
