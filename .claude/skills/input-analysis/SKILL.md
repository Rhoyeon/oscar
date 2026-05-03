---
name: input-analysis
description: "텍스트, PDF, JSON, CSV, URL, 코드 등 모든 형식의 입력 데이터를 파싱하고 엔티티·관계·도메인 개념을 추출한다. 온톨로지나 지식그래프 생성을 위한 원시 데이터 분석, 문서에서 개념 추출, 데이터 구조 파악이 필요하면 반드시 이 스킬을 사용할 것."
---

# Input Analysis Skill

## 목적

Oscar 파이프라인의 첫 단계. 입력 데이터에서 온톨로지 설계와 지식그래프 구축에 필요한 구조화된 정보를 추출한다.

## 입력 형식 감지

입력 형식을 자동 감지하고 적합한 파서를 선택한다:

| 형식 | 감지 방법 | 파싱 전략 |
|-----|---------|---------|
| 텍스트/문서 | .txt, .md, .docx | NLP 기반 NER + 관계 추출 |
| PDF | .pdf | 텍스트 추출 후 NLP 처리 |
| 구조화 데이터 | .json, .csv, .xml | 스키마 추론 + 값 분류 |
| URL | http(s):// | 웹 크롤링 + 텍스트 추출 |
| 코드 | .py, .js, .ts 등 | AST 파싱 + 의존성 추출 |

## 추출 대상

1. **엔티티(Entity)**: 고유하게 식별 가능한 개념/객체
2. **관계(Relation)**: 엔티티 간 연결 (동사구, 전치사구 등)
3. **속성(Attribute)**: 엔티티의 특성·값
4. **도메인 개념(Concept)**: 추상적 카테고리·분류

## 품질 기준

- 엔티티 신뢰도 임계값: 0.6 이상만 포함 (미만은 ambiguities에 기록)
- 관계 추출은 명시적 표현 우선, 암시적 관계는 confidence 0.7 미만으로 표기
- 동일 엔티티의 다른 표현(동의어, 약어)은 canonical form으로 통합

## 출력 위치

`_workspace/01_analyst_extraction.json` — 상세 스키마는 `references/extraction-schema.md` 참조
