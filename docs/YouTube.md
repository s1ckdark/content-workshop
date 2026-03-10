# YouTube Shorts Studio

이 문서는 `컨텐츠제작소`의 YouTube Shorts 생성 파이프라인을 설명합니다.

## 동작 방식

YouTube 기능은 아래 구성으로 이어집니다.

1. Ollama로 아이디어 생성
2. 짧은 스크립트 생성
3. 제목과 설명 생성
4. 이미지 프롬프트 생성
5. Gemini 이미지 API로 장면 이미지 생성
6. KittenTTS로 음성 생성
7. faster-whisper 또는 AssemblyAI로 자막 생성
8. MoviePy로 세로 영상 합성
9. Chrome/Chromium 프로필을 이용해 YouTube Studio 업로드

## 필요한 설정

```json
{
  "browser_profile": "/path/to/chrome/user-data",
  "headless": true,
  "ollama_base_url": "http://127.0.0.1:11434",
  "ollama_model": "llama3.2:3b",
  "nanobanana2_api_key": "your_gemini_api_key",
  "threads": 4,
  "is_for_kids": false
}
```

## 참고

- 배경음악은 `Songs/` 폴더에 직접 넣거나 `zip_url`로 받아옵니다.
- 스케줄러는 foreground 방식입니다.
- DOM 구조가 바뀌면 Playwright 업로드가 깨질 수 있으니 정기 점검이 필요합니다.
