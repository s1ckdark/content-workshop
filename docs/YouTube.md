# YouTube Shorts Studio

이 문서는 `컨텐츠제작소`의 YouTube Shorts 생성 파이프라인을 설명합니다.

## 동작 방식

YouTube 기능은 아래 구성으로 이어집니다.

1. OpenRouter로 아이디어 생성
2. 짧은 스크립트 생성
3. 제목과 설명 생성
4. 이미지 프롬프트 생성
5. OpenRouter의 Gemini 이미지 모델로 장면 이미지 생성
6. OpenRouter의 Gemini TTS로 음성 생성
7. OpenRouter의 Whisper로 자막 생성
8. MoviePy로 세로 영상 합성
9. Chrome/Chromium 프로필을 이용해 YouTube Studio 업로드

## 필요한 설정

```json
{
  "browser_profile": "/path/to/chrome/user-data",
  "headless": true,
  "llm_provider": "openrouter",
  "llm_base_url": "https://openrouter.ai/api/v1",
  "llm_model": "google/gemini-2.5-flash",
  "image_model": "google/gemini-3.1-flash-image-preview",
  "tts_provider": "openrouter",
  "openrouter_tts_model": "google/gemini-3.1-flash-tts-preview",
  "openrouter_tts_voice": "Kore",
  "stt_provider": "openrouter",
  "openrouter_stt_model": "openai/whisper-1",
  "threads": 4,
  "is_for_kids": false
}
```

## 참고

- 앱 실행 환경에 `OPENROUTER_API_KEY`를 설정합니다. Google Gemini 키는 필요하지 않습니다.
- 레퍼런스 기능 브랜치에서는 공개 YouTube URL을 OpenRouter로 분석하고, 저장한 템플릿을 주제·대본·이미지·음성 말투·자막 스타일에 적용합니다.
- 배경음악은 `Songs/` 폴더에 직접 넣거나 `zip_url`로 받아옵니다.
- 스케줄러는 foreground 방식입니다.
- DOM 구조가 바뀌면 Playwright 업로드가 깨질 수 있으니 정기 점검이 필요합니다.
