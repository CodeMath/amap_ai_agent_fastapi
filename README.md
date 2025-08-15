## AMAP(AI + Tmap)

> FastAPI 로 구축한 AI Agent 기반 Chat 입니다.

### 사이드프로젝트 리뷰
[📝 Notion 리뷰 보기](https://jadecon.notion.site/AMAP-AI-21640f9a6b7c800d898fc4d539dc5e29)

* MVP 수준으로 코드 퀄리티는 보장하지 못합니다.
* 코드 내 SECRET_KEY는 임시 JWT 해시키 입니다.


### Tech Stack

* python 3.13
* fastapi
* openai-agents


```bash
pip install -r requirements.txt
```

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```


### Feature
* 프롬프트 기반 AI Agent 챗봇 대화
* 웹검색 기반 최신 정보 사용
* Google Places API 를 통한, 위치 기반 챗봇 자동 생성
* 업적 시스템을 통한 게이미피케이션 추가


### Todo

- [X] JWT 인증
- [X] Google Map 기반 위도 경도 처리
- [x] ~~퀘스트~~ 업적 시스템 기획 및 구현
- [x] 챗봇 자동화 추가

### Deprecated: 운영 종료로 인한...
- [ ] AD
- [ ] OpenAI API -> LiteLLM Model 

## 테스트 및 커버리지

![Coverage](https://img.shields.io/badge/coverage-73%25-yellow)

```bash
pytest --cov=app --cov-report=term --cov-report=html
```

### 커버리지 리포트

| 파일 | Statements | Missing | Branches | Coverage |
|------|------------|---------|----------|----------|
| `app/__init__.py` | 0 | 0 | 0 | **100%** |
| `app/agents/api/__init__.py` | 0 | 0 | 0 | **100%** |
| `app/agents/api/achievement_router.py` | 36 | 10 | 0 | **72%** |
| `app/agents/api/agent_router.py` | 170 | 42 | 0 | **75%** |
| `app/agents/api/subsrbe_router.py` | 53 | 24 | 0 | **55%** |
| `app/agents/api/user_router.py` | 43 | 0 | 0 | **100%** |
| `app/agents/core/achivement_manager.py` | 68 | 7 | 0 | **90%** |
| `app/agents/core/agent_manager.py` | 273 | 90 | 0 | **67%** |
| `app/agents/core/d1_database.py` | 101 | 43 | 0 | **57%** |
| `app/agents/core/user_manager.py` | 11 | 6 | 0 | **45%** |
| `app/agents/schemas/achivement_schemas.py` | 13 | 0 | 0 | **100%** |
| `app/agents/schemas/agent_schemas.py` | 23 | 0 | 0 | **100%** |
| `app/agents/schemas/chat_schemas.py` | 28 | 0 | 0 | **100%** |
| `app/agents/schemas/user_schemas.py` | 10 | 0 | 0 | **100%** |
| **Total** | **829** | **222** | **0** | **73%** |

### 커버리지 요약

- **전체 커버리지**: 73%
- **테스트된 파일**: 14개
- **미테스트 파일**: 0개
- **스키마 파일들**: 100% 커버리지 (모든 Pydantic 모델)
- **API 라우터**: 평균 76% 커버리지
- **코어 로직**: 평균 65% 커버리지

### 개선 필요 영역

- `user_manager.py` (45%): 사용자 관리 기능 테스트 추가 필요
- `d1_database.py` (57%): 데이터베이스 쿼리 테스트 추가 필요
- `subsrbe_router.py` (55%): 구독 관련 기능 테스트 추가 필요

자세한 커버리지 리포트는 `htmlcov/index.html`에서 확인할 수 있습니다.

