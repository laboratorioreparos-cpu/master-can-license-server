import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# URL do Google Apps Script publicado como Web App
SHEETS_API_URL = os.environ.get("SHEETS_API_URL", "").strip()


def _check_config():
    if not SHEETS_API_URL:
        return False, jsonify({
            "erro": "SHEETS_API_URL nao configurado no Render",
            "status": "config_pendente"
        }), 500
    return True, None, None


def _call_sheets(payload=None, method="GET"):
    ok, resp, code = _check_config()
    if not ok:
        return resp, code
    try:
        if method == "GET":
            r = requests.get(SHEETS_API_URL, timeout=20)
        else:
            r = requests.post(SHEETS_API_URL, json=payload or {}, timeout=20)
        try:
            return jsonify(r.json()), r.status_code
        except Exception:
            return jsonify({"erro": "resposta invalida do Google Apps Script", "texto": r.text}), 502
    except Exception as exc:
        return jsonify({"erro": str(exc)}), 500


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "server": "MASTER CAN ANALYSE License Server",
        "status": "online",
        "banco": "Google Sheets",
        "endpoints": ["/health", "/clientes", "/clientes/<id>", "/backup"]
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "server": "MASTER CAN ANALYSE License Server",
        "banco": "Google Sheets",
        "sheets_api_configurada": bool(SHEETS_API_URL)
    })


@app.route("/clientes", methods=["GET"])
def listar_clientes():
    return _call_sheets(method="GET")


@app.route("/clientes", methods=["POST"])
def criar_cliente():
    data = request.get_json(silent=True) or {}
    data["acao"] = "salvar"
    return _call_sheets(data, method="POST")


@app.route("/clientes/<cliente_id>", methods=["GET"])
def obter_cliente(cliente_id):
    resp, code = _call_sheets(method="GET")
    if code != 200:
        return resp, code
    clientes = resp.get_json() if hasattr(resp, 'get_json') else []
    for c in clientes:
        if str(c.get("id", "")).strip().lower() == str(cliente_id).strip().lower():
            return jsonify(c)
    return jsonify({"erro": "cliente nao encontrado", "id": cliente_id}), 404


@app.route("/clientes/<cliente_id>", methods=["DELETE"])
def excluir_cliente(cliente_id):
    return _call_sheets({"acao": "excluir", "id": cliente_id}, method="POST")


@app.route("/backup", methods=["GET", "POST"])
def backup():
    return _call_sheets({"acao": "backup"}, method="POST")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
