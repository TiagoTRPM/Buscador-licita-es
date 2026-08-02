# etp_manager.py
import json
import uuid
from datetime import datetime
from pathlib import Path

ETP_PATH = Path(__file__).parent / "etp_lista.json"


def _carregar() -> dict:
    if ETP_PATH.exists():
        try:
            with open(ETP_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"etps": {}}
    return {"etps": {}}


def _salvar(dados: dict):
    with open(ETP_PATH, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


def novo_etp(titulo: str = "Novo ETP") -> dict:
    dados = _carregar()
    etp_id = f"etp_{uuid.uuid4().hex[:8]}"
    agora = datetime.now().strftime("%Y-%m-%d %H:%M")

    etp = {
        "id":       etp_id,
        "titulo":   titulo,
        "criado":   agora,
        "alterado": agora,
        "status":   "em_andamento",

        "cabecalho": {
            "orgao":       "",
            "municipio":   "",
            "estado":      "",
            "processo":    "",
            "responsavel": "",
            "cargo":       "",
            "data":        datetime.now().strftime("%Y-%m-%d"),
            "modo_cabecalho": "dinamico",  # ou "arquivo"
            "brasao_path": "",
            "cabecalho_path": "",
        },

        "campos_fixos": {
            "descricao_necessidade":        "",
            "previsao_pca":                 "",
            "requisitos_contratacao":       "",
            "descricao_solucao":            "",
            "estimativa_valor":             "",
            "justificativa_parcelamento":   "Não haverá parcelamento da solução.",
            "resultados_pretendidos":       "",
            "providencias_previas":         "",
            "contratacoes_correlatas":      "Não há contratações que impactam significativamente a presente contratação.",
            "impactos_ambientais":          "Não há impactos ambientais significativos na presente contratação.",
            "posicionamento_conclusivo":    "Diante do exposto, declaramos a viabilidade da contratação.",
        },

        "itens": [],          # lista de itens para estimativa de quantidades
        "levantamento": [],   # resultados de preços buscados
        "campos_livres": [],  # campos extras adicionados pelo usuário
        "etapas_puladas": [], # campos do fluxo guiado que o usuário decidiu preencher depois
    }

    dados["etps"][etp_id] = etp
    _salvar(dados)
    return etp


def listar_etps() -> list:
    dados = _carregar()
    etps = list(dados["etps"].values())
    return sorted(etps, key=lambda x: x.get("alterado", ""), reverse=True)


def get_etp(etp_id: str) -> dict | None:
    dados = _carregar()
    return dados["etps"].get(etp_id)


def salvar_etp(etp_id: str, atualizacoes: dict) -> dict | None:
    dados = _carregar()
    if etp_id not in dados["etps"]:
        return None

    etp = dados["etps"][etp_id]

    # Atualiza campos recursivamente
    for chave, valor in atualizacoes.items():
        if chave in ("cabecalho", "campos_fixos") and isinstance(valor, dict):
            etp[chave].update(valor)
        else:
            etp[chave] = valor

    etp["alterado"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    dados["etps"][etp_id] = etp
    _salvar(dados)
    return etp


def importar_campos_fixos(etp_id: str, campos: dict[str, str]) -> dict | None:
    """Atualiza os blocos de conteúdo extraídos de um ETP importado."""
    dados = _carregar()
    etp = dados["etps"].get(etp_id)
    if not etp:
        return None

    etp["campos_fixos"].update({campo: valor for campo, valor in campos.items() if valor.strip()})
    etp["alterado"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    _salvar(dados)
    return etp


def deletar_etp(etp_id: str) -> bool:
    dados = _carregar()
    if etp_id not in dados["etps"]:
        return False
    del dados["etps"][etp_id]
    _salvar(dados)
    return True


def adicionar_item(etp_id: str, item: dict) -> dict | None:
    dados = _carregar()
    if etp_id not in dados["etps"]:
        return None

    item["id"] = uuid.uuid4().hex[:8]
    dados["etps"][etp_id]["itens"].append(item)
    dados["etps"][etp_id]["alterado"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    _salvar(dados)
    return dados["etps"][etp_id]


def adicionar_todos_itens_do_levantamento(etp_id: str) -> int | None:
    """Converte as referências salvas no levantamento em itens do ETP."""
    dados = _carregar()
    etp = dados["etps"].get(etp_id)
    if not etp:
        return None

    incluidos = 0
    for levantamento in etp.get("levantamento", []):
        for referencia in levantamento.get("referencias", []):
            descricao = (
                referencia.get("descricao_item")
                or referencia.get("objeto")
                or levantamento.get("termo", "")
            ).strip()
            if not descricao:
                continue

            etp["itens"].append({
                "id": uuid.uuid4().hex[:8],
                "nome": descricao[:100],
                "descricao": descricao,
                "quantidade": referencia.get("quantidade") or 1,
                "unidade": referencia.get("unidade") or "un",
            })
            incluidos += 1

    if incluidos:
        etp["alterado"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        _salvar(dados)
    return incluidos


def remover_item(etp_id: str, item_id: str) -> bool:
    dados = _carregar()
    if etp_id not in dados["etps"]:
        return False

    etp = dados["etps"][etp_id]
    etp["itens"] = [i for i in etp["itens"] if i.get("id") != item_id]
    etp["alterado"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    _salvar(dados)
    return True


def editar_nome_item(etp_id: str, item_id: str, nome: str) -> bool:
    dados = _carregar()
    etp = dados["etps"].get(etp_id)
    if not etp:
        return False

    item = next((item for item in etp["itens"] if item.get("id") == item_id), None)
    if not item:
        return False

    item["nome"] = " ".join(nome.split())[:100]
    etp["alterado"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    _salvar(dados)
    return True


def salvar_levantamento(etp_id: str, termo: str, referencias: list) -> dict | None:
    dados = _carregar()
    if etp_id not in dados["etps"]:
        return None

    etp = dados["etps"][etp_id]

    # Remove levantamento anterior do mesmo termo se existir
    etp["levantamento"] = [
        l for l in etp["levantamento"]
        if l.get("termo", "").lower() != termo.lower()
    ]

    etp["levantamento"].append({
        "termo":       termo,
        "referencias": referencias,
        "buscado_em":  datetime.now().strftime("%Y-%m-%d %H:%M"),
    })

    etp["alterado"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    _salvar(dados)
    return etp


def adicionar_referencia(etp_id: str, termo: str, referencia: dict) -> tuple[dict | None, bool]:
    """Inclui uma referência individual em um levantamento, sem apagar as demais."""
    dados = _carregar()
    etp = dados["etps"].get(etp_id)
    if not etp:
        return None, False

    termo = (termo or "Referências da consulta").strip() or "Referências da consulta"
    levantamento = next(
        (item for item in etp["levantamento"] if item.get("termo", "").lower() == termo.lower()),
        None,
    )
    if levantamento is None:
        levantamento = {
            "termo": termo,
            "referencias": [],
            "buscado_em": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        etp["levantamento"].append(levantamento)

    numero_controle = referencia.get("numero_controle")
    item_id = referencia.get("item_id")
    link = referencia.get("link")
    ja_existe = any(
        (numero_controle and ref.get("numero_controle") == numero_controle
         and ref.get("item_id") == item_id)
        or (not numero_controle and link and ref.get("link") == link)
        for ref in levantamento["referencias"]
    )
    if ja_existe:
        return etp, False

    levantamento["referencias"].append(referencia)
    levantamento["buscado_em"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    etp["alterado"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    _salvar(dados)
    return etp, True


def adicionar_campo_livre(etp_id: str, nome: str, conteudo: str) -> dict | None:
    dados = _carregar()
    if etp_id not in dados["etps"]:
        return None

    campo = {"id": uuid.uuid4().hex[:8], "nome": nome, "conteudo": conteudo}
    dados["etps"][etp_id]["campos_livres"].append(campo)
    dados["etps"][etp_id]["alterado"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    _salvar(dados)
    return dados["etps"][etp_id]
