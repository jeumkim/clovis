# GitHub 업로드 가이드

## 올려야 하는 파일

- `backend/`, `frontend/`, `common/`
- `docs/`
- `README.md`, `.gitignore`, `.env.example`
- `run_local.py`, `run_local.bat`
- 데모 재현에 필요한 `ships_seed.json`, `scenarios/*.json`

## 올리면 안 되는 파일

- `.env`와 실제 API 키
- `receiver.db` 같은 로컬 실행 DB
- `__pycache__/`, `*.pyc`
- `.venv/`, `venv/`
- 로그, 임시 파일, 개인 다운로드 파일

`.gitignore`에 위 항목을 반영해 두었습니다.

## 처음 업로드하는 방법

프로젝트 폴더에서 PowerShell을 열고 실행합니다.

```powershell
git init
git branch -M main
git add .
git status
```

`git status`에서 `.env`, `.db`, `__pycache__`가 포함되지 않았는지 확인한 다음:

```powershell
git commit -m "feat: add CLOVIS MOVE.AI hackathon MVP"
git remote add origin https://github.com/<사용자명>/<저장소명>.git
git push -u origin main
```

이미 원격 저장소에 파일이 있다면 덮어쓰기 전에 먼저 원격 내용을 확인해야 합니다. 강제
푸시(`--force`)는 사용하지 않는 것을 권장합니다.

## GitHub 웹에서 ZIP으로 올리는 경우

1. 준비된 `clovis-github-ready-20260813.zip`을 압축 해제합니다.
2. 압축 파일 자체가 아니라 내부 파일과 폴더를 업로드합니다.
3. `.env.example`은 올리고 `.env`는 올리지 않습니다.
4. 업로드 후 README의 폴더 링크와 Mermaid 구성도가 표시되는지 확인합니다.

## 업로드 전 최종 체크

- [ ] README 첫 화면에서 서비스 목적을 10초 안에 이해할 수 있음
- [ ] 실행 명령과 포트가 정확함
- [ ] `.env.example`과 AI 키 연결 방법이 설명됨
- [ ] 실서비스 미구현 범위가 명시됨
- [ ] 실제 API 키와 개인정보가 없음
- [ ] 로컬 DB와 캐시 파일이 없음
- [ ] GitHub에 올린 뒤 새 폴더에서 실행 테스트 완료
