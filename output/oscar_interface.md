---
name: oscar-harness-kb
description: "하네스 엔지니어링 지식베이스를 조회한다. 황민호 하네스, BloomLabs Content Harness, Claude Code Agent Teams, 아키텍처 패턴, A/B 실험 결과, 전문가별 활용법 등 하네스 엔지니어링 관련 모든 질문에 이 스킬을 사용할 것."
---

# Oscar Harness Knowledge Base

이 스킬은 Oscar 파이프라인이 구축한 하네스 엔지니어링 지식그래프(70 노드 / 68 엣지 / 33 온톨로지 클래스)를 조회하기 위한 인터페이스를 제공한다. 자연어, Python API, SPARQL 세 가지 방식이 지원된다.

## 1. 지식베이스 개요

- **도메인**: 하네스 엔지니어링 (Harness Engineering) — 2026년의 핵심 AI 엔지니어링 패러다임
- **출처**: `https://wiki.webnori.com/pages/viewpage.action?pageId=125731373`
- **네임스페이스**: `https://oscar.ai/harness/`
- **온톨로지**: 33 classes, 51 properties, 8 constraints
- **지식그래프**: 70 nodes, 68 edges, 평균 신뢰도 ≈ 0.90
- **임베딩**: 208 documents (70 nodes + 68 edges + 70 subgraphs), default `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- **검색 전략**: hybrid (vector + BM25, RRF 융합) + 1-hop 온톨로지 컨텍스트 확장

## 2. 쿼리 방법

### 2.1. 자연어 (권장)
```python
from oscar import query
result = query("황민호가 만든 하네스는 무엇인가?", top_k=5)
```
- 내부적으로 hybrid retrieval (vector + BM25) → ontology context expansion 수행
- 반환: `{"query", "top_k", "results": {"nodes": [...], "edges": [...], "subgraphs": [...]}}`

### 2.2. Python API (그래프 내비게이션)
```python
from oscar import get_node, get_neighbors, get_subgraph

node    = get_node("E029")                  # entity_id 또는 label로 조회
nbrs    = get_neighbors("E029", hops=1)     # 인접 엣지+노드
sub     = get_subgraph("E032", hops=2)      # 2-hop 서브그래프
```

### 2.3. SPARQL
- TTL: `_workspace/03_knowledge_graph.ttl`
- 예제 10개: `output/oscar_queries.sparql`
- prefix: `PREFIX oscar: <https://oscar.ai/harness/>`

## 3. 주요 엔티티 목록

### 인물 (Person)
| ID | Label | 비고 |
|----|-------|------|
| E001 | 황민호 | 카카오 AI Native 전략 팀 리더, `revfactory/harness` 제작자 |
| E004 | PSMON | 본 문서 작성자 |
| E005 | 메이커 에반 | "클로드 코드는 치매에 걸린 아인슈타인" 발언 |

### 조직 (Organization)
| ID | Label |
|----|-------|
| E002 | 카카오 |
| E003 | 카카오 AI Native 전략 팀 |
| E007 | BloomLabs |

### 하네스 제품 (Harness)
| ID | Label | 핵심 메타 |
|----|-------|-----------|
| E029 | `revfactory/harness` | v1.0.1, 2026-03-28, Apache 2.0, 6 워크플로우 단계, 6 패턴 |
| E030 | `revfactory/harness-100` | 10 도메인, 200 패키지, 1808 MD |
| E031 | `revfactory/claude-code-harness` | 참고 자료 레포 |
| E032 | BloomLabs Content Harness | v0.10.0, 3 에이전트, 11 스킬, 7 상태, 5축 평가 |

### 기술 (Technology)
| ID | Label | 비고 |
|----|-------|------|
| E020 | Claude Code | Anthropic 공식 CLI |
| E021 | Claude Code Agent Teams | v2.1.32+, experimental, `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` |

### 패러다임 (EngineeringParadigm)
- E018 프롬프트 엔지니어링 (2024) → E019 컨텍스트 엔지니어링 (2025) → E009 하네스 엔지니어링 (2026)

### 아키텍처 패턴 (ArchitecturePattern)
- E034 Pipeline · E035 Fan-out/Fan-in · E036 Expert Pool · E037 Producer-Reviewer · E038 Supervisor · E039 Hierarchical Delegation

### 6단계 워크플로우 (WorkflowStep)
1. E040 도메인분석 → 2. E041 팀아키텍처설계 → 3. E042 에이전트정의생성 → 4. E043 스킬생성 → 5. E044 통합&오케스트레이션 → 6. E045 검증&테스트

### A/B 실험 지표 (QualityMetric)
- E061 품질 점수 49.5 → 79.3 (+60%)
- E062 승률 0% → 100% (15전 15승)
- E063 출력 분산 −32%

### 전문가 역할 (Role) → 권장 패턴
- E064 개발자 → Fan-out/Fan-in + Expert Pool
- E065 PM/기획자 → Supervisor + Pipeline
- E066 콘텐츠 제작자 → Producer-Reviewer + Fan-out/Fan-in
- E067 QA 엔지니어 → Expert Pool + Pipeline
- E068 데이터 분석가 → Fan-out/Fan-in
- E069 교육자 → Hierarchical Delegation

## 4. 예시 쿼리

```python
from oscar import query

# 1) 인물·작품 관계
query("황민호가 만든 하네스와 그 라이선스는?")

# 2) 제품 구성
query("BloomLabs Content Harness가 사용하는 아키텍처 패턴과 발행 매체는?")

# 3) 활성화 절차
query("Claude Code Agent Teams를 활성화하려면 어떤 환경 변수가 필요한가?")

# 4) 패러다임 진화
query("프롬프트→컨텍스트→하네스 엔지니어링 진화 흐름을 설명")

# 5) 정량 결과
query("A/B 실험에서 측정된 품질 점수와 승률 변화는?")

# 6) 직무별 활용
query("PM이나 기획자에게 추천되는 에이전트 아키텍처 패턴은?")
```

## 5. 폴백 동작

- 임베딩 API 실패 시 → `sentence-transformers` (다국어 MiniLM) 자동 전환
- 벡터 DB 실패 시 → 로컬 Chroma 또는 in-memory store
- 두 백엔드가 모두 불가하면 BM25 단독으로 동작 (재현율 저하 경고 출력)

## 6. 참고 파일

- 온톨로지: `_workspace/02_ontology_schema.json`
- 지식그래프 JSON: `_workspace/03_knowledge_graph.json`
- 지식그래프 TTL: `_workspace/03_knowledge_graph.ttl`
- RAG 설정: `_workspace/04_rag_config.json`
- RAG 빌더: `_workspace/scripts/setup_rag.py`
