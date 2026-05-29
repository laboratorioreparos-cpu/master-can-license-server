MASTER CAN - SERVIDOR HÍBRIDO SEM BANCO

Este servidor não salva clientes nem licenças.
Ele apenas valida online as chaves geradas pelo gerenciador local.

Rotas:
- GET /health
- POST /licencas/validar

Vantagens:
- Render não apaga cadastro porque não há banco no Render.
- Clientes ficam salvos só no gerenciador local.
- MASTER CAN ANALYSE continua validando online.
