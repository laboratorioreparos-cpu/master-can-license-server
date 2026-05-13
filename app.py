from flask import Flask, request, jsonify
import os
import hashlib
from datetime import datetime, timezone

app = Flask(__name__)

LICENSES = {
    "CLIENTE001": {
        "machine_id": "",
        "status": "active",
        "expires": "2099-12-31",
        "name": "Cliente Teste"
    }
}

MASTER_SECRET = "CHINA_REPAROS_MASTER_CAN_ANALYSE"


def gerar_assinatura(license_key, machine_id):
    texto = f"{license_key}|{machine_id}|{MASTER_SECRET}"
    return hashlib.sha256(texto.encode()).hexdigest()


@app.route("/")
def home():
    return jsonify({
        "status": "online",
        "server": "MASTER CAN ANALYSE"
    })


@app.route("/activate", methods=["POST"])
def activate():

    data = request.json

    license_key = data.get("license_key")
    machine_id = data.get("machine_id")

    if license_key not in LICENSES:
        return jsonify({
            "ok": False,
            "message": "Licença inválida"
        })

    lic = LICENSES[license_key]

    assinatura = gerar_assinatura(
        license_key,
        machine_id
    )

    return jsonify({
        "ok": True,
        "license_key": license_key,
        "signature": assinatura,
        "expires": lic["expires"],
        "status": lic["status"]
    })


@app.route("/verify", methods=["POST"])
def verify():

    data = request.json

    license_key = data.get("license_key")
    machine_id = data.get("machine_id")
    signature = data.get("signature")

    assinatura_correta = gerar_assinatura(
        license_key,
        machine_id
    )

    if signature != assinatura_correta:
        return jsonify({
            "ok": False,
            "message": "Assinatura inválida"
        })

    return jsonify({
        "ok": True,
        "message": "Licença válida"
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(
        host="0.0.0.0",
        port=port
    )
