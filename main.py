import os
import sqlite3
import secrets
import shutil
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

# Banco persistente. No Render, use /var/data/licencas.db com Disk ativado.
# Localmente, se DB_PATH não existir, salva ao lado do main.py.
DB = Path(os.environ.get("DB_PATH", str(Path(__file__).with_name("licencas.db")))).expanduser()
BACKUP_DIR = Path(os.environ.get("BACKUP_DIR", str(DB.parent / "backups"))).expanduser()
MAX_BACKUPS = int(os.environ.get("MAX_BACKUPS", "30"))

MODULOS = [
    "monitor",
    "sniffer",
    "logs",
    "radar",
    "engenharia",
    "simulador",
    "atualizacao_online",
]



def backup_db(motivo: str = "manual") -> str | None:
    """Cria backup do banco antes de alterações importantes."""
    try:
        if not DB.exists():
            return None
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_motivo = "".join(ch for ch in motivo if ch.isalnum() or ch in ("_", "-"))[:40] or "backup"
        destino = BACKUP_DIR / f"licencas_{stamp}_{safe_motivo}.db"
        shutil.copy2(DB, destino)

        backups = sorted(BACKUP_DIR.glob("licencas_*.db"), key=lambda x: x.stat().st_mtime, reverse=True)
        for old in backups[MAX_BACKUPS:]:
            try:
                old.unlink()
            except Exception:
                pass
        return str(destino)
    except Exception:
        return None


def executar_write(sql: str, params: tuple = (), motivo_backup: str = "alteracao"):
    backup_db(motivo_backup)
    con = db()
    cur = con.cursor()
    cur.execute(sql, params)
    con.commit()
    last_id = cur.lastrowid
    con.close()
    return last_id

app = FastAPI(title="MASTER CAN ANALYSE - Servidor de Licencas")

class ClienteIn(BaseModel):
    nome: str
    telefone: str = ""
    email: str = ""
    observacao: str = ""

class LicencaIn(BaseModel):
    cliente_id: int
    modulos: list[str] = []
    tipo: str = "permanente"
    max_ativacoes: int = 1

class AtivacaoIn(BaseModel):
    chave: str
    machine_id: str
    versao_programa: str = "1.0"

class ModulosIn(BaseModel):
    modulos: list[str] = []

def db():
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con

def init():
    con = db()
    cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS clientes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        telefone TEXT,
        email TEXT,
        observacao TEXT,
        criado_em TEXT DEFAULT CURRENT_TIMESTAMP)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS licencas(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numero TEXT UNIQUE,
        chave TEXT UNIQUE,
        cliente_id INTEGER,
        tipo TEXT DEFAULT 'permanente',
        status TEXT DEFAULT 'ativa',
        machine_id TEXT,
        max_ativacoes INTEGER DEFAULT 1,
        data_ativacao TEXT,
        ultima_verificacao TEXT,
        ultima_versao TEXT,
        criado_em TEXT DEFAULT CURRENT_TIMESTAMP)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS modulos_licenca(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        licenca_id INTEGER,
        modulo TEXT,
        liberado INTEGER DEFAULT 0,
        UNIQUE(licenca_id, modulo))""")
    cur.execute("""CREATE TABLE IF NOT EXISTS ativacoes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        licenca_id INTEGER,
        machine_id TEXT,
        versao_programa TEXT,
        ip TEXT,
        criado_em TEXT DEFAULT CURRENT_TIMESTAMP)""")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_clientes_nome ON clientes(nome)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_licencas_cliente ON licencas(cliente_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_licencas_chave ON licencas(chave)")
    con.commit()
    con.close()

@app.on_event("startup")
def startup():
    init()

def garantir_modulos(lid):
    con = db()
    cur = con.cursor()
    for m in MODULOS:
        cur.execute("INSERT OR IGNORE INTO modulos_licenca(licenca_id,modulo,liberado) VALUES(?,?,0)", (lid, m))
    con.commit()
    con.close()

def mods(cur, lid):
    garantir_modulos(lid)
    cur.execute("SELECT modulo,liberado FROM modulos_licenca WHERE licenca_id=?", (lid,))
    return {r["modulo"]: bool(r["liberado"]) for r in cur.fetchall()}

def proximo_numero():
    con = db()
    cur = con.cursor()
    cur.execute("SELECT numero FROM licencas ORDER BY numero")
    usados = set()
    for row in cur.fetchall():
        try:
            usados.add(int(str(row["numero"]).replace("MCA-", "")))
        except Exception:
            pass
    con.close()
    n = 1
    while n in usados:
        n += 1
    return f"MCA-{n:04d}"

def gerar_chave():
    return "CHINA-" + "-".join(secrets.token_hex(2).upper() for _ in range(4))

@app.get("/")
def home():
    return {"status": "online", "sistema": "MASTER CAN ANALYSE LICENCAS", "db": str(DB), "persistencia": DB.exists()}

@app.get("/health")
def health():
    return {"ok": True, "db_existe": DB.exists(), "db_path": str(DB), "backup_dir": str(BACKUP_DIR)}

@app.post("/backup")
def criar_backup_manual():
    caminho = backup_db("manual")
    return {"ok": True, "backup": caminho}

@app.post("/clientes")
def criar_cliente(d: ClienteIn):
    nome = d.nome.strip()
    if not nome:
        raise HTTPException(400, "Nome do cliente e obrigatorio")
    backup_db("antes_criar_cliente")
    con = db()
    cur = con.cursor()
    cur.execute("INSERT INTO clientes(nome,telefone,email,observacao) VALUES(?,?,?,?)", (nome, d.telefone.strip(), d.email.strip(), d.observacao.strip()))
    con.commit()
    cid = cur.lastrowid
    con.close()
    return {"ok": True, "cliente_id": cid}

@app.get("/clientes")
def listar_clientes():
    con = db()
    cur = con.cursor()
    cur.execute("SELECT * FROM clientes ORDER BY id DESC")
    rows = [dict(r) for r in cur.fetchall()]
    con.close()
    return rows

@app.put("/clientes/{cid}")
def editar_cliente(cid: int, d: ClienteIn):
    nome = d.nome.strip()
    if not nome:
        raise HTTPException(400, "Nome do cliente e obrigatorio")
    backup_db("antes_editar_cliente")
    con = db()
    cur = con.cursor()
    cur.execute("UPDATE clientes SET nome=?,telefone=?,email=?,observacao=? WHERE id=?", (nome, d.telefone.strip(), d.email.strip(), d.observacao.strip(), cid))
    if cur.rowcount == 0:
        con.close()
        raise HTTPException(404, "Cliente nao encontrado")
    con.commit()
    con.close()
    return {"ok": True}

@app.delete("/clientes/{cid}")
def excluir_cliente(cid: int):
    backup_db("antes_excluir_cliente")
    con = db()
    cur = con.cursor()
    cur.execute("SELECT id FROM clientes WHERE id=?", (cid,))
    if not cur.fetchone():
        con.close()
        raise HTTPException(404, "Cliente nao encontrado")
    cur.execute("SELECT id FROM licencas WHERE cliente_id=?", (cid,))
    lids = [r["id"] for r in cur.fetchall()]
    for lid in lids:
        cur.execute("DELETE FROM modulos_licenca WHERE licenca_id=?", (lid,))
        cur.execute("DELETE FROM ativacoes WHERE licenca_id=?", (lid,))
    cur.execute("DELETE FROM licencas WHERE cliente_id=?", (cid,))
    cur.execute("DELETE FROM clientes WHERE id=?", (cid,))
    con.commit()
    con.close()
    return {"ok": True}

@app.post("/licencas")
def criar_licenca(d: LicencaIn):
    backup_db("antes_criar_licenca")
    con = db()
    cur = con.cursor()
    cur.execute("SELECT id FROM clientes WHERE id=?", (d.cliente_id,))
    if not cur.fetchone():
        con.close()
        raise HTTPException(404, "Cliente nao encontrado")
    numero = proximo_numero()
    chave = gerar_chave()
    cur.execute("INSERT INTO licencas(numero,chave,cliente_id,tipo,max_ativacoes) VALUES(?,?,?,?,?)", (numero, chave, d.cliente_id, d.tipo, max(1, d.max_ativacoes)))
    lid = cur.lastrowid
    con.commit()
    con.close()
    garantir_modulos(lid)
    atualizar_modulos(lid, ModulosIn(modulos=d.modulos))
    return {"ok": True, "licenca_id": lid, "numero": numero, "chave": chave}

@app.get("/licencas")
def listar_licencas():
    con = db()
    cur = con.cursor()
    cur.execute("""SELECT l.*, c.nome cliente, c.telefone, c.email, c.observacao
                   FROM licencas l JOIN clientes c ON c.id=l.cliente_id
                   ORDER BY l.id DESC""")
    out = []
    for r in cur.fetchall():
        d = dict(r)
        m = mods(cur, d["id"])
        d["ativada"] = bool(d.get("machine_id"))
        d["machine_curta"] = (d["machine_id"][:12] + "...") if d.get("machine_id") else ""
        d["modulos_texto"] = ", ".join([k for k, v in m.items() if v])
        out.append(d)
    con.close()
    return out

@app.get("/licencas/{lid}")
def obter_licenca(lid: int):
    con = db()
    cur = con.cursor()
    cur.execute("""SELECT l.*, c.nome cliente, c.telefone, c.email, c.observacao
                   FROM licencas l JOIN clientes c ON c.id=l.cliente_id
                   WHERE l.id=?""", (lid,))
    r = cur.fetchone()
    if not r:
        con.close()
        raise HTTPException(404, "Licenca nao encontrada")
    d = dict(r)
    d["ativada"] = bool(d.get("machine_id"))
    d["modulos"] = mods(cur, lid)
    con.close()
    return d

@app.delete("/licencas/{lid}")
def excluir_licenca(lid: int):
    backup_db("antes_excluir_licenca")
    con = db()
    cur = con.cursor()
    cur.execute("DELETE FROM modulos_licenca WHERE licenca_id=?", (lid,))
    cur.execute("DELETE FROM ativacoes WHERE licenca_id=?", (lid,))
    cur.execute("DELETE FROM licencas WHERE id=?", (lid,))
    con.commit()
    con.close()
    return {"ok": True}

@app.put("/licencas/{lid}/resetar")
def resetar(lid: int):
    backup_db("antes_resetar_licenca")
    con = db()
    cur = con.cursor()
    cur.execute("UPDATE licencas SET machine_id=NULL,data_ativacao=NULL,ultima_verificacao=NULL,ultima_versao=NULL WHERE id=?", (lid,))
    cur.execute("DELETE FROM ativacoes WHERE licenca_id=?", (lid,))
    con.commit()
    con.close()
    return {"ok": True}

@app.get("/licencas/{lid}/modulos")
def obter_modulos(lid: int):
    con = db()
    cur = con.cursor()
    m = mods(cur, lid)
    con.close()
    return m

@app.put("/licencas/{lid}/modulos")
def atualizar_modulos(lid: int, d: ModulosIn):
    backup_db("antes_atualizar_modulos")
    garantir_modulos(lid)
    con = db()
    cur = con.cursor()
    cur.execute("UPDATE modulos_licenca SET liberado=0 WHERE licenca_id=?", (lid,))
    for m in d.modulos:
        if m in MODULOS:
            cur.execute("UPDATE modulos_licenca SET liberado=1 WHERE licenca_id=? AND modulo=?", (lid, m))
    con.commit()
    con.close()
    return {"ok": True}

@app.put("/licencas/{lid}/status/{status}")
def status(lid: int, status: str):
    if status not in ["ativa", "bloqueada", "cancelada"]:
        raise HTTPException(400, "Status invalido")
    backup_db("antes_alterar_status")
    con = db()
    cur = con.cursor()
    cur.execute("UPDATE licencas SET status=? WHERE id=?", (status, lid))
    con.commit()
    con.close()
    return {"ok": True}

@app.post("/ativar")
def ativar(d: AtivacaoIn, request: Request):
    con = db()
    cur = con.cursor()
    cur.execute("SELECT * FROM licencas WHERE chave=?", (d.chave,))
    lic = cur.fetchone()
    if not lic:
        con.close()
        raise HTTPException(404, "Chave invalida")
    if lic["status"] != "ativa":
        con.close()
        raise HTTPException(403, f"Licenca {lic['status']}")
    if lic["machine_id"] and lic["machine_id"] != d.machine_id:
        con.close()
        raise HTTPException(403, "Licenca ja ativada em outra maquina")
    if not lic["machine_id"]:
        backup_db("antes_ativar_licenca")
        cur.execute("UPDATE licencas SET machine_id=?,data_ativacao=CURRENT_TIMESTAMP,ultima_verificacao=CURRENT_TIMESTAMP,ultima_versao=? WHERE id=?", (d.machine_id, d.versao_programa, lic["id"]))
        cur.execute("INSERT INTO ativacoes(licenca_id,machine_id,versao_programa,ip) VALUES(?,?,?,?)", (lic["id"], d.machine_id, d.versao_programa, request.client.host if request.client else ""))
    else:
        cur.execute("UPDATE licencas SET ultima_verificacao=CURRENT_TIMESTAMP,ultima_versao=? WHERE id=?", (d.versao_programa, lic["id"]))
    con.commit()
    cur.execute("SELECT * FROM licencas WHERE id=?", (lic["id"],))
    lic2 = cur.fetchone()
    m = mods(cur, lic["id"])
    con.close()
    return {"ok": True, "numero": lic2["numero"], "tipo": lic2["tipo"], "status": lic2["status"], "machine_id": lic2["machine_id"], "data_ativacao": lic2["data_ativacao"], "ultima_verificacao": lic2["ultima_verificacao"], "modulos": m}

@app.post("/verificar")
def verificar(d: AtivacaoIn):
    con = db()
    cur = con.cursor()
    cur.execute("SELECT * FROM licencas WHERE chave=?", (d.chave,))
    lic = cur.fetchone()
    if not lic:
        con.close()
        raise HTTPException(404, "Chave invalida")
    if lic["status"] != "ativa":
        con.close()
        raise HTTPException(403, f"Licenca {lic['status']}")
    if lic["machine_id"] != d.machine_id:
        con.close()
        raise HTTPException(403, "Maquina nao autorizada")
    cur.execute("UPDATE licencas SET ultima_verificacao=CURRENT_TIMESTAMP,ultima_versao=? WHERE id=?", (d.versao_programa, lic["id"]))
    con.commit()
    cur.execute("SELECT * FROM licencas WHERE id=?", (lic["id"],))
    lic2 = cur.fetchone()
    m = mods(cur, lic["id"])
    con.close()
    return {"ok": True, "numero": lic2["numero"], "tipo": lic2["tipo"], "status": lic2["status"], "machine_id": lic2["machine_id"], "data_ativacao": lic2["data_ativacao"], "ultima_verificacao": lic2["ultima_verificacao"], "modulos": m}