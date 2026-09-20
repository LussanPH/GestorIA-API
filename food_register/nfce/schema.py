NFCe_SCHEMA = {
    "type": "object",
    "properties": {
        "Chave de acesso": {
            "type": "string"
        },

        "Data da compra": {
            "type": "string"
        },

        "Valor total": {
            "type": "number"
        },

        "CNPJ": {
            "type": "string"
        },

        "Método de pagamento": {
            "type": "string"
        },

        "Produtos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "Nome": {
                        "type": "string"
                    },

                    "Valor total": {
                        "type": "number"
                    },

                    "Valor unitário": {
                        "type": "number"
                    },

                    "Un": {
                        "type": "string"
                    }
                },
                "required": [
                    "Nome",
                    "Valor total",
                    "Valor unitário",
                    "Un"
                ]
            }
        }
    },

    "required": [
        "Chave de acesso",
        "Data da compra",
        "Valor total",
        "CNPJ",
        "Método de pagamento",
        "Produtos"
    ]
}