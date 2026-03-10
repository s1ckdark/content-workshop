# Twitter/X Automation

이 기능은 주제 기반 텍스트를 생성하고 Firefox 프로필을 사용해 X에 직접 게시합니다.

## 필요한 설정

```json
{
  "twitter_language": "English",
  "headless": true,
  "ollama_base_url": "http://127.0.0.1:11434",
  "ollama_model": "llama3.2:3b"
}
```

## 메모

- 게시 기능과 스케줄러 기능 모두 Ollama 모델이 필요합니다.
- 로그인 상태가 유지된 Firefox 프로필이 필요합니다.
- X의 compose DOM 구조가 바뀌면 선택자 보정이 필요합니다.
