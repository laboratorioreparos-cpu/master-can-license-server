import base64
import hashlib
import hmac
import json
import os
import unicodedata
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from fastapi import FastAPI
from pydantic import BaseModel

# IMPORTANTE:
# A chave MCA2 usa base64 URL-safe. Esse texto pode conter '-' dentro do payload
# ou da assinatura. Por isso NÃO pode usar chave.split('-') esperando 3 partes.
# A assinatura HMAC-SHA256 em base64url sem '=' tem tamanho fixo de 43 caracteres.

SEGREDOS = [
    b"MASTER_CAN_ANALYSE_HIBRIDO_2026_CHINA_REPAROS",
    os.environ.get("MCA_SECRET_KEY", "").encode("utf-8"),
    b"MASTER_CAN_ANALYSE_ONLINE_2026_CHINA_REPAROS",
    b"MASTER_CAN_ANALYSE_CACHE_LOCAL_2026",
]
SEGREDOS = [s for s in SEGREDOS if s]

MODULOS_VALIDOS = {
    "monitor",
    "sniffer",
    "logs",
    "radar",
    "engenharia_can",
    "simulador_can",
    "atualizacao_online",
}

app = FastAPI(title="MASTER CAN ANALYSE - Validação Online V151 Compatível")


class ValidarIn(BaseModel):
    chave: str = ""
    license_key: str = ""
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


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def assinar(payload_b64: str, segredo: bytes) -> str:
    sig = hmac.new(segredo, payload_b64.encode("utf-8"), hashlib.sha256).digest()
    return b64url(sig)


def separar_chave_mca2(chave: str) -> Tuple[bool, str, str, str]:
    chave = (chave or "").strip()
    if not chave.startswith("MCA2-"):
        return False, "", "", "Formato de chave inválido"

    resto = chave[5:]
    # Formato: MCA2-<payload_b64>-<assinatura_43_chars>
    # Base64url permite '-' dentro do payload e dentro da assinatura.
    # Então a única forma segura aqui é pegar os últimos 43 caracteres como assinatura
    # e o caractere anterior precisa ser o separador '-'.
    if len(resto) < 45:
        return False, "", "", "Chave incompleta"

    sig = resto[-43:]
    sep = resto[-44:-43]
    payload_b64 = resto[:-44]
    if sep != "-" or not payload_b64 or not sig:
        return False, "", "", "Separador da chave inválido"
    return True, payload_b64, sig, "ok"


def _sem_acentos(txt: str) -> str:
    txt = unicodedata.normalize("NFKD", txt or "")
    return "".join(c for c in txt if not unicodedata.combining(c))


def normalizar_modulo(m: Any) -> str:
    mm = _sem_acentos(str(m or "").strip().lower())
    mm = mm.replace("-", "_").replace("/", "_").replace(" ", "_")
    while "__" in mm:
        mm = mm.replace("__", "_")
    mapa = {
        "farejador": "sniffer",
        "sniffer_farejador": "sniffer",
        "troncos": "logs",
        "logs_troncos": "logs",
        "engenharia": "engenharia_can",
        "engenharia_can": "engenharia_can",
        "simulador": "simulador_can",
        "simulador_can": "simulador_can",
        "atualizacao": "atualizacao_online",
        "atualizacao_online": "atualizacao_online",
        "atualizacao_on_line": "atualizacao_online",
    }
    return mapa.get(mm, mm)


def normalizar_modulos(modulos: Any) -> List[str]:
    if isinstance(modulos, str):
        try:
            modulos = json.loads(modulos)
        except Exception:
            modulos = [x.strip() for x in modulos.split(",") if x.strip()]
    saida: List[str] = []
    for m in modulos or []:
        mm = normalizar_modulo(m)
        if mm in MODULOS_VALIDOS and mm not in saida:
            saida.append(mm)
    return saida


def validar_chave(chave: str) -> Tuple[bool, Dict[str, Any], str]:
    ok, payload_b64, sig_recebida, msg = separar_chave_mca2(chave)
    if not ok:
        return False, {}, msg

    assinatura_ok = False
    for segredo in SEGREDOS:
        if hmac.compare_digest(assinar(payload_b64, segredo), sig_recebida):
            assinatura_ok = True
            break
    if not assinatura_ok:
        return False, {}, "Assinatura inválida"

    try:
        payload = b64url_json_decode(payload_b64)
    except Exception as e:
        return False, {}, f"Payload inválido: {e}"

    return True, payload, "ok"


def resposta_bloqueada(msg: str) -> dict:
    return {
        "ok": False,
        "success": False,
        "valid": False,
        "ativada": False,
        "liberada": False,
        "status": "bloqueada",
        "licenca": "bloqueada",
        "message": msg,
        "mensagem": msg,
        "modulos": [],
        "funcoes": [],
        "modules": [],
        "modulos_liberados": [],
    }


def resposta_ativa(chave: str, payload: dict) -> dict:
    modulos = normalizar_modulos(payload.get("modulos", []))
    numero = payload.get("numero", "MCA-ONLINE")
    return {
        "ok": True,
        "success": True,
        "valid": True,
        "ativada": True,
        "liberada": True,
        # O MASTER CAN V151 aceita active/ativa/valid.
        "status": "active",
        "licenca": "ativa",
        "tipo": payload.get("tipo", "permanente"),
        "numero": numero,
        "chave": chave,
        "license_key": chave,
        "cliente": payload.get("cliente", ""),
        "id_maquina": payload.get("id_maquina", ""),
        "machine_id": payload.get("id_maquina", ""),
        "expires": payload.get("expires", "2099-12-31"),
        "modulos": modulos,
        "funcoes": modulos,
        "modules": modulos,
        "modulos_liberados": modulos,
        "message": "Licença validada online com sucesso",
        "mensagem": "Licença validada online com sucesso",
    }


def processar_validacao(d: ValidarIn) -> dict:
    chave = (d.chave or d.license_key or "").strip()
    ok, payload, msg = validar_chave(chave)
    if not ok:
        return resposta_bloqueada(msg)

    id_recebido = (d.id_maquina or d.machine_id or "").strip()
    id_chave = str(payload.get("id_maquina", "")).strip()
    if id_chave and id_recebido and id_chave != id_recebido:
        return resposta_bloqueada("Licença pertence a outra máquina")

    return resposta_ativa(chave, payload)


@app.get("/")
def home():
    return {
        "ok": True,
        "status": "online",
        "sistema": "MASTER CAN ANALYSE",
        "versao_servidor": "V151_FIX_CHAVE_MCA2",
        "rotas": ["/health", "/licencas/validar", "/ativar", "/verificar"],
    }


@app.get("/health")
def health():
    return {
        "ok": True,
        "status": "online",
        "versao_servidor": "V151_FIX_CHAVE_MCA2",
        "hora": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


@app.post("/licencas/validar")
def licencas_validar(d: ValidarIn):
    return processar_validacao(d)


@app.post("/ativar")
def ativar(d: ValidarIn):
    return processar_validacao(d)


@app.post("/verificar")
def verificar(d: ValidarIn):
    return processar_validacao(d)
