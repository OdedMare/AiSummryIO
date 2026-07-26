def merge_system_into_user(messages: list) -> list:
    system = [item["content"] for item in messages if item["role"] == "system"]
    rest = [item for item in messages if item["role"] != "system"]
    if not system or not rest:
        return rest or messages
    merged = dict(rest[0])
    merged["content"] = "\n\n".join(system + [merged["content"]])
    return [merged] + rest[1:]

