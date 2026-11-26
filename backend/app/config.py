import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _database_url():
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        instance = BASE_DIR / "instance"
        instance.mkdir(exist_ok=True)
        return f"sqlite:///{instance / 'barbearia.db'}"
    # A Render entrega "postgres://" ou "postgresql://". Indicamos o driver explicitamente
    # (psycopg2, que está no requirements.txt), porque versões novas do SQLAlchemy
    # usam o psycopg 3 como padrão e o deploy falharia.
    for prefixo in ("postgres://", "postgresql://"):
        if url.startswith(prefixo):
            url = "postgresql+psycopg2://" + url[len(prefixo):]
    return url


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-chave-insegura-troque-em-producao")
    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    ADMIN_USUARIO = os.getenv("ADMIN_USUARIO", "barbeiro")
    ADMIN_SENHA = os.getenv("ADMIN_SENHA", "barbeiro123")

    FUSO_HORARIO = "America/Sao_Paulo"
    # Intervalo entre horários oferecidos no agendamento (minutos)
    INTERVALO_MINUTOS = 30
    # Até quantos dias à frente o cliente pode agendar
    DIAS_ANTECEDENCIA_MAX = 30
    # Antecedência mínima para agendar (minutos)
    ANTECEDENCIA_MIN_MINUTOS = 30

    BARBEARIA = {
        "nome": os.getenv("BARBEARIA_NOME", "Zangão Barbearia"),
        "endereco": os.getenv("BARBEARIA_ENDERECO", "Rua das Colmeias, 120 - Vila Mel, São Paulo - SP"),
        "telefone": os.getenv("BARBEARIA_TELEFONE", "(11) 95235-3041"),
        "whatsapp": os.getenv("BARBEARIA_WHATSAPP", "5511952353041"),
        # Deixe vazio para não exibir link de Instagram
        "instagram": os.getenv("BARBEARIA_INSTAGRAM", ""),
        # "1" = mostra no rodapé que a barbearia é fictícia (projeto acadêmico)
        "ficticia": os.getenv("BARBEARIA_FICTICIA", "1") == "1",
    }


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SECRET_KEY = "teste"
    ADMIN_USUARIO = "barbeiro"
    ADMIN_SENHA = "barbeiro123"
