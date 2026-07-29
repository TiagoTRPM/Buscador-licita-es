# main.py
import io
import os
import re
from datetime import datetime, timedelta
from fastapi.concurrency import run_in_threadpool

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config import ESTADOS, BASE_DIR, MODALIDADES_DISPONIVEIS
from pncp_buscador import buscar_licitacoes_eficiente
from pncp_extrator import extrair_licitacoes
from expansor import expandir_termo
import cache as cache_module
import atualizador

# =====================================================
# INICIALIZAÇÃO
# =====================================================

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    atualizador.iniciar_monitor_noturno()
    yield

app = FastAPI(lifespan=lifespan)


app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

_ultima_busca: dict | None = None

def _data_padrao_inicial():
    return (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")

def _data_padrao_final():
    return datetime.now().strftime("%Y-%m-%d")



# =====================================================
# ROTAS: ATUALIZADOR DE CACHE
# =====================================================

@app.post("/api/atualizar/iniciar")
async def atualizar_iniciar():
    if not _ultima_busca:
        return {"ok": False, "erro": "Faça uma busca primeiro"}
    lics     = _ultima_busca.get("licitacoes", [])
    pendentes = cache_module.listar_pendentes(lics)
    return atualizador.iniciar(pendentes)


@app.post("/api/atualizar/cancelar")
async def atualizar_cancelar():
    atualizador.cancelar()
    return {"ok": True}


@app.get("/api/atualizar/progresso")
async def atualizar_progresso():
    return atualizador.progresso()


@app.get("/api/cache/stats")
async def cache_stats():
    return cache_module.stats()


@app.get("/api/valor/{numero_controle:path}")
async def api_valor_cache(numero_controle: str):
    """Tenta cache primeiro, depois busca na API."""
    cached = cache_module.get(numero_controle)
    if cached and cached.get("valor"):
        return {"valor": cached["valor"], "fonte": "cache"}

    import requests as req
    import time as tm
    try:
        partes    = numero_controle.split("/")
        ano       = partes[1].strip()
        segmentos = partes[0].split("-")
        cnpj      = segmentos[0].strip()
        seq       = str(int(segmentos[2].strip()))
    except Exception:
        return {"valor": None, "erro": "Número de controle inválido"}

    url = f"https://pncp.gov.br/api/consulta/v1/contratacoes/{cnpj}/{ano}/{seq}"
    try:
        tm.sleep(0.5)
        resp = req.get(url, headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
            "Referer": "https://pncp.gov.br/app/editais",
        }, timeout=10)
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
            unidade = d.get("unidadeOrgao") or {}
            orgao   = d.get("orgaoEntidade") or {}
            registro = {
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
            cache_module.set(numero_controle, registro)
            return {"valor": valor_fmt, "fonte": "api"}
        return {"valor": None, "erro": f"API retornou {resp.status_code}"}
    except Exception as e:
        return {"valor": None, "erro": str(e)}


# =====================================================
# ROTA: INDEX
# =====================================================

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    response = templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "estados":      ESTADOS,
            "modalidades":  MODALIDADES_DISPONIVEIS,
            "data_inicial": _data_padrao_inicial(),
            "data_final":   _data_padrao_final(),
        },
    )
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response


@app.get("/buscar")
async def buscar_get_invalido():
    return RedirectResponse("/", status_code=303)


# =====================================================
# ROTA: API — expandir termos via Gemini
# =====================================================

@app.get("/api/expandir")
async def api_expandir(termo: str = ""):
    if not termo or len(termo.strip()) < 2:
        return {"termos_incluir": [], "termos_excluir": []}
    resultado = await run_in_threadpool(expandir_termo, termo.strip())
    return resultado


# =====================================================
# ROTA: API — municípios de um estado
# =====================================================

@app.get("/api/municipios/{uf}")
async def api_municipios(uf: str, termo: str = "", data_inicial: str = "", data_final: str = ""):
    if not termo:
        return {"municipios": []}

    hoje = datetime.now().date()
    try:
        dt_ini = datetime.strptime(data_inicial, "%Y-%m-%d").date() if data_inicial else hoje - timedelta(days=180)
        dt_fim = datetime.strptime(data_final,   "%Y-%m-%d").date() if data_final   else hoje
    except ValueError:
        dt_ini = hoje - timedelta(days=180)
        dt_fim = hoje

    dias = max((hoje - dt_ini).days + (dt_fim - hoje).days, 1)
    dados_json = buscar_licitacoes_eficiente(termo, ufs=[uf], limite=500, dias=dias)
    licitacoes = extrair_licitacoes(dados_json)
    municipios = sorted({l["municipio"] for l in licitacoes})
    return {"municipios": municipios}


# =====================================================
# ROTA: BUSCA COM SSE (progresso em tempo real)
# =====================================================

@app.post("/buscar-stream")
async def buscar_stream(request: Request):

    form = await request.form()

    termo               = form.get("termo", "").strip()
    data_inicial        = form.get("data_inicial", "")
    data_final          = form.get("data_final", "")
    limite_registros    = int(form.get("limite_registros", 200))
    incluir_sem_periodo = form.get("incluir_sem_periodo", "nao")
    ufs_selecionadas    = form.getlist("ufs") or ["PR"]
    filtros_cidade      = form.getlist("cidades_filtro")
    mods_form           = form.getlist("modalidades")
    modalidades_selecionadas = [int(m) for m in mods_form] if mods_form else list(MODALIDADES_DISPONIVEIS.keys())

    termos_extras  = form.getlist("termos_incluir")
    termos_excluir = form.getlist("termos_excluir")

    if not termo:
        return RedirectResponse("/", status_code=303)

    hoje = datetime.now().date()
    try:
        dt_ini = datetime.strptime(data_inicial, "%Y-%m-%d").date() if data_inicial else hoje - timedelta(days=180)
        dt_fim = datetime.strptime(data_final,   "%Y-%m-%d").date() if data_final   else hoje
    except ValueError:
        dt_ini = hoje - timedelta(days=180)
        dt_fim = hoje

    dias = max((hoje - dt_ini).days + (dt_fim - hoje).days, 1)

    todos_termos = [termo] + [t for t in termos_extras if t.strip()]

    STOPWORDS = {
        "contratacao", "contratação", "servico", "serviço", "servicos", "serviços",
        "de", "da", "do", "das", "dos", "para", "com", "a", "e", "em", "um", "uma", "por"
    }

    async def gerar_eventos():
        todas_licitacoes = []
        vistos_link = set()

        for i, t in enumerate(todos_termos, 1):
            # Evento de progresso
            yield f"data: {{'\"tipo\": \"progresso\", \"atual\": {i}, \"total\": {len(todos_termos)}, \"termo\": \"{t}\"}}\n\n"

            dados_json = await run_in_threadpool(
                buscar_licitacoes_eficiente,
                t,
                ufs=ufs_selecionadas,
                limite=limite_registros,
                dias=dias,
                modalidades=modalidades_selecionadas,
            )

            licitacoes = extrair_licitacoes(dados_json) if dados_json else []

            # Filtro de termo no objeto
            palavras_usuario = [
                p.lower().strip() for p in t.split()
                if len(p) > 2 and p.lower() not in STOPWORDS
            ]

            novas = 0
            for l in licitacoes:
                if l["link"] in vistos_link:
                    continue

                objeto_original = l["objeto"].lower()
                objeto_limpo = re.sub(r'^\s*\[.*?\]\s*-?\s*', '', objeto_original)

                if palavras_usuario:
                    if not any(p in objeto_limpo or p in objeto_original for p in palavras_usuario):
                        continue

                vistos_link.add(l["link"])
                todas_licitacoes.append(l)
                novas += 1

            yield f"data: {{\"tipo\": \"parcial\", \"termo\": \"{t}\", \"encontrados\": {novas}, \"total_ate_agora\": {len(todas_licitacoes)}}}\n\n"

        # Filtro de exclusão
        if termos_excluir:
            excluir_lower = [t.lower() for t in termos_excluir]
            todas_licitacoes = [
                l for l in todas_licitacoes
                if not any(ex in l["objeto"].lower() for ex in excluir_lower)
            ]

        # Filtro de período
        def dentro_do_periodo(l):
            if l["_dt_ref"] is None:
                return incluir_sem_periodo == "sim"
            return dt_ini <= l["_dt_ref"] <= dt_fim

        todas_licitacoes = [l for l in todas_licitacoes if dentro_do_periodo(l)]

        # Filtro de cidades
        if filtros_cidade:
            cidades_set = set()
            for fc in filtros_cidade:
                partes = fc.split(":", 1)
                if len(partes) == 2:
                    cidades_set.add(partes[1].strip().lower())
            todas_licitacoes = [l for l in todas_licitacoes if l["municipio"].lower() in cidades_set]

        if limite_registros > 0:
            todas_licitacoes = todas_licitacoes[:limite_registros]

        # Separa por status
        abertos    = sorted([l for l in todas_licitacoes if l["status"] == "Em Aberto"],           key=lambda x: x["dias"])
        aguardando = sorted([l for l in todas_licitacoes if l["status"] == "Aguardando Abertura"], key=lambda x: x["dias"])
        julgamento = sorted([l for l in todas_licitacoes if l["status"] == "Em Julgamento"],       key=lambda x: x["dias"])
        encerrados = sorted([l for l in todas_licitacoes if l["status"] == "Encerrado"],           key=lambda x: x["dias"], reverse=True)
        indefinidos=        [l for l in todas_licitacoes if l["status"] == "Indefinido"]

        municipios_por_uf = {}
        for l in todas_licitacoes:
            uf = l["uf"]
            if uf not in municipios_por_uf:
                municipios_por_uf[uf] = set()
            municipios_por_uf[uf].add(l["municipio"])
        municipios_por_uf = {uf: sorted(cids) for uf, cids in sorted(municipios_por_uf.items())}

        global _ultima_busca
        _ultima_busca = {
            "termo":                    termo,
            "ufs_selecionadas":         ufs_selecionadas,
            "licitacoes":               todas_licitacoes,
            "abertos":                  abertos,
            "aguardando":               aguardando,
            "julgamento":               julgamento,
            "encerrados":               encerrados,
            "indefinidos":              indefinidos,
            "todos":                    abertos + aguardando + julgamento + encerrados + indefinidos,
            "data_inicial":             data_inicial or dt_ini.strftime("%Y-%m-%d"),
            "data_final":               data_final or dt_fim.strftime("%Y-%m-%d"),
            "incluir_sem_periodo":      incluir_sem_periodo,
            "total":                    len(todas_licitacoes),
            "municipios_por_uf":        municipios_por_uf,
            "limite_registros":         limite_registros,
            "modalidades":              MODALIDADES_DISPONIVEIS,
            "modalidades_selecionadas": modalidades_selecionadas,
        }

        yield f"data: {{\"tipo\": \"concluido\", \"total\": {len(todas_licitacoes)}, \"redirect\": \"/resultados\"}}\n\n"

    return StreamingResponse(
        gerar_eventos(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


# =====================================================
# ROTA: BUSCAR (POST normal — mantido para segurança)
# =====================================================

@app.post("/buscar", response_class=HTMLResponse)
async def buscar(request: Request):
    form = await request.form()
    termo = form.get("termo", "").strip()
    if not termo:
        return RedirectResponse("/", status_code=303)
    # Redireciona para o fluxo normal sem variações
    return RedirectResponse("/", status_code=303)


# =====================================================
# ROTA: RESULTADOS
# =====================================================

@app.get("/resultados", response_class=HTMLResponse)
async def resultados(request: Request):
    if not _ultima_busca:
        return RedirectResponse("/", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="resultados.html",
        context={
            "estados": ESTADOS,
            **_ultima_busca,
        },
    )


# =====================================================
# ROTA: EXPORTAR EXCEL
# =====================================================

@app.get("/exportar/excel")
async def exportar_excel():
    if not _ultima_busca:
        return RedirectResponse("/", status_code=303)

    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        return HTMLResponse("Instale openpyxl: pip install openpyxl", status_code=500)

    licitacoes = _ultima_busca.get("licitacoes", [])
    termo      = _ultima_busca.get("termo", "licitacoes")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Licitações PNCP"

    cabecalhos = ["UF", "Município", "Status", "Prazo", "Encerramento",
                  "Publicação", "Objeto", "Valor Estimado", "Modalidade", "Órgão", "Link"]

    fill_header = PatternFill("solid", fgColor="1e3a8a")
    font_header = Font(color="FFFFFF", bold=True)
    for col, cab in enumerate(cabecalhos, 1):
        cell = ws.cell(row=1, column=col, value=cab)
        cell.fill      = fill_header
        cell.font      = font_header
        cell.alignment = Alignment(horizontal="center")

    for row, l in enumerate(licitacoes, 2):
        ws.cell(row=row, column=1,  value=l["uf"])
        ws.cell(row=row, column=2,  value=l["municipio"])
        ws.cell(row=row, column=3,  value=l["status"])
        ws.cell(row=row, column=4,  value=l["prazo"])
        ws.cell(row=row, column=5,  value=l["encerramento"])
        ws.cell(row=row, column=6,  value=l["publicacao"])
        ws.cell(row=row, column=7,  value=l["objeto"])
        ws.cell(row=row, column=8,  value=l["valor"])
        ws.cell(row=row, column=9,  value=l["modalidade"])
        ws.cell(row=row, column=10, value=l["orgao"])
        ws.cell(row=row, column=11, value=l["link"])

    larguras = [6, 22, 12, 14, 20, 20, 70, 18, 18, 45, 55]
    for col, larg in enumerate(larguras, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = larg

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    nome_arquivo = f"licitacoes_{termo.replace(' ', '_')}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={nome_arquivo}"},
    )


# =====================================================
# INICIALIZAÇÃO LOCAL
# =====================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8001, reload=False)
