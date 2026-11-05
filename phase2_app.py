from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import Flask, Response, jsonify, request, send_from_directory

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "cpp_engine" / "frontend"

app = Flask(__name__, static_folder=None)

SERVICES = {
    "core": "http://127.0.0.1:5000",
    "scoring": "http://127.0.0.1:5001",
    "tournament": "http://127.0.0.1:5002",
}


@app.get("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.get("/style.css")
def stylesheet():
    return send_from_directory(FRONTEND_DIR, "style.css")


@app.get("/app.js")
def javascript():
    return send_from_directory(FRONTEND_DIR, "app.js")


@app.route("/api/<service>/<path:endpoint>", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
def proxy_api(service, endpoint):
    if service not in SERVICES:
        return jsonify({"error": f"Unknown API service: {service}"}), 404

    target_url = f"{SERVICES[service]}/api/{endpoint}"
    body = request.get_data()
    headers = {}
    if request.content_type:
        headers["Content-Type"] = request.content_type

    upstream_request = Request(
        target_url,
        data=body if request.method not in ("GET", "HEAD") else None,
        headers=headers,
        method=request.method,
    )

    try:
        with urlopen(upstream_request, timeout=20) as upstream:
            payload = upstream.read()
            content_type = upstream.headers.get("Content-Type", "application/json")
            return Response(payload, status=upstream.status, content_type=content_type)
    except HTTPError as exc:
        payload = exc.read()
        content_type = exc.headers.get("Content-Type", "application/json")
        return Response(payload, status=exc.code, content_type=content_type)
    except URLError as exc:
        return jsonify({
            "error": f"Could not connect to {service} backend.",
            "details": str(exc.reason),
            "hint": "Start app.py (5000), phase1_9_app.py (5001), and phase1_10_app.py (5002).",
        }), 502
    except TimeoutError:
        return jsonify({"error": f"{service} backend timed out."}), 504


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5003, debug=True)
