# 💈 Barbearia — Sistema de Agendamento

<p align="center">
  Sistema web para apresentação de serviços e agendamento de horários em uma barbearia.
</p>

---

## 📌 Sobre o projeto

Projeto acadêmico de desenvolvimento de um site para uma barbearia de bairro, com apresentação de serviços, avaliações de clientes, agendamento online e um **painel para o barbeiro** gerenciar a agenda.

## 🎥 Demonstração

[Assista ao vídeo de demonstração do sistema](https://youtu.be/I4esbNbmNMc)

## ✨ Funcionalidades

**Para o cliente**
- 🏠 Página inicial, página "Sobre" com horário de funcionamento e mapa.
- ✂️ Catálogo de serviços com preço e duração.
- 📅 Agendamento em 3 passos: serviço → dia/horário → dados. Só aparecem horários realmente livres.
- 🔗 Link de confirmação com os detalhes, botão para avisar no WhatsApp e **cancelamento pelo próprio cliente** (até 2 h antes).
- ⭐ Avaliações com nota de 1 a 5 estrelas (com proteção simples contra spam).

**Para o barbeiro (`/admin`)**
- 📋 Agenda do dia com navegação entre datas e indicadores (atendimentos hoje, próximos 7 dias, faturado e previsto no mês).
- ✅ Marcar atendimento como concluído, cancelado ou "não compareceu".
- ➕ Registrar agendamentos feitos por telefone/WhatsApp ou encaixes na hora.
- 💲 Cadastrar, editar e ocultar serviços (o preço de agendamentos antigos é preservado).
- 🕘 Configurar horário de cada dia da semana, pausa de almoço e bloquear dias (feriados, folgas).
- 👥 Lista de clientes com número de atendimentos e busca.
- 🛡️ Moderar avaliações (ocultar/excluir).

**Regras de negócio**
- 🔒 Nenhum horário pode se sobrepor a outro (considera a duração de cada serviço).
- Respeita expediente, pausa, dias fechados, dias bloqueados, antecedência mínima (30 min) e máxima (30 dias).
- O cliente é identificado pelo telefone: quem agenda de novo com o mesmo número é o mesmo cliente.
- Proteção CSRF em todos os formulários e na API.

## 🚀 Tecnologias utilizadas

| Tecnologia | Aplicação |
|---|---|
| HTML5, CSS3, JavaScript | Páginas, estilo e interatividade (sem frameworks) |
| Python + Flask | Backend |
| Jinja2 | Templates com navbar/rodapé compartilhados |
| Flask-SQLAlchemy | Acesso ao banco de dados |
| SQLite / PostgreSQL | Banco em desenvolvimento / produção |
| pytest | Testes automatizados |
| Git e GitHub | Versionamento e colaboração |
| Render + Gunicorn | Hospedagem |

## ▶️ Como rodar na sua máquina

Pré-requisitos: [Python 3.10+](https://www.python.org/downloads/) e [Git](https://git-scm.com/).

```bash
# 1. Baixar o projeto
git clone https://github.com/thiagoNR7/barbearia.git
cd barbearia/backend

# 2. Criar e ativar um ambiente virtual
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac

# 3. Instalar as dependências
pip install -r requirements.txt

# 4. Criar o arquivo de configuração
copy .env.example .env         # Windows
# cp .env.example .env         # Linux/Mac

# 5. Rodar
python run.py
```

Abra **http://127.0.0.1:5000**. Na primeira execução o banco (`backend/instance/barbearia.db`) é criado com serviços, horários e avaliações de exemplo.

Painel do barbeiro: **http://127.0.0.1:5000/admin** — usuário e senha são os definidos em `ADMIN_USUARIO` e `ADMIN_SENHA` no `.env`.

Comandos úteis (dentro de `backend/`, com o venv ativo):

```bash
flask --app run reset-db      # apaga e recria o banco com os dados de exemplo
python -m pytest -v           # roda os testes (antes: pip install -r requirements-dev.txt)
```

## 📁 Estrutura do projeto

```text
Barbearia_projeto/
├── backend/
│   ├── app/
│   │   ├── __init__.py        # cria a aplicação, CSRF, filtros, dados iniciais
│   │   ├── config.py          # configurações (lidas do .env)
│   │   ├── models.py          # tabelas do banco
│   │   ├── agenda.py          # regras: horários livres, validação, criação
│   │   ├── routes.py          # páginas públicas e API
│   │   ├── admin.py           # painel do barbeiro
│   │   ├── templates/
│   │   │   ├── base.html, index.html, sobre.html, servicos.html,
│   │   │   ├── agendamento.html, confirmacao.html, avaliacoes.html, erro.html
│   │   │   ├── partials/      # navbar, rodapé, estrelas, formulário de agendamento
│   │   │   └── admin/         # telas do painel
│   │   └── static/
│   │       ├── css/style.css
│   │       ├── js/main.js, agendamento.js
│   │       └── img/
│   ├── tests/test_agendamento.py
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── run.py
│   └── .env.example
├── render.yaml
└── README.md
```

## 🗄️ Banco de dados

```text
clientes 1 ──── N agendamentos N ──── 1 servicos
clientes 1 ──── N avaliacoes
horarios_funcionamento  (um registro por dia da semana)
dias_bloqueados         (feriados e folgas)
```

| Tabela | Descrição |
|---|---|
| `clientes` | Nome, telefone (único) e e-mail |
| `servicos` | Nome, descrição, preço, duração, ativo/oculto |
| `agendamentos` | Cliente, serviço, início, fim, preço cobrado, status (`confirmado`, `concluido`, `cancelado`, `faltou`) e código do link de confirmação |
| `avaliacoes` | Nome, nota (1–5, com CHECK no banco), comentário, visível |
| `horarios_funcionamento` | Abertura, fechamento e pausa de cada dia |
| `dias_bloqueados` | Datas sem atendimento e motivo |

## 🔗 Rotas

| Método | Rota | Funcionalidade |
|---|---|---|
| GET | `/` | Página inicial |
| GET | `/sobre` | Sobre, horários e mapa |
| GET | `/servicos` | Serviços e preços |
| GET/POST | `/agendamento` | Formulário de agendamento |
| GET | `/agendamento/<codigo>` | Confirmação do agendamento |
| POST | `/agendamento/<codigo>/cancelar` | Cancelamento pelo cliente |
| GET/POST | `/avaliacoes` | Ver e enviar avaliações |
| GET | `/api/servicos` | Lista de serviços (JSON) |
| GET | `/api/horarios?data=AAAA-MM-DD&servico_id=1` | Horários livres (JSON) |
| POST | `/api/agendamentos` | Criar agendamento (JSON) |
| GET | `/admin/` | Painel: agenda do dia |
| — | `/admin/servicos`, `/admin/horarios`, `/admin/clientes`, `/admin/avaliacoes` | Gestão |

Exemplo de `POST /api/agendamentos` (precisa do cabeçalho `X-CSRF-Token`, que o site já envia):

```json
{ "nome": "João", "telefone": "(11) 91234-5678", "servico_id": 1, "data": "2026-11-20", "hora": "10:00" }
```

## 🌍 Publicando na Render

1. Faça push do projeto para o GitHub.
2. Na Render: **New + → Blueprint** → escolha este repositório. O `render.yaml` cria o PostgreSQL e o serviço web.
3. Informe a `ADMIN_SENHA` quando a Render pedir e ajuste nome, endereço, telefone e WhatsApp da barbearia nas variáveis de ambiente.

### 🔐 Cuidados
- O `.env` está no `.gitignore` — nunca envie senhas para o GitHub.
- Em produção, `SECRET_KEY` é gerada pela Render e o banco é PostgreSQL.

## ✏️ Personalizando para o barbeiro

- **Nome, endereço, telefone, WhatsApp, Instagram:** variáveis `BARBEARIA_*` no `.env`.
- **Serviços, preços e horários:** pelo próprio painel `/admin` (ou em `popular_dados_iniciais`, em `app/__init__.py`).
- **Texto "Nossa história":** `app/templates/sobre.html`.
- **Cores:** variáveis no topo de `app/static/css/style.css`.

## 👥 Colaboração

Sugestão de fluxo: cada integrante cria uma branch (`git checkout -b minha-parte`), faz suas alterações, envia (`git push -u origin minha-parte`) e abre um Pull Request no GitHub.

---

<p align="center">
  Desenvolvido como projeto acadêmico de Análise e Desenvolvimento de Sistemas.
</p>
