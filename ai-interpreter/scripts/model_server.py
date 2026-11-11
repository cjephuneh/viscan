"""VIA model server. Run it on whatever GPU runtime you have; the laptop only stores the URL.

  python scripts/model_server.py --port 8088 --token "$REMOTE_MODEL_TOKEN"

Colab starts this from notebooks/viscan_colab.ipynb. The same process runs on
Kaggle, a cloud VM, or another machine. One request at a time: the GPU holds
a single copy of the model.
"""

import argparse
import hmac
import json
import sys
from pathlib import Path

from flask import Flask, jsonify, request

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.services.interpreter import LocalVisionInterpreter, ReferenceExample  # noqa: E402


def create_server(model_dir: str, adapter_dir: str, max_new_tokens: int, token: str,
                  interpreter=None) -> Flask:
    app = Flask(__name__)
    if interpreter is None:
        interpreter = LocalVisionInterpreter(model_dir, adapter_dir, max_new_tokens)
        interpreter._ensure_loaded()
    app.config["REMOTE_MODEL_TOKEN"] = token

    def authorized() -> bool:
        expected = app.config["REMOTE_MODEL_TOKEN"]
        if not expected:
            return True
        header = request.headers.get("Authorization", "")
        return hmac.compare_digest(header, f"Bearer {expected}")

    @app.get("/health")
    def health():
        if not authorized():
            return jsonify(error="Missing or wrong bearer token."), 401
        return jsonify(status="ok", engine=interpreter.engine, model=interpreter.model)

    @app.post("/interpret")
    def interpret():
        if not authorized():
            return jsonify(error="Missing or wrong bearer token."), 401
        upload = request.files.get("image")
        if upload is None or not upload.filename:
            return jsonify(error="Upload the image in multipart field 'image'."), 400
        before = request.files.get("image_before")
        before_bytes = before.read() if before is not None and before.filename else None
        try:
            context = json.loads(request.form.get("context") or "{}")
            described = json.loads(request.form.get("examples") or "[]")
        except json.JSONDecodeError:
            return jsonify(error="context and examples must be JSON."), 400
        examples = []
        for index, item in enumerate(described):
            blob = request.files.get(f"example_{index}")
            if blob is None:
                continue
            examples.append(ReferenceExample(
                0, blob.read(), item.get("via_result") or "", item.get("notes") or "",
            ))
        try:
            result = interpreter.interpret(upload.read(), context, examples, before_bytes=before_bytes)
        except Exception as exc:
            app.logger.exception("Remote interpretation failed")
            return jsonify(error=str(exc)), 500
        return jsonify(result)

    return app


def main() -> None:
    from app.config import Config

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8088)
    parser.add_argument("--token", default=Config.REMOTE_MODEL_TOKEN)
    parser.add_argument("--model-dir", default=Config.LOCAL_MODEL_DIR)
    parser.add_argument("--adapter-dir", default=Config.LOCAL_ADAPTER_DIR)
    parser.add_argument("--max-new-tokens", type=int, default=Config.LOCAL_MAX_NEW_TOKENS)
    args = parser.parse_args()

    print(f"Loading weights from {args.model_dir} ...", flush=True)
    app = create_server(args.model_dir, args.adapter_dir, args.max_new_tokens, args.token)
    print(f"Model ready on http://{args.host}:{args.port}", flush=True)
    app.run(host=args.host, port=args.port, threaded=False, use_reloader=False)


if __name__ == "__main__":
    main()
