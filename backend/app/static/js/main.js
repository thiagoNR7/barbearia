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

  window.Barbearia = { mascararTelefone: mascararTelefone };
})();
