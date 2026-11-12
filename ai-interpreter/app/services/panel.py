"""Read one VIA image with every configured model at the same time.

The stored result is still the selected interpreter. The other readings are
shown beside it. Nothing here is averaged into a final label.
"""

from concurrent.futures import ThreadPoolExecutor

from .interpreter import HeuristicInterpreter, RemoteInterpreter, build_interpreter


def _urls(value) -> list[str]:
    return [part.strip().rstrip("/") for part in str(value or "").split(",") if part.strip()]


def readers_for(config) -> list:
    """Selected interpreter, the on-device baseline when it is not already selected, and any extra servers."""
    primary = build_interpreter(config)
    readers = [primary]
    if primary.engine != "heuristic":
        readers.append(HeuristicInterpreter())
    token = config.get("REMOTE_MODEL_TOKEN") or ""
    timeout = int(config.get("PANEL_TIMEOUT_SECONDS") or 90)
    for url in _urls(config.get("PANEL_URLS")):
        remote = RemoteInterpreter(url, token, timeout)
        host = url.split("//", 1)[-1].split("/", 1)[0]
        remote.model = host or "remote"
        readers.append(remote)
    return readers


def _call(reader, image_bytes, context, examples, before_bytes):
    try:
        return reader.interpret(image_bytes, context, examples, before_bytes=before_bytes), None
    except Exception as exc:
        return None, exc


def run_readers(readers, image_bytes, context, examples, before_bytes):
    """Run every reader together. The first reader is the one that is stored."""
    if len(readers) == 1:
        result, error = _call(readers[0], image_bytes, context, examples if readers[0].uses_references else [], before_bytes)
        if error:
            raise error
        return result, summarise(readers, [(result, None)])

    with ThreadPoolExecutor(max_workers=len(readers)) as pool:
        futures = [
            pool.submit(
                _call,
                reader,
                image_bytes,
                context,
                examples if index == 0 and reader.uses_references else [],
                before_bytes,
            )
            for index, reader in enumerate(readers)
        ]
        done = [future.result() for future in futures]
    primary, primary_error = done[0]
    if primary_error:
        raise primary_error
    return primary, summarise(readers, done)


def summarise(readers, done) -> dict:
    readings = []
    for reader, (result, error) in zip(readers, done):
        if error or not isinstance(result, dict) or not result.get("via_result"):
            readings.append({
                "engine": reader.engine,
                "model": reader.model,
                "via_result": None,
                "confidence": None,
                "error": "This model could not read the image." if error or not result else "No VIA result.",
            })
            continue
        confidence = result.get("confidence")
        readings.append({
            "engine": reader.engine,
            "model": reader.model,
            "via_result": result.get("via_result"),
            "confidence": float(confidence) if confidence is not None else None,
            "error": None,
        })
    labels = {row["via_result"] for row in readings if row["via_result"]}
    return {
        "agreement": "agree" if len(labels) <= 1 else "split",
        "readings": readings,
    }


def read_together(config, image_bytes, context, examples, before_bytes):
    readers = readers_for(config)
    primary_examples = examples if readers[0].uses_references else []
    result, panel = run_readers(readers, image_bytes, context, primary_examples, before_bytes)
    return result, readers[0].engine, readers[0].model, primary_examples, panel
