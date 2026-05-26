SERVIDOR ONLINE - MASTER CAN ANALYSE

Suba estes arquivos em uma hospedagem Python/FastAPI.

Render:
Build command:
pip install -r requirements.txt

Start command:
uvicorn main:app --host 0.0.0.0 --port $PORT

Variável:
DB_PATH=/var/data/licencas.db

Disco persistente:
mountPath=/var/data
size: 1GB

Depois use a URL gerada no config_servidor.json.
