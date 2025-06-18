## AMAP(AI + Tmap)

> FastAPI 로 구축한 AI Agent 기반 Chat 입니다.

### Tech Stack

* python 3.13
* fastapi
* openai-agents

### 사이드프로젝트 리뷰
[Notion 리뷰 보기](https://jadecon.notion.site/AMAP-AI-21640f9a6b7c800d898fc4d539dc5e29)


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

```bash
pytest --cov=app --cov-report=term --cov-report=html
```

- 커버리지 리포트는 `htmlcov/index.html`에서 확인할 수 있습니다.

| Type      | Coverage |
|-----------|----------|
| Statements|  85%     |
| Branches  |  80%     |
| Functions |  90%     |
| Lines     |  85%     |
