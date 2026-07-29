import requests
import json

# Busca todos os estados
estados = requests.get(
    "https://servicodados.ibge.gov.br/api/v1/localidades/estados"
).json()

resultado = {}

for estado in estados:
    uf = estado["sigla"]

    print(f"Baixando {uf}...")

    municipios = requests.get(
        f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}/municipios"
    ).json()

    resultado[uf] = {
        "id": estado["id"],
        "nome": estado["nome"],
        "municipios": [
            {
                "id": m["id"],
                "nome": m["nome"]
            }
            for m in municipios
        ]
    }

with open("ibge.json", "w", encoding="utf-8") as f:
    json.dump(resultado, f, ensure_ascii=False, indent=4)

print("Concluído!")