// CEF Desk — comportements JS communs (sans dépendance).
(function () {
  "use strict";

  // Lignes de tableau cliquables (attribut data-href).
  document.querySelectorAll("tr[data-href]").forEach(function (row) {
    row.addEventListener("click", function (e) {
      // On ignore uniquement les contrôles situés DANS la ligne (le tableau lui-même peut être dans un formulaire).
      var control = e.target.closest("a, button, input, label, select, textarea");
      if (control && row.contains(control)) return;
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

  // Confirmation générique (data-confirm="message") : fenêtre Bootstrap, plus fiable que window.confirm
  // (souvent bloqué dans les navigateurs intégrés) et plus lisible pour le comité.
  var confirmModalEl = null, confirmModal = null, pendingForm = null;
  function ensureConfirmModal() {
    if (confirmModalEl) return;
    var wrap = document.createElement("div");
    wrap.innerHTML =
      '<div class="modal fade" id="cefConfirmModal" tabindex="-1" aria-hidden="true"><div class="modal-dialog modal-dialog-centered"><div class="modal-content">' +
      '<div class="modal-header"><h5 class="modal-title">Confirmation</h5><button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Fermer"></button></div>' +
      '<div class="modal-body" id="cefConfirmMessage"></div>' +
      '<div class="modal-footer"><button type="button" class="btn btn-link" data-bs-dismiss="modal">Annuler</button>' +
      '<button type="button" class="btn btn-primary" id="cefConfirmOk">Confirmer</button></div></div></div></div>';
    document.body.appendChild(wrap.firstChild);
    confirmModalEl = document.getElementById("cefConfirmModal");
    confirmModal = new bootstrap.Modal(confirmModalEl);
    document.getElementById("cefConfirmOk").addEventListener("click", function () {
      var f = pendingForm; pendingForm = null;
      confirmModal.hide();
      if (f) { f.dataset.confirmed = "1"; f.submit(); }
    });
  }
  document.querySelectorAll("form[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      if (form.dataset.confirmed === "1") return;
      e.preventDefault();
      ensureConfirmModal();
      pendingForm = form;
      document.getElementById("cefConfirmMessage").textContent = form.dataset.confirm;
      var danger = /supprim|annul|retirer|d[ée]finitiv/i.test(form.dataset.confirm);
      var ok = document.getElementById("cefConfirmOk");
      ok.className = "btn " + (danger ? "btn-danger" : "btn-primary");
      ok.textContent = danger ? "Oui, continuer" : "Confirmer";
      confirmModal.show();
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
