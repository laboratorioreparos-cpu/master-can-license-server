CORRECAO DO ERRO ModuleNotFoundError: flask
===========================================

O Render antigo estava tentando iniciar o servidor por `python app.py`.
Antes existia um app.py antigo em Flask, mas o servidor correto atual é FastAPI no main.py.

Correção aplicada:
- app.py agora apenas chama o servidor FastAPI do main.py
- não precisa instalar Flask
- funciona tanto com `python app.py` quanto com `uvicorn main:app --host 0.0.0.0 --port $PORT`

Arquivos importantes:
- main.py = servidor corrigido com persistência/backup
- app.py = compatibilidade com configuração antiga do Render
- requirements.txt = fastapi, uvicorn, pydantic
- render.yaml = configuração recomendada para Render com disco persistente
