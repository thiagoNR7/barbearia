// Formulário de agendamento: carrega horários livres e envia o pedido
(function () {
  "use strict";

  const form = document.getElementById("form-agendamento");
  if (!form) return;

  const modoBarbeiro = form.dataset.modoBarbeiro === "sim";
  const urlHorarios = form.dataset.apiHorarios;
  const urlAgendar = form.dataset.apiAgendar;
  const csrf = document.querySelector('meta[name="csrf-token"]').content;

  const campoData = document.getElementById("campo-data");
  const campoHora = document.getElementById("campo-hora");
  const caixaHorarios = document.getElementById("horarios");
  const aviso = document.getElementById("horarios-aviso");
  const caixaErro = document.getElementById("form-erro");
  const botao = document.getElementById("botao-confirmar");

  const resumo = {
    servico: document.getElementById("resumo-servico"),
    duracao: document.getElementById("resumo-duracao"),
    data: document.getElementById("resumo-data"),
    hora: document.getElementById("resumo-hora"),
    preco: document.getElementById("resumo-preco"),
  };

  const DIAS = ["domingo", "segunda", "terça", "quarta", "quinta", "sexta", "sábado"];
  let requisicaoAtual = 0;

  function servicoSelecionado() {
    return form.querySelector('input[name="servico_id"]:checked');
  }

  function formatarData(iso) {
    if (!iso) return "-";
    const [a, m, d] = iso.split("-").map(Number);
    const dt = new Date(a, m - 1, d);
    return DIAS[dt.getDay()] + ", " + String(d).padStart(2, "0") + "/" + String(m).padStart(2, "0");
  }

  function mostrarErro(texto) {
    caixaErro.textContent = texto || "";
    caixaErro.hidden = !texto;
  }

  function atualizarResumo() {
    const s = servicoSelecionado();
    resumo.servico.textContent = s ? s.dataset.nome : "-";
    resumo.duracao.textContent = s ? s.dataset.duracao + " min" : "-";
    resumo.preco.textContent = s ? s.dataset.preco : "-";
    resumo.data.textContent = formatarData(campoData.value);
    resumo.hora.textContent = campoHora.value || "-";
  }

  function escolherHorario(botaoHorario) {
    caixaHorarios.querySelectorAll(".horario").forEach(function (b) {
      b.classList.remove("selecionado");
      b.setAttribute("aria-pressed", "false");
    });
    botaoHorario.classList.add("selecionado");
    botaoHorario.setAttribute("aria-pressed", "true");
    campoHora.value = botaoHorario.dataset.hora;
    mostrarErro("");
    atualizarResumo();
  }

  async function carregarHorarios() {
    const s = servicoSelecionado();
    const horaAnterior = campoHora.value;
    campoHora.value = "";
    caixaHorarios.innerHTML = "";
    atualizarResumo();

    if (!s || !campoData.value) {
      aviso.textContent = "Escolha um serviço e uma data para ver os horários livres.";
      aviso.hidden = false;
      return;
    }

    aviso.textContent = "Carregando horários…";
    aviso.hidden = false;
    const minhaRequisicao = ++requisicaoAtual;

    const params = new URLSearchParams({ data: campoData.value, servico_id: s.value });
    if (modoBarbeiro) params.set("encaixe", "1");

    try {
      const resp = await fetch(urlHorarios + "?" + params.toString(), { headers: { Accept: "application/json" } });
      const dados = await resp.json();
      if (minhaRequisicao !== requisicaoAtual) return; // chegou uma resposta mais nova

      if (!resp.ok) {
        aviso.textContent = dados.erro || "Não foi possível carregar os horários.";
        return;
      }
      if (!dados.horarios.length) {
        aviso.textContent = dados.motivo || "Nenhum horário livre nesse dia.";
        return;
      }

      aviso.hidden = true;
      dados.horarios.forEach(function (hora) {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "horario";
        b.textContent = hora;
        b.dataset.hora = hora;
        b.setAttribute("aria-pressed", "false");
        b.addEventListener("click", function () { escolherHorario(b); });
        caixaHorarios.appendChild(b);
        if (hora === horaAnterior) escolherHorario(b);
      });
    } catch (e) {
      if (minhaRequisicao === requisicaoAtual) {
        aviso.textContent = "Sem conexão com o servidor. Tente novamente.";
      }
    }
  }

  function validar() {
    if (!servicoSelecionado()) return "Escolha um serviço.";
    if (!campoData.value) return "Escolha a data.";
    if (!campoHora.value) return "Escolha um dos horários livres.";
    if (form.nome.value.trim().length < 2) return "Informe o nome.";
    const digitos = form.telefone.value.replace(/\D/g, "");
    if (digitos.length < 10 || digitos.length > 11) return "Informe um telefone com DDD.";
    if (form.email.value && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(form.email.value)) return "E-mail inválido.";
    return null;
  }

  form.addEventListener("change", function (e) {
    if (e.target.name === "servico_id" || e.target === campoData) carregarHorarios();
  });

  form.addEventListener("submit", async function (e) {
    const erro = validar();
    if (erro) {
      e.preventDefault();
      mostrarErro(erro);
      return;
    }
    // No painel, o barbeiro envia o formulário normal (rota do admin aceita encaixes)
    if (modoBarbeiro) return;

    e.preventDefault();
    mostrarErro("");
    botao.disabled = true;
    botao.textContent = "Agendando…";

    const dados = Object.fromEntries(new FormData(form).entries());
    delete dados.csrf_token;

    try {
      const resp = await fetch(urlAgendar, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf, Accept: "application/json" },
        body: JSON.stringify(dados),
      });
      const resposta = await resp.json();
      if (resp.ok) {
        window.location.href = resposta.url;
        return;
      }
      mostrarErro(resposta.erro || "Não foi possível concluir o agendamento.");
      // Se alguém pegou o horário antes, recarrega a lista
      if (resp.status === 422) carregarHorarios();
    } catch (err) {
      mostrarErro("Sem conexão com o servidor. Tente novamente.");
    }
    botao.disabled = false;
    botao.textContent = "Confirmar agendamento";
  });

  // Estado inicial (ex.: veio de "Agendar" em um serviço, ou voltou com erro)
  if (!campoData.value) {
    const hoje = new Date();
    campoData.value = hoje.getFullYear() + "-" + String(hoje.getMonth() + 1).padStart(2, "0") + "-" + String(hoje.getDate()).padStart(2, "0");
  }
  carregarHorarios();
})();
