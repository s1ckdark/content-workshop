# 컨텐츠제작소

로컬 환경에서 돌아가는 콘텐츠 제작 자동화 스튜디오입니다.  
YouTube Shorts 생성, Twitter/X 포스팅, 제휴 문구 생성, 로컬 비즈니스 아웃리치까지 한 저장소에서 다룹니다.

이 저장소는 기존 자동화 코드를 정리하면서, 과장된 수익형 브랜딩 대신 실제 작업 중심의 `콘텐츠 제작 워크벤치` 방향으로 재구성하는 중입니다.

## 현재 가능한 작업

- YouTube Shorts 주제/스크립트/이미지/TTS/자막/영상 합성
- YouTube Studio 업로드 자동화
- Twitter/X 문구 생성 및 자동 게시
- Amazon 제휴 링크 기반 홍보 문구 생성
- Google Maps 기반 로컬 비즈니스 수집 및 이메일 아웃리치

## YouTube 흐름

YouTube 기능은 아래 순서로 동작합니다.

1. 채널 주제에 맞는 아이디어 생성
2. 짧은 스크립트 생성
3. 제목과 설명 생성
4. 이미지 프롬프트 생성
5. Gemini 이미지 API로 장면 이미지 생성
6. KittenTTS로 음성 생성
7. Whisper 또는 AssemblyAI로 자막 생성
8. MoviePy로 세로 영상 합성
9. Playwright로 YouTube Studio 업로드

핵심 구현은 [src/classes/YouTube.py](src/classes/YouTube.py)에 있습니다.

## 빠른 시작

```bash
git clone https://github.com/s1ckdark/content-workshop.git
cd content-workshop
cp config.example.json config.json
bash scripts/setup_local.sh
source venv/bin/activate
python3 src/main.py
```

## 요구 사항

- Python 3.12
- Chrome 또는 Chromium 기반 프로필
- Ollama
- ImageMagick
- YouTube 생성 기능 사용 시 Gemini API 키
- Outreach 기능 사용 시 Go

## 설정

주요 설정은 `config.json`에서 관리합니다.

- `ollama_model`: 텍스트 생성에 사용할 Ollama 모델
- `nanobanana2_api_key`: Gemini 이미지 API 키
- `browser_profile`: 업로드/게시용 Chrome/Chromium user data dir
- `zip_url`: 배경음악 ZIP URL
- `stt_provider`: `local_whisper` 또는 `third_party_assemblyai`

상세 항목은 [docs/Configuration.md](docs/Configuration.md)를 참고하면 됩니다.

## 스케줄러

앱 안의 스케줄러는 시스템 cron을 설치하는 방식이 아니라, 현재 프로세스를 켜 둔 상태에서 예약 작업을 실행하는 foreground scheduler입니다.  
스케줄을 시작한 뒤에는 프로세스를 유지해야 하며, 종료는 `Ctrl+C`로 합니다.

## 프로젝트 구조

- `src/main.py`: CLI 진입점
- `src/classes/YouTube.py`: Shorts 생성 및 업로드
- `src/classes/Twitter.py`: Twitter/X 자동 포스팅
- `src/classes/AFM.py`: 제휴 문구 생성
- `src/classes/Outreach.py`: 스크래핑 및 이메일 아웃리치
- `src/config.py`: 설정 로딩
- `src/cache.py`: `.mp` JSON 캐시 관리
- `scripts/`: 로컬 셋업, 프리플라이트, 업로드 스크립트

## 저장소 커스터마이징

새 GitHub 저장소로 옮길 때는 최소한 아래를 바꾸면 됩니다.

```bash
git remote set-url origin https://github.com/s1ckdark/content-workshop.git
```

필요하면 저장소 이름만 바꿔서 같은 형식으로 맞추면 됩니다.

## 검증

```bash
python3 scripts/preflight_local.py
python3 src/main.py
```

## 라이선스

기존 저장소의 라이선스를 그대로 유지합니다. 자세한 내용은 [LICENSE](LICENSE)를 참고하세요.
