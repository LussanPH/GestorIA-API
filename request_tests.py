import requests as req

credentials = {
    "email":"pedrohenriquelunalessa@gmail.com",
    "password":"pedro123456",
    "nome_completo":"Pedro Henrique Luna Lessa"
}

login = {
    "email":"pedrohenriquelunalessa@gmail.com",
    "password":"pedro123456"
}

header = {
    'Authorization':'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzg4ODEyODU0LCJpYXQiOjE3ODg3MjY0NTUsImp0aSI6IjFhNDZjNjM3ODA1ZDQ3N2JhMzBkMWQ0NWExZjk1YzBkIiwidXNlcl9pZCI6IjEifQ.3n8np4NNdYAmPRQwJWKg4_LW4CvzE2Dj6hNPXljQzkE'
}

refresh_token_logout = {
    'refresh':'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoicmVmcmVzaCIsImV4cCI6MTc4OTMzMTI1NCwiaWF0IjoxNzg4NzI2NDU0LCJqdGkiOiI2NTY5NTMxMDY1ODc0ZGRjYjQzMGQwNmZjNjFmZjY1MSIsInVzZXJfaWQiOiIxIn0.vx-Nud3v-ul2wwLM3HWPPPTweBotm5AGB9OQ_au0Z40'
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