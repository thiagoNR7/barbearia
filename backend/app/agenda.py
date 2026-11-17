"""Regras de negócio da agenda: horários livres, validação e criação de agendamentos.

Fica separado das rotas para que o site (formulário) e a API usem exatamente
as mesmas regras.
"""
import re
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from flask import current_app
from sqlalchemy import select

from . import db
from .models import Agendamento, Cliente, DiaBloqueado, HorarioFuncionamento, Servico


class AgendaErro(Exception):
    """Erro de validação que pode ser mostrado ao cliente."""


def agora():
    """Data/hora atual no fuso da barbearia (sem tzinfo, igual ao que fica no banco)."""
    fuso = ZoneInfo(current_app.config["FUSO_HORARIO"])
    return datetime.now(fuso).replace(tzinfo=None, second=0, microsecond=0)


def hoje():
    return agora().date()


def normalizar_telefone(telefone):
    digitos = re.sub(r"\D", "", telefone or "")
    if len(digitos) in (12, 13) and digitos.startswith("55"):
        digitos = digitos[2:]
    if len(digitos) not in (10, 11):
        raise AgendaErro("Informe um telefone válido com DDD.")
    return digitos


def _sobrepoe(inicio_a, fim_a, inicio_b, fim_b):
    return inicio_a < fim_b and inicio_b < fim_a


def motivo_dia_fechado(dia):
    """Retorna um texto explicando por que não há horários no dia, ou None se o dia é válido."""
    limite = hoje() + timedelta(days=current_app.config["DIAS_ANTECEDENCIA_MAX"])
    if dia < hoje():
        return "Essa data já passou."
    if dia > limite:
        return f"Só é possível agendar até {limite.strftime('%d/%m/%Y')}."
    bloqueio = db.session.scalar(select(DiaBloqueado).filter_by(data=dia))
    if bloqueio:
        return f"Não haverá atendimento nesse dia{': ' + bloqueio.motivo if bloqueio.motivo else ''}."
    expediente = db.session.scalar(select(HorarioFuncionamento).filter_by(dia_semana=dia.weekday()))
    if not expediente or not expediente.aberto:
        return "A barbearia não abre nesse dia da semana."
    return None


def horarios_disponiveis(dia, servico, ignorar_agendamento_id=None, pelo_barbeiro=False):
    """Lista de horários (datetime) em que o serviço cabe inteiro, sem conflito.

    `pelo_barbeiro=True` dispensa a antecedência mínima (para registrar encaixes na hora)."""
    if motivo_dia_fechado(dia):
        return []

    expediente = db.session.scalar(select(HorarioFuncionamento).filter_by(dia_semana=dia.weekday()))
    duracao = timedelta(minutes=servico.duracao_minutos)
    passo = timedelta(minutes=current_app.config["INTERVALO_MINUTOS"])
    antecedencia = 0 if pelo_barbeiro else current_app.config["ANTECEDENCIA_MIN_MINUTOS"]
    minimo = agora() + timedelta(minutes=antecedencia)

    abertura = datetime.combine(dia, expediente.abertura)
    fechamento = datetime.combine(dia, expediente.fechamento)
    pausa = None
    if expediente.pausa_inicio and expediente.pausa_fim:
        pausa = (datetime.combine(dia, expediente.pausa_inicio), datetime.combine(dia, expediente.pausa_fim))

    consulta = select(Agendamento).where(
        Agendamento.status.in_(Agendamento.STATUS_ATIVOS),
        Agendamento.inicio < fechamento,
        Agendamento.fim > abertura,
    )
    if ignorar_agendamento_id:
        consulta = consulta.where(Agendamento.id != ignorar_agendamento_id)
    ocupados = [(a.inicio, a.fim) for a in db.session.scalars(consulta)]

    livres = []
    inicio = abertura
    while inicio + duracao <= fechamento:
        fim = inicio + duracao
        conflito = (
            inicio < minimo
            or (pausa and _sobrepoe(inicio, fim, *pausa))
            or any(_sobrepoe(inicio, fim, oi, of) for oi, of in ocupados)
        )
        if not conflito:
            livres.append(inicio)
        inicio += passo
    return livres


def _ler_data(texto):
    try:
        return date.fromisoformat(texto)
    except (TypeError, ValueError):
        raise AgendaErro("Data inválida.")


def _ler_hora(texto):
    try:
        return time.fromisoformat(texto)
    except (TypeError, ValueError):
        raise AgendaErro("Horário inválido.")


def buscar_servico_ativo(servico_id):
    try:
        servico = db.session.get(Servico, int(servico_id))
    except (TypeError, ValueError):
        servico = None
    if not servico or not servico.ativo:
        raise AgendaErro("Escolha um serviço válido.")
    return servico


def criar_agendamento(dados, pelo_barbeiro=False):
    """Valida os dados recebidos (do formulário ou da API) e grava o agendamento.

    `dados` é um dict com: nome, telefone, email (opcional), servico_id, data (AAAA-MM-DD),
    hora (HH:MM) e observacao (opcional). Lança AgendaErro com a mensagem para o usuário.
    """
    nome = (dados.get("nome") or "").strip()
    if len(nome) < 2:
        raise AgendaErro("Informe seu nome.")
    if len(nome) > 120:
        raise AgendaErro("Nome muito longo.")
    telefone = normalizar_telefone(dados.get("telefone"))
    email = (dados.get("email") or "").strip()[:120]
    if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise AgendaErro("E-mail inválido.")
    observacao = (dados.get("observacao") or "").strip()[:255]

    servico = buscar_servico_ativo(dados.get("servico_id"))
    dia = _ler_data(dados.get("data"))
    inicio = datetime.combine(dia, _ler_hora(dados.get("hora")))

    # Trava a linha do expediente do dia: em PostgreSQL isso faz dois pedidos
    # simultâneos para o mesmo dia esperarem um pelo outro, evitando que ambos
    # vejam o horário como livre (o SQLite já serializa as escritas sozinho).
    db.session.execute(
        select(HorarioFuncionamento).filter_by(dia_semana=dia.weekday()).with_for_update()
    )

    motivo = motivo_dia_fechado(dia)
    if motivo:
        raise AgendaErro(motivo)
    if inicio not in horarios_disponiveis(dia, servico, pelo_barbeiro=pelo_barbeiro):
        raise AgendaErro("Esse horário não está mais disponível. Escolha outro.")

    cliente = db.session.scalar(select(Cliente).filter_by(telefone=telefone))
    if cliente is None:
        cliente = Cliente(nome=nome, telefone=telefone, email=email or None)
        db.session.add(cliente)
    else:
        cliente.nome = nome
        if email:
            cliente.email = email

    agendamento = Agendamento(
        cliente=cliente,
        servico=servico,
        inicio=inicio,
        fim=inicio + timedelta(minutes=servico.duracao_minutos),
        preco=servico.preco,
        observacao=observacao,
    )
    db.session.add(agendamento)
    db.session.commit()
    return agendamento


def pode_cancelar(agendamento):
    """O cliente pode cancelar sozinho até 2 horas antes."""
    return agendamento.status == "confirmado" and agendamento.inicio - agora() >= timedelta(hours=2)
