# 레퍼런스 기반 포맷 템플릿 — 설계 문서

> 2026-10-21 업데이트: 이 문서는 최초 Gemini 직접 호출 설계/계획의 기록입니다. 현재 구현은 OpenRouter를 사용합니다. API 설정과 모델은 [Configuration.md](../../Configuration.md)를 따릅니다.

- 작성일: 2026-09-14
- 상위 로드맵: "A. 반자동 니치 채널" 전략의 첫 번째 하위 프로젝트
- 상태: 설계 승인됨, 구현 계획 작성 전

## 1. 배경과 목표

현재 YouTube Shorts 파이프라인은 계정의 `niche` 한 줄로 LLM에게 즉흥 주제를 받아 고정된 스타일(4문장, 노란 자막, 영어 KittenTTS)로 영상을 만든다. 채널이 아직 없는 운영자에게는 니치를 추상적으로 정하기보다, **본인이 좋다고 판단한 쇼츠 URL에서 포맷을 역추출**하는 편이 현실적이다.

**목표**: 운영자가 레퍼런스 쇼츠 URL 1~10개를 입력하면, 파이프라인이 실제로 조절할 수 있는 값으로 구성된 "포맷 템플릿"을 만들고, 이를 YouTube 계정에 연결해 **스타일은 따르되 내용은 새로운** 영상을 반복 생성한다.

**성공 기준**
1. URL 2개 이상으로 템플릿을 생성·수정·저장·삭제할 수 있다.
2. 템플릿이 연결된 계정으로 생성한 영상의 주제·첫 문장·이미지 스타일·자막 색·문장 수가 템플릿을 따른다.
3. 생성 주제가 템플릿의 `avoid` 목록 및 해당 계정의 기존 영상 제목과 겹치지 않도록 프롬프트에 제약이 들어간다.
4. 한국어 계정에서 한국어 내레이션이 생성된다.
5. 템플릿이 없는 계정은 기존과 동일하게 동작한다.

## 2. 범위

**포함**: 레퍼런스 분석(Gemini 영상 이해), 템플릿 합성·저장, 템플릿 관리 UI, 계정-템플릿 연결, 생성 파이프라인 반영, Gemini TTS 제공자 추가, 순수 로직 단위 테스트.

**제외 (후속 하위 프로젝트)**: 검수 큐 편집 UI, YouTube Data API 업로드, YouTube Analytics 수집, 레퍼런스 자동 수집/템플릿 자동 갱신.

## 3. 원칙: 벤치마킹과 복제의 경계

| 허용 (템플릿에 반영) | 금지 (생성 시 차단) |
|---|---|
| 훅 유형, 흐름 구조, 길이/문장 수, 말투, 자막·이미지 스타일, 주제를 잡는 각도 | 레퍼런스의 구체적 주제, 대본 문장, 원본 영상·음성·썸네일 재사용 |

금지 항목은 `avoid` 필드로 코드상 강제한다. 영상 파일은 다운로드하지 않으며, 분석은 Gemini API의 공개 YouTube URL 입력 기능만 사용한다.

## 4. 아키텍처

```
[URL 1~10개] ─▶ ReferenceAnalyzer.analyze(url)   (URL마다 Gemini 1회)
                    │ 영상별 분석 dict
                    ▼
               templates.synthesize(analyses)
                 ├─ 규칙 계산: sentence_count, subtitle_color
                 ├─ Gemini 1회: topic_angle, hook_pattern, tone, visual_style, example_topics, niche
                 └─ 직접 수집: avoid
                    ▼
            TemplateReviewDialog (수정) ─▶ .mp/templates.json
                                                 ▲
YouTube 계정.template_id ────────────────────────┘
        ▼
VideoWorker → YouTube(template=...) → topic / script / prompts / combine
                                   → TTS(provider=gemini|kittentts, style=tone)
```

### 4.1 구성 요소

| 파일 | 상태 | 책임 | 의존 |
|---|---|---|---|
| `src/classes/ReferenceAnalyzer.py` | 신규 | `normalize_youtube_url(url) -> str \| None`, `analyze(url) -> dict`. Gemini REST 호출, 구조화 출력 | `config`, `requests` |
| `src/templates.py` | 신규 | `merge_numeric(analyses) -> dict`(규칙 계산), `synthesize(analyses, name) -> dict`, `get_templates()`, `get_template(id)`, `add_template(t)`, `remove_template(id)` | `cache.write_json_atomic`, `ReferenceAnalyzer` 결과 형식 |
| `src/prompts.py` | 신규 | 템플릿 유무에 따른 topic/script/image 프롬프트 문자열 구성 (순수 함수, 테스트 대상) | 없음 |
| `src/classes/Tts.py` | 변경 | `tts_provider` 분기, `synthesize(text, output_file, style=None)` | `config`, `requests`, `wave` |
| `src/classes/YouTube.py` | 변경 | 생성자에 `template: Optional[dict]`, 프롬프트 구성을 `prompts.py`로 위임, 자막 색 반영 | `prompts` |
| `src/ui/workers.py` | 변경 | `TemplateWorker` 추가, `VideoWorker`가 템플릿 로드 | `templates` |
| `src/ui/template_dialog.py` | 신규 | URL·이름 입력 다이얼로그, 결과 검토·수정 다이얼로그 | PySide6 |
| `src/ui/platforms.py` | 변경 | "포맷 템플릿" 플랫폼, `Platform.custom_add`, `FieldSpec.kind="choice"`, YouTube 계정 `template_id` 필드 | `templates` |
| `src/ui/main_window.py`, `src/ui/account_dialog.py` | 변경 | `custom_add` 분기, `choice` 필드 렌더링 | — |
| `src/config.py`, `config.example.json`, `docs/Configuration.md` | 변경 | 신규 설정 키 | — |

## 5. 데이터 모델

### 5.1 영상별 분석 결과 (`analyze` 반환값, 저장하지 않음 — 템플릿의 `analyses`에 원본 보존)

```json
{
  "url": "https://www.youtube.com/watch?v=ID",
  "topic": "구체적 주제 한 문장",
  "hook_text": "처음 3초 동안의 대사/문구",
  "hook_type": "question | shocking_fact | contrarian | list | story | other",
  "beats": ["흐름 단계 1", "흐름 단계 2"],
  "sentence_count": 6,
  "duration_sec": 38,
  "tone": "말투 서술",
  "visual_style": "비주얼 스타일 서술 (이미지 프롬프트에 붙일 수 있는 영어 문구)",
  "subtitle_color": "#FFFFFF",
  "language": "korean",
  "why_it_works": "효과적인 이유 서술"
}
```

Gemini `responseSchema`로 위 필드를 강제한다. `hook_type`은 enum.

### 5.2 템플릿 (`.mp/templates.json` → `{"templates": [...]}`)

```json
{
  "id": "uuid4",
  "name": "사용자 지정 이름",
  "created_at": "ISO-8601",
  "source_urls": ["..."],
  "niche": "한 줄 니치 요약",
  "topic_angle": "주제를 잡는 각도",
  "hook_pattern": "첫 문장 작성 지침",
  "sentence_count": 5,
  "tone": "말투 지침",
  "language": "korean",
  "visual_style": "이미지 프롬프트 접미 문구",
  "subtitle_color": "#FFFF00",
  "example_topics": ["레퍼런스와 겹치지 않는 후보 주제"],
  "avoid": ["레퍼런스 topic", "레퍼런스 hook_text"],
  "analyses": [ { "...5.1 형식..." } ]
}
```

### 5.3 합성 규칙

| 필드 | 방법 |
|---|---|
| `sentence_count` | `merge_numeric`에서 규칙으로 계산. 결과는 3~12로 clamp. **정확한 집계 방식(중앙값/최솟값/가중)은 구현 시 운영자가 직접 작성** |
| `subtitle_color` | 최빈값, 동률이면 첫 번째. `#RRGGBB` 형식이 아니면 `#FFFF00` |
| `language` | 최빈값 |
| `niche`, `topic_angle`, `hook_pattern`, `tone`, `visual_style`, `example_topics`(5개) | 분석 결과 전체를 입력으로 Gemini 1회 호출, 구조화 출력. `example_topics`는 `avoid`와 겹치지 않도록 지시 |
| `avoid` | 모든 분석의 `topic`, `hook_text`를 공백 제거·중복 제거하여 수집 (LLM 미사용) |

### 5.4 계정 확장

YouTube 계정 dict에 선택 필드 `template_id: str` 추가. 없거나 빈 문자열이면 템플릿 미사용.

## 6. 설정 키 (신규)

| 키 | 기본값 | 설명 |
|---|---|---|
| `reference_analysis_model` | `gemini-3.6-flash` | 영상 분석·합성용 Gemini 모델 |
| `tts_provider` | `kittentts` | `kittentts` \| `gemini` |
| `gemini_tts_model` | `""` (필수 입력 안내) | Gemini TTS 모델 ID |
| `gemini_tts_voice` | `""` | Gemini TTS 프리셋 음성 이름 |

API 키와 base URL은 기존 `nanobanana2_api_key`, `nanobanana2_api_base_url`을 재사용한다(`get_nanobanana2_api_key()`의 환경변수 폴백 포함).

## 7. 생성 파이프라인 반영

템플릿이 `None`이면 `prompts.py`는 **현재 프롬프트 문자열과 동일한 결과**를 반환한다(회귀 방지 테스트 대상).

| 단계 | 템플릿이 있을 때 |
|---|---|
| `generate_topic` | `niche`, `topic_angle`, `example_topics`(예시로만), `avoid`(금지), 계정 기존 영상 제목 최근 30개(금지)를 포함 |
| `generate_script` | 문장 수 = `template.sentence_count` (설정값보다 우선). 첫 문장은 `hook_pattern`, 전체는 `tone`. `avoid` 문구 사용 금지 |
| `generate_metadata` | 변경 없음 |
| `generate_prompts` | LLM이 만든 각 프롬프트 끝에 `, {visual_style}` 추가 (코드에서 붙임) |
| `combine` | 자막 색 = `template.subtitle_color`, 없으면 `#FFFF00` |
| 언어 | 계정 `language` 우선, 비었으면 `template.language` |
| TTS | `style = template.tone`을 `TTS.synthesize`에 전달 (Gemini 제공자만 사용, KittenTTS는 무시) |

## 8. TTS 제공자

- `kittentts`: 기존 동작 유지. 영어 전용.
- `gemini`: `{base_url}/models/{gemini_tts_model}:generateContent`로 `responseModalities: ["AUDIO"]`, `speechConfig.voiceConfig.prebuiltVoiceConfig.voiceName` 요청. `style`이 있으면 텍스트 앞에 "다음을 {style} 말투로 읽어 주세요:" 형태의 지시를 붙인다. 응답의 base64 PCM(16-bit, mono, 24kHz)을 `wave` 모듈로 WAV로 저장한다.
- 구현 전 공식 문서로 요청/응답 필드명과 PCM 사양을 재확인한다.
- 한국어 계정은 `whisper_model`을 `small` 이상으로 권장한다고 `docs/Configuration.md`에 명시한다.

## 9. UI 흐름

1. 사이드바 "포맷 템플릿" 선택 → 표 컬럼: 이름, 니치, 언어, 레퍼런스 수, ID.
2. [추가] → `TemplateInputDialog`: 이름(필수), URL 여러 줄(1~10개). 정규화 실패 URL은 입력 단계에서 목록으로 표시하고 진행을 막는다.
3. `JobDialog(TemplateWorker)`: "분석 중 i/N", "템플릿 합성 중" 진행 표시. `TemplateWorker`는 `VideoWorker`와 동일한 `progress/log/finished/failed` Signal 규약과 취소 체크를 따른다.
4. `TemplateReviewDialog`: 합성 필드를 폼으로 표시(`example_topics`, `avoid`는 줄 단위 텍스트). [저장] 시 `add_template`.
5. YouTube 계정 추가 다이얼로그에 "포맷 템플릿" 드롭다운(`FieldSpec(kind="choice")`, 첫 항목 "사용 안 함").
6. `Platform.custom_add: Optional[Callable[[QWidget], bool]]` — 설정되어 있으면 `_on_add`가 기본 `AccountDialog` 대신 호출하고, `True` 반환 시 표를 새로고침한다.

템플릿 수정 기능(저장 후 재편집)은 이번 범위에서 표 더블클릭 → `TemplateReviewDialog` 재사용으로 제공한다.

## 10. 오류 처리

| 상황 | 동작 |
|---|---|
| Gemini API 키 없음 | `TemplateWorker` 시작 즉시 `failed("Gemini API 키가 설정되지 않았습니다")` |
| URL 정규화 실패 | 입력 다이얼로그에서 차단 |
| 개별 URL 분석 실패 (HTTP 오류, 비공개/삭제 영상) | 로그에 URL·사유 기록 후 건너뜀 |
| 응답 JSON이 스키마와 불일치 | 해당 URL 1회 재시도, 재실패 시 건너뜀 |
| 성공한 분석 0개 | `failed`로 실패 URL 목록 표시 |
| 합성 LLM 호출 실패 | 1회 재시도, 재실패 시 `failed` (분석 결과는 로그로만 남김) |
| 계정의 `template_id`에 해당하는 템플릿 없음 | 경고 로그 후 템플릿 없이 생성 |
| Gemini TTS 실패 | 작업 실패로 처리 (조용히 KittenTTS로 대체하지 않음 — 언어 불일치 영상 방지) |
| 템플릿 삭제 시 연결된 계정 존재 | 삭제 확인 창에 연결 계정 수 표시 |

## 11. 테스트

`requirements-dev.txt`에 `pytest` 추가, `tests/` 신설. 외부 네트워크 호출 없음.

| 테스트 | 대상 |
|---|---|
| `test_url_normalize.py` | `watch?v=`, `/shorts/ID`, `youtu.be/ID`, 쿼리 파라미터 포함, 비YouTube/잘못된 ID → `None` |
| `test_merge_numeric.py` | 분석 1개, 짝수·홀수 개, clamp 경계, 잘못된 색상값, 언어 최빈값 |
| `test_prompts.py` | 템플릿 `None`일 때 기존 문자열과 동일, `avoid`·기존 제목·`hook_pattern` 포함 여부, `visual_style` 접미 |
| `test_templates_store.py` | 임시 디렉터리에서 추가/조회/삭제, 없는 ID 조회 → `None` |
| `test_reference_analyzer.py` | `requests.post` 모킹: 정상, HTTP 오류, 스키마 불일치 후 재시도 |
| `test_gemini_tts.py` | `requests.post` 모킹 → 생성 WAV의 채널/샘플폭/샘플레이트 확인 |

**수동 E2E**: 실제 공개 쇼츠 URL 2개 → 템플릿 생성·검토·저장 → 계정 연결 → 영상 1편 생성(업로드 안 함) → 주제가 `avoid`와 다른지, 자막 색·문장 수·한국어 내레이션 확인.

## 12. 위험과 대응

| 위험 | 대응 |
|---|---|
| Gemini YouTube URL 입력은 프리뷰 기능 — 요금·한도 변경 가능 | 분석은 템플릿 생성 시에만 호출, 모델명 설정화 |
| 생성물이 여전히 템플릿화된 반복 콘텐츠로 판단될 위험 | 이번 범위는 입력 품질 개선. 후속 "검수 큐"에서 사람 편집 단계 추가 |
| 로컬 LLM이 `avoid` 제약을 무시 | 후속 과제로 생성 후 문자열 유사도 검사 고려 (이번 범위 제외) |
| `YouTube.py`에 미커밋 변경 존재 | 구현 착수 전 해당 변경의 커밋 여부를 운영자와 확인 |
