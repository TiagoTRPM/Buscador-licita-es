// app.js

// ── Loading ao submeter formulário ──────────────────
let abortControllerBusca = null;

document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("form-busca");
    const loading = document.getElementById("loading");
    const btn = document.getElementById("btn-buscar");
    const btnCancelar = document.getElementById("btn-cancelar-busca");

    if (form && loading) {
        form.addEventListener("submit", function (e) {
            // Permite submissão se for clique no botão (e.submitter) OU se for via Enter (e.submitter é nulo)
            if (e.submitter && e.submitter.id !== "btn-buscar") {
                e.preventDefault();
                return;
            }

            // Se já houver um controlador, cancela a submissão anterior
            if (abortControllerBusca) abortControllerBusca.abort();
            abortControllerBusca = new AbortController();

            loading.classList.remove("hidden");
            if (btn) {
                btn.disabled = true;
                btn.textContent = "⏳ Buscando...";
            }
            // Verifica se o botão existe antes de tentar acessar
            if (btnCancelar) {
                btnCancelar.classList.remove("hidden");
            }
        });
    }
});

// ── Troca de abas ───────────────────────────────────
function mostrarAba(nome, botao) {
    document.querySelectorAll(".aba-content").forEach(el => el.classList.add("hidden"));
    document.querySelectorAll(".tab-btn").forEach(el => el.classList.remove("active"));
    const aba = document.getElementById("aba-" + nome);
    if (aba) aba.classList.remove("hidden");
    if (botao) botao.classList.add("active");
}

// ── Filtro por município (atua em todas as abas) ────
function filtrarTabelas() {
    const municipio = document.getElementById("filtro-municipio").value;
    document.querySelectorAll(".tabela tbody tr").forEach(function (tr) {
        if (!municipio || tr.dataset.municipio === municipio) {
            tr.classList.remove("filtrado-out");
        } else {
            tr.classList.add("filtrado-out");
        }
    });
}
