---
name: oscar-harness-kb
description: "하네스 엔지니어링 지식베이스를 조회한다. 황민호 하네스, BloomLabs Content Harness, Claude Code Agent Teams, 아키텍처 패턴, A/B 실험 결과, 전문가별 활용법 등 하네스 엔지니어링 관련 모든 질문에 이 스킬을 사용할 것."
---

# Oscar Harness Knowledge Base

Oscar 파이프라인이 구축한 **하네스 엔지니어링 지식베이스**를 조회하는 스킬이다.
온톨로지(33 클래스 / 53 속성), 지식그래프(70 노드 / 68 엣지), RAG(208 임베딩)을
하나의 자연어/SPARQL/Python 인터페이스로 통합 노출한다.

## 1. 지식베이스 개요

| 항목 | 값 |
|------|----|
| 네임스페이스 | `https://oscar.ai/harness/` |
| 출처 | https://wiki.webnori.com/pages/viewpage.action?pageId=125731373 |
| 온톨로지 클래스 | 33 |
| 온톨로지 속성 | 53 |
| 그래프 노드 | 70 |
| 그래프 엣지 | 68 |
| RAG 임베딩 | 208 (노드 70 + 엣지 68 + 서브그래프 70) |
| 벡터 스토어 | Chroma (fallback: in-memory) |
| 임베딩 백엔드 | sentence-transformers (multilingual MiniLM) / OpenAI / hash-stub |
| 검색 전략 | Hybrid (BM25 + Vector, RRF 융합) + 1-hop 컨텍스트 확장 |

## 2. 쿼리 방법

### A. 자연어 (권장)

```python
from oscar import query
result = query("황민호가 만든 하네스는 무엇인가?", top_k=5)
```

### B. 노드/이웃 직접 조회

```python
from oscar import get_node, get_neighbors, get_subgraph
get_node("revfactory/harness")          # 라벨로 노드 조회
get_neighbors("BloomLabs Content Harness", hops=1)
get_subgraph("Claude Code Agent Teams", hops=2)
```

### C. SPARQL

`output/oscar_queries.sparql` 의 예제 10개 참고. RDF Turtle은
`_workspace/03_knowledge_graph.ttl` 에 직렬화되어 있다.

## 3. 주요 엔티티 (허브 Top 10)

| 라벨 | 클래스 | 비고 |
|------|--------|------|
| revfactory/harness | Harness | 황민호의 OSS 하네스 v1.0.1 (Apache 2.0). 6 워크플로우 단계, 6 패턴 지원, 4 설계 원칙 따름 |
| BloomLabs Content Harness | Harness | v0.10.0. 3 에이전트(researcher/writer/evaluator), 5 발행 매체, 5축+3축 평가 |
| Claude Code Agent Teams | Technology | Claude Code v2.1.32+ 실험 기능. CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1로 활성화 |
| Claude Code | Technology | Anthropic 공식 코딩 CLI. 컴팩션 메커니즘 보유 |
| 황민호 | Person | 카카오 AI Native 전략 팀 리더, GitHub: revfactory |
| A/B 실험 | Experiment | revfactory/harness 검증 실험 (3개 지표 측정) |
| 하네스 엔지니어링 | EngineeringParadigm | 2026 패러다임 (프롬프트→컨텍스트→하네스로 진화) |
| Producer-Reviewer | ArchitecturePattern | BloomLabs가 사용. 콘텐츠 제작자 역할에 매핑 |
| 5축 100점 평가 | EvaluationSystem | BloomLabs 콘텐츠 평가 체계 |
| 7 State 워크플로우 | Workflow | BloomLabs idle→recording 7개 상태 |

## 4. 주요 클래스 카테고리

- **Agent 계열** (C001~C008): Person, Organization, Team, AIAgent, TeamLead, Teammate, Subagent
- **Concept 계열** (C100~C106): EngineeringParadigm, DesignPrinciple, Strategy, Mechanism, Role, License
- **Artifact 계열** (C300~C308): Harness, Technology, Skill, MetaSkill, ConfigurationFile, EnvironmentVariable, PublicationChannel, CommunicationChannel
- **Process 계열** (C400~C404): Workflow, WorkflowStep, WorkflowState, Experiment
- **Metric 계열** (C500~C502): EvaluationSystem, QualityMetric
- **ArchitecturePattern** (C200): Pipeline, Fan-out/Fan-in, Expert Pool, Producer-Reviewer, Supervisor, Hierarchical Delegation

## 5. 예시 쿼리

```python
query("황민호가 만든 하네스는 무엇인가?")
query("BloomLabs Content Harness가 사용하는 아키텍처 패턴과 발행 매체는?")
query("Claude Code Agent Teams를 활성화하려면 어떤 환경 변수가 필요한가?")
query("하네스 엔지니어링 패러다임은 어떤 흐름으로 진화했는가?")
query("A/B 실험에서 측정된 품질 지표 변화는?")
query("개발자 역할이 활용하는 아키텍처 패턴은?")
query("revfactory/harness가 따르는 설계 원칙들은?")
query("BloomLabs 하네스의 7 State 워크플로우 구성")
query("Teammate와 Subagent의 차이는?")
query("민호 하네스의 6단계 워크플로우 순서")
```

## 6. 활용 트리거

다음 키워드가 등장하면 이 스킬을 사용하라:
- 하네스 / harness / 하네스 엔지니어링
- 황민호 / revfactory / 카카오 AI Native
- BloomLabs / Content Harness
- Claude Code Agent Teams / Teammates / Subagent
- Progressive Disclosure / Why-First / 경계 검증
- Pipeline / Fan-out / Expert Pool / Producer-Reviewer / Supervisor / Hierarchical Delegation
- A/B 실험 / 품질 점수 / 승률 / 출력 분산
- 5축 100점 / 디자인 3축 / 7 State 워크플로우
