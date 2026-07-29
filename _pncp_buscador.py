import requests
import time

from config import TAMANHO_PAGINA

URL_SEARCH = "https://pncp.gov.br/api/search/"


def buscar_search(
    termo,
    ufs,
    pagina=1,
    tamanho=TAMANHO_PAGINA,
    status="recebendo_proposta",
):

    params = {
        "q": termo.strip(),
        "tipos_documento": "edital",
        "ordenacao": "-data",
        "pagina": pagina,
        "tam_pagina": tamanho,
        "status": status,
    }

    if ufs:
        estados = [
            uf.upper()
            for uf in ufs
            if uf.upper() != "TODOS"
        ]

        if estados:
            params["ufs"] = ",".join(estados)

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
    }

    time.sleep(0.10)

    resposta = requests.get(
        URL_SEARCH,
        params=params,
        headers=headers,
        timeout=30,
    )

    resposta.raise_for_status()

    return resposta.json()

def buscar_licitacoes_eficiente(
    termo,
    ufs,
    limite=200,
    dias=180,
    modalidades=None,
):

    pagina = 1
    resultado_final = []

    while len(resultado_final) < limite:

        resultado = buscar_search(
            termo=termo,
            ufs=ufs,
            pagina=pagina,
            tamanho=min(TAMANHO_PAGINA, limite),
        )

        itens = resultado.get("items", [])

        if not itens:
            break

        for item in itens:

            convertido = {
                "numeroControlePNCP": item.get("numero_controle_pncp"),

                "objetoCompra": (
                    item.get("description")
                    or item.get("title")
                    or ""
                ),

                "dataPublicacaoPncp": item.get("data_publicacao_pncp"),

                "modalidadeNome": item.get(
                    "modalidade_licitacao_nome"
                ),

                "modalidadeLicitacaoNome": item.get(
                    "modalidade_licitacao_nome"
                ),

                "situacaoNome": item.get(
                    "situacao_nome"
                ),

                "orgaoEntidade": {
                    "razaoSocial": item.get("orgao_nome"),
                    "cnpj": item.get("orgao_cnpj"),
                },
                                "unidadeOrgao": {
                    "municipioNome": item.get("municipio_nome"),
                    "ufSigla": item.get("uf"),
                },

                "linkSistemaOrigem": (
                    "https://pncp.gov.br/app/editais/"
                    + item.get("numero_controle_pncp", "")
                ),
            }

            resultado_final.append(convertido)

        total = resultado.get("total", 0)

        if pagina * TAMANHO_PAGINA >= total:
            break

        pagina += 1

    #
    # Remove duplicados
    #
    vistos = set()
    dados = []

    for item in resultado_final:

        chave = item.get("numeroControlePNCP")

        if chave in vistos:
            continue

        vistos.add(chave)
        dados.append(item)

    return {
        "data": dados[:limite],
        "totalRegistros": len(dados),
    }