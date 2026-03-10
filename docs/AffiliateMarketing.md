# Affiliate Campaigns

이 기능은 Amazon 상품 페이지를 읽고, 제품 정보 기반 홍보 문구를 만든 뒤 Twitter/X에 게시하는 흐름입니다.

## 동작 방식

1. 제휴 링크로 상품 페이지 접속
2. 제목과 핵심 특징 수집
3. Ollama로 짧은 홍보 문구 생성
4. 링크를 붙여 Twitter/X에 게시

## 필요한 설정

```json
{
  "firefox_profile": "/path/to/firefox/profile",
  "headless": true,
  "ollama_base_url": "http://127.0.0.1:11434",
  "ollama_model": "llama3.2:3b"
}
```

## 주의할 점

- 연결된 Twitter 계정 UUID가 유효해야 합니다.
- Amazon 페이지 구조가 바뀌면 선택자 수정이 필요할 수 있습니다.
