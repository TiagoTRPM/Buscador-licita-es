from datetime import datetime


def primeiro(*valores):
    """
    Retorna o primeiro valor válido encontrado.
    """

    for valor in valores:
        if valor not in (None, "", [], {}):
            return valor

    return None


def _parse_data(raw):

    if not raw:
        return None

    try:
        return datetime.fromisoformat(
            raw.replace("Z", "+00:00")
        )
    except Exception:
        return None


def _fmt_data(dt):

    if dt is None:
        return "Não informada"

    return dt.strftime("%d/%m/%Y %H:%M")


def _formatar_valor(valor):

    if valor in (None, "", 0):
        return "Não informado"

    try:
        return (
            f"R$ {float(valor):,.2f}"
            .replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )

    except Exception:
        return "Não informado"


def extrair_licitacoes(dados_json):

    if not dados_json:
        return []

    itens = (
        dados_json.get("data")
        or dados_json.get("items")
        or []
    )

    hoje = datetime.now().date()

    resultado = []
    
    for item in itens:

        unidade = primeiro(
            item.get("unidadeOrgao"),
            {}
        )

        orgao_entidade = primeiro(
            item.get("orgaoEntidade"),
            {}
        )

        municipio = primeiro(
            unidade.get("municipioNome"),
            item.get("municipio_nome"),
            orgao_entidade.get("municipioNome"),
            item.get("municipioNome"),
            "Não informado",
        )

        uf = primeiro(
            unidade.get("ufSigla"),
            item.get("uf"),
            "",
        )

        orgao = primeiro(
            orgao_entidade.get("razaoSocial"),
            orgao_entidade.get("nome"),
            item.get("orgao_nome"),
            unidade.get("nomeUnidade"),
            "Não informado",
        )

        modalidade = primeiro(
            item.get("modalidadeNome"),
            item.get("modalidadeLicitacaoNome"),
            item.get("modalidade_licitacao_nome"),
            "Não informada",
        )

        situacao = primeiro(
            item.get("situacaoCompraNome"),
            item.get("situacaoNome"),
            item.get("situacao_nome"),
            item.get("situacao"),
            "Não informada",
        )

        objeto = primeiro(
            item.get("objetoCompra"),
            item.get("objeto"),
            item.get("description"),
            item.get("title"),
            "Sem descrição disponível",
        )

        objeto = " ".join(objeto.split())

        dt_publicacao = _parse_data(
            primeiro(
                item.get("dataPublicacaoPncp"),
                item.get("data_publicacao_pncp"),
            )
        )

        dt_abertura = _parse_data(
            item.get("dataAberturaProposta")
        )

        dt_encerramento = _parse_data(
            item.get("dataEncerramentoProposta")
        )
        
        if dt_encerramento:
            dias = (dt_encerramento.date() - hoje).days
        elif dt_abertura:
            dias = (dt_abertura.date() - hoje).days
        else:
            dias = None

        if dias is None:
            prazo = "Sem prazo"
        elif dias > 0:
            prazo = f"⏳ {dias} dias"
        elif dias == 0:
            prazo = "🚨 É HOJE!"
        else:
            prazo = "🏁 Encerrado"

        valor = primeiro(
            item.get("valorTotalEstimado"),
            item.get("valorTotalHomologado"),
            item.get("valorGlobal"),
            item.get("valor"),
        )

        valor_fmt = _formatar_valor(valor)

        numero_controle = primeiro(
            item.get("numeroControlePNCP"),
            item.get("numero_controle_pncp"),
        )

        processo = primeiro(
            item.get("processo"),
            item.get("numeroCompra"),
            numero_controle,
            "Não informado",
        )

        link = primeiro(
            item.get("linkSistemaOrigem"),
            item.get("linkProcessoEletronico"),
            item.get("linkPncp"),
            item.get("item_url"),
        )

        if not link and numero_controle:
            link = (
                "https://pncp.gov.br/app/editais/"
                f"{numero_controle}"
            )

        resultado.append({

            "uf": uf.upper() if uf else "?",

            "municipio": municipio.title(),

            "orgao": orgao,

            "processo": processo,

            "modalidade": modalidade,

            "abertura": _fmt_data(dt_abertura),

            "encerramento": _fmt_data(dt_encerramento),

            "publicacao": _fmt_data(dt_publicacao),

            "objeto": objeto,

            "valor": valor_fmt,

            "situacao": situacao,

            "status": situacao,

            "prazo": prazo,

            "dias": dias if dias is not None else 9999,

            "link": link,

            "_dt_ref": (
                dt_publicacao.date()
                if dt_publicacao
                else None
            ),

            "_numeroControlePNCP": numero_controle,

        })

    return resultado