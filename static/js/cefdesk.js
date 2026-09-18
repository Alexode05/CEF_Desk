// CEF Desk — comportements JS communs (sans dépendance).
(function () {
  "use strict";

  // Lignes de tableau cliquables (attribut data-href).
  document.querySelectorAll("tr[data-href]").forEach(function (row) {
    row.addEventListener("click", function (e) {
      if (e.target.closest("a, button, input, label, select, form")) return;
      window.location = row.dataset.href;
    });
  });

  // Case « tout sélectionner » (data-check-all="selecteur des cases").
  document.querySelectorAll("[data-check-all]").forEach(function (master) {
    var boxes = document.querySelectorAll(master.dataset.checkAll);
    master.addEventListener("change", function () {
      boxes.forEach(function (b) { b.checked = master.checked; });
      document.dispatchEvent(new CustomEvent("cef:selection-changed"));
    });
    boxes.forEach(function (b) {
      b.addEventListener("change", function () {
        document.dispatchEvent(new CustomEvent("cef:selection-changed"));
      });
    });
  });

  // Compteur de sélection + activation des boutons d'action de masse.
  function refreshSelection() {
    var boxes = document.querySelectorAll("input.row-check:checked");
    document.querySelectorAll("[data-selection-count]").forEach(function (el) {
      el.textContent = boxes.length;
    });
    document.querySelectorAll("[data-needs-selection]").forEach(function (el) {
      el.disabled = boxes.length === 0;
    });
  }
  document.addEventListener("cef:selection-changed", refreshSelection);
  refreshSelection();

  // Confirmation générique (data-confirm="message").
  document.querySelectorAll("form[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      if (!window.confirm(form.dataset.confirm)) e.preventDefault();
    });
  });

  // Affichage/masquage des données sensibles (N° AVS).
  document.querySelectorAll("[data-reveal]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var target = document.querySelector(btn.dataset.reveal);
      if (!target) return;
      target.classList.toggle("sensitive-hidden");
      btn.innerHTML = target.classList.contains("sensitive-hidden")
        ? '<i class="bi bi-eye"></i> Afficher'
        : '<i class="bi bi-eye-slash"></i> Masquer';
    });
  });

  // Enregistrement automatique des notes post-it (délai 1.2 s après la dernière frappe).
  var postit = document.querySelector("[data-autosave-url]");
  if (postit) {
    var timer = null;
    var status = document.querySelector("[data-autosave-status]");
    postit.addEventListener("input", function () {
      clearTimeout(timer);
      if (status) status.textContent = "Modifications non enregistrées…";
      timer = setTimeout(function () {
        var body = new FormData();
        body.append("content", postit.value);
        body.append("csrfmiddlewaretoken", document.querySelector("[name=csrfmiddlewaretoken]").value);
        fetch(postit.dataset.autosaveUrl, { method: "POST", body: body, credentials: "same-origin" })
          .then(function (r) { if (status) status.textContent = r.ok ? "Enregistré" : "Erreur d'enregistrement"; })
          .catch(function () { if (status) status.textContent = "Erreur d'enregistrement"; });
      }, 1200);
    });
  }
})();
