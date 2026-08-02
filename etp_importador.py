import io
import re
import unicodedata

from docx import Document


CAMPOS_POR_SECAO = {
    1: "descricao_necessidade",
    2: "previsao_pca",
    3: "requisitos_contratacao",
    6: "estimativa_valor",
    7: "descricao_solucao",
    8: "justificativa_parcelamento",
    9: "resultados_pretendidos",
    10: "providencias_previas",
    11: "contratacoes_correlatas",
    12: "impactos_ambientais",
    13: "posicionamento_conclusivo",
}


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).strip().lower()


def _numero_secao(texto: str) -> int | None:
    encontrado = re.match(r"^\s*(\d{1,2})\s*(?:[.º°]|[-–—])", texto or "")
    return int(encontrado.group(1)) if encontrado else None


def _eh_titulo(paragrafo) -> bool:
    texto = (paragrafo.text or "").strip()
    if not texto:
        return False
    if _numero_secao(texto) is not None:
        return True

    estilo = _normalizar(getattr(paragrafo.style, "name", ""))
    if "heading" in estilo or "titulo" in estilo or "cabecalho" in estilo:
        return True

    letras = [c for c in texto if c.isalpha()]
    return bool(letras) and len(texto) <= 120 and "".join(letras).isupper()


def extrair_campos_etp(arquivo: bytes) -> dict[str, str]:
    """Extrai os blocos textuais de um ETP Word por numeração e posição."""
    documento = Document(io.BytesIO(arquivo))
    secoes = []
    titulo_atual = None
    conteudo_atual = []

    def finalizar_secao():
        if titulo_atual and conteudo_atual:
            conteudo = "\n\n".join(conteudo_atual).strip()
            if conteudo:
                secoes.append((titulo_atual, conteudo))

    for paragrafo in documento.paragraphs:
        texto = (paragrafo.text or "").strip()
        if not texto:
            continue
        if _eh_titulo(paragrafo):
            finalizar_secao()
            titulo_atual = texto
            conteudo_atual = []
        elif titulo_atual:
            conteudo_atual.append(texto)
    finalizar_secao()

    campos = {}
    usados = set()

    # A numeração é a fonte mais confiável: o nome da seção pode variar.
    for indice, (titulo, conteudo) in enumerate(secoes):
        numero = _numero_secao(titulo)
        campo = CAMPOS_POR_SECAO.get(numero)
        if campo and campo not in campos:
            campos[campo] = conteudo
            usados.add(indice)

    # Para documentos sem numeração, usa a sequência dos blocos de conteúdo.
    candidatos = [
        (indice, conteudo)
        for indice, (titulo, conteudo) in enumerate(secoes)
        if indice not in usados
        and not _normalizar(titulo).startswith(("introducao", "estudo tecnico preliminar"))
    ]
    faltantes = [campo for campo in CAMPOS_POR_SECAO.values() if campo not in campos]
    for campo, (_, conteudo) in zip(faltantes, candidatos):
        campos[campo] = conteudo

    return campos
