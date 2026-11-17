import secrets
from datetime import datetime, time
from decimal import Decimal
from zoneinfo import ZoneInfo

from . import db

def agora_local():
    """Hora de Brasília: o servidor da Render roda em UTC."""
    return datetime.now(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)


DIAS_SEMANA = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]


class Cliente(db.Model):
    __tablename__ = "clientes"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    # Somente dígitos, com DDD. É a "chave" do cliente: quem agenda com o mesmo
    # telefone é reconhecido como o mesmo cliente.
    telefone = db.Column(db.String(20), nullable=False, unique=True, index=True)
    email = db.Column(db.String(120))
    criado_em = db.Column(db.DateTime, nullable=False, default=agora_local)

    agendamentos = db.relationship("Agendamento", back_populates="cliente", lazy="dynamic")

    @property
    def telefone_formatado(self):
        t = self.telefone
        if len(t) == 11:
            return f"({t[:2]}) {t[2:7]}-{t[7:]}"
        if len(t) == 10:
            return f"({t[:2]}) {t[2:6]}-{t[6:]}"
        return t


class Servico(db.Model):
    __tablename__ = "servicos"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), nullable=False)
    descricao = db.Column(db.String(255), default="")
    preco = db.Column(db.Numeric(10, 2), nullable=False)
    duracao_minutos = db.Column(db.Integer, nullable=False)
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    ordem = db.Column(db.Integer, nullable=False, default=0)

    agendamentos = db.relationship("Agendamento", back_populates="servico", lazy="dynamic")

    def to_dict(self):
        return {
            "id": self.id,
            "nome": self.nome,
            "descricao": self.descricao,
            "preco": float(self.preco),
            "preco_formatado": formatar_moeda(self.preco),
            "duracao_minutos": self.duracao_minutos,
        }


class HorarioFuncionamento(db.Model):
    """Um registro por dia da semana (0 = segunda ... 6 = domingo)."""

    __tablename__ = "horarios_funcionamento"

    id = db.Column(db.Integer, primary_key=True)
    dia_semana = db.Column(db.Integer, nullable=False, unique=True)
    aberto = db.Column(db.Boolean, nullable=False, default=True)
    abertura = db.Column(db.Time, nullable=False, default=time(9, 0))
    fechamento = db.Column(db.Time, nullable=False, default=time(19, 0))
    # Pausa opcional (ex.: almoço)
    pausa_inicio = db.Column(db.Time)
    pausa_fim = db.Column(db.Time)

    @property
    def nome_dia(self):
        return DIAS_SEMANA[self.dia_semana]


class DiaBloqueado(db.Model):
    """Feriados, folgas e outros dias em que a barbearia não atende."""

    __tablename__ = "dias_bloqueados"

    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.Date, nullable=False, unique=True)
    motivo = db.Column(db.String(120), default="")


class Agendamento(db.Model):
    __tablename__ = "agendamentos"

    STATUS = {
        "confirmado": "Confirmado",
        "concluido": "Concluído",
        "cancelado": "Cancelado",
        "faltou": "Não compareceu",
    }
    # Status que ocupam a agenda (impedem outro agendamento no mesmo horário)
    STATUS_ATIVOS = ("confirmado", "concluido")

    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(16), nullable=False, unique=True, index=True,
                       default=lambda: secrets.token_urlsafe(8))
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=False)
    servico_id = db.Column(db.Integer, db.ForeignKey("servicos.id"), nullable=False)
    inicio = db.Column(db.DateTime, nullable=False, index=True)
    fim = db.Column(db.DateTime, nullable=False)
    # Preço "congelado" no momento do agendamento: se o barbeiro mudar o preço
    # do serviço depois, o histórico continua correto.
    preco = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="confirmado", index=True)
    observacao = db.Column(db.String(255), default="")
    criado_em = db.Column(db.DateTime, nullable=False, default=agora_local)

    cliente = db.relationship("Cliente", back_populates="agendamentos")
    servico = db.relationship("Servico", back_populates="agendamentos")

    @property
    def status_label(self):
        return self.STATUS.get(self.status, self.status)

    def to_dict(self):
        return {
            "id": self.id,
            "codigo": self.codigo,
            "cliente": self.cliente.nome,
            "servico": self.servico.nome,
            "inicio": self.inicio.isoformat(timespec="minutes"),
            "fim": self.fim.isoformat(timespec="minutes"),
            "preco": float(self.preco),
            "status": self.status,
        }


class Avaliacao(db.Model):
    __tablename__ = "avaliacoes"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), nullable=False)
    nota = db.Column(db.Integer, nullable=False)
    comentario = db.Column(db.Text, nullable=False)
    visivel = db.Column(db.Boolean, nullable=False, default=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=agora_local)
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"))

    __table_args__ = (db.CheckConstraint("nota BETWEEN 1 AND 5", name="ck_avaliacao_nota"),)


def formatar_moeda(valor):
    valor = Decimal(valor or 0).quantize(Decimal("0.01"))
    inteiro, centavos = f"{valor:.2f}".split(".")
    inteiro = f"{int(inteiro):,}".replace(",", ".")
    return f"R$ {inteiro},{centavos}"
