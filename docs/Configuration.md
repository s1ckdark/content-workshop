# Configuration

모든 설정은 루트의 `config.json`에서 관리합니다. 처음에는 `config.example.json`을 복사해서 시작합니다.

## 주요 값

- `verbose`: 상세 로그 출력 여부
- `browser_profile`: 업로드/게시용 Chrome/Chromium user data dir
- `headless`: 브라우저를 headless로 실행할지 여부
- `ollama_base_url`: Ollama 서버 주소
- `ollama_model`: 텍스트 생성에 사용할 Ollama 모델
- `twitter_language`: Twitter/X 문구 생성 언어
- `nanobanana2_api_base_url`: Gemini 이미지 API base URL
- `nanobanana2_api_key`: Gemini 이미지 API 키
- `nanobanana2_model`: 이미지 생성 모델명
- `nanobanana2_aspect_ratio`: 이미지 비율
- `threads`: MoviePy 렌더 스레드 수
- `zip_url`: 배경음악 ZIP URL
- `is_for_kids`: YouTube 업로드 시 아동용 여부
- `google_maps_scraper`: Google Maps scraper ZIP URL
- `google_maps_scraper_niche`: 수집할 업종/키워드
- `scraper_timeout`: 스크래퍼 실행 제한 시간
- `outreach_message_subject`: 이메일 제목 템플릿
- `outreach_message_body_file`: 이메일 본문 HTML 파일
- `stt_provider`: `local_whisper` 또는 `third_party_assemblyai`
- `whisper_model`: faster-whisper 모델명
- `whisper_device`: `auto`, `cpu`, `cuda`
- `whisper_compute_type`: 예: `int8`, `float16`
- `assembly_ai_api_key`: AssemblyAI API 키
- `tts_voice`: KittenTTS 음성 이름
- `font`: 자막 렌더링에 사용할 폰트 파일명
- `imagemagick_path`: ImageMagick 실행 파일 경로
- `script_sentence_length`: 스크립트 문장 수

## 메모

- `nanobanana2_api_key`가 비어 있으면 `GEMINI_API_KEY` 환경 변수를 사용합니다.
- 앱은 필요한 시점에만 모델과 음원을 준비하도록 정리돼 있습니다.
- YouTube 스케줄러를 돌릴 때는 `Songs/`에 음원이 준비돼 있어야 합니다.
