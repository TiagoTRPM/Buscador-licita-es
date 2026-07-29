# cache.py
import json
import os
from datetime import datetime
from pathlib import Path

CACHE_PATH = Path(__file__).parent / "cache_valores.json"


def _carregar() -> dict:
    if CACHE_PATH.exists():
        try:
            with open(CACHE_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _salvar(dados: dict):
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


def get(numero_controle: str) -> dict | None:
    dados = _carregar()
    return dados.get(numero_controle)


def set(numero_controle: str, registro: dict):
    dados = _carregar()
    dados[numero_controle] = {
        **registro,
        "data_cache": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    _salvar(dados)


def listar_pendentes(licitacoes: list) -> list:
    """Retorna licitações que ainda não têm valor no cache."""
    dados = _carregar()
    return [
        l for l in licitacoes
        if l.get("_numeroControlePNCP")
        and l["_numeroControlePNCP"] not in dados
    ]


def stats() -> dict:
    dados = _carregar()
    com_valor = sum(1 for v in dados.values() if v.get("valor"))
    return {
        "total": len(dados),
        "com_valor": com_valor,
        "sem_valor": len(dados) - com_valor,
    }


def registrar_execucao():
    """Registra timestamp de uma execução do atualizador."""
    dados = _carregar()
    historico = dados.get("__execucoes__", [])
    hoje = datetime.now().strftime("%Y-%m-%d")
    historico = [e for e in historico if e.startswith(hoje)]  # só hoje
    historico.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    dados["__execucoes__"] = historico
    _salvar(dados)


def execucoes_hoje() -> int:
    dados = _carregar()
    hoje = datetime.now().strftime("%Y-%m-%d")
    return len([e for e in dados.get("__execucoes__", []) if e.startswith(hoje)])
