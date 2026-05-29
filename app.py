import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from fastapi import FastAPI
from pydantic import BaseModel

SECRET_KEY = os.environ.get("MCA_SECRET_KEY", "MASTER_CAN_ANALYSE_HIBRIDO_2026_CHINA_REPAROS").encode("utf-8")

MODULOS_VALIDOS = {
    "monitor",
    "sniffer",
    "logs",
    "radar",
    "engenharia_can",
    "simulador_can",
    "atualizacao_online",
}

app = FastAPI(title="MASTER CAN ANALYSE - Validação Online Híbrida")

class ValidarIn(BaseModel):
    chave: str
    id_maquina: str = ""
    machine_id: str = ""
    versao: str = "1.5"
    versao_programa: str = "1.5"


def b64url_decode(texto: str) -> bytes:
    texto = (texto or "").strip()
    texto += "=" * (-len(texto) % 4)
    return base64.urlsafe_b64decode(texto.encode("utf-8"))


def b64url_json_decode(texto: str) -> dict:
    return json.loads(b64url_decode(texto).decode("utf-8"))


def assinar(payload_b64: str) -> str:
    sig = hmac.new(SECRET_KEY, payload_b64.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(sig).decode("utf-8").rstrip("=")


def normalizar_modulos(modulos):
    mapa = {
        "farejador": "sniffer",
        "troncos": "logs",
        "engenharia": "engenharia_can",
        "simulador": "simulador_can",
    }
    saida = []
    for m in modulos or []:
        mm = str(m or "").strip().lower().replace("-", "_").replace(" ", "_")
        mm = mapa.get(mm, mm)
        if mm in MODULOS_VALIDOS and mm not in saida:
            saida.append(mm)
    return saida


def validar_chave(chave: str) -> tuple[bool, dict, str]:
    chave = (chave or "").strip()
    if not chave.startswith("MCA2-"):
        return False, {}, "Formato de chave inválido"
    partes = chave.split("-")
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

@app.get("/")
def home():
    return {
        "status": "online",
        "sistema": "MASTER CAN ANALYSE",
        "modo": "hibrido_sem_banco",
        "rotas": ["/health", "/licencas/validar"],
    }

@app.get("/health")
def health():
    return {
        "ok": True,
        "status": "online",
        "modo": "hibrido_sem_banco",
        "hora": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

@app.post("/licencas/validar")
def licencas_validar(d: ValidarIn):
    ok, payload, msg = validar_chave(d.chave)
    if not ok:
        return {"ok": False, "status": "bloqueada", "message": msg, "modulos": []}

    id_recebido = (d.id_maquina or d.machine_id or "").strip()
    id_chave = str(payload.get("id_maquina", "")).strip()
    if id_chave and id_recebido and id_chave != id_recebido:
        return {
            "ok": False,
            "status": "bloqueada",
            "message": "Licença pertence a outra máquina",
            "modulos": [],
        }

    modulos = normalizar_modulos(payload.get("modulos", []))
    return {
        "ok": True,
        "status": "ativa",
        "tipo": payload.get("tipo", "permanente"),
        "numero": payload.get("numero", "MCA-OFFLINE"),
        "chave": d.chave,
        "cliente": payload.get("cliente", ""),
        "id_maquina": id_chave,
        "expires": payload.get("expires", "2099-12-31"),
        "modulos": modulos,
        "message": "Licença validada online com sucesso",
    }

# Compatibilidade opcional com versões antigas
@app.post("/ativar")
def ativar(d: ValidarIn):
    return licencas_validar(d)

@app.post("/verificar")
def verificar(d: ValidarIn):
    return licencas_validar(d)
