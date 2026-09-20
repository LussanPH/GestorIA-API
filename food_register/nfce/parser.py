import json

import requests

from .schema import NFCe_SCHEMA


OLLAMA_URL = "http://localhost:11434/api/chat"

MODEL_NAME = "richardyoung/schematron-8b:Q4_K_M"


def extrair_nfce(html):

    schema = json.dumps(
        NFCe_SCHEMA,
        ensure_ascii=False
    )

    prompt = f"""
Você vai receber uma página HTML de uma NFC-e.

Extraia os dados da nota fiscal de acordo
com o JSON Schema abaixo.

Retorne SOMENTE JSON válido.

Não adicione explicações.
Não adicione markdown.
Não adicione texto antes ou depois do JSON.

JSON Schema:

{schema}

HTML:

{html}
"""


    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL_NAME,

            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],

            "stream": False,

            "options": {
                "temperature": 0
            }
        },

        timeout=120
    )


    response.raise_for_status()


    data = response.json()

    content = data["message"]["content"]

    return json.loads(content)