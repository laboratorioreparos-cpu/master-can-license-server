"""
Compatibilidade com Render antigo.
Se o Render estiver configurado para rodar `python app.py`, este arquivo sobe o mesmo servidor FastAPI do main.py.
"""
import os
import uvicorn
from main import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
