from datetime import datetime


def primeiro(*valores):
    for valor in valores:
        if valor not in (None, "", [], {}):
            return valor
    return None


def _parse_data(raw):
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
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


def _montar_link_pncp(numero_controle):
    """
    Converte numeroControlePNCP para URL pública do edital.
    Ex: "76970326000103-1-000142/2026" → .../editais/76970326000103/2026/142
    """
    try:
        nc       = numero_controle.strip()
        partes   = nc.split("/")
        ano      = partes[1].strip()
        segmentos = partes[0].split("-")
        cnpj     = segmentos[0].strip()
        seq      = str(int(segmentos[2].strip()))
        if cnpj and ano and seq:
            return f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{seq}"
    except Exception:
        pass
    return f"https://pncp.gov.br/app/editais/{numero_controle}"


def _inferir_status(dt_abertura, dt_encerramento, situacao_raw, cancelado):
    """
    Infere o status legível baseado nas datas e situação da API.
    A API /search não retorna status processual diretamente.
    """
    situacao = (situacao_raw or "").lower()

    if cancelado:
        return "Encerrado"

    if "cancel" in situacao or "revog" in situacao or "anulad" in situacao:
        return "Encerrado"

    if "suspend" in situacao:
        return "Aguardando Abertura"

    hoje = datetime.now().replace(tzinfo=None)

    def naive(dt):
        if dt is None:
            return None
        return dt.replace(tzinfo=None) if dt.tzinfo else dt

    ab  = naive(dt_abertura)
    enc = naive(dt_encerramento)

    if enc is not None:
        if ab and hoje < ab:
            return "Aguardando Abertura"
        if hoje <= enc:
            return "Em Aberto"
        dias_encerrado = (hoje - enc).days
        if dias_encerrado <= 30:
            return "Em Julgamento"
        return "Encerrado"

    if ab is not None:
        if hoje < ab:
            return "Aguardando Abertura"
        return "Em Aberto"

    # Sem datas — usa situação textual
    if "divulgada" in situacao or "publicada" in situacao:
        return "Em Aberto"
    if "homolog" in situacao or "adjudic" in situacao or "encerrad" in situacao:
        return "Encerrado"
    if "julgamento" in situacao or "análise" in situacao:
        return "Em Julgamento"

    return "Indefinido"


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

        unidade        = primeiro(item.get("unidadeOrgao"), {})
        orgao_entidade = primeiro(item.get("orgaoEntidade"), {})

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
            item.get("unidade_nome"),
            "Não informado",
        )

        modalidade = primeiro(
            item.get("modalidadeNome"),
            item.get("modalidadeLicitacaoNome"),
            item.get("modalidade_licitacao_nome"),
            "Não informada",
        )

        situacao_raw = primeiro(
            item.get("situacaoCompraNome"),
            item.get("situacaoNome"),
            item.get("situacao_nome"),
            item.get("situacao"),
            "",
        )

        cancelado = bool(item.get("cancelado", False))

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
            primeiro(
                item.get("dataAberturaProposta"),
                item.get("data_inicio_vigencia"),
                item.get("dataInicioVigencia"),
            )
        )

        dt_encerramento = _parse_data(
            primeiro(
                item.get("dataEncerramentoProposta"),
                item.get("data_fim_vigencia"),
                item.get("dataFimVigencia"),
            )
        )

        status = _inferir_status(dt_abertura, dt_encerramento, situacao_raw, cancelado)

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
            item.get("valor_global"),
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

        item_url = item.get("item_url", "")
        if item_url:
            link = "https://pncp.gov.br/app" + item_url.replace("/compras/", "/editais/")
        else:
            link = primeiro(
                item.get("linkSistemaOrigem"),
                item.get("linkProcessoEletronico"),
                item.get("linkPncp"),
            )
            if not link and numero_controle:
                link = _montar_link_pncp(numero_controle)

        resultado.append({
            "uf":          uf.upper() if uf else "?",
            "municipio":   municipio.title(),
            "orgao":       orgao,
            "processo":    processo,
            "modalidade":  modalidade,
            "abertura":    _fmt_data(dt_abertura),
            "encerramento": _fmt_data(dt_encerramento),
            "publicacao":  _fmt_data(dt_publicacao),
            "objeto":      objeto,
            "valor":       valor_fmt,
            "situacao":    situacao_raw or "Não informada",
            "status":      status,
            "prazo":       prazo,
            "dias":        dias if dias is not None else 9999,
            "link":        link,
            "_dt_ref":     (dt_publicacao.date() if dt_publicacao else None),
            "_numeroControlePNCP": numero_controle,
        })

    return resultado