import requests as req
import json

credentials = {
    "email":"usuario@gmail.com",
    "password":"pedro123456",
    "re_password":"pedro123456",
    "nome_completo":"Pedro Henrique Luna Lessa"
}

login = {
    "email":"usuario@gmail.com",
    "password":"pedro123456"
}

header = {
    'Authorization':'Bearer SEU_ACCESS_TOKEN'
}

refresh_token_logout = {
    'refresh':'SEU_REFRESH_TOKEN'
}

#Criando Usuário
"""
resposta = req.post("http://localhost:8000/auth/users/", json=credentials)

print(resposta.json())
"""

"""
#Realizando Login
resposta = req.post("http://localhost:8000/auth/jwt/create", json=login)

print(resposta.json())
"""


#Acessando rotas seguras
"""
resposta = req.get("http://localhost:8000/auth/users/me", headers=header)

print(resposta.json())
"""

#Rota de Logout
"""
resposta = req.post("http://localhost:8000/auth/jwt/logout/", json=refresh_token_logout)

if resposta.status_code == 200:
    print("Logout realizado com sucesso!")
"""

#Teste extração nota fiscal
with open("nota.json", encoding="utf-8") as f:
   nota = json.load(f)
   
resposta = req.post("http://localhost:8000/api/produtos/extrair/", json=nota, headers=header)

print(resposta.status_code)
print(json.dumps(resposta.json(), indent=2, ensure_ascii=False))