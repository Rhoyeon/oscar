---
name: ontology-design
description: "추출된 엔티티와 관계로부터 OWL/RDF 호환 온톨로지 스키마를 설계한다. 클래스 계층 구조 정의, 속성 도메인/레인지 설정, 표준 온톨로지(Schema.org, FOAF 등) 매핑이 필요하면 반드시 이 스킬을 사용할 것."
---

# Ontology Design Skill

## 목적

입력 분석 결과를 체계적인 온톨로지 스키마로 변환한다. 지식그래프 구축의 설계도 역할을 한다.

## 설계 원칙

### 클래스 계층 설계
- 최상위 클래스는 도메인의 핵심 개념만 포함 (3~7개 권장)
- 계층 깊이는 최대 5단계 (너무 깊으면 유지보수 어려움)
- 추상 클래스를 활용하여 공통 속성을 상위로 끌어올린다

### 표준 온톨로지 매핑 우선순위
1. Schema.org — 범용 웹 데이터
2. FOAF — 사람·조직·소셜 관계
3. Dublin Core — 문서·미디어 메타데이터
4. OWL Time — 시간 관련 개념
5. GeoSPARQL — 공간 데이터
6. 커스텀 네임스페이스 (`https://oscar.ai/ontology/`) — 위에 없는 경우

### 속성 설계
- **Object Property**: 엔티티 간 관계 (domain → range가 모두 Class)
- **Data Property**: 엔티티의 값 속성 (range가 xsd 타입)
- Cardinality 제약은 명확한 도메인 규칙이 있을 때만 설정

## 검증 체크리스트

- [ ] 순환 상속 없음
- [ ] 모든 속성에 domain과 range 정의
- [ ] 고아 클래스(부모 없는 비최상위 클래스) 없음
- [ ] 표준 온톨로지 매핑 주석 포함

## 출력 위치

`_workspace/02_ontology_schema.json` — 상세 스키마는 `references/ontology-patterns.md` 참조
