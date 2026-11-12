"""Several models can read one image together. The first result is the one that is stored."""

import time

from app.services.panel import run_readers, summarise


class _Reader:
    def __init__(self, name, result, delay=0, error=None):
        self.engine = name
        self.model = name
        self.uses_references = False
        self._result = result
        self._delay = delay
        self._error = error

    def interpret(self, image_bytes, context, examples, before_bytes=None):
        if self._delay:
            time.sleep(self._delay)
        if self._error:
            raise RuntimeError(self._error)
        return self._result


def test_readers_run_at_the_same_time_and_keep_the_first_result():
    readers = [
        _Reader("primary", {"via_result": "VIA_NEGATIVE", "confidence": 0.55}, delay=0.25),
        _Reader("second", {"via_result": "VIA_POSITIVE", "confidence": 0.8}, delay=0.25),
    ]
    started = time.perf_counter()
    result, panel = run_readers(readers, b"image", {}, [], None)
    elapsed = time.perf_counter() - started

    assert elapsed < 0.45
    assert result["via_result"] == "VIA_NEGATIVE"
    assert panel["agreement"] == "split"
    assert [row["via_result"] for row in panel["readings"]] == ["VIA_NEGATIVE", "VIA_POSITIVE"]


def test_a_failed_extra_reader_does_not_replace_the_stored_result():
    readers = [
        _Reader("primary", {"via_result": "VIA_NEGATIVE", "confidence": 0.55}),
        _Reader("second", {}, error="timed out"),
    ]
    result, panel = run_readers(readers, b"image", {}, [], None)
    assert result["via_result"] == "VIA_NEGATIVE"
    assert panel["agreement"] == "agree"
    assert panel["readings"][1]["error"] == "This model could not read the image."
    assert panel["readings"][1]["via_result"] is None


def test_the_stored_reading_stays_the_first_model(tmp_path, monkeypatch):
    from app import create_app
    from app.services import panel as panel_mod
    from tests.test_api import cervix_image, upload

    class Extra:
        engine = "remote"
        model = "other-host"
        uses_references = False

        def interpret(self, image_bytes, context, examples, before_bytes=None):
            return {"via_result": "SUSPICIOUS_FOR_CANCER", "confidence": 0.2}

    real = panel_mod.readers_for

    def wrapped(config):
        return [*real(config), Extra()]

    monkeypatch.setattr(panel_mod, "readers_for", wrapped)
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "UPLOAD_DIR": tmp_path,
        "INTERPRETER_MODE": "heuristic",
        "API_KEY": "",
    })
    body = upload(app.test_client(), cervix_image(False)).json
    assert body["engine"]["name"] == "heuristic"
    assert body["verdict"]["via_result"] == body["panel"]["readings"][0]["via_result"]
    assert body["panel"]["readings"][1]["model"] == "other-host"
    assert body["panel"]["readings"][1]["via_result"] == "SUSPICIOUS_FOR_CANCER"
    assert body["panel"]["agreement"] == "split"


def test_matching_results_are_marked_as_agreement():
    panel = summarise(
        [_Reader("a", {}), _Reader("b", {})],
        [({"via_result": "VIA_NEGATIVE", "confidence": 0.4}, None),
         ({"via_result": "VIA_NEGATIVE", "confidence": 0.7}, None)],
    )
    assert panel["agreement"] == "agree"
