---
name: graph-construction
description: "온톨로지 스키마와 추출된 엔티티를 기반으로 실제 지식그래프를 구축한다. RDF Turtle, JSON-LD 형식 출력, 노드/엣지 생성, 중복 병합, 그래프 검증이 필요하면 반드시 이 스킬을 사용할 것."
---

# Graph Construction Skill

## 목적

온톨로지 스키마를 설계도 삼아 실제 지식그래프 인스턴스를 생성한다. 추출된 엔티티를 노드로, 관계를 엣지로 변환한다.

## 구축 프로세스

### 1. 노드 생성
- 각 엔티티 → 온톨로지 클래스에 매핑하여 인스턴스 생성
- URI 패턴: `https://oscar.ai/instance/{class}/{uuid}`
- confidence 0.6 미만 엔티티는 `provisional` 플래그 추가

### 2. 중복 병합 전략
동일 엔티티를 나타내는 노드를 병합한다:
- **정확 매칭**: 동일 레이블 + 동일 클래스 → 자동 병합
- **유사 매칭**: 편집거리 < 0.2 + 같은 클래스 → 병합 후 로그 기록
- **의미 유사**: 임베딩 유사도 > 0.95 → 사용자 확인 요청 플래그

### 3. 엣지 생성
- 관계 → 온톨로지 Object Property에 매핑
- 가중치(weight): 관계 confidence 값 사용
- 방향성: 모든 엣지는 기본적으로 방향 있음 (undirected는 명시 필요)

### 4. 출력 형식
- **JSON-LD**: 웹 표준, API 응답용
- **RDF Turtle**: 시맨틱 웹 도구 호환용
- **JSON Graph**: RAG 임베딩 및 내부 처리용

## 검증 기준

- 스키마 준수율 95% 이상 목표
- 고립 노드 비율 10% 미만 권장
- 평균 노드 연결도(degree) 2 이상 권장

## 출력 위치

`_workspace/03_knowledge_graph.json`, `_workspace/03_knowledge_graph.ttl`
