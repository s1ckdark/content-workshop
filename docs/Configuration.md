# Configuration

모든 설정은 루트의 `config.json`에서 관리합니다. 처음에는 `config.example.json`을 복사해서 시작합니다.

## 주요 값

- `verbose`: 상세 로그 출력 여부
- `browser_profile`: 업로드/게시용 Chrome/Chromium user data dir
- `headless`: 브라우저를 headless로 실행할지 여부
- `llm_provider`: `openrouter`, `ollama`, `lmstudio`, `openai_compatible`
- `llm_base_url`: 텍스트 생성 API 주소. OpenRouter에서는 비어 있으면 `https://openrouter.ai/api/v1` 사용
- `llm_model`: 제공자의 모델 ID. OpenRouter 예시: `google/gemini-2.5-flash`
- `llm_api_key`: 선택적 API 키. 기본 OpenRouter 설정에서는 모든 AI 작업이 공유하며, 환경변수 `OPENROUTER_API_KEY` 사용을 권장
- `ollama_base_url`: Ollama 서버 주소
- `ollama_model`: 텍스트 생성에 사용할 Ollama 모델
- `twitter_language`: Twitter/X 문구 생성 언어
- `image_model`: OpenRouter 이미지 모델 ID. 기본 `google/gemini-3.1-flash-image-preview`
- `image_aspect_ratio`: 이미지 비율. 기본 `9:16`
- `reference_analysis_model`: 레퍼런스 영상 분석·템플릿 합성용 모델. 기본 `google/gemini-2.5-flash`
- `threads`: MoviePy 렌더 스레드 수
- `zip_url`: 배경음악 ZIP URL
- `is_for_kids`: YouTube 업로드 시 아동용 여부
- `google_maps_scraper`: Google Maps scraper 소스 ZIP URL
- `google_maps_scraper_niche`: 수집할 업종/키워드 (빈 문자열이면 CLI에서 입력)
- `scraper_timeout`: 스크래퍼 실행 제한 시간 (초)
- `stt_provider`: `openrouter`(기본) 또는 `local_whisper`
- `openrouter_stt_model`: 자막용 모델. 기본 `openai/whisper-1`; `verbose_json` 타임스탬프 지원 필요
- `whisper_model`: faster-whisper 모델명
- `whisper_device`: `auto`, `cpu`, `cuda`
- `whisper_compute_type`: 예: `int8`, `float16`
- `tts_provider`: `openrouter`(기본) 또는 `kittentts`(로컬 영어 전용)
- `openrouter_tts_model`: 기본 `google/gemini-3.1-flash-tts-preview`
- `openrouter_tts_voice`: 기본 `Kore`
- `tts_voice`: 로컬 KittenTTS를 선택했을 때만 사용하는 음성 이름
- `font`: 자막 렌더링에 사용할 폰트 파일명
- `imagemagick_path`: ImageMagick 실행 파일 경로
- `script_sentence_length`: 스크립트 문장 수

## 메모

- OpenRouter 키 조회 순서는 `openrouter_api_key` → `llm_api_key`(`llm_provider=openrouter`일 때) → `OPENROUTER_API_KEY`입니다. 다른 서비스의 `OPENAI_API_KEY`나 `LLM_API_KEY`를 자동으로 사용하지 않습니다.
- Ollama는 API 키 없이 사용할 수 있습니다. LM Studio와 일반 OpenAI 호환 서버는 `llm_api_key` → `OPENAI_API_KEY` → `LLM_API_KEY` 순서로 읽습니다.
- OpenRouter로 전환할 때는 이전 로컬 서버의 `llm_base_url`과 `llm_model`도 함께 변경하세요. Ollama 모델은 OpenRouter에 자동 적용되지 않습니다.
- 기본 API 주소는 `llm_base_url`입니다. 로컬 텍스트 모델과 OpenRouter 미디어를 함께 쓰거나 주소를 별도로 지정하려면 `openrouter_base_url`을 사용할 수 있습니다.
- `python3 scripts/preflight_local.py`는 인증, 모델 존재 여부, 이미지·영상 입력·음성·전사 기능과 TTS 목소리를 확인합니다. 실제 생성과 업로드는 별도 검증이 필요합니다.
- 텍스트·이미지·레퍼런스 분석·템플릿 합성·TTS·자막 인식이 모두 OpenRouter를 호출합니다. 기존 `nanobanana2_api_key`, `GEMINI_API_KEY`, `assembly_ai_api_key`는 읽지 않습니다.
- 이전 `nanobanana2_model`/`nanobanana2_aspect_ratio`, `gemini_tts_model`/`gemini_tts_voice`는 새 이름이 없을 때만 호환용으로 읽습니다. `gemini-*` 모델명에는 `google/`를 붙이고, `tts_provider=gemini`도 OpenRouter로 연결합니다.
- Gemini TTS는 PCM으로 받아 WAV로 저장합니다. 말투 지시는 `instructions`로 전달하고 대본과 분리합니다. 실패 시 로컬 TTS로 자동 대체하지 않습니다.
- 자막은 제공자가 반환한 실제 구간·단어 타임스탬프로 만듭니다. 타임스탬프가 없으면 오류를 표시하며 임의로 시간을 만들지 않습니다.
- 공개 YouTube URL 분석은 OpenRouter의 Google AI Studio 경로를 사용합니다. 원본 영상을 내려받지 않습니다.
- 앱은 필요한 시점에만 모델과 음원을 준비하도록 정리돼 있습니다.
- YouTube 스케줄러를 돌릴 때는 `Songs/`에 음원이 준비돼 있어야 합니다.

## API 참고

- [이미지 생성](https://openrouter.ai/docs/guides/overview/multimodal/image-generation)
- [Gemini TTS](https://openrouter.ai/docs/guides/overview/multimodal/tts)
- [타임스탬프를 포함한 음성 인식](https://openrouter.ai/docs/guides/overview/multimodal/stt)
- [YouTube 영상 입력](https://openrouter.ai/docs/guides/overview/multimodal/videos)
