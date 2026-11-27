import secrets
from datetime import time

import click
from dotenv import load_dotenv

# Carrega o .env ANTES de importar a configuração
load_dotenv()

from flask import Flask, abort, request, session  # noqa: E402
from flask_migrate import Migrate  # noqa: E402
from flask_sqlalchemy import SQLAlchemy  # noqa: E402

from .config import Config  # noqa: E402

db = SQLAlchemy()
migrate = Migrate()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)

    from . import models  # noqa: F401  (registra as tabelas)
    from .admin import admin_bp
    from .routes import api_bp, main_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    _configurar_csrf(app)
    _configurar_templates(app)
    _registrar_comandos(app)

    with app.app_context():
        # Cria as tabelas que ainda não existem (prático para o projeto acadêmico).
        # Se o grupo passar a usar migrações, rode "flask db init/migrate/upgrade".
        db.create_all()
        if not app.testing:
            _popular_se_vazio()

    return app


def _configurar_csrf(app):
    """Proteção simples contra CSRF: todo POST precisa enviar o token da sessão,
    no campo "csrf_token" (formulários) ou no cabeçalho "X-CSRF-Token" (fetch/JS)."""

    def gerar_token():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(32)
        return session["csrf_token"]

    @app.before_request
    def verificar_csrf():
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            enviado = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
            esperado = session.get("csrf_token")
            if not esperado or not enviado or not secrets.compare_digest(enviado, esperado):
                abort(400, description="Sessão expirada. Recarregue a página e tente novamente.")

    app.jinja_env.globals["csrf_token"] = gerar_token


def _configurar_templates(app):
    from .models import DIAS_SEMANA, formatar_moeda

    app.jinja_env.filters["moeda"] = formatar_moeda
    app.jinja_env.filters["data_br"] = lambda d: d.strftime("%d/%m/%Y") if d else ""
    app.jinja_env.filters["hora"] = lambda d: d.strftime("%H:%M") if d else ""
    app.jinja_env.filters["dia_semana"] = lambda d: DIAS_SEMANA[d.weekday()] if d else ""

    @app.context_processor
    def dados_globais():
        from .agenda import agora

        return {"barbearia": app.config["BARBEARIA"], "ano_atual": agora().year}

    @app.errorhandler(404)
    def nao_encontrado(e):
        from flask import render_template

        return render_template("erro.html", codigo=404, mensagem="Página não encontrada."), 404

    @app.errorhandler(400)
    def requisicao_invalida(e):
        from flask import jsonify, render_template

        if request.path.startswith("/api/"):
            return jsonify(erro=e.description), 400
        return render_template("erro.html", codigo=400, mensagem=e.description), 400


def _popular_se_vazio():
    from .models import Servico

    if db.session.query(Servico).count() == 0:
        # Sem avaliações de exemplo: num site público elas pareceriam opiniões reais
        popular_dados_iniciais(com_exemplos=False)


def popular_dados_iniciais(com_exemplos=True):
    """Serviços, horário de funcionamento e algumas avaliações de exemplo.
    Edite à vontade para refletir a barbearia real."""
    from .models import Avaliacao, HorarioFuncionamento, Servico

    if db.session.query(Servico).count() == 0:
        # Serviços e preços da Charme Chave (duração estimada; ajuste pelo painel se precisar)
        servicos = [
            ("Corte degradê", "Degradê na máquina com acabamento na navalha.", "40.00", 30),
            ("Corte degradê e sobrancelha", "Degradê com sobrancelha alinhada na navalha.", "45.00", 40),
            ("Corte e escova", "Corte com escova e finalização.", "50.00", 45),
            ("Corte e pigmentação", "Corte com pigmentação para destacar o desenho.", "50.00", 60),
            ("Corte e penteado", "Corte com penteado para ocasiões especiais.", "70.00", 60),
            ("Corte e barba", "Corte completo com barba modelada.", "70.00", 60),
        ]
        for ordem, (nome, desc, preco, dur) in enumerate(servicos):
            db.session.add(Servico(nome=nome, descricao=desc, preco=preco, duracao_minutos=dur, ordem=ordem))

    if db.session.query(HorarioFuncionamento).count() == 0:
        # Charme Chave: terça a quinta 10h às 20h; sexta e sábado 7h às 20h;
        # domingo e segunda fechado (0 = segunda ... 6 = domingo)
        for dia in range(7):
            if dia in (0, 6):
                db.session.add(HorarioFuncionamento(dia_semana=dia, aberto=False,
                                                    abertura=time(10), fechamento=time(20)))
            elif dia in (4, 5):
                db.session.add(HorarioFuncionamento(dia_semana=dia, abertura=time(7), fechamento=time(20)))
            else:
                db.session.add(HorarioFuncionamento(dia_semana=dia, abertura=time(10), fechamento=time(20)))

    if com_exemplos and db.session.query(Avaliacao).count() == 0:
        exemplos = [
            ("Lucas M.", 5, "Melhor degradê da região, atendimento nota 10!"),
            ("Rafael S.", 5, "Agendei pelo site em 1 minuto e fui atendido no horário certinho."),
            ("Pedro H.", 4, "Ambiente top e preço justo. Só demorou um pouco para estacionar."),
        ]
        for nome, nota, texto in exemplos:
            db.session.add(Avaliacao(nome=nome, nota=nota, comentario=texto))

    db.session.commit()


def _registrar_comandos(app):
    @app.cli.command("seed")
    @click.option("--sem-exemplos", is_flag=True, help="Não cria avaliações de exemplo.")
    def seed(sem_exemplos):
        """Popula o banco com serviços e horários iniciais."""
        popular_dados_iniciais(com_exemplos=not sem_exemplos)
        click.echo("Banco populado.")

    @app.cli.command("reset-db")
    @click.confirmation_option(prompt="Isso APAGA todos os dados. Continuar?")
    def reset_db():
        """Apaga e recria todas as tabelas (somente desenvolvimento)."""
        db.drop_all()
        db.create_all()
        popular_dados_iniciais()
        click.echo("Banco recriado.")
