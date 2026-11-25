// Comportamentos usados em todas as páginas
(function () {
  "use strict";

  // Menu do celular
  const botaoMenu = document.querySelector(".nav__menu");
  const menu = document.getElementById("menu");
  if (botaoMenu && menu) {
    botaoMenu.addEventListener("click", function () {
      const aberto = menu.classList.toggle("aberto");
      botaoMenu.setAttribute("aria-expanded", String(aberto));
    });
  }

  // Mensagens de sucesso somem sozinhas depois de alguns segundos
  document.querySelectorAll(".mensagem--ok").forEach(function (el) {
    setTimeout(function () {
      el.style.opacity = "0";
      setTimeout(function () { el.remove(); }, 400);
    }, 5000);
  });

  // Pede confirmação antes de enviar formulários marcados com data-confirmar
  document.querySelectorAll("form[data-confirmar]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      if (!window.confirm(form.dataset.confirmar)) e.preventDefault();
    });
  });

  // Máscara de telefone: (11) 91234-5678
  function mascararTelefone(valor) {
    const d = valor.replace(/\D/g, "").slice(0, 11);
    if (d.length <= 2) return d.length ? "(" + d : "";
    if (d.length <= 6) return "(" + d.slice(0, 2) + ") " + d.slice(2);
    if (d.length <= 10) return "(" + d.slice(0, 2) + ") " + d.slice(2, 6) + "-" + d.slice(6);
    return "(" + d.slice(0, 2) + ") " + d.slice(2, 7) + "-" + d.slice(7);
  }
  document.querySelectorAll('[data-mascara="telefone"]').forEach(function (input) {
    input.addEventListener("input", function () { input.value = mascararTelefone(input.value); });
    if (input.value) input.value = mascararTelefone(input.value);
  });

  // ------------------------------------------------------------------------
  // Cookies (LGPD): aviso na primeira visita e mapa do Google só com permissão
  // ------------------------------------------------------------------------
  const NOME_COOKIE = "consentimento_cookies";
  const aviso = document.getElementById("aviso-cookies");

  function lerConsentimento() {
    const achado = document.cookie.split("; ").find(function (c) { return c.indexOf(NOME_COOKIE + "=") === 0; });
    return achado ? achado.split("=")[1] : null;
  }

  function salvarConsentimento(valor) {
    const seguro = location.protocol === "https:" ? "; Secure" : "";
    document.cookie = NOME_COOKIE + "=" + valor + "; Max-Age=31536000; Path=/; SameSite=Lax" + seguro;
  }

  function carregarMapa(caixa) {
    if (!caixa || caixa.dataset.carregado) return;
    const iframe = document.createElement("iframe");
    iframe.className = "mapa";
    iframe.loading = "lazy";
    iframe.referrerPolicy = "no-referrer-when-downgrade";
    iframe.title = "Mapa com a localização da barbearia";
    iframe.src = caixa.dataset.mapaSrc;
    caixa.dataset.carregado = "sim";
    caixa.replaceWith(iframe);
  }

  function aplicarConsentimento(valor) {
    if (valor === "todos") {
      document.querySelectorAll("[data-mapa-src]").forEach(carregarMapa);
    }
  }

  function mostrarAviso() {
    if (!aviso) return;
    aviso.hidden = false;
    document.body.classList.add("com-aviso-cookies");
  }

  function esconderAviso() {
    if (!aviso) return;
    aviso.hidden = true;
    document.body.classList.remove("com-aviso-cookies");
  }

  document.querySelectorAll("[data-cookies]").forEach(function (botao) {
    botao.addEventListener("click", function () {
      const valor = botao.dataset.cookies;
      salvarConsentimento(valor);
      esconderAviso();
      aplicarConsentimento(valor);
    });
  });

  document.querySelectorAll("[data-abrir-cookies]").forEach(function (botao) {
    botao.addEventListener("click", function () {
      mostrarAviso();
      const primeiro = aviso && aviso.querySelector("button");
      if (primeiro) primeiro.focus();
    });
  });

  // "Mostrar mapa": a pessoa pediu o mapa, então ele carrega só desta vez
  document.querySelectorAll("[data-carregar-mapa]").forEach(function (botao) {
    botao.addEventListener("click", function () { carregarMapa(botao.closest("[data-mapa-src]")); });
  });

  const consentimento = lerConsentimento();
  if (consentimento) {
    aplicarConsentimento(consentimento);
  } else {
    mostrarAviso();
  }

  window.Barbearia = { mascararTelefone: mascararTelefone };
})();
