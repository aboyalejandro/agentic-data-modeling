import os
import requests

HOST = os.getenv("OPENMETADATA_HOST", "http://localhost:8585")
TOKEN = os.getenv("OPENMETADATA_JWT_TOKEN", "")

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}


def _get(path: str, params: dict = None) -> dict:
    r = requests.get(f"{HOST}/api/v1{path}", headers=HEADERS, params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def search_metadata(query: str, entity_type: str = None, limit: int = 10) -> dict:
    index_map = {
        "table": "table_search_index",
        "dashboard": "dashboard_search_index",
        "pipeline": "pipeline_search_index",
    }
    index = index_map.get(entity_type, "all") if entity_type else "all"
    params = {"q": query, "index": index, "from": 0, "size": limit}
    data = _get("/search/query", params=params)
    hits = data.get("hits", {}).get("hits", [])
    results = []
    for h in hits:
        src = h.get("_source", {})
        results.append({
            "name": src.get("name"),
            "fqn": src.get("fullyQualifiedName"),
            "type": src.get("entityType"),
            "description": src.get("description", ""),
        })
    return {"results": results, "total": len(results)}


def get_entity_details(fqn: str, entity_type: str = "table") -> dict:
    path = f"/tables/name/{fqn}"
    params = {"fields": "columns,description,tags,followers,owners"}
    data = _get(path, params=params)
    columns = []
    for col in data.get("columns", []):
        columns.append({
            "name": col.get("name"),
            "dataType": col.get("dataType"),
            "description": col.get("description", ""),
        })
    return {
        "id": data.get("id"),
        "name": data.get("name"),
        "fqn": data.get("fullyQualifiedName"),
        "description": data.get("description", ""),
        "columns": columns,
        "tags": [t.get("tagFQN") for t in data.get("tags", [])],
    }


def get_entity_lineage(fqn: str, depth: int = 2) -> dict:
    params = {"upstreamDepth": depth, "downstreamDepth": depth}
    data = _get(f"/lineage/table/name/{fqn}", params=params)
    entity = data.get("entity", {})
    nodes = {n["id"]: n.get("fullyQualifiedName", n.get("name", n["id"]))
             for n in data.get("nodes", [])}
    nodes[entity.get("id", "")] = fqn

    upstream, downstream = [], []
    for edge in data.get("upstreamEdges", []):
        src = nodes.get(edge.get("fromEntity", ""), edge.get("fromEntity", ""))
        upstream.append(src)
    for edge in data.get("downstreamEdges", []):
        dst = nodes.get(edge.get("toEntity", ""), edge.get("toEntity", ""))
        downstream.append(dst)

    return {"entity": fqn, "upstream": upstream, "downstream": downstream}


def patch_entity(fqn: str, patch: list, entity_type: str = "table") -> dict:
    # First fetch to get the ID
    detail = get_entity_details(fqn, entity_type)
    entity_id = detail["id"]

    patch_headers = {**HEADERS, "Content-Type": "application/json-patch+json"}
    r = requests.patch(
        f"{HOST}/api/v1/tables/{entity_id}",
        headers=patch_headers,
        json=patch,
        timeout=15,
    )
    r.raise_for_status()
    return {"status": "ok", "patched_fields": len(patch)}
