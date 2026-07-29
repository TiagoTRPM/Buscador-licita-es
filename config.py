# config.py
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# =====================================================
# PASTAS
# =====================================================
PASTA_TEMP  = os.path.join(BASE_DIR, "temp")
PASTA_SAIDA = os.path.join(BASE_DIR, "saida")

# =====================================================
# API PNCP
# =====================================================
TAMANHO_PAGINA = 200

# =====================================================
# ESTADOS DISPONÍVEIS
# =====================================================
ESTADOS = [
    "PR", "SP", "SC", "RS", "RJ", "MG",
    "BA", "GO", "PE", "ES", "CE", "AM",
    "PA", "DF", "MT", "MS", "TO", "TODOS"
]

# =====================================================
# MODALIDADES DISPONÍVEIS
# =====================================================
MODALIDADES_DISPONIVEIS = {
    1: "Leilão",
    4: "Concorrência",
    5: "Pregão Eletrônico",
    6: "Credenciamento",
    7: "Pregão Presencial",
    8: "Dispensa",
    9: "Inexigibilidade",
}
