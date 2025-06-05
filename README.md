
## AMAP(AI + Tmap)

> FastAPI 로 구축한 AI Agent 기반 Chat 입니다.

### Tech Stack

* fastapi
* openai-agents



```bash
pip install -r requirements.txt

uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Feature
* 프롬프트 기반 대화
* 웹검색 기반 최신 정보 사용


### Todo

- [X] JWT 인증
- [X] Google Map 기반 위도 경도 처리
- [ ] 퀘스트 시스템 기획 및 구현
- [ ] AD
- [ ] OpenAI API -> LiteLLM Model 
