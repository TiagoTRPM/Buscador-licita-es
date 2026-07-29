# atualizador.py
import time
import requests
import threading
from datetime import datetime

import cache as cache_module

LIMITE_DIA       = 2       # máx cliques manuais por dia
HORARIO_NOTURNO  = 22      # hora que inicia automático
DELAY_REQUISICAO = 0.8     # segundos entre cada requisição

# Estado em memória
_rodando        = False
_progresso      = {"atual": 0, "total": 0, "status": "idle", "log": []}
_thread_noturna = None


def _parsear_controle(numero_controle: str):
    partes    = numero_controle.split("/")
    ano       = partes[1].strip()
    segmentos = partes[0].split("-")
    cnpj      = segmentos[0].strip()
    seq       = str(int(segmentos[2].strip()))
    return cnpj, ano, seq


def _buscar_detalhe(numero_controle: str) -> dict | None:
    try:
        cnpj, ano, seq = _parsear_controle(numero_controle)
        url = f"https://pncp.gov.br/api/consulta/v1/contratacoes/{cnpj}/{ano}/{seq}"

        resp = requests.get(url, headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
            "Referer": "https://pncp.gov.br/app/editais",
            "sec-fetch-site": "same-origin",
            "sec-fetch-mode": "cors",
        }, timeout=15)

        if resp.status_code == 200:
            d = resp.json()
            valor = d.get("valorTotalEstimado") or d.get("valorTotalHomologado")
            valor_fmt = None
            if valor:
                valor_fmt = (
                    f"R$ {float(valor):,.2f}"
                    .replace(",", "X")
                    .replace(".", ",")
                    .replace("X", ".")
                )

            # Extrai unidade/municipio
            unidade = d.get("unidadeOrgao") or {}
            orgao   = d.get("orgaoEntidade") or {}

            return {
                "valor":          valor_fmt,
                "objeto":         (d.get("objetoCompra") or "")[:200],
                "orgao":          orgao.get("razaoSocial") or "",
                "municipio":      unidade.get("municipioNome") or "",
                "uf":             unidade.get("ufSigla") or "",
                "modalidade":     d.get("modalidadeNome") or "",
                "numero_edital":  d.get("numeroCompra") or numero_controle,
                "data_publicacao": (d.get("dataPublicacaoPncp") or "")[:10],
                "situacao":       d.get("situacaoCompraNome") or "",
            }
        return None

    except Exception as e:
        print(f"[atualizador] Erro em {numero_controle}: {e}")
        return None


def _executar(pendentes: list):
    global _rodando, _progresso

    _rodando = True
    _progresso = {
        "atual":  0,
        "total":  len(pendentes),
        "status": "rodando",
        "log":    [],
        "inicio": datetime.now().strftime("%H:%M:%S"),
    }

    cache_module.registrar_execucao()

    for i, nc in enumerate(pendentes, 1):
        if not _rodando:
            _progresso["status"] = "cancelado"
            break

        _progresso["atual"] = i
        resultado = _buscar_detalhe(nc)

        if resultado:
            cache_module.set(nc, resultado)
            valor_str = resultado.get("valor") or "sem valor"
            _progresso["log"].append(
                f"✅ [{i}/{len(pendentes)}] {resultado.get('municipio','')} — {valor_str}"
            )
        else:
            _progresso["log"].append(f"⚠️ [{i}/{len(pendentes)}] {nc} — sem retorno")

        # Mantém só as últimas 50 linhas de log
        if len(_progresso["log"]) > 50:
            _progresso["log"] = _progresso["log"][-50:]

        time.sleep(DELAY_REQUISICAO)

    _progresso["status"] = "concluido" if _rodando else "cancelado"
    _progresso["fim"] = datetime.now().strftime("%H:%M:%S")
    _rodando = False


def iniciar(pendentes: list) -> dict:
    global _rodando

    if _rodando:
        return {"ok": False, "erro": "Já está rodando"}

    execucoes = cache_module.execucoes_hoje()
    if execucoes >= LIMITE_DIA:
        return {"ok": False, "erro": f"Limite de {LIMITE_DIA} execuções por dia atingido"}

    if not pendentes:
        return {"ok": False, "erro": "Nenhum edital pendente"}

    t = threading.Thread(target=_executar, args=(pendentes,), daemon=True)
    t.start()

    return {"ok": True, "total": len(pendentes)}


def cancelar():
    global _rodando
    _rodando = False


def progresso() -> dict:
    return {**_progresso, "execucoes_hoje": cache_module.execucoes_hoje()}


def _monitor_noturno():
    """Thread que verifica todo dia às 22h se há pendentes e inicia."""
    from main import _ultima_busca  # pncp_buscador e pncp_extrator usados via main  # importado aqui para evitar circular

    while True:
        agora = datetime.now()
        if agora.hour == HORARIO_NOTURNO and not _rodando:
            if cache_module.execucoes_hoje() < LIMITE_DIA:
                ultima = _ultima_busca
                if ultima:
                    lics = ultima.get("licitacoes", [])
                    pendentes = cache_module.listar_pendentes(lics)
                    if pendentes:
                        print(f"[atualizador] Iniciando atualização noturna — {len(pendentes)} pendentes")
                        iniciar(pendentes)
        time.sleep(60)  # verifica a cada minuto


def iniciar_monitor_noturno():
    global _thread_noturna
    if _thread_noturna is None or not _thread_noturna.is_alive():
        _thread_noturna = threading.Thread(target=_monitor_noturno, daemon=True)
        _thread_noturna.start()
        print("[atualizador] Monitor noturno iniciado (22h)")
