from datetime import date

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy import func, select

from . import db
from .agenda import (
    AgendaErro,
    agora,
    buscar_servico_ativo,
    criar_agendamento,
    hoje,
    horarios_disponiveis,
    motivo_dia_fechado,
    pode_cancelar,
)
from .models import Agendamento, Avaliacao, HorarioFuncionamento, Servico

main_bp = Blueprint("main", __name__)
api_bp = Blueprint("api", __name__)


def _servicos_ativos():
    return db.session.scalars(
        select(Servico).filter_by(ativo=True).order_by(Servico.ordem, Servico.nome)
    ).all()


def _resumo_avaliacoes():
    media, total = db.session.execute(
        select(func.avg(Avaliacao.nota), func.count(Avaliacao.id)).filter_by(visivel=True)
    ).one()
    return (round(float(media), 1) if media else None), total


# --------------------------------------------------------------------------
# Páginas
# --------------------------------------------------------------------------

@main_bp.route("/")
def index():
    avaliacoes = db.session.scalars(
        select(Avaliacao).filter_by(visivel=True).order_by(Avaliacao.criado_em.desc()).limit(3)
    ).all()
    media, total = _resumo_avaliacoes()
    return render_template(
        "index.html",
        servicos=_servicos_ativos()[:4],
        avaliacoes=avaliacoes,
        media=media,
        total_avaliacoes=total,
    )


@main_bp.route("/sobre")
def sobre():
    horarios = db.session.scalars(select(HorarioFuncionamento).order_by(HorarioFuncionamento.dia_semana)).all()
    return render_template("sobre.html", horarios=horarios, dia_hoje=hoje().weekday())


@main_bp.route("/servicos")
def servicos():
    return render_template("servicos.html", servicos=_servicos_ativos())


@main_bp.route("/agendamento", methods=["GET", "POST"])
def agendamento():
    """GET mostra o formulário. O JavaScript envia para /api/agendamentos, mas o POST
    aqui funciona como alternativa caso o navegador esteja com JavaScript desativado."""
    if request.method == "POST":
        try:
            novo = criar_agendamento(request.form)
        except AgendaErro as erro:
            db.session.rollback()
            flash(str(erro), "erro")
            return render_template(
                "agendamento.html", servicos=_servicos_ativos(), form=request.form, hoje=hoje()
            ), 422
        return redirect(url_for("main.ver_agendamento", codigo=novo.codigo))

    return render_template(
        "agendamento.html",
        servicos=_servicos_ativos(),
        form={"servico_id": request.args.get("servico", "")},
        hoje=hoje(),
    )


@main_bp.route("/agendamento/<codigo>")
def ver_agendamento(codigo):
    ag = db.session.scalar(select(Agendamento).filter_by(codigo=codigo)) or abort(404)
    return render_template("confirmacao.html", ag=ag, pode_cancelar=pode_cancelar(ag))


@main_bp.post("/agendamento/<codigo>/cancelar")
def cancelar_agendamento(codigo):
    ag = db.session.scalar(select(Agendamento).filter_by(codigo=codigo)) or abort(404)
    if pode_cancelar(ag):
        ag.status = "cancelado"
        db.session.commit()
        flash("Agendamento cancelado. Esperamos você em outra oportunidade!", "ok")
    else:
        flash("Não é mais possível cancelar pelo site. Fale com a barbearia pelo WhatsApp.", "erro")
    return redirect(url_for("main.ver_agendamento", codigo=codigo))


@main_bp.route("/privacidade")
def privacidade():
    return render_template("privacidade.html")


@main_bp.route("/avaliacoes", methods=["GET", "POST"])
def avaliacoes():
    form = {}
    if request.method == "POST":
        form = request.form
        # Campo "site" é invisível: só robôs de spam preenchem
        if form.get("site"):
            return redirect(url_for("main.avaliacoes"))
        nome = (form.get("nome") or "").strip()
        comentario = (form.get("comentario") or "").strip()
        try:
            nota = int(form.get("nota", 0))
        except ValueError:
            nota = 0
        if len(nome) < 2 or len(nome) > 80:
            flash("Informe seu nome (até 80 caracteres).", "erro")
        elif not 1 <= nota <= 5:
            flash("Escolha uma nota de 1 a 5 estrelas.", "erro")
        elif len(comentario) < 5 or len(comentario) > 1000:
            flash("Escreva um comentário entre 5 e 1000 caracteres.", "erro")
        else:
            db.session.add(Avaliacao(nome=nome, nota=nota, comentario=comentario))
            db.session.commit()
            flash("Obrigado pela sua avaliação!", "ok")
            return redirect(url_for("main.avaliacoes"))

    lista = db.session.scalars(
        select(Avaliacao).filter_by(visivel=True).order_by(Avaliacao.criado_em.desc())
    ).all()
    media, total = _resumo_avaliacoes()
    return render_template("avaliacoes.html", avaliacoes=lista, media=media, total=total, form=form)


# --------------------------------------------------------------------------
# API (JSON)
# --------------------------------------------------------------------------

@api_bp.get("/servicos")
def api_servicos():
    return jsonify([s.to_dict() for s in _servicos_ativos()])


@api_bp.get("/horarios")
def api_horarios():
    """Horários livres de um dia para um serviço. Ex.: /api/horarios?data=2026-11-20&servico_id=1"""
    try:
        servico = buscar_servico_ativo(request.args.get("servico_id"))
        dia = date.fromisoformat(request.args.get("data", ""))
    except AgendaErro as erro:
        return jsonify(erro=str(erro)), 400
    except ValueError:
        return jsonify(erro="Data inválida."), 400

    # O painel do barbeiro pede "encaixe=1" para ver também horários em cima da hora
    pelo_barbeiro = bool(request.args.get("encaixe")) and bool(session.get("admin"))
    horarios = [h.strftime("%H:%M") for h in horarios_disponiveis(dia, servico, pelo_barbeiro=pelo_barbeiro)]
    motivo = motivo_dia_fechado(dia)
    if not horarios and not motivo:
        motivo = "Todos os horários desse dia já foram preenchidos."
    return jsonify(data=dia.isoformat(), servico_id=servico.id, horarios=horarios, motivo=motivo)


@api_bp.post("/agendamentos")
def api_criar_agendamento():
    dados = request.get_json(silent=True) or {}
    try:
        novo = criar_agendamento(dados)
    except AgendaErro as erro:
        db.session.rollback()
        return jsonify(erro=str(erro)), 422
    return jsonify(
        agendamento=novo.to_dict(),
        url=url_for("main.ver_agendamento", codigo=novo.codigo),
    ), 201


@api_bp.get("/status")
def api_status():
    return jsonify(ok=True, horario_servidor=agora().isoformat(timespec="minutes"))
