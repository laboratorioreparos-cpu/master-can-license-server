from flask import Flask, request, jsonify
import os
import json
import hashlib
from datetime import datetime, timezone

app = Flask(__name__)

ARQ_CLIENTES = "clientes.json"
ARQ_LICENCAS = "licencas.json"
ARQ_HISTORICO = "historico.json"

MASTER_SECRET = os.environ.get("MASTER_SECRET", "CHINA_REPAROS_MASTER_CAN_ANALYSE")
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "CHINA_MASTER_ADMIN_2026")


def agora():
    return datetime.now(timezone.utc).isoformat()


def carregar_json(caminho, padrao):
    if not os.path.exists(caminho):
        return padrao
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return padrao


def salvar_json(caminho, dados):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


def clientes():
    return carregar_json(ARQ_CLIENTES, [])


def licencas():
    return carregar_json(ARQ_LICENCAS, [])


def historico():
    return carregar_json(ARQ_HISTORICO, [])


def salvar_clientes(dados):
    salvar_json(ARQ_CLIENTES, dados)


def salvar_licencas(dados):
    salvar_json(ARQ_LICENCAS, dados)


def salvar_historico(dados):
    salvar_json(ARQ_HISTORICO, dados)


def add_historico(acao, detalhe=""):
    h = historico()
    h.append({
        "id": len(h) + 1,
        "acao": acao,
        "detalhe": detalhe,
        "hora": agora()
    })
    salvar_historico(h)


def normalizar_modulo(nome):
    n = str(nome).strip().lower()
    mapa = {
        "monitor": "monitor",
        "logs": "logs",
        "logs / troncos": "logs",
        "sniffer": "sniffer",
        "sniffer / farejador": "sniffer",
        "radar": "radar",
        "engenharia": "engenharia_can",
        "engenharia can": "engenharia_can",
        "simulador": "simulador_can",
        "simulador can": "simulador_can",
        "atualizacao": "atualizacao_online",
        "atualização": "atualizacao_online",
        "atualizacao online": "atualizacao_online",
        "atualização online": "atualizacao_online",
    }
    return mapa.get(n, n.replace(" ", "_").replace("/", "_"))


def normalizar_modulos(modulos):
    if modulos is None:
        return []
    if isinstance(modulos, str):
        # aceita "monitor,radar" ou "['monitor']"
        txt = modulos.replace("[", "").replace("]", "").replace("'", "").replace('"', "")
        modulos = [m.strip() for m in txt.split(",") if m.strip()]
    return [normalizar_modulo(m) for m in modulos]


def gerar_chave(id_maquina, cliente_nome=""):
    base = f"{id_maquina}|{cliente_nome}|{MASTER_SECRET}"
    h = hashlib.sha256(base.encode("utf-8")).hexdigest().upper()
    return "MC-" + h[:8] + h[8:16] + h[16:24]


def gerar_assinatura(chave, id_maquina):
    texto = f"{chave}|{id_maquina}|{MASTER_SECRET}"
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "online",
        "ok": True,
        "service": "MASTER CAN ANALYSE License Server",
        "developer": "CHINA REPAROS AUTOMOTIVOS",
        "time": agora()
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True, "status": "online", "hora": agora()})


@app.route("/docs", methods=["GET"])
def docs():
    return """
    <html><body style='font-family:Arial;background:#111;color:#eee;padding:25px'>
    <h2>MASTER CAN ANALYSE - License Server</h2>
    <p>Servidor online funcionando.</p>
    <h3>Rotas principais</h3>
    <ul>
      <li>GET /health</li>
      <li>GET /clientes</li>
      <li>POST /clientes</li>
      <li>GET /licencas</li>
      <li>POST /licencas</li>
      <li>POST /licencas/validar</li>
      <li>PUT /licencas/modulos</li>
      <li>PUT /licencas/&lt;id&gt;/bloquear</li>
      <li>PUT /licencas/&lt;id&gt;/reativar</li>
      <li>PUT /licencas/&lt;id&gt;/editar-id</li>
      <li>DELETE /licencas/&lt;id&gt;</li>
    </ul>
    </body></html>
    """


@app.route("/clientes", methods=["GET"])
def listar_clientes():
    return jsonify(clientes())


@app.route("/clientes", methods=["POST"])
def cadastrar_cliente():
    data = request.get_json(silent=True) or {}
    lista = clientes()
    item = {
        "id": len(lista) + 1,
        "nome": data.get("nome") or data.get("cliente_nome") or "",
        "telefone": data.get("telefone", ""),
        "email": data.get("email", ""),
        "observacao": data.get("observacao", ""),
        "criado_em": agora()
    }
    lista.append(item)
    salvar_clientes(lista)
    add_historico("cliente_cadastrado", item.get("nome", ""))
    return jsonify({"ok": True, **item})


@app.route("/licencas", methods=["GET"])
def listar_licencas():
    return jsonify(licencas())


@app.route("/licencas", methods=["POST"])
def criar_ou_atualizar_licenca():
    data = request.get_json(silent=True) or {}

    id_maquina = str(data.get("id_maquina") or data.get("machine_id") or "").strip()
    cliente_nome = str(data.get("cliente_nome") or data.get("nome") or data.get("name") or "").strip()
    tipo = str(data.get("tipo") or "vitalicia")
    modulos = normalizar_modulos(data.get("modulos", []))

    if not id_maquina:
        return jsonify({"ok": False, "erro": "id_maquina obrigatório"}), 400

    lista = licencas()

    # Se já existir para a máquina, atualiza módulos sem criar duplicada
    for lic in lista:
        if str(lic.get("id_maquina", "")).strip() == id_maquina:
            if cliente_nome:
                lic["cliente_nome"] = cliente_nome
            lic["tipo"] = tipo
            lic["status"] = lic.get("status", "ativa")
            lic["modulos"] = modulos
            lic["ultima_verificacao"] = agora()
            lic["chave"] = lic.get("chave") or gerar_chave(id_maquina, cliente_nome)
            salvar_licencas(lista)
            add_historico("licenca_atualizada", id_maquina)
            return jsonify({"ok": True, "mensagem": "Licença atualizada", **lic})

    chave = gerar_chave(id_maquina, cliente_nome)
    item = {
        "id": len(lista) + 1,
        "cliente_nome": cliente_nome,
        "chave": chave,
        "id_maquina": id_maquina,
        "machine_id": id_maquina,
        "tipo": tipo,
        "status": "ativa",
        "modulos": modulos,
        "criado_em": agora(),
        "ultima_verificacao": agora(),
        "assinatura": gerar_assinatura(chave, id_maquina)
    }
    lista.append(item)
    salvar_licencas(lista)
    add_historico("licenca_criada", id_maquina)
    return jsonify({"ok": True, **item})


@app.route("/licencas/validar", methods=["POST"])
@app.route("/activate", methods=["POST"])
@app.route("/verify", methods=["POST"])
def validar_licenca():
    data = request.get_json(silent=True) or {}
    chave = str(data.get("chave") or data.get("license_key") or data.get("key") or "").strip()
    id_maquina = str(data.get("id_maquina") or data.get("machine_id") or "").strip()

    lista = licencas()

    encontrada = None
    for lic in lista:
        if chave and str(lic.get("chave", "")).strip() == chave:
            encontrada = lic
            break

    if encontrada is None and id_maquina:
        for lic in lista:
            if str(lic.get("id_maquina", "")).strip() == id_maquina:
                encontrada = lic
                break

    if encontrada is None:
        return jsonify({"ok": False, "status": "invalid", "mensagem": "Licença não encontrada"}), 404

    if encontrada.get("status") not in ("ativa", "active", "ATIVA"):
        return jsonify({"ok": False, "status": "blocked", "mensagem": "Licença bloqueada"}), 403

    if id_maquina and str(encontrada.get("id_maquina", "")).strip() != id_maquina:
        return jsonify({"ok": False, "status": "machine_mismatch", "mensagem": "ID da máquina diferente"}), 403

    encontrada["ultima_verificacao"] = agora()
    salvar_licencas(lista)

    return jsonify({
        "ok": True,
        "status": "active",
        "licenca": "ATIVADO",
        "cliente_nome": encontrada.get("cliente_nome", ""),
        "chave": encontrada.get("chave", ""),
        "license_key": encontrada.get("chave", ""),
        "id_maquina": encontrada.get("id_maquina", ""),
        "machine_id": encontrada.get("id_maquina", ""),
        "tipo": encontrada.get("tipo", "vitalicia"),
        "modulos": normalizar_modulos(encontrada.get("modulos", [])),
        "assinatura": gerar_assinatura(encontrada.get("chave", ""), encontrada.get("id_maquina", "")),
        "signature": gerar_assinatura(encontrada.get("chave", ""), encontrada.get("id_maquina", ""))
    })


@app.route("/licencas/modulos", methods=["PUT", "POST"])
def atualizar_modulos():
    data = request.get_json(silent=True) or {}
    id_maquina = str(data.get("id_maquina") or data.get("machine_id") or "").strip()
    modulos = normalizar_modulos(data.get("modulos", []))

    lista = licencas()
    for lic in lista:
        if str(lic.get("id_maquina", "")).strip() == id_maquina:
            lic["modulos"] = modulos
            lic["ultima_verificacao"] = agora()
            salvar_licencas(lista)
            add_historico("modulos_atualizados", id_maquina)
            return jsonify({"ok": True, "mensagem": "Módulos atualizados", "modulos": modulos})

    return jsonify({"ok": False, "detail": "Licença não encontrada"}), 404


@app.route("/licencas/<int:licenca_id>/bloquear", methods=["PUT", "POST"])
def bloquear_licenca(licenca_id):
    lista = licencas()
    for lic in lista:
        if int(lic.get("id", 0)) == licenca_id:
            lic["status"] = "bloqueada"
            salvar_licencas(lista)
            add_historico("licenca_bloqueada", str(licenca_id))
            return jsonify({"ok": True, "status": "bloqueada"})
    return jsonify({"ok": False, "detail": "Licença não encontrada"}), 404


@app.route("/licencas/<int:licenca_id>/reativar", methods=["PUT", "POST"])
def reativar_licenca(licenca_id):
    lista = licencas()
    for lic in lista:
        if int(lic.get("id", 0)) == licenca_id:
            lic["status"] = "ativa"
            salvar_licencas(lista)
            add_historico("licenca_reativada", str(licenca_id))
            return jsonify({"ok": True, "status": "ativa"})
    return jsonify({"ok": False, "detail": "Licença não encontrada"}), 404


@app.route("/licencas/<int:licenca_id>/editar-id", methods=["PUT", "POST"])
def editar_id_licenca(licenca_id):
    data = request.get_json(silent=True) or {}
    novo_id = str(data.get("novo_id") or data.get("id_maquina") or data.get("machine_id") or "").strip()

    if not novo_id:
        return jsonify({"ok": False, "detail": "novo_id obrigatório"}), 400

    lista = licencas()
    for lic in lista:
        if int(lic.get("id", 0)) == licenca_id:
            lic["id_maquina"] = novo_id
            lic["machine_id"] = novo_id
            lic["assinatura"] = gerar_assinatura(lic.get("chave", ""), novo_id)
            salvar_licencas(lista)
            add_historico("id_maquina_editado", str(licenca_id))
            return jsonify({"ok": True, "novo_id": novo_id})
    return jsonify({"ok": False, "detail": "Licença não encontrada"}), 404


@app.route("/licencas/<int:licenca_id>", methods=["DELETE", "POST"])
def excluir_licenca(licenca_id):
    lista = licencas()
    nova = [l for l in lista if int(l.get("id", 0)) != licenca_id]
    if len(nova) == len(lista):
        return jsonify({"ok": False, "detail": "Licença não encontrada"}), 404
    salvar_licencas(nova)
    add_historico("licenca_excluida", str(licenca_id))
    return jsonify({"ok": True, "mensagem": "Licença excluída"})


@app.route("/historico", methods=["GET"])
def listar_historico():
    return jsonify(historico())


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
