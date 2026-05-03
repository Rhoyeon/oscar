#!/usr/bin/env python3
"""Build knowledge graph from analyst extraction + ontology schema."""
import json
from collections import Counter, defaultdict
from pathlib import Path

WS = Path("/home/user/oscar/_workspace")
extraction = json.loads((WS / "01_analyst_extraction.json").read_text(encoding="utf-8"))
ontology = json.loads((WS / "02_ontology_schema.json").read_text(encoding="utf-8"))

# ---- Mapping rules ----
# Map entity type + name/id heuristics to ontology class id
TYPE_TO_CLASS = {
    "Person": "C002",
    "Organization": "C003",
    "Concept": "C100",
    "Technology": "C302",
    "Product": "C301",  # default; refined per id
    "Pattern": "C200",
    "Metric": "C500",
}

# Per-entity overrides for finer-grained class mapping
ENTITY_CLASS_OVERRIDES = {
    "E003": "C004",   # 카카오 AI Native 전략 팀 -> Team
    "E022": "C006",   # TeamLead
    "E023": "C007",   # Teammate
    "E026": "C008",   # Subagent
    "E010": "C303",   # 스킬 -> Skill class
    "E011": "C005",   # 에이전트 -> AIAgent
    "E012": "C304",   # 메타 스킬 -> MetaSkill
    "E013": "C104",   # 컴팩션 -> Mechanism
    "E014": "C102",   # Progressive Disclosure -> DesignPrinciple
    "E015": "C102",
    "E016": "C102",
    "E017": "C102",
    "E018": "C101",   # Prompt Engineering -> Paradigm
    "E019": "C101",
    "E009": "C101",   # 하네스 엔지니어링 -> Paradigm
    "E029": "C301",   # Harness
    "E030": "C301",
    "E031": "C301",
    "E032": "C301",
    "E033": "C106",   # Apache 2.0 -> License
    "E027": "C305",   # settings.json -> ConfigurationFile
    "E028": "C306",   # CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS -> EnvironmentVariable
    "E024": "C308",   # Shared Task List -> CommunicationChannel
    "E025": "C308",   # Mailbox -> CommunicationChannel
    "E040": "C402",   # 워크플로우 스텝
    "E041": "C402",
    "E042": "C402",
    "E043": "C402",
    "E044": "C402",
    "E045": "C402",
    "E046": "C005",   # researcher agent
    "E047": "C005",
    "E048": "C005",
    "E049": "C401",   # 7 State 워크플로우
    "E050": "C501",   # 5축 100점 평가 -> EvaluationSystem
    "E051": "C501",
    "E052": "C100",   # RPG 게이미피케이션 -> Concept
    "E053": "C104",   # 이벤트 소싱 -> Mechanism
    "E054": "C104",   # 스냅샷 압축
    "E055": "C307",   # Memorizer -> PublicationChannel
    "E056": "C307",
    "E057": "C307",
    "E058": "C307",
    "E059": "C307",
    "E060": "C404",   # A/B 실험 -> Experiment
    "E061": "C502",   # 품질 점수 -> QualityMetric
    "E062": "C502",
    "E063": "C502",
    "E064": "C105",   # 직무 Role
    "E065": "C105",
    "E066": "C105",
    "E067": "C105",
    "E068": "C105",
    "E069": "C105",
    "E070": "C103",   # AI Native 전략 -> Strategy
    "E020": "C302",   # Claude Code Tech
    "E021": "C302",   # Agent Teams Tech
    "E008": "C100",   # 하네스 -> Concept
    "E034": "C200",   # Patterns
    "E035": "C200",
    "E036": "C200",
    "E037": "C200",
    "E038": "C200",
    "E039": "C200",
}

# Predicate name -> property id
PRED_TO_PROP = {
    "worksFor": "P001",
    "leads": "P002",
    "memberOf": "P003",
    "partOf": "P004",
    "created": "P005",
    "authored": "P006",
    "operates": "P007",
    "drives": "P008",
    "quotedAbout": "P009",
    "follows": "P100",
    "supportsPattern": "P101",
    "usesPattern": "P102",
    "implements": "P103",
    "definesAgent": "P104",
    "definesSkill": "P105",
    "appliedTo": "P106",
    "evolvesInto": "P107",
    "hasMechanism": "P108",
    "logsVia": "P109",
    "featureOf": "P200",
    "includes": "P201",
    "uses": "P202",
    "activatedBy": "P203",
    "configuredIn": "P204",
    "differsFrom": "P205",
    "communicatesVia": "P206",
    "publishesTo": "P207",
    "licensedUnder": "P208",
    "hasWorkflow": "P300",
    "hasWorkflowStep": "P301",
    "hasState": "P302",
    "validatedBy": "P304",
    "measures": "P305",
    "evaluatedBy": "P306",
    "rolePerforms": "P400",
    "subClassOf": "P401",
}

# ---- Class label lookup ----
class_lookup = {c["id"]: c for c in ontology["classes"]}
prop_lookup = {p["id"]: p for p in ontology["properties"]}

# ---- Build nodes ----
entities = extraction["entities"]
attributes = extraction["attributes"]
relations = extraction["relations"]

attr_by_entity = defaultdict(dict)
for a in attributes:
    attr_by_entity[a["entity_id"]][a["key"]] = a["value"]

# Detect duplicates by normalized name (lowercased, stripped)
seen_names = {}
merged_duplicates = 0
entity_alias = {}  # original eid -> canonical eid
for e in entities:
    key = e["name"].strip().lower()
    if key in seen_names:
        canonical = seen_names[key]
        entity_alias[e["id"]] = canonical
        merged_duplicates += 1
    else:
        seen_names[key] = e["id"]
        entity_alias[e["id"]] = e["id"]

# Construct node objects (only canonical)
nodes = []
node_index = {}  # eid -> node dict
node_id_seq = 0
def class_label(cid):
    return class_lookup.get(cid, {}).get("name", cid)

slug_safe = lambda s: "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in s)

for e in entities:
    if entity_alias[e["id"]] != e["id"]:
        continue
    node_id_seq += 1
    nid = f"node_{node_id_seq:03d}"
    cls = ENTITY_CLASS_OVERRIDES.get(e["id"], TYPE_TO_CLASS.get(e["type"], "C100"))
    cls_name = class_label(cls)
    uri = f"https://oscar.ai/harness/instance/{cls_name}/{e['id']}"
    props = dict(attr_by_entity.get(e["id"], {}))
    props["description"] = e.get("description", "")
    props["entity_type_raw"] = e["type"]
    provisional = e.get("confidence", 1.0) < 0.6
    node = {
        "id": nid,
        "uri": uri,
        "class": cls,
        "class_label": cls_name,
        "label": e["name"],
        "entity_id": e["id"],
        "confidence": e.get("confidence"),
        "properties": props,
        "provisional": provisional,
    }
    nodes.append(node)
    node_index[e["id"]] = node

# ---- Build edges ----
edges = []
edge_id_seq = 0
schema_violations = []
warnings = []

# Validation issues V001/V002 — handle specific relations as data properties
DATA_PROPERTY_RELATIONS = {
    "R009": ("E008", "etymology", "마구(馬具)"),
    "R012": ("E021", "minVersion", "Claude Code v2.1.32"),
    "R069": ("E010", "definitionPath", ".claude/skills/"),
    "R070": ("E011", "definitionPath", ".claude/agents/"),
    "R071": None,  # MetaSkill subClassOf Skill: encoded in class hierarchy, skip
}

for r in relations:
    rid = r["id"]
    if rid in DATA_PROPERTY_RELATIONS:
        spec = DATA_PROPERTY_RELATIONS[rid]
        if spec is None:
            warnings.append(f"{rid} subClassOf encoded at class level (C304->C303); skipped at instance level.")
            continue
        eid, key, value = spec
        if eid in node_index:
            node_index[eid]["properties"][key] = value
        continue

    subj = entity_alias.get(r["subject"], r["subject"])
    obj = entity_alias.get(r["object"], r["object"])
    if subj not in node_index:
        warnings.append(f"{rid}: subject {r['subject']} not a known entity")
        continue
    if obj not in node_index:
        warnings.append(f"{rid}: object '{r['object']}' is a literal — not converted to edge")
        continue
    pred = r["predicate"]
    prop_id = PRED_TO_PROP.get(pred)
    if not prop_id:
        schema_violations.append(f"{rid}: predicate '{pred}' not in ontology properties")
        continue
    edge_id_seq += 1
    eid_e = f"edge_{edge_id_seq:03d}"
    weight = r.get("confidence", 1.0)
    provisional = weight < 0.6
    src_node = node_index[subj]["id"]
    tgt_node = node_index[obj]["id"]
    # Lightweight schema check: domain/range
    prop_meta = prop_lookup[prop_id]
    edges.append({
        "id": eid_e,
        "source": src_node,
        "target": tgt_node,
        "source_entity": subj,
        "target_entity": obj,
        "relation": prop_id,
        "relation_label": pred,
        "weight": weight,
        "provisional": provisional,
    })

# Compute hub statistics + isolated nodes
deg = Counter()
for ed in edges:
    deg[ed["source"]] += 1
    deg[ed["target"]] += 1

isolated = [n["id"] for n in nodes if deg[n["id"]] == 0]

stats = {
    "node_count": len(nodes),
    "edge_count": len(edges),
    "isolated_nodes": len(isolated),
    "merged_duplicates": merged_duplicates,
}

graph = {
    "nodes": nodes,
    "edges": edges,
    "stats": stats,
    "validation": {
        "schema_violations": schema_violations,
        "warnings": warnings,
        "isolated_node_ids": isolated,
    },
}

(WS / "03_knowledge_graph.json").write_text(
    json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8"
)

# ---- Top hubs ----
top_hubs = deg.most_common(5)
hub_info = []
nodes_by_id = {n["id"]: n for n in nodes}
for nid, d in top_hubs:
    n = nodes_by_id[nid]
    hub_info.append((n["label"], n["class_label"], d, n["entity_id"]))

# ---- Build TTL ----
ttl_lines = []
ttl_lines.append("@prefix harness: <https://oscar.ai/harness/> .")
ttl_lines.append("@prefix oscar: <https://oscar.ai/harness/instance/> .")
ttl_lines.append("@prefix ocls: <https://oscar.ai/harness/class/> .")
ttl_lines.append("@prefix oprop: <https://oscar.ai/harness/property/> .")
ttl_lines.append("@prefix schema: <https://schema.org/> .")
ttl_lines.append("@prefix foaf: <http://xmlns.com/foaf/0.1/> .")
ttl_lines.append("@prefix owl: <http://www.w3.org/2002/07/owl#> .")
ttl_lines.append("@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .")
ttl_lines.append("@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .")
ttl_lines.append("@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .")
ttl_lines.append("@prefix prov: <http://www.w3.org/ns/prov#> .")
ttl_lines.append("@prefix dcterms: <http://purl.org/dc/terms/> .")
ttl_lines.append("")

def ttl_iri_for_node(n):
    return f"oscar:{slug_safe(n['class_label'])}_{n['entity_id']}"

def ttl_escape(v):
    s = str(v).replace("\\", "\\\\").replace("\"", "\\\"")
    return f"\"{s}\""

# Class declarations (subset, focusing on used classes)
ttl_lines.append("# ---- Class hierarchy (subset) ----")
used_classes = {n["class"] for n in nodes}
for cid in sorted(used_classes):
    c = class_lookup[cid]
    iri = f"ocls:{slug_safe(c['name'])}"
    ttl_lines.append(f"{iri} a owl:Class ;")
    ttl_lines.append(f"    rdfs:label {ttl_escape(c['name'])} ;")
    if c.get("parent"):
        parent = class_lookup[c["parent"]]
        ttl_lines.append(f"    rdfs:subClassOf ocls:{slug_safe(parent['name'])} ;")
    if c.get("standard_mapping"):
        ttl_lines.append(f"    owl:equivalentClass {c['standard_mapping']} ;")
    ttl_lines.append(f"    rdfs:comment {ttl_escape(c['description'])} .")
    ttl_lines.append("")

# Property declarations
ttl_lines.append("# ---- Object/Data Properties ----")
used_props = {ed["relation"] for ed in edges}
for pid in sorted(used_props):
    p = prop_lookup[pid]
    iri = f"oprop:{slug_safe(p['name'])}"
    ptype = "owl:ObjectProperty" if p["type"] == "object" else "owl:DatatypeProperty"
    ttl_lines.append(f"{iri} a {ptype} ;")
    ttl_lines.append(f"    rdfs:label {ttl_escape(p['name'])} ;")
    if p.get("domain"):
        ttl_lines.append(f"    rdfs:domain ocls:{slug_safe(class_label(p['domain']))} ;")
    if p.get("range") and p["type"] == "object":
        ttl_lines.append(f"    rdfs:range ocls:{slug_safe(class_label(p['range']))} ;")
    if p.get("standard_mapping"):
        ttl_lines.append(f"    owl:equivalentProperty {p['standard_mapping']} ;")
    ttl_lines.append(f"    rdfs:comment {ttl_escape('Mapped from predicate ' + p['name'])} .")
    ttl_lines.append("")

# Instance triples
ttl_lines.append("# ---- Instances (nodes) ----")
for n in nodes:
    iri = ttl_iri_for_node(n)
    ttl_lines.append(f"{iri} a ocls:{slug_safe(n['class_label'])} ;")
    ttl_lines.append(f"    rdfs:label {ttl_escape(n['label'])} ;")
    ttl_lines.append(f"    dcterms:identifier {ttl_escape(n['entity_id'])} ;")
    if n.get("confidence") is not None:
        ttl_lines.append(f"    oprop:confidence \"{n['confidence']}\"^^xsd:decimal ;")
    if n["provisional"]:
        ttl_lines.append(f"    oprop:provisional \"true\"^^xsd:boolean ;")
    desc = n["properties"].get("description", "")
    if desc:
        ttl_lines.append(f"    rdfs:comment {ttl_escape(desc)} ;")
    # Selected data properties
    p = n["properties"]
    for k, v in p.items():
        if k in ("description", "entity_type_raw"):
            continue
        ttl_lines.append(f"    oprop:{slug_safe(k)} {ttl_escape(v)} ;")
    # close with period (replace last ;)
    if ttl_lines[-1].endswith(" ;"):
        ttl_lines[-1] = ttl_lines[-1][:-2] + " ."
    else:
        ttl_lines.append("    .")
    ttl_lines.append("")

# Edges
ttl_lines.append("# ---- Relations (edges) ----")
for ed in edges:
    src = nodes_by_id[ed["source"]]
    tgt = nodes_by_id[ed["target"]]
    src_iri = ttl_iri_for_node(src)
    tgt_iri = ttl_iri_for_node(tgt)
    prop_name = prop_lookup[ed["relation"]]["name"]
    ttl_lines.append(f"{src_iri} oprop:{slug_safe(prop_name)} {tgt_iri} .")

(WS / "03_knowledge_graph.ttl").write_text("\n".join(ttl_lines), encoding="utf-8")

# Print summary
print(f"Nodes: {stats['node_count']}")
print(f"Edges: {stats['edge_count']}")
print(f"Isolated: {stats['isolated_nodes']}")
print(f"Merged duplicates: {stats['merged_duplicates']}")
print(f"Schema violations: {len(schema_violations)}")
print(f"Warnings: {len(warnings)}")
print("Top 5 hubs:")
for label, cls, d, eid in hub_info:
    print(f"  - {label} [{cls}] (eid={eid}) degree={d}")
