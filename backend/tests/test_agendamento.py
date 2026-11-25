"""Testes automatizados. Rode dentro da pasta backend:  python -m pytest -v"""
from datetime import datetime

import pytest

import app.agenda as agenda
from app import create_app, db, popular_dados_iniciais
from app.config import TestConfig
from app.models import Agendamento, DiaBloqueado, Servico

# "Agora" fixo: segunda-feira, 16/11/2026, 08:00
AGORA = datetime(2026, 11, 16, 8, 0)
DIA = "2026-11-17"  # terça


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setattr(agenda, "agora", lambda: AGORA)
    aplicacao = create_app(TestConfig)
    with aplicacao.app_context():
        popular_dados_iniciais(com_exemplos=False)
        yield aplicacao
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    c = app.test_client()
    with c.session_transaction() as s:
        s["csrf_token"] = "tok"
    return c


def corte():
    return db.session.query(Servico).filter_by(nome="Corte de cabelo").one()


def agendar(client, hora="10:00", servico=None, telefone="(11) 91234-5678", data=DIA):
    return client.post(
        "/api/agendamentos",
        json={"nome": "João", "telefone": telefone, "servico_id": (servico or corte()).id,
              "data": data, "hora": hora},
        headers={"X-CSRF-Token": "tok"},
    )


def test_paginas_publicas_abrem(client):
    for url in ["/", "/sobre", "/servicos", "/agendamento", "/avaliacoes", "/privacidade", "/api/servicos"]:
        assert client.get(url).status_code == 200, url


def test_horarios_respeitam_expediente_e_pausa(client):
    r = client.get(f"/api/horarios?data={DIA}&servico_id={corte().id}").get_json()
    assert r["horarios"][0] == "09:00"
    assert r["horarios"][-1] == "18:30"          # 18:30 + 30 min = 19:00 (fechamento)
    assert "12:00" not in r["horarios"]          # pausa de almoço
    assert "11:30" in r["horarios"]


def test_servico_longo_nao_invade_pausa(client):
    combo = db.session.query(Servico).filter_by(nome="Corte + Barba").one()  # 60 min
    r = client.get(f"/api/horarios?data={DIA}&servico_id={combo.id}").get_json()
    assert "11:30" not in r["horarios"]          # terminaria 12:30, dentro da pausa
    assert "11:00" in r["horarios"]


def test_agendar_e_impedir_duplicado(client):
    r = agendar(client, "10:00")
    assert r.status_code == 201
    assert client.get(r.get_json()["url"]).status_code == 200

    r2 = agendar(client, "10:00", telefone="11988887777")
    assert r2.status_code == 422
    assert db.session.query(Agendamento).count() == 1


def test_sobreposicao_parcial_bloqueada(client):
    combo = db.session.query(Servico).filter_by(nome="Corte + Barba").one()
    assert agendar(client, "15:00", servico=combo).status_code == 201   # 15:00–16:00
    assert agendar(client, "15:30").status_code == 422                   # cairia no meio
    assert agendar(client, "16:00").status_code == 201


def test_domingo_fechado_e_dia_bloqueado(client):
    assert agendar(client, "10:00", data="2026-11-22").status_code == 422  # domingo
    db.session.add(DiaBloqueado(data=datetime(2026, 11, 18).date(), motivo="Feriado"))
    db.session.commit()
    r = client.get(f"/api/horarios?data=2026-11-18&servico_id={corte().id}").get_json()
    assert r["horarios"] == [] and "Feriado" in r["motivo"]


def test_nao_agenda_no_passado_nem_em_cima_da_hora(client):
    assert agendar(client, "10:00", data="2026-11-15").status_code == 422
    assert agendar(client, "08:00", data="2026-11-16").status_code == 422  # abre às 9, e é "agora"
    r = client.get(f"/api/horarios?data=2026-11-16&servico_id={corte().id}").get_json()
    assert r["horarios"][0] == "09:00"


def test_validacoes_de_dados(client):
    r = client.post("/api/agendamentos", json={"nome": "J", "telefone": "123"},
                    headers={"X-CSRF-Token": "tok"})
    assert r.status_code == 422
    assert agendar(client, telefone="123").status_code == 422


def test_csrf_obrigatorio(client):
    r = client.post("/api/agendamentos", json={})
    assert r.status_code == 400


def test_cancelamento_libera_horario(client):
    codigo = agendar(client, "10:00").get_json()["agendamento"]["codigo"]
    client.post(f"/agendamento/{codigo}/cancelar", data={"csrf_token": "tok"})
    assert db.session.query(Agendamento).one().status == "cancelado"
    assert agendar(client, "10:00").status_code == 201


def test_mesmo_telefone_e_mesmo_cliente(client):
    agendar(client, "10:00", telefone="(11) 91234-5678")
    agendar(client, "11:00", telefone="5511912345678")
    ags = db.session.query(Agendamento).all()
    assert ags[0].cliente_id == ags[1].cliente_id


def test_painel_exige_login(client):
    assert client.get("/admin/").status_code == 302
    r = client.post("/admin/login", data={"usuario": "barbeiro", "senha": "barbeiro123", "csrf_token": "tok"})
    assert r.status_code == 302
    assert client.get("/admin/").status_code == 200
    for url in ["/admin/servicos", "/admin/horarios", "/admin/clientes", "/admin/avaliacoes",
                "/admin/agendamentos/novo"]:
        assert client.get(url).status_code == 200, url


def test_avaliacao(client):
    r = client.post("/avaliacoes", data={"nome": "Ana", "nota": "5", "comentario": "Muito bom!",
                                         "csrf_token": "tok"})
    assert r.status_code == 302
    assert b"Muito bom!" in client.get("/avaliacoes").data
