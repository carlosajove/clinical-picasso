"""In-memory graph client with the same interface as the OmniGraph CLI wrapper.

Stores nodes and edges as Python dicts. Supports the named queries defined
in the ``queries/`` directory via a built-in query engine that interprets
the query names and parameters.

This replaces the OmniGraph CLI wrapper so the pipeline can run without
an external binary.  The public API is identical:
  init, load, load_jsonl, query, mutate, export, snapshot.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path


class OmniGraphClient:
    """In-memory knowledge graph with the OmniGraph-compatible interface."""

    def __init__(
        self,
        repo_path: str | Path,
        schema_path: str | Path | None = None,
        queries_dir: str | Path | None = None,
    ) -> None:
        self.repo_path = Path(repo_path)
        self.schema_path = Path(schema_path) if schema_path else None
        self.queries_dir = Path(queries_dir) if queries_dir else None

        # Storage: {node_type: {key_value: {field: value, ...}}}
        self._nodes: dict[str, dict[str, dict]] = defaultdict(dict)
        # Storage: [(edge_type, from_key, to_key, {field: value})]
        self._edges: list[tuple[str, str, str, dict]] = []

        # Schema: parsed node key fields and edge definitions
        self._node_keys: dict[str, str] = {}  # node_type -> key_field_name
        self._initialized = False

    # ------------------------------------------------------------------ init

    def init(self, schema_path: str | Path | None = None) -> None:
        """Parse the schema to learn node key fields."""
        schema = Path(schema_path) if schema_path else self.schema_path
        if schema is None:
            raise ValueError("schema_path required for init")
        self._parse_schema(schema)
        self._initialized = True

    def _parse_schema(self, schema_path: Path) -> None:
        text = schema_path.read_text()
        # Extract node types and their @key fields
        for m in re.finditer(r'node\s+(\w+)\s*\{([^}]+)\}', text):
            node_type = m.group(1)
            body = m.group(2)
            for field_m in re.finditer(r'(\w+)\s*:\s*\S+.*?@key', body):
                self._node_keys[node_type] = field_m.group(1)

    # ------------------------------------------------------------------ load

    def load(
        self,
        data_path: str | Path,
        *,
        branch: str = "main",
        mode: str = "append",
    ) -> None:
        data_path = Path(data_path)
        lines = [json.loads(line) for line in data_path.read_text().strip().splitlines() if line.strip()]
        for item in lines:
            self._ingest_item(item)

    def load_jsonl(
        self,
        lines: list[dict],
        *,
        branch: str = "main",
        mode: str = "append",
    ) -> None:
        for item in lines:
            self._ingest_item(item)

    def _ingest_item(self, item: dict) -> None:
        if "type" in item and "data" in item:
            # Node
            node_type = item["type"]
            data = item["data"]
            key_field = self._node_keys.get(node_type)
            if key_field and key_field in data:
                key_val = data[key_field]
                # Upsert: merge new data into existing
                if key_val in self._nodes[node_type]:
                    self._nodes[node_type][key_val].update(
                        {k: v for k, v in data.items() if v is not None}
                    )
                else:
                    self._nodes[node_type][key_val] = dict(data)
            else:
                # No key — just store with a synthetic key
                self._nodes[node_type][str(len(self._nodes[node_type]))] = dict(data)
        elif "edge" in item:
            # Edge
            edge_type = item["edge"]
            from_key = item["from"]
            to_key = item["to"]
            edge_data = item.get("data", {})
            # Dedup: don't add identical edges
            for existing in self._edges:
                if existing[0] == edge_type and existing[1] == from_key and existing[2] == to_key:
                    return
            self._edges.append((edge_type, from_key, to_key, edge_data))

    # ------------------------------------------------------------------ read

    def read(
        self,
        query_file: str | Path,
        query_name: str,
        params: dict | None = None,
        *,
        branch: str | None = None,
    ) -> list[dict]:
        return self._execute_query(query_name, params or {})

    def query(
        self,
        query_name: str,
        params: dict | None = None,
        *,
        query_file: str | None = None,
        branch: str | None = None,
    ) -> list[dict]:
        return self._execute_query(query_name, params or {})

    # ----------------------------------------------------------------- change

    def change(
        self,
        query_file: str | Path,
        query_name: str,
        params: dict | None = None,
        *,
        branch: str | None = None,
    ) -> dict:
        return self._execute_mutation(query_name, params or {})

    def mutate(
        self,
        query_name: str,
        params: dict | None = None,
        *,
        query_file: str | None = None,
        branch: str | None = None,
    ) -> dict:
        return self._execute_mutation(query_name, params or {})

    # ---------------------------------------------------------------- export

    def export(self, *, branch: str | None = None) -> list[dict]:
        result = []
        for node_type, nodes in self._nodes.items():
            for data in nodes.values():
                result.append({"type": node_type, "data": dict(data)})
        for edge_type, from_key, to_key, data in self._edges:
            item = {"edge": edge_type, "from": from_key, "to": to_key}
            if data:
                item["data"] = dict(data)
            result.append(item)
        return result

    # ------------------------------------------------------------ snapshot

    def snapshot(self) -> str:
        lines = []
        for node_type, nodes in self._nodes.items():
            lines.append(f"\n=== {node_type} ({len(nodes)} nodes) ===")
            for key, data in nodes.items():
                lines.append(f"  [{key}] {json.dumps(data, default=str)[:200]}")
        lines.append(f"\n=== Edges ({len(self._edges)} total) ===")
        for edge_type, from_key, to_key, data in self._edges:
            extra = f" {data}" if data else ""
            lines.append(f"  {from_key} --[{edge_type}]--> {to_key}{extra}")
        return "\n".join(lines)

    # --------------------------------------------------------- query engine

    def _find_node(self, node_type: str, key_value: str) -> dict | None:
        return self._nodes.get(node_type, {}).get(key_value)

    def _find_nodes(self, node_type: str, **filters) -> list[dict]:
        results = []
        for data in self._nodes.get(node_type, {}).values():
            match = True
            for k, v in filters.items():
                if data.get(k) != v:
                    match = False
                    break
            if match:
                results.append(data)
        return results

    def _edges_of_type(self, edge_type: str) -> list[tuple[str, str, dict]]:
        return [(f, t, d) for et, f, t, d in self._edges if et == edge_type]

    def _edges_from(self, edge_type: str, from_key: str) -> list[tuple[str, dict]]:
        return [(t, d) for et, f, t, d in self._edges if et == edge_type and f == from_key]

    def _edges_to(self, edge_type: str, to_key: str) -> list[tuple[str, dict]]:
        return [(f, d) for et, f, t, d in self._edges if et == edge_type and t == to_key]

    def _has_edge(self, edge_type: str, from_key: str, to_key: str | None = None) -> bool:
        for et, f, t, _ in self._edges:
            if et == edge_type and f == from_key:
                if to_key is None or t == to_key:
                    return True
        return False

    def _is_superseded(self, doc_id: str) -> bool:
        """Check if any document supersedes this one."""
        return any(t == doc_id for _, _, t, _ in self._edges if _ == "Supersedes")

    def _is_superseded_check(self, doc_id: str) -> bool:
        for et, f, t, d in self._edges:
            if et == "Supersedes" and t == doc_id:
                return True
        return False

    def _superseder_of(self, doc_id: str) -> str | None:
        for et, f, t, d in self._edges:
            if et == "Supersedes" and t == doc_id:
                return f
        return None

    def _doc_prefix(self, data: dict) -> dict:
        return {f"doc.{k}": v for k, v in data.items()}

    def _trial_prefix(self, data: dict) -> dict:
        return {f"trial.{k}": v for k, v in data.items()}

    def _phase_prefix(self, data: dict) -> dict:
        return {f"phase.{k}": v for k, v in data.items()}

    def _traverse_edges(self, edge_type: str, start_id: str, max_hops: int = 10) -> list[str]:
        """Traverse edges in reverse (find nodes that point TO start via edge_type)."""
        visited = set()
        frontier = {start_id}
        for _ in range(max_hops):
            next_frontier = set()
            for et, f, t, _ in self._edges:
                if et == edge_type and t in frontier and f not in visited and f != start_id:
                    next_frontier.add(f)
            visited.update(next_frontier)
            frontier = next_frontier
            if not frontier:
                break
        return list(visited)

    def _execute_query(self, name: str, params: dict) -> list[dict]:
        """Dispatch named queries."""

        # --- match_existing.gq ---

        if name == "find_version_match":
            doc_type = params["doc_type"]
            trial_id = params["trial_id"]
            results = []
            for doc_id, data in self._nodes.get("Document", {}).items():
                if data.get("document_type") != doc_type:
                    continue
                # Check belongs to trial
                if not self._has_edge("BelongsToTrial", doc_id, trial_id):
                    continue
                # Not superseded
                if self._is_superseded_check(doc_id):
                    continue
                results.append(self._doc_prefix(data))
            return results

        if name == "find_trial":
            pid = params.get("trial_key") or params.get("protocol_id")
            trial = self._find_node("Trial", pid)
            if trial:
                return [self._trial_prefix(trial)]
            return []

        if name == "find_trial_by_nct":
            nct = params["nct_id"]
            for data in self._nodes.get("Trial", {}).values():
                if data.get("nct_id") == nct:
                    return [self._trial_prefix(data)]
            return []

        if name == "find_trial_by_eudract":
            eid = params["eudract_id"]
            for data in self._nodes.get("Trial", {}).values():
                if data.get("eudract_id") == eid:
                    return [self._trial_prefix(data)]
            return []

        if name == "find_doc_by_hash":
            h = params["content_hash"]
            for data in self._nodes.get("Document", {}).values():
                if data.get("content_hash") == h:
                    return [self._doc_prefix(data)]
            return []

        if name == "find_amendment_targets":
            doc_type = params["doc_type"]
            trial_id = params["trial_id"]
            results = []
            for doc_id, data in self._nodes.get("Document", {}).items():
                if data.get("document_type") != doc_type:
                    continue
                if not self._has_edge("BelongsToTrial", doc_id, trial_id):
                    continue
                if self._is_superseded_check(doc_id):
                    continue
                # Not already amended
                amended = any(et == "Amends" and t == doc_id for et, f, t, d in self._edges)
                if amended:
                    continue
                results.append(self._doc_prefix(data))
            return results

        # --- phase.gq ---

        if name == "find_phase":
            phase_id = params["phase_id"]
            phase = self._find_node("Phase", phase_id)
            if phase:
                return [self._phase_prefix(phase)]
            return []

        if name == "phase_documents":
            phase_id = params["phase_id"]
            results = []
            for et, f, t, d in self._edges:
                if et == "BelongsToPhase" and t == phase_id:
                    doc = self._find_node("Document", f)
                    if doc and not self._is_superseded_check(f):
                        results.append(self._doc_prefix(doc))
            return results

        if name == "trial_phases":
            pid = params.get("trial_key") or params.get("protocol_id")
            results = []
            for et, f, t, d in self._edges:
                if et == "HasPhase" and f == pid:
                    phase = self._find_node("Phase", t)
                    if phase:
                        results.append(self._phase_prefix(phase))
            return results

        # --- orphans.gq ---

        if name == "find_orphans":
            results = []
            for doc_id, data in self._nodes.get("Document", {}).items():
                has_any_edge = False
                for et, f, t, _ in self._edges:
                    if f == doc_id or t == doc_id:
                        has_any_edge = True
                        break
                if not has_any_edge:
                    results.append(self._doc_prefix(data))
            return results

        if name == "low_confidence":
            threshold = params.get("threshold", 0.6)
            results = []
            for data in self._nodes.get("Document", {}).values():
                if data.get("classification_confidence", 1.0) < threshold:
                    results.append(self._doc_prefix(data))
            return results

        # --- inconsistencies.gq ---

        if name == "stale_parents":
            results = []
            for et, child_id, parent_id, d in self._edges:
                if et != "DerivedFrom":
                    continue
                newer_id = self._superseder_of(parent_id)
                if newer_id is None:
                    continue
                child = self._find_node("Document", child_id)
                parent = self._find_node("Document", parent_id)
                newer = self._find_node("Document", newer_id)
                if child and parent and newer and not self._is_superseded_check(child_id):
                    row = {}
                    row.update({f"child.{k}": v for k, v in child.items()})
                    row.update({f"parent.{k}": v for k, v in parent.items()})
                    row.update({f"newer.{k}": v for k, v in newer.items()})
                    results.append(row)
            return results

        if name == "stale_references":
            results = []
            for et, doc_id, ref_id, d in self._edges:
                if et != "References":
                    continue
                newer_id = self._superseder_of(ref_id)
                if newer_id is None:
                    continue
                doc = self._find_node("Document", doc_id)
                ref = self._find_node("Document", ref_id)
                newer = self._find_node("Document", newer_id)
                if doc and ref and newer and not self._is_superseded_check(doc_id):
                    row = {}
                    row.update({f"doc.{k}": v for k, v in doc.items()})
                    row.update({f"ref.{k}": v for k, v in ref.items()})
                    row.update({f"newer.{k}": v for k, v in newer.items()})
                    results.append(row)
            return results

        if name == "stale_governance":
            results = []
            for et, gov_id, doc_id, d in self._edges:
                if et != "Governs":
                    continue
                newer_id = self._superseder_of(doc_id)
                if newer_id is None:
                    continue
                gov = self._find_node("Document", gov_id)
                doc = self._find_node("Document", doc_id)
                newer = self._find_node("Document", newer_id)
                if gov and doc and newer and not self._is_superseded_check(gov_id):
                    row = {}
                    row.update({f"gov.{k}": v for k, v in gov.items()})
                    row.update({f"doc.{k}": v for k, v in doc.items()})
                    row.update({f"newer.{k}": v for k, v in newer.items()})
                    results.append(row)
            return results

        if name == "superseded_documents":
            results = []
            for doc_id, data in self._nodes.get("Document", {}).items():
                if data.get("status") == "superseded":
                    results.append(self._doc_prefix(data))
            return results

        if name == "current_documents":
            results = []
            for doc_id, data in self._nodes.get("Document", {}).items():
                if data.get("status") == "archived":
                    continue
                if self._is_superseded_check(doc_id):
                    continue
                results.append(self._doc_prefix(data))
            return results

        # --- cascade.gq ---

        if name == "cascade_derived":
            changed_id = params["changed_id"]
            affected_ids = self._traverse_edges("DerivedFrom", changed_id)
            results = []
            for aid in affected_ids:
                doc = self._find_node("Document", aid)
                if doc and not self._is_superseded_check(aid):
                    results.append({f"affected.{k}": v for k, v in doc.items()})
            return results

        if name == "cascade_references":
            changed_id = params["changed_id"]
            affected_ids = self._traverse_edges("References", changed_id)
            results = []
            for aid in affected_ids:
                doc = self._find_node("Document", aid)
                if doc and not self._is_superseded_check(aid):
                    results.append({f"affected.{k}": v for k, v in doc.items()})
            return results

        if name == "cascade_governed":
            changed_id = params["changed_id"]
            affected_ids = self._traverse_edges("Governs", changed_id)
            results = []
            for aid in affected_ids:
                doc = self._find_node("Document", aid)
                if doc and not self._is_superseded_check(aid):
                    results.append({f"affected.{k}": v for k, v in doc.items()})
            return results

        if name == "cascade_amendment":
            amendment_id = params["amendment_id"]
            # Find what the amendment amends
            base_ids = [t for et, f, t, d in self._edges if et == "Amends" and f == amendment_id]
            results = []
            for base_id in base_ids:
                affected_ids = self._traverse_edges("DerivedFrom", base_id)
                for aid in affected_ids:
                    doc = self._find_node("Document", aid)
                    if doc and not self._is_superseded_check(aid):
                        results.append({f"affected.{k}": v for k, v in doc.items()})
            return results

        # --- audit.gq ---

        if name == "trial_documents":
            pid = params.get("trial_key") or params.get("protocol_id")
            results = []
            for et, doc_id, trial_id, _ in self._edges:
                if et == "BelongsToTrial" and trial_id == pid:
                    doc = self._find_node("Document", doc_id)
                    if doc and doc.get("status") != "archived" and not self._is_superseded_check(doc_id):
                        results.append(self._doc_prefix(doc))
            return results

        if name == "all_documents":
            return [self._doc_prefix(d) for d in self._nodes.get("Document", {}).values()]

        if name == "all_trials":
            return [self._trial_prefix(t) for t in self._nodes.get("Trial", {}).values()]

        if name == "all_edges":
            return [
                {"edge_type": et, "from": f, "to": t, **d}
                for et, f, t, d in self._edges
            ]

        # Fallback for LLM-generated queries: return full graph snapshot
        # so the LLM can answer from the data.
        if name == "nl_query":
            rows: list[dict] = []
            rows.extend(self._trial_prefix(t) for t in self._nodes.get("Trial", {}).values())
            rows.extend(self._doc_prefix(d) for d in self._nodes.get("Document", {}).values())
            return rows

        raise ValueError(f"Unknown query: {name!r}")

    def _execute_mutation(self, name: str, params: dict) -> dict:
        """Dispatch named mutations."""

        if name == "add_document":
            doc_id = params["doc_id"]
            self._nodes["Document"][doc_id] = dict(params)
            return {"inserted": 1}

        if name == "add_trial":
            pid = params.get("trial_key") or params.get("protocol_id")
            self._nodes["Trial"][pid] = dict(params)
            return {"inserted": 1}

        if name == "add_belongs_to_trial":
            self._edges.append(("BelongsToTrial", params["doc_id"], params["trial_id"], {}))
            return {"inserted": 1}

        if name == "add_supersedes":
            self._edges.append(("Supersedes", params["new_id"], params["old_id"], {"reason": params.get("reason")}))
            return {"inserted": 1}

        if name == "add_derived_from":
            self._edges.append(("DerivedFrom", params["child_id"], params["parent_id"], {"derivation_type": params.get("derivation_type")}))
            return {"inserted": 1}

        if name == "add_references":
            self._edges.append(("References", params["from_id"], params["to_id"], {"citation_text": params.get("citation_text")}))
            return {"inserted": 1}

        if name == "add_governs":
            self._edges.append(("Governs", params["gov_id"], params["doc_id"], {"authority_type": params.get("authority_type")}))
            return {"inserted": 1}

        if name == "mark_superseded":
            doc_id = params["doc_id"]
            if doc_id in self._nodes.get("Document", {}):
                self._nodes["Document"][doc_id]["status"] = "superseded"
            return {"updated": 1}

        if name == "add_phase":
            pid = params["phase_id"]
            self._nodes["Phase"][pid] = dict(params)
            return {"inserted": 1}

        if name == "add_has_phase":
            self._edges.append(("HasPhase", params["trial_id"], params["phase_id"], {}))
            return {"inserted": 1}

        if name == "add_belongs_to_phase":
            self._edges.append(("BelongsToPhase", params["doc_id"], params["phase_id"], {}))
            return {"inserted": 1}

        if name == "add_amends":
            self._edges.append(("Amends", params["amendment_id"], params["base_id"], {
                "amendment_label": params.get("amendment_label"),
                "scope": params.get("scope"),
            }))
            return {"inserted": 1}

        if name == "update_document_type":
            doc_id = params["doc_id"]
            if doc_id in self._nodes.get("Document", {}):
                self._nodes["Document"][doc_id]["document_type"] = params["document_type"]
                self._nodes["Document"][doc_id]["classification_confidence"] = params["classification_confidence"]
            return {"updated": 1}

        raise ValueError(f"Unknown mutation: {name!r}")
