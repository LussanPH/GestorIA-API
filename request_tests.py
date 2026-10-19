import requests as req
import json

credentials = {
    "email":"pedrohenriquelunalessa@gmail.com",
    "password":"pedro123456",
    "re_password":"pedro123456",
    "nome_completo":"Pedro Henrique Luna Lessa"
}

login = {
    "email":"pedrohenriquelunalessa@gmail.com",
    "password":"pedro123456"
}

header = {
    'Authorization':'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzkyNTA1MTg2LCJpYXQiOjE3OTI0MTg3ODcsImp0aSI6ImRhYTZkM2I2ZWZiODQ1OWVhNWY3NzkwNjA5ZjExZThiIiwidXNlcl9pZCI6IjEifQ.8zBr-Qke91jHdEc6-ZyyicYPu_71vyZi5p3Ion5pVSE'
}

refresh_token_logout = {
    'refresh':'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoicmVmcmVzaCIsImV4cCI6MTc5MzAyMzU4NiwiaWF0IjoxNzkyNDE4Nzg2LCJqdGkiOiJkMDc5ODFhNTI1MTk0NDViYjFhZWRmNGJmMTdlZGIwZiIsInVzZXJfaWQiOiIxIn0.EbNbsIPYfrSg94vhCVGuK4HuoT5mV5Bvf6dk8bxNH6c'
}

#Criando Usuário
"""
resposta = req.post("http://localhost:8000/auth/users/", json=credentials)

print(resposta.json())
"""
#Realizando Login
"""
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