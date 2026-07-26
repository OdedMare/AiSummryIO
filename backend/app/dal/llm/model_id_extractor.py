def extract_model_ids(payload) -> list:
    items = payload
    if isinstance(payload, dict):
        items = payload.get("data", payload.get("models", []))
    if not isinstance(items, list):
        return []
    identifiers = set()
    for item in items:
        if isinstance(item, str):
            identifiers.add(item)
        elif isinstance(item, dict):
            value = item.get("id") or item.get("name") or item.get("model")
            if value:
                identifiers.add(str(value))
    return sorted(identifiers)

