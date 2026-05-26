CORRECAO - CADASTROS NAO APAGAREM
=================================

Esta versao foi ajustada para o servidor online MASTER CAN ANALYSE.

O que foi corrigido:
- Banco SQLite continua em DB_PATH.
- No Render, DB_PATH deve ficar em /var/data/licencas.db.
- render.yaml ja mantem Disk persistente em /var/data.
- Criado backup automatico antes de cadastrar, editar, excluir, resetar, ativar e alterar modulos/status.
- Backups ficam em /var/data/backups no Render ou na pasta backups local.
- Criado endpoint /health para conferir caminho do banco.
- Criado endpoint /backup para backup manual.
- Valida cliente antes de criar licenca.
- Evita cadastro de cliente sem nome.
- Protege edicao/exclusao quando cliente nao existe.

IMPORTANTE NO RENDER:
Se trocar de servico ou apagar o Disk do Render, os clientes somem porque o banco fica no Disk.
Nao apagar o Disk master-can-db.

Fluxo de teste:
1. Subir estes arquivos no GitHub.
2. Fazer deploy no Render.
3. Abrir /health e conferir db_path = /var/data/licencas.db.
4. Cadastrar cliente.
5. Fechar e reabrir o painel/gerenciador.
6. O cliente deve continuar listado.
