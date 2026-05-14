from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sqlite3
import secrets
from pathlib import Path
from datetime import datetime

DB = Path(__file__).with_name("licencas.db")

MODULOS_PADRAO = [
    "monitor",
    "farejador",
    "troncos",
    "radar",
    "engenharia",
    "simulador",
    "atualizacao_online",
]

app = FastAPI(title="MASTER CAN LICENSE SERVER")


class Cliente(BaseModel):
    nome: str
    telefone: str = ""
    email: str = ""
    observacao: str = ""


class CriarLicenca(BaseModel):
    cliente_nome: str
    id_maquina: str
    tipo: str = "vitalicia"
    modulos: list[str] = MODULOS_PADRAO


class Ativacao(BaseModel):
    chave: str
    id_maquina: str
    versao: str = ""


def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def inicializar_banco():
    con = db()
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            telefone TEXT,
            email TEXT,
            observacao TEXT,
            criado_em TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS licencas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_nome TEXT NOT NULL,
            chave TEXT UNIQUE NOT NULL,
            id_maquina TEXT NOT NULL,
            tipo TEXT,
            status TEXT,
            modulos TEXT,
            criada_em TEXT,
            ultima_verificacao TEXT,
            ultima_versao TEXT
        )
    """)

    con.commit()
    con.close()


inicializar_banco()


@app.get("/")
def home():
    return {
        "ok": True,
        "servidor": "MASTER CAN ANALYSE",
        "status": "online",
        "mensagem": "Servidor de licenca ativo"
    }


@app.get("/status")
def status():
    return {
        "ok": True,
        "status": "online",
        "hora": datetime.now().isoformat()
    }


@app.post("/clientes")
def criar_cliente(c: Cliente):
    con = db()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO clientes (nome, telefone, email, observacao, criado_em) VALUES (?, ?, ?, ?, ?)",
        (c.nome, c.telefone, c.email, c.observacao, datetime.now().isoformat())
    )
    con.commit()
    cliente_id = cur.lastrowid
    con.close()

    return {
        "ok": True,
        "cliente_id": cliente_id,
        "nome": c.nome
    }


@app.get("/clientes")
def listar_clientes():
    con = db()
    cur = con.cursor()
    cur.execute("SELECT * FROM clientes ORDER BY id DESC")
    dados = [dict(row) for row in cur.fetchall()]
    con.close()
    return dados


@app.post("/licencas")
def criar_licenca(l: CriarLicenca):
    chave = "MC-" + secrets.token_hex(12).upper()
    modulos_txt = ",".join(l.modulos)

    con = db()
    cur = con.cursor()
    cur.execute(
        """
        INSERT INTO licencas
        (cliente_nome, chave, id_maquina, tipo, status, modulos, criada_em, ultima_verificacao, ultima_versao)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            l.cliente_nome,
            chave,
            l.id_maquina,
            l.tipo,
            "ativa",
            modulos_txt,
            datetime.now().isoformat(),
            "",
            ""
        )
    )
    con.commit()
    licenca_id = cur.lastrowid
    con.close()

    return {
        "ok": True,
        "licenca_id": licenca_id,
        "cliente_nome": l.cliente_nome,
        "chave": chave,
        "id_maquina": l.id_maquina,
        "tipo": l.tipo,
        "status": "ativa",
        "modulos": l.modulos
    }


@app.get("/licencas")
def listar_licencas():
    con = db()
    cur = con.cursor()
    cur.execute("SELECT * FROM licencas ORDER BY id DESC")
    dados = [dict(row) for row in cur.fetchall()]
    con.close()
    return dados


@app.post("/verificar")
def verificar(d: Ativacao):
    con = db()
    cur = con.cursor()

    cur.execute("SELECT * FROM licencas WHERE chave = ?", (d.chave,))
    licenca = cur.fetchone()

    if not licenca:
        con.close()
        raise HTTPException(status_code=404, detail="Chave invalida")

    if licenca["status"] != "ativa":
        con.close()
        raise HTTPException(status_code=403, detail=f"Licenca {licenca['status']}")

    if licenca["id_maquina"] != d.id_maquina:
        con.close()
        raise HTTPException(status_code=403, detail="Maquina nao autorizada")

    cur.execute(
        "UPDATE licencas SET ultima_verificacao = ?, ultima_versao = ? WHERE id = ?",
        (datetime.now().isoformat(), d.versao, licenca["id"])
    )
    con.commit()

    cur.execute("SELECT * FROM licencas WHERE id = ?", (licenca["id"],))
    licenca = cur.fetchone()
    con.close()

    return {
        "ok": True,
        "cliente_nome": licenca["cliente_nome"],
        "chave": licenca["chave"],
        "id_maquina": licenca["id_maquina"],
        "tipo": licenca["tipo"],
        "status": licenca["status"],
        "modulos": licenca["modulos"].split(",") if licenca["modulos"] else [],
        "ultima_verificacao": licenca["ultima_verificacao"],
        "ultima_versao": licenca["ultima_versao"]
    }


@app.post("/bloquear/{licenca_id}")
def bloquear_licenca(licenca_id: int):
    con = db()
    cur = con.cursor()
    cur.execute("UPDATE licencas SET status = ? WHERE id = ?", ("bloqueada", licenca_id))
    con.commit()
    con.close()
    return {"ok": True, "licenca_id": licenca_id, "status": "bloqueada"}


@app.post("/ativar/{licenca_id}")
def ativar_licenca(licenca_id: int):
    con = db()
    cur = con.cursor()
    cur.execute("UPDATE licencas SET status = ? WHERE id = ?", ("ativa", licenca_id))
    con.commit()
    con.close()
    return {"ok": True, "licenca_id": licenca_id, "status": "ativa"}
