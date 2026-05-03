# Oscar 파이프라인 결과 요약

**생성일**: 2026-05-03
**소스**: https://wiki.webnori.com/pages/viewpage.action?pageId=125731373
**도메인**: 하네스 엔지니어링 (Harness Engineering)
**네임스페이스**: `https://oscar.ai/harness/`

---

## 1. 파이프라인 통계

| 단계 | 산출물 | 규모 |
|------|--------|------|
| 01. 추출 | `01_analyst_extraction.json` | 원시 엔티티/관계 추출 |
| 02. 온톨로지 | `02_ontology_schema.json` | **33 classes, 51 properties, 8 constraints** |
| 03. 지식그래프 | `03_knowledge_graph.json` (+ `.ttl`) | **70 nodes, 68 edges, 5 isolated** |
| 04. RAG | `04_rag_config.json` | **208 임베딩** (70 nodes + 68 edges + 70 subgraphs) |
| 05. 인터페이스 | `output/` | skill / python / sparql / NL |

### 온톨로지 계층 (주요 루트)
- **Agent (C001)** → Person, Organization → Team, AIAgent → TeamLead/Teammate/Subagent
- **Concept (C100)** → EngineeringParadigm, DesignPrinciple, Strategy, Mechanism, Role, License
- **ArchitecturePattern (C200)**
- **Artifact (C300)** → Harness, Technology, Skill→MetaSkill, ConfigurationFile, EnvironmentVariable, PublicationChannel, CommunicationChannel
- **Process (C400)** → Workflow, WorkflowStep, WorkflowState, Experiment
- **Metric (C500)** → EvaluationSystem, QualityMetric

### 그래프 검증
- 스키마 위반: 0건
- 경고: 1건 (R071 `MetaSkill subClassOf Skill` — 클래스 계층으로 직접 인코딩됨)
- 고립 노드 5개: node_006(오후다섯씨), node_008(Subagent 미참조 인스턴스), node_010(스킬 개념), node_011(에이전트 개념), node_031(`revfactory/claude-code-harness`)

---

## 2. 주요 허브 노드 Top 5 (degree 기준)

| 순위 | Entity | Label | Class | 차수 | 역할 |
|------|--------|-------|-------|-----:|------|
| 1 | E029 | revfactory/harness | Harness | **23** | 전체 그래프의 중심. 6 워크플로우 단계 + 6 패턴 + 4 디자인 원칙 + A/B 검증을 모두 보유 |
| 2 | E032 | BloomLabs Content Harness | Harness | **15** | 콘텐츠 도메인 허브. 3 에이전트, 7 상태 워크플로우, 5 발행 매체, 2 평가 체계 |
| 3 | E021 | Claude Code Agent Teams | Technology | **8** | Agent Teams 기능 허브. TeamLead/Teammate/Subagent, 통신 채널, 활성화 ENV 연결 |
| 4 | E001 | 황민호 | Person | **5** | `revfactory/harness`·`harness-100` 제작자, 카카오 AI Native 전략 팀 리더 |
| 5 | E060 | A/B 실험 | Experiment | **4** | revfactory/harness 검증 실험, 3개 정량 지표 측정 |

---

## 3. 예시 쿼리와 기대 결과

### Q1. "황민호가 만든 하네스는 무엇인가?"
- **검색 경로**: 자연어 → BM25(`황민호`, `하네스`) ⊕ vector(임베딩) → RRF 융합 → 1-hop 확장
- **반환**: E029(`revfactory/harness`, v1.0.1, Apache 2.0), E030(`revfactory/harness-100`, 10도메인/200패키지)
- **컨텍스트**: P005(created) 엣지 2건, 클래스 경로 Harness→Artifact

### Q2. "BloomLabs Content Harness가 사용하는 아키텍처 패턴과 발행 매체는?"
- **반환**:
  - 패턴: Producer-Reviewer (P102 usesPattern)
  - 매체 5개: Memorizer, Confluence, Webnori Wiki, private-doc, Pencil Design (P207 publishesTo)

### Q3. "Claude Code Agent Teams를 활성화하려면?"
- **반환 체인**: E021 —activatedBy→ E028(`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`) —configuredIn→ E027(`settings.json`)
- **부가 정보**: minVersion=`Claude Code v2.1.32`, status=`experimental`

### Q4. "패러다임 진화"
- **반환**: E018 프롬프트(2024) → E019 컨텍스트(2025) → E009 하네스(2026), 모두 P107(evolvesInto), Claude Code(E020)에 적용됨

### Q5. "A/B 실험 지표"
- **반환**:
  - 품질 점수 49.5 → 79.3 (+60%)
  - 승률 0% → 100% (15전 15승)
  - 출력 분산 −32%

---

## 4. 활용 방법 가이드

### 4.1. Claude 에이전트로 사용
`output/oscar_interface.md` 를 `.claude/skills/oscar-harness-kb/SKILL.md` 로 배치하면 자동 트리거된다. description의 키워드(황민호, BloomLabs, Agent Teams, 아키텍처 패턴, A/B, 전문가 활용)에 매칭되는 사용자 질문이 들어오면 호출된다.

### 4.2. Python 코드에서 사용
```python
import sys; sys.path.insert(0, "output")
from oscar import query, get_node, get_neighbors, get_subgraph

query("Producer-Reviewer 패턴은 어디서 쓰이나?", top_k=5)
get_node("E029")
get_neighbors("E032", hops=1)
get_subgraph("황민호", hops=2)
```

### 4.3. SPARQL
```bash
# rdflib 예시
python -c "
import rdflib
g = rdflib.Graph().parse('_workspace/03_knowledge_graph.ttl', format='turtle')
for r in g.query(open('output/oscar_queries.sparql').read().split('# Q1.')[1].split('# Q2.')[0]):
    print(r)
"
```

### 4.4. 직무별 진입점
- 개발자 → Q3 (Agent Teams 활성화) → Q9 (직무별 패턴)
- 콘텐츠 제작자 → Q4 (BloomLabs 발행 매체) → Q9
- 의사결정자 → Q8 (A/B 결과) → Q6 (패러다임 진화)

---

## 5. 한계 및 향후 개선

- 고립 노드 5개는 텍스트 추출 단계의 ambiguity로 인한 미참조 → 인스턴스 재추출 시 제거 가능
- BloomLabs 운영 주체는 confidence 0.85 — 추가 출처로 보강 권장
- 워크플로우 단계 순서(P303 stepOrder)가 그래프에는 미기재 — 도메인 분석으로 보강 필요
