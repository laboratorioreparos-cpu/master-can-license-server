
import os
import json
import shutil
import time
from pathlib import Path
from flask import Flask, request, jsonify

app = Flask(__name__)

DATA_DIR = Path(os.environ.get('DATA_DIR', '/var/data'))
if not DATA_DIR.exists():
    DATA_DIR = Path(os.environ.get('RENDER_DATA_DIR', '.'))
DB_FILE = DATA_DIR / 'clientes.json'
BACKUP_DIR = DATA_DIR / 'backups'


def _ensure_dirs():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def _default_db():
    return {'clientes': []}


def load_db():
    _ensure_dirs()
    if not DB_FILE.exists():
        save_db(_default_db(), backup=False)
        return _default_db()
    try:
        data = json.loads(DB_FILE.read_text(encoding='utf-8'))
        if isinstance(data, list):
            return {'clientes': data}
        if 'clientes' not in data or not isinstance(data['clientes'], list):
            data['clientes'] = []
        return data
    except Exception:
        broken = BACKUP_DIR / f'clientes_corrompido_{int(time.time())}.json'
        try:
            shutil.copy2(DB_FILE, broken)
        except Exception:
            pass
        save_db(_default_db(), backup=False)
        return _default_db()


def save_db(data, backup=True):
    _ensure_dirs()
    if backup and DB_FILE.exists():
        try:
            shutil.copy2(DB_FILE, BACKUP_DIR / f'clientes_backup_{int(time.time())}.json')
        except Exception:
            pass
    tmp = DB_FILE.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(tmp, DB_FILE)


def find_cliente(data, cliente_id):
    cliente_id = str(cliente_id)
    for i, c in enumerate(data.get('clientes', [])):
        if str(c.get('id')) == cliente_id or str(c.get('machine_id')) == cliente_id:
            return i, c
    return None, None


@app.get('/')
def index():
    return jsonify({
        'status': 'online',
        'server': 'MASTER CAN ANALYSE License Server',
        'persistencia': str(DB_FILE),
        'endpoints': ['/health', '/clientes', '/clientes/<id>', '/backup']
    })


@app.get('/health')
def health():
    data = load_db()
    return jsonify({
        'ok': True,
        'clientes': len(data.get('clientes', [])),
        'db_file': str(DB_FILE),
        'db_exists': DB_FILE.exists(),
        'backup_dir': str(BACKUP_DIR)
    })


@app.get('/clientes')
def listar_clientes():
    return jsonify(load_db().get('clientes', []))


@app.post('/clientes')
def criar_cliente():
    payload = request.get_json(silent=True) or {}
    data = load_db()
    clientes = data.setdefault('clientes', [])

    cliente_id = payload.get('id') or payload.get('machine_id') or payload.get('nome') or str(int(time.time()))
    idx, antigo = find_cliente(data, cliente_id)

    if idx is not None:
        novo = dict(antigo)
        novo.update(payload)
        novo['id'] = antigo.get('id') or str(cliente_id)
        clientes[idx] = novo
        save_db(data)
        return jsonify({'ok': True, 'acao': 'atualizado', 'cliente': novo})

    novo = dict(payload)
    novo['id'] = str(cliente_id)
    clientes.append(novo)
    save_db(data)
    return jsonify({'ok': True, 'acao': 'criado', 'cliente': novo}), 201


@app.get('/clientes/<cliente_id>')
def obter_cliente(cliente_id):
    data = load_db()
    idx, cliente = find_cliente(data, cliente_id)
    if cliente is None:
        return jsonify({'ok': False, 'erro': 'cliente nao encontrado'}), 404
    return jsonify(cliente)


@app.put('/clientes/<cliente_id>')
@app.patch('/clientes/<cliente_id>')
def atualizar_cliente(cliente_id):
    payload = request.get_json(silent=True) or {}
    data = load_db()
    idx, cliente = find_cliente(data, cliente_id)
    if cliente is None:
        return jsonify({'ok': False, 'erro': 'cliente nao encontrado'}), 404
    novo = dict(cliente)
    novo.update(payload)
    data['clientes'][idx] = novo
    save_db(data)
    return jsonify({'ok': True, 'cliente': novo})


@app.delete('/clientes/<cliente_id>')
def excluir_cliente(cliente_id):
    data = load_db()
    idx, cliente = find_cliente(data, cliente_id)
    if cliente is None:
        return jsonify({'ok': False, 'erro': 'cliente nao encontrado'}), 404
    removido = data['clientes'].pop(idx)
    save_db(data)
    return jsonify({'ok': True, 'removido': removido})


@app.post('/backup')
def backup_manual():
    _ensure_dirs()
    if DB_FILE.exists():
        dest = BACKUP_DIR / f'clientes_backup_manual_{int(time.time())}.json'
        shutil.copy2(DB_FILE, dest)
        return jsonify({'ok': True, 'backup': str(dest)})
    return jsonify({'ok': False, 'erro': 'banco ainda nao existe'}), 404


if __name__ == '__main__':
    port = int(os.environ.get('PORT', '10000'))
    app.run(host='0.0.0.0', port=port)
