"""Painel do barbeiro: agenda do dia, serviços, horários, avaliações e clientes."""
import hmac
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from functools import wraps

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from sqlalchemy import func, select

from . import db
from .agenda import AgendaErro, criar_agendamento, hoje
from .models import (
    Agendamento,
    Avaliacao,
    Cliente,
    DiaBloqueado,
    HorarioFuncionamento,
    Servico,
)

admin_bp = Blueprint("admin", __name__)


def login_obrigatorio(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin.login", proximo=request.path))
        return view(*args, **kwargs)

    return wrapper


def _ler_data(texto, padrao=None):
    try:
        return date.fromisoformat(texto)
    except (TypeError, ValueError):
        return padrao


def _ler_hora(texto):
    try:
        return time.fromisoformat(texto) if texto else None
    except ValueError:
        return None


# --------------------------------------------------------------------------
# Login
# --------------------------------------------------------------------------

@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form.get("usuario", "")
        senha = request.form.get("senha", "")
        ok_usuario = hmac.compare_digest(usuario.encode(), current_app.config["ADMIN_USUARIO"].encode())
        ok_senha = hmac.compare_digest(senha.encode(), current_app.config["ADMIN_SENHA"].encode())
        if ok_usuario and ok_senha:
            csrf = session.get("csrf_token")
            session.clear()  # evita fixação de sessão
            if csrf:
                session["csrf_token"] = csrf
            session["admin"] = True
            proximo = request.args.get("proximo", "")
            # Só redireciona para caminhos internos do painel
            if not proximo.startswith("/admin"):
                proximo = url_for("admin.painel")
            return redirect(proximo)
        flash("Usuário ou senha incorretos.", "erro")
    return render_template("admin/login.html")


@admin_bp.post("/logout")
def logout():
    session.pop("admin", None)
    return redirect(url_for("main.index"))


# --------------------------------------------------------------------------
# Agenda
# --------------------------------------------------------------------------

@admin_bp.route("/")
@login_obrigatorio
def painel():
    dia = _ler_data(request.args.get("data"), hoje())
    inicio_dia = datetime.combine(dia, time.min)
    agendamentos = db.session.scalars(
        select(Agendamento)
        .where(Agendamento.inicio >= inicio_dia, Agendamento.inicio < inicio_dia + timedelta(days=1))
        .order_by(Agendamento.inicio)
    ).all()

    # Indicadores
    hoje_ = hoje()
    inicio_mes = datetime.combine(hoje_.replace(day=1), time.min)
    proximo_mes = (inicio_mes.replace(day=28) + timedelta(days=4)).replace(day=1)
    inicio_hoje = datetime.combine(hoje_, time.min)

    def soma(*filtros):
        return db.session.scalar(select(func.coalesce(func.sum(Agendamento.preco), 0)).where(*filtros)) or 0

    def conta(*filtros):
        return db.session.scalar(select(func.count(Agendamento.id)).where(*filtros)) or 0

    no_mes = (Agendamento.inicio >= inicio_mes, Agendamento.inicio < proximo_mes)
    indicadores = {
        "hoje": conta(Agendamento.inicio >= inicio_hoje, Agendamento.inicio < inicio_hoje + timedelta(days=1),
                      Agendamento.status.in_(Agendamento.STATUS_ATIVOS)),
        "semana": conta(Agendamento.inicio >= inicio_hoje, Agendamento.inicio < inicio_hoje + timedelta(days=7),
                        Agendamento.status == "confirmado"),
        "faturado_mes": soma(*no_mes, Agendamento.status == "concluido"),
        "previsto_mes": soma(*no_mes, Agendamento.status.in_(Agendamento.STATUS_ATIVOS)),
    }

    return render_template(
        "admin/painel.html",
        dia=dia,
        dia_anterior=dia - timedelta(days=1),
        dia_seguinte=dia + timedelta(days=1),
        agendamentos=agendamentos,
        indicadores=indicadores,
        status=Agendamento.STATUS,
        bloqueio=db.session.scalar(select(DiaBloqueado).filter_by(data=dia)),
    )


@admin_bp.post("/agendamentos/<int:ag_id>/status")
@login_obrigatorio
def mudar_status(ag_id):
    ag = db.get_or_404(Agendamento, ag_id)
    novo = request.form.get("status")
    if novo not in Agendamento.STATUS:
        flash("Status inválido.", "erro")
    elif novo in Agendamento.STATUS_ATIVOS and ag.status not in Agendamento.STATUS_ATIVOS:
        # Reativar um cancelado: confere se o horário continua livre
        conflito = db.session.scalar(
            select(Agendamento).where(
                Agendamento.id != ag.id,
                Agendamento.status.in_(Agendamento.STATUS_ATIVOS),
                Agendamento.inicio < ag.fim,
                Agendamento.fim > ag.inicio,
            )
        )
        if conflito:
            flash(f"Não dá para reativar: o horário já está ocupado por {conflito.cliente.nome}.", "erro")
        else:
            ag.status = novo
            db.session.commit()
            flash("Status atualizado.", "ok")
    else:
        ag.status = novo
        db.session.commit()
        flash("Status atualizado.", "ok")
    return redirect(url_for("admin.painel", data=ag.inicio.date().isoformat()))


@admin_bp.route("/agendamentos/novo", methods=["GET", "POST"])
@login_obrigatorio
def novo_agendamento():
    """Para o barbeiro registrar quem marcou por telefone/WhatsApp ou chegou na hora."""
    servicos = db.session.scalars(select(Servico).filter_by(ativo=True).order_by(Servico.ordem)).all()
    form = request.form if request.method == "POST" else {"data": request.args.get("data", hoje().isoformat())}
    if request.method == "POST":
        try:
            ag = criar_agendamento(request.form, pelo_barbeiro=True)
        except AgendaErro as erro:
            db.session.rollback()
            flash(str(erro), "erro")
        else:
            flash(f"Agendamento de {ag.cliente.nome} registrado.", "ok")
            return redirect(url_for("admin.painel", data=ag.inicio.date().isoformat()))
    return render_template("admin/novo_agendamento.html", servicos=servicos, form=form, hoje=hoje())


# --------------------------------------------------------------------------
# Serviços
# --------------------------------------------------------------------------

def _dados_servico(form):
    nome = (form.get("nome") or "").strip()
    descricao = (form.get("descricao") or "").strip()[:255]
    try:
        preco = Decimal((form.get("preco") or "").replace(",", ".")).quantize(Decimal("0.01"))
        duracao = int(form.get("duracao_minutos") or 0)
        ordem = int(form.get("ordem") or 0)
    except (InvalidOperation, ValueError):
        return None, "Preço, duração e ordem precisam ser números."
    if not nome:
        return None, "Informe o nome do serviço."
    if preco < 0:
        return None, "O preço não pode ser negativo."
    if not 5 <= duracao <= 480:
        return None, "A duração deve ficar entre 5 e 480 minutos."
    return {"nome": nome[:80], "descricao": descricao, "preco": preco,
            "duracao_minutos": duracao, "ordem": ordem}, None


@admin_bp.route("/servicos", methods=["GET", "POST"])
@login_obrigatorio
def servicos():
    if request.method == "POST":
        dados, erro = _dados_servico(request.form)
        if erro:
            flash(erro, "erro")
        else:
            db.session.add(Servico(**dados))
            db.session.commit()
            flash("Serviço criado.", "ok")
        return redirect(url_for("admin.servicos"))
    lista = db.session.scalars(select(Servico).order_by(Servico.ativo.desc(), Servico.ordem, Servico.nome)).all()
    return render_template("admin/servicos.html", servicos=lista)


@admin_bp.post("/servicos/<int:servico_id>")
@login_obrigatorio
def editar_servico(servico_id):
    servico = db.get_or_404(Servico, servico_id)
    dados, erro = _dados_servico(request.form)
    if erro:
        flash(erro, "erro")
    else:
        for campo, valor in dados.items():
            setattr(servico, campo, valor)
        db.session.commit()
        flash(f"“{servico.nome}” atualizado. Agendamentos já feitos mantêm o preço antigo.", "ok")
    return redirect(url_for("admin.servicos"))


@admin_bp.post("/servicos/<int:servico_id>/alternar")
@login_obrigatorio
def alternar_servico(servico_id):
    servico = db.get_or_404(Servico, servico_id)
    servico.ativo = not servico.ativo
    db.session.commit()
    flash(f"“{servico.nome}” {'ativado' if servico.ativo else 'desativado (não aparece mais no site)'}.", "ok")
    return redirect(url_for("admin.servicos"))


# --------------------------------------------------------------------------
# Horários de funcionamento e dias bloqueados
# --------------------------------------------------------------------------

@admin_bp.route("/horarios", methods=["GET", "POST"])
@login_obrigatorio
def horarios():
    expedientes = db.session.scalars(
        select(HorarioFuncionamento).order_by(HorarioFuncionamento.dia_semana)
    ).all()

    if request.method == "POST":
        erros = []
        for h in expedientes:
            p = f"d{h.dia_semana}_"
            aberto = request.form.get(p + "aberto") == "on"
            abertura = _ler_hora(request.form.get(p + "abertura"))
            fechamento = _ler_hora(request.form.get(p + "fechamento"))
            pausa_i = _ler_hora(request.form.get(p + "pausa_inicio"))
            pausa_f = _ler_hora(request.form.get(p + "pausa_fim"))
            if aberto:
                if not abertura or not fechamento or abertura >= fechamento:
                    erros.append(f"{h.nome_dia}: a abertura precisa ser antes do fechamento.")
                    continue
                if bool(pausa_i) != bool(pausa_f) or (pausa_i and not (abertura <= pausa_i < pausa_f <= fechamento)):
                    erros.append(f"{h.nome_dia}: a pausa precisa ter início e fim dentro do expediente.")
                    continue
            h.aberto = aberto
            if abertura and fechamento:
                h.abertura, h.fechamento = abertura, fechamento
            h.pausa_inicio, h.pausa_fim = pausa_i, pausa_f
        db.session.commit()
        for e in erros:
            flash(e, "erro")
        if not erros:
            flash("Horários salvos.", "ok")
        return redirect(url_for("admin.horarios"))

    bloqueios = db.session.scalars(
        select(DiaBloqueado).where(DiaBloqueado.data >= hoje()).order_by(DiaBloqueado.data)
    ).all()
    return render_template("admin/horarios.html", expedientes=expedientes, bloqueios=bloqueios, hoje=hoje())


@admin_bp.post("/bloqueios")
@login_obrigatorio
def adicionar_bloqueio():
    dia = _ler_data(request.form.get("data"))
    motivo = (request.form.get("motivo") or "").strip()[:120]
    if not dia or dia < hoje():
        flash("Escolha uma data futura.", "erro")
    elif db.session.scalar(select(DiaBloqueado).filter_by(data=dia)):
        flash("Esse dia já está bloqueado.", "erro")
    else:
        db.session.add(DiaBloqueado(data=dia, motivo=motivo))
        db.session.commit()
        inicio = datetime.combine(dia, time.min)
        afetados = db.session.scalar(
            select(func.count(Agendamento.id)).where(
                Agendamento.inicio >= inicio,
                Agendamento.inicio < inicio + timedelta(days=1),
                Agendamento.status == "confirmado",
            )
        )
        msg = f"Dia {dia.strftime('%d/%m/%Y')} bloqueado."
        if afetados:
            msg += f" Atenção: já existem {afetados} agendamento(s) nesse dia. Avise os clientes."
        flash(msg, "ok")
    return redirect(url_for("admin.horarios"))


@admin_bp.post("/bloqueios/<int:bloqueio_id>/remover")
@login_obrigatorio
def remover_bloqueio(bloqueio_id):
    db.session.delete(db.get_or_404(DiaBloqueado, bloqueio_id))
    db.session.commit()
    flash("Bloqueio removido.", "ok")
    return redirect(url_for("admin.horarios"))


# --------------------------------------------------------------------------
# Avaliações
# --------------------------------------------------------------------------

@admin_bp.route("/avaliacoes")
@login_obrigatorio
def avaliacoes():
    lista = db.session.scalars(select(Avaliacao).order_by(Avaliacao.criado_em.desc())).all()
    return render_template("admin/avaliacoes.html", avaliacoes=lista)


@admin_bp.post("/avaliacoes/<int:av_id>/alternar")
@login_obrigatorio
def alternar_avaliacao(av_id):
    av = db.get_or_404(Avaliacao, av_id)
    av.visivel = not av.visivel
    db.session.commit()
    flash("Avaliação " + ("publicada." if av.visivel else "ocultada do site."), "ok")
    return redirect(url_for("admin.avaliacoes"))


@admin_bp.post("/avaliacoes/<int:av_id>/excluir")
@login_obrigatorio
def excluir_avaliacao(av_id):
    db.session.delete(db.get_or_404(Avaliacao, av_id))
    db.session.commit()
    flash("Avaliação excluída.", "ok")
    return redirect(url_for("admin.avaliacoes"))


# --------------------------------------------------------------------------
# Clientes
# --------------------------------------------------------------------------

@admin_bp.route("/clientes")
@login_obrigatorio
def clientes():
    busca = (request.args.get("q") or "").strip()
    visitas = func.count(Agendamento.id).filter(Agendamento.status == "concluido")
    consulta = (
        select(Cliente, visitas.label("visitas"), func.max(Agendamento.inicio).label("ultimo"))
        .outerjoin(Agendamento)
        .group_by(Cliente.id)
        .order_by(Cliente.nome)
    )
    if busca:
        digitos = "".join(c for c in busca if c.isdigit())
        filtro = Cliente.nome.ilike(f"%{busca}%")
        if digitos:
            filtro = filtro | Cliente.telefone.contains(digitos)
        consulta = consulta.where(filtro)
    linhas = db.session.execute(consulta).all()
    return render_template("admin/clientes.html", linhas=linhas, busca=busca)
