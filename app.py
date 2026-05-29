import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

SECRET_KEY = os.environ.get("MCA_SECRET_KEY", "MASTER_CAN_ANALYSE_HIBRIDO_2026_CHINA_REPAROS").encode("utf-8")
STORE_FILE = Path(os.environ.get("MCA_STORE_FILE", "licencas_online.json"))

MODULOS_VALIDOS = {
    "monitor",
    "sniffer",
    "logs",
    "radar",
    "engenharia_can",
    "simulador_can",
    "atualizacao_online",
}

app = FastAPI(title="MASTER CAN ANALYSE - Validação Online V151")

class ValidarIn(BaseModel):
    chave: str = ""
    id_maquina: str = ""
    machine_id: str = ""
    versao: str = "1.5"
    versao_programa: str = "1.5"

class AdminSalvarIn(BaseModel):
    chave: str = ""
    id_maquina: str = ""
    machine_id: str = ""
    cliente: str = ""
    numero: str = ""
    tipo: str = "permanente"
    expires: str = "2099-12-31"
    modulos: list[str] = []


def agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def b64url_decode(texto: str) -> bytes:
    texto = (texto or "").strip()
    texto += "=" * (-len(texto) % 4)
    return base64.urlsafe_b64decode(texto.encode("utf-8"))


def b64url_json_decode(texto: str) -> dict:
    return json.loads(b64url_decode(texto).decode("utf-8"))


def assinar(payload_b64: str) -> str:
    sig = hmac.new(SECRET_KEY, payload_b64.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(sig).decode("utf-8").rstrip("=")


def normalizar_modulos(modulos: Any) -> list[str]:
    mapa = {
        "farejador": "sniffer",
        "sniffer_farejador": "sniffer",
        "troncos": "logs",
        "logs_troncos": "logs",
        "engenharia": "engenharia_can",
        "engenharia can": "engenharia_can",
        "simulador": "simulador_can",
        "simulador can": "simulador_can",
        "atualizacao": "atualizacao_online",
        "atualizacao online": "atualizacao_online",
    }
    if isinstance(modulos, dict):
        entrada = [k for k, v in modulos.items() if bool(v)]
    elif isinstance(modulos, str):
        entrada = [m.strip() for m in modulos.replace("[", "").replace("]", "").replace("'", "").replace('"', "").split(",") if m.strip()]
    else:
        entrada = list(modulos or [])

    saida = []
    for m in entrada:
        mm = str(m or "").strip().lower()
        mm = mm.replace("-", "_").replace("/", "_").replace("__", "_")
        mm = mm.replace("_", " ") if mm in ("engenharia_can", "simulador_can", "atualizacao_online") else mm
        mm = mapa.get(mm, mm.replace(" ", "_"))
        if mm in MODULOS_VALIDOS and mm not in saida:
            saida.append(mm)
    return saida


def validar_chave(chave: str) -> tuple[bool, dict, str]:
    chave = (chave or "").strip()
    if not chave.startswith("MCA2-"):
        return False, {}, "Formato de chave inválido"
    partes = chave.split("-", 2)
    if len(partes) != 3:
        return False, {}, "Chave incompleta"
    _, payload_b64, sig_recebida = partes
    sig_ok = assinar(payload_b64)
    if not hmac.compare_digest(sig_ok, sig_recebida):
        return False, {}, "Assinatura inválida"
    try:
        payload = b64url_json_decode(payload_b64)
    except Exception as e:
        return False, {}, f"Payload inválido: {e}"
    return True, payload, "ok"


def carregar_store() -> dict:
    if not STORE_FILE.exists():
        return {"licencas": {}}
    try:
        data = json.loads(STORE_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"licencas": {}}
        data.setdefault("licencas", {})
        return data
    except Exception:
        return {"licencas": {}}


def salvar_store(data: dict) -> None:
    data["updated_at"] = agora()
    STORE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def chave_id(chave: str) -> str:
    return hashlib.sha256((chave or "").strip().encode("utf-8")).hexdigest()


def montar_resposta(chave: str, payload: dict, id_maquina_recebido: str = "") -> dict:
    id_chave = str(payload.get("id_maquina", "")).strip()
    if id_chave and id_maquina_recebido and id_chave != id_maquina_recebido:
        return {"ok": False, "": "bloqueada", "message": "Licença pertence a outra máquina", "modulos": []}

    store = carregar_store()
    reg = store.get("licencas", {}).get(chave_id(chave), {})

    # Prioridade: módulos atualizados online pelo gerenciador. Se não existir, usa os módulos que nasceram dentro da chave.
    modulos = normalizar_modulos(reg.get("modulos") if reg else payload.get("modulos", []))

    return {
        "ok": True,
        "status": "ATIVADO",
        "tipo": reg.get("tipo") or payload.get("tipo", "permanente"),
        "numero": reg.get("numero") or payload.get("numero", "MCA-OFFLINE"),
        "chave": chave,
        "cliente": reg.get("cliente") or payload.get("cliente", ""),
        "id_maquina": reg.get("id_maquina") or id_chave,
        "expires": reg.get("expires") or payload.get("expires", "2099-12-31"),
        "modulos": modulos,
        "funcoes": modulos,
        "modulos_liberados": modulos,
        "modules": modulos,
        "message": "Licença validada online com sucesso",
    }

@app.get("/")
def home():
    return {"status": "online", "sistema": "MASTER CAN ANALYSE", "modo": "v151_com_modulos_online", "rotas": ["/health", "/licencas/validar", "/admin/licenca/salvar"]}

@app.get("/health")
def health():
    store = carregar_store()
    return {"ok": True, "status": "online", "modo": "v151_com_modulos_online", "licencas_salvas": len(store.get("licencas", {})), "hora": agora()}

@app.post("/licencas/validar")
def licencas_validar(d: ValidarIn):
    chave = (d.chave or "").strip()
    ok, payload, msg = validar_chave(chave)
    if not ok:
        return {"ok": False, "status": "bloqueada", "message": msg, "modulos": []}
    id_recebido = (d.id_maquina or d.machine_id or "").strip()
    return montar_resposta(chave, payload, id_recebido)

@app.post("/ativar")
def ativar(d: ValidarIn):
    return licencas_validar(d)

@app.post("/verificar")
def verificar(d: ValidarIn):
    return licencas_validar(d)

@app.post("/admin/licenca/salvar")
def admin_licenca_salvar(d: AdminSalvarIn):
    chave = (d.chave or "").strip()
    ok, payload, msg = validar_chave(chave)
    if not ok:
        return {"ok": False, "status": "erro", "message": msg}

    id_payload = str(payload.get("id_maquina", "")).strip()
    id_recebido = (d.id_maquina or d.machine_id or "").strip()
    if id_payload and id_recebido and id_payload != id_recebido:
        return {"ok": False, "status": "erro", "message": "ID da máquina não confere com a chave"}

    store = carregar_store()
    store.setdefault("licencas", {})[chave_id(chave)] = {
        "cliente": d.cliente or payload.get("cliente", ""),
        "id_maquina": id_payload or id_recebido,
        "numero": d.numero or payload.get("numero", "MCA-OFFLINE"),
        "tipo": d.tipo or payload.get("tipo", "permanente"),
        "expires": d.expires or payload.get("expires", "2099-12-31"),
        "modulos": normalizar_modulos(d.modulos),
        "atualizado_em": agora(),
    }
    salvar_store(store)
    return {"ok": True, "status": "salvo", "message": "Licença/módulos atualizados no servidor", "modulos": store["licencas"][chave_id(chave)]["modulos"]}


