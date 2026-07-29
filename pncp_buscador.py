import requests
import time
import random
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import TAMANHO_PAGINA

URL_SEARCH = "https://pncp.gov.br/api/search/"


def _criar_sessao():
    """
    Cria uma sessão com headers realistas e retry automático.
    """
    sessao = requests.Session()

    # Retry automático em falhas de conexão e 5xx
    retry = Retry(
        total=3,
        backoff_factor=2,  # espera 2s, 4s, 8s entre tentativas
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    sessao.mount("https://", adapter)
    sessao.mount("http://", adapter)

    # Headers que imitam o browser Chrome (copiados do seu Texto_colado.txt)
    sessao.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/150.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://pncp.gov.br/app/editais",
            "Origin": "https://pncp.gov.br",
            "sec-ch-ua": '"Not;A=Brand";v="8", "Chromium";v="150", "Google Chrome";v="150"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "Connection": "keep-alive",
        }
    )

    return sessao


# Sessão global reutilizada entre chamadas (keep-alive)
_sessao = _criar_sessao()


def buscar_search(
    termo,
    ufs,
    pagina=1,
    tamanho=TAMANHO_PAGINA,
    status=None,
):
    global _sessao

    params = {
        "q": termo.strip(),
        "tipos_documento": "edital",
        "ordenacao": "-data",
        "pagina": pagina,
        "tam_pagina": tamanho,
    }

    if status:
        params["status"] = status

    if ufs:
        estados = [uf.upper() for uf in ufs if uf.upper() != "TODOS"]
        if estados:
            params["ufs"] = ",".join(estados)

    # Delay humanizado: entre 0.3s e 0.8s (evita parecer robô)
    time.sleep(random.uniform(0.3, 0.8))

    for tentativa in range(3):
        try:
            resposta = _sessao.get(
                URL_SEARCH,
                params=params,
                timeout=30,
            )
            resposta.raise_for_status()
            return resposta.json()

        except requests.exceptions.ConnectionError as e:
            if tentativa < 2:
                # Recria a sessão e tenta de novo com espera maior
                _sessao = _criar_sessao()
                espera = (tentativa + 1) * 3 + random.uniform(0, 2)
                print(
                    f"[buscador] ConnectionError na tentativa {tentativa+1}, aguardando {espera:.1f}s..."
                )
                time.sleep(espera)
            else:
                raise

        except requests.exceptions.Timeout:
            if tentativa < 2:
                time.sleep((tentativa + 1) * 5)
            else:
                raise


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
                "objetoCompra": (item.get("description") or item.get("title") or ""),
                "dataPublicacaoPncp": item.get("data_publicacao_pncp"),
                "modalidadeNome": item.get("modalidade_licitacao_nome"),
                "modalidadeLicitacaoNome": item.get("modalidade_licitacao_nome"),
                "situacaoNome": item.get("situacao_nome"),
                # Campos de data que a /search realmente retorna
                "data_inicio_vigencia": item.get("data_inicio_vigencia"),
                "data_fim_vigencia": item.get("data_fim_vigencia"),
                "cancelado": item.get("cancelado", False),
                "orgaoEntidade": {
                    "razaoSocial": item.get("orgao_nome"),
                    "cnpj": item.get("orgao_cnpj"),
                },
                "unidadeOrgao": {
                    "municipioNome": item.get("municipio_nome"),
                    "ufSigla": item.get("uf"),
                    "nomeUnidade": item.get("unidade_nome"),
                },
                "item_url": item.get("item_url", ""),
                "orgao_cnpj": item.get("orgao_cnpj"),
                "municipio_nome": item.get("municipio_nome"),
                "uf": item.get("uf"),
                "orgao_nome": item.get("orgao_nome"),
                "unidade_nome": item.get("unidade_nome"),
            }

            resultado_final.append(convertido)

        total = resultado.get("total", 0)

        if pagina * TAMANHO_PAGINA >= total:
            break

        pagina += 1

    # Remove duplicados
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
