---
name: oscar-orchestrator
description: "Oscar 에이전트 팀을 조율하여 입력 데이터로부터 온톨로지·지식그래프·RAG 시스템을 자동 생성한다. '온톨로지 만들어줘', '지식그래프 생성해줘', '이 문서로 RAG 만들어줘', '지식베이스 구축해줘', '다시 실행', '재실행', '업데이트', '추가 데이터로 보완', '결과 개선', '이전 결과 기반으로 수정' 등 Oscar 관련 모든 요청에 반드시 이 스킬을 사용할 것."
---

# Oscar Orchestrator

## 역할

Oscar 파이프라인의 총지휘자. 5개 전문 에이전트를 팀으로 구성하고, 입력부터 최종 인터페이스 생성까지 전체 워크플로우를 조율한다.

**실행 모드:** 에이전트 팀 (TeamCreate + TaskCreate + SendMessage)

---

## Phase 0: 컨텍스트 확인

실행 시작 시 이전 실행 결과 존재 여부를 확인한다:

```
_workspace/ 존재 여부 확인
├── 없음 → 초기 실행 (Phase 1부터)
├── 있음 + 사용자가 부분 수정 요청 → 부분 재실행 (해당 에이전트만)
└── 있음 + 새 입력 제공 → 새 실행 (_workspace를 _workspace_prev/로 이동)
```

---

## Phase 1: 팀 구성

```python
TeamCreate(
  team_name="oscar-pipeline",
  members=["input-analyst", "ontology-architect", "graph-builder", "rag-engineer", "interface-agent"]
)
```

작업 할당:
```python
TaskCreate([
  {"id": "T1", "agent": "input-analyst", "title": "입력 데이터 분석 및 엔티티 추출"},
  {"id": "T2", "agent": "ontology-architect", "title": "온톨로지 스키마 설계", "depends_on": ["T1"]},
  {"id": "T3", "agent": "graph-builder", "title": "지식그래프 구축", "depends_on": ["T2"]},
  {"id": "T4", "agent": "rag-engineer", "title": "RAG 시스템 구성", "depends_on": ["T3"]},
  {"id": "T5", "agent": "interface-agent", "title": "에이전트 인터페이스 생성", "depends_on": ["T4"]}
])
```

---

## Phase 2~5: 파이프라인 실행

각 에이전트는 이전 에이전트의 SendMessage를 받은 후 작업을 시작한다.

**데이터 전달 경로:**
```
입력 데이터
  → [input-analyst] → _workspace/01_analyst_extraction.json
  → [ontology-architect] → _workspace/02_ontology_schema.json
  → [graph-builder] → _workspace/03_knowledge_graph.json + .ttl
  → [rag-engineer] → _workspace/04_rag_config.json
  → [interface-agent] → output/
```

---

## 에러 핸들링

| 상황 | 처리 방식 |
|-----|---------|
| 에이전트 작업 실패 | 1회 재시도, 재실패 시 다음 단계 건너뜀 + 보고서에 기록 |
| 중간 파일 누락 | 누락된 단계부터 재실행 |
| 전체 파이프라인 중단 | 마지막 성공 단계의 결과를 보존하고 실패 지점 보고 |

---

## 부분 재실행 (후속 작업)

특정 단계만 다시 실행할 때:

```
"입력 추가해줘" → T1(input-analyst)부터 재실행
"온톨로지 수정해줘" → T2(ontology-architect)부터 재실행
"RAG 설정 바꿔줘" → T4(rag-engineer)부터 재실행
```

---

## 완료 보고

전체 파이프라인 완료 시 사용자에게 요약 보고:

```markdown
## Oscar 실행 완료

- **온톨로지**: 클래스 {N}개, 속성 {M}개
- **지식그래프**: 노드 {N}개, 엣지 {M}개
- **RAG**: 임베딩 {N}개, 검색 전략: 하이브리드
- **출력 파일**: output/ 디렉토리

다른 에이전트에서 Oscar를 사용하려면 `output/oscar_interface.md` 참조
```

완료 후 피드백을 요청한다: "결과에서 개선할 부분이 있나요?"

---

## 테스트 시나리오

**정상 흐름:**
1. "이 회사 조직도 PDF로 지식그래프 만들어줘"
2. input-analyst → ontology-architect → graph-builder → rag-engineer → interface-agent 순 실행
3. `output/oscar_interface.md` 생성 확인

**에러 흐름:**
1. PDF 파싱 실패 → "지원되는 형식으로 변환 후 재시도" 안내
2. 임베딩 API 실패 → 로컬 모델로 자동 전환 후 계속 진행
