import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Força carregar o .env da pasta do projeto independente de onde o script é chamado
load_dotenv(dotenv_path=Path(__file__).parent / ".env")

from google import genai

_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError(
                "GOOGLE_API_KEY não encontrada. "
                "Verifique se o arquivo .env está na raiz do projeto com GOOGLE_API_KEY=sua_chave"
            )
        _client = genai.Client(api_key=api_key)
    return _client


PROMPT_EXPANSAO = """
Você é um especialista em licitações públicas brasileiras.

O usuário quer buscar licitações com o termo: "{termo}"

Gere variações de busca para encontrar o máximo de editais relevantes.
Considere:
- Variações ortográficas (notebook / note book)
- Sinônimos (notebook / laptop / computador portátil)
- Especificações comuns (notebook i5 / notebook intel core i5)
- Abreviações e siglas
- NÃO inclua termos genéricos demais que tragam ruído

Retorne APENAS um JSON válido, sem markdown, sem explicação, neste formato exato:
{{
  "termos_incluir": ["variação 1", "variação 2", "variação 3", "variação 4"],
  "termos_excluir": ["termo ruído 1", "termo ruído 2"]
}}

Máximo 4 termos para incluir e 3 para excluir.
O termo original NÃO deve aparecer na lista — ele já será buscado separadamente.
"""


def expandir_termo(termo: str) -> dict:
    try:
        client = _get_client()
        prompt = PROMPT_EXPANSAO.format(termo=termo)

        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt,
        )

        texto = response.text.strip()

        # Remove markdown se vier com ```json ... ```
        if "```" in texto:
            partes = texto.split("```")
            for parte in partes:
                parte = parte.strip()
                if parte.startswith("json"):
                    parte = parte[4:].strip()
                if parte.startswith("{"):
                    texto = parte
                    break

        dados = json.loads(texto)

        return {
            "termos_incluir": dados.get("termos_incluir", [])[:4],
            "termos_excluir": dados.get("termos_excluir", [])[:3],
        }

    except Exception as e:
        print(f"[expansor] Erro ao expandir termo: {e}")
        return {
            "termos_incluir": [],
            "termos_excluir": [],
            "erro": str(e),
        }
