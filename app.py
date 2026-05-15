from flask import Flask, request, jsonify
import os
import json
import hashlib
from datetime import datetime, timezone

app = Flask(__name__)

# Banco simples em memória/arquivo.
# Para começar, as licenças podem ser cadastradas neste dicionário.
# Depois podemos evoluir para banco online.
LICENSES = {
    # Exemplo:
    # "CLIENTE001": {
    #     "machine_id": "ID_DA_MAQUINA_DO_CLIENTE",
    #     "status": "active",
    #     "expires": "2099-12-31",
    #     "name": "Cliente teste"
    # }
}

MASTER_SECRET = os.environ.get("MASTER_SECRET", "CHINA_REPAROS_MASTER_CAN_ANALYSE")


def gerar_assinatura(license_key: str, machine_id: str) -> str:
    texto = f"{license_key}|{machine_id}|{MASTER_SECRET}"
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "online",
        "service": "MASTER CAN ANALYSE License Server",
        "developer": "CHINA REPAROS AUTOMOTIVOS",
        "time": datetime.now(timezone.utc).isoformat()
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True})


@app.route("/activate", methods=["POST"])
def activate():
    data = request.get_json(silent=True) or {}

    license_key = str(data.get("license_key", "")).strip()
    machine_id = str(data.get("machine_id", "")).strip()

    if not license_key or not machine_id:
        return jsonify({
            "ok": False,
            "message": "license_key e machine_id são obrigatórios"
        }), 400

    lic = LICENSES.get(license_key)

    if not lic:
        return jsonify({
            "ok": False,
            "status": "invalid",
            "message": "Licença não encontrada"
        }), 403

    if lic.get("status") != "active":
        return jsonify({
            "ok": False,
            "status": "blocked",
            "message": "Licença bloqueada"
        }), 403

    expires = lic.get("expires", "2099-12-31")
    try:
        exp_date = datetime.strptime(expires, "%Y-%m-%d").date()
        if exp_date < datetime.now().date():
            return jsonify({
                "ok": False,
                "status": "expired",
                "message": "Licença expirada"
            }), 403
    except Exception:
        pass

    saved_machine = str(lic.get("machine_id", "")).strip()

    # Se machine_id estiver vazio, aceita a primeira ativação.
    # Se estiver preenchido, só aceita a mesma máquina.
    if saved_machine and saved_machine != machine_id:
        return jsonify({
            "ok": False,
            "status": "machine_mismatch",
            "message": "Licença já vinculada a outra máquina"
        }), 403

    assinatura = gerar_assinatura(license_key, machine_id)

    return jsonify({
        "ok": True,
        "status": "active",
        "message": "Licença ativada com sucesso",
        "license_key": license_key,
        "machine_id": machine_id,
        "expires": expires,
        "name": lic.get("name", ""),
        "signature": assinatura
    })


@app.route("/verify", methods=["POST"])
def verify():
    data = request.get_json(silent=True) or {}

    license_key = str(data.get("license_key", "")).strip()
    machine_id = str(data.get("machine_id", "")).strip()
    signature = str(data.get("signature", "")).strip()

    if not license_key or not machine_id or not signature:
        return jsonify({
            "ok": False,
            "message": "license_key, machine_id e signature são obrigatórios"
        }), 400

    expected = gerar_assinatura(license_key, machine_id)

    if signature != expected:
        return jsonify({
            "ok": False,
            "status": "invalid_signature",
            "message": "Assinatura inválida"
        }), 403

    return jsonify({
        "ok": True,
        "status": "valid",
        "message": "Licença válida"
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


# =========================================================
# ROTAS NOVAS MASTER CAN ANALYSE
# =========================================================

@app.put("/licencas/modulos")
def atualizar_modulos(dados: dict):
    """
    Atualiza módulos liberados sem gerar nova licença.
    """
    id_maquina = dados.get("id_maquina")
    modulos = dados.get("modulos", [])

    for lic in licencas:
        if lic.get("id_maquina") == id_maquina:
            lic["modulos"] = modulos
            salvar_licencas()
            return {
                "ok": True,
                "mensagem": "Módulos atualizados",
                "modulos": modulos
            }

    raise HTTPException(status_code=404, detail="Licença não encontrada")


@app.put("/licencas/{licenca_id}/bloquear")
def bloquear_licenca(licenca_id: int):
    for lic in licencas:
        if lic.get("id") == licenca_id:
            lic["status"] = "bloqueada"
            salvar_licencas()
            return {"ok": True, "status": "bloqueada"}

    raise HTTPException(status_code=404, detail="Licença não encontrada")


@app.put("/licencas/{licenca_id}/reativar")
def reativar_licenca(licenca_id: int):
    for lic in licencas:
        if lic.get("id") == licenca_id:
            lic["status"] = "ativa"
            salvar_licencas()
            return {"ok": True, "status": "ativa"}

    raise HTTPException(status_code=404, detail="Licença não encontrada")


@app.put("/licencas/{licenca_id}/editar-id")
def editar_id_maquina(licenca_id: int, dados: dict):
    novo_id = dados.get("novo_id")

    for lic in licencas:
        if lic.get("id") == licenca_id:
            lic["id_maquina"] = novo_id
            salvar_licencas()
            return {
                "ok": True,
                "novo_id": novo_id
            }

    raise HTTPException(status_code=404, detail="Licença não encontrada")


@app.delete("/licencas/{licenca_id}")
def excluir_licenca(licenca_id: int):
    global licencas

    nova_lista = [l for l in licencas if l.get("id") != licenca_id]

    if len(nova_lista) == len(licencas):
        raise HTTPException(status_code=404, detail="Licença não encontrada")

    licencas = nova_lista
    salvar_licencas()

    return {
        "ok": True,
        "mensagem": "Licença excluída"
    }

