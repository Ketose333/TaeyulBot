# Vercel Deploy App Guide (범용)

## 프로젝트 설정
- Framework Preset: Other (또는 실제 스택에 맞춤)
- Root Directory: 배포 앱 루트
- Build/Output: 필요 없으면 비움

## 권장 원칙
- 엔트리 수 최소화, action 분기 확장 우선
- 인증은 서버 세션 기준 처리(클라 주입 신뢰 금지)
- 저장소 미연결 fallback 동작을 명시

## 운영 체크
- 환경변수 누락 시 안전한 실패
- 로컬/배포 쿠키 동작 차이 점검
- 배포 전 predeploy 스크립트 성공 확인

## TCG 메모
- `tcg/vercel/package.json`의 palette 빌드는
  `python3 ../utility/theme/build_palette.py` 기준 유지
