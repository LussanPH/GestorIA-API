from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openrouter import ChatOpenRouter
from langchain_core.prompts import ChatPromptTemplate as CPT, FewShotChatMessagePromptTemplate
from dotenv import load_dotenv
from formato_json import ItemNotaFiscal
import json
from pathlib import Path
from datetime import datetime, timedelta

load_dotenv()


def llm_choice(provider):
    if provider == 0:
        return ChatOpenAI(model="gpt-4o-mini", temperature=0)
    elif provider == 1:
        return ChatGoogleGenerativeAI(model="gemini-3.6-flash", temperature=0)
    else:
        return ChatOpenRouter(model="meta-llama/llama-3.1-8b-instruct", temperature=0, openrouter_provider={"require_parameters": True})
    

def load(path):
    with open(path, encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if linha:
                yield json.loads(linha)
                
                
def evaluate(input, output, chain):
    inicio = datetime.now()
    feitos = set()
    if Path(output).exists():
        feitos = {r["id"] for r in load(output)}
        
    with open(output, "a", encoding="utf-8") as out:
        for item in load(input):
            if item["id"] in feitos:
                continue
            
            registro = {"id": item["id"], "descricao_nf": item["descricao_nf"],
                        "esperado": item["esperado"]}
        
            #try:
            resultado = chain.invoke({"entrada": item["descricao_nf"]})
            if resultado["parsing_error"]:
                registro["json_pass"] = False
                registro["erro"] = str(resultado["parsing_error"])
            
            else:
                registro["json_pass"] = True
                registro["previsto"] = resultado["parsed"].model_dump()
            
            #except Exception as e:
                #registro["json_pass"] = False
                #registro["erro"] = f"{type(e).__name__}: {e}"
        
            out.write(json.dumps(registro, ensure_ascii=False) + "\n")
            out.flush()
    
    fim = datetime.now()
    duracao = fim - inicio
    print(duracao)
        


prompt_text = """Você extrai dados estruturados de itens de notas fiscais brasileiras.

A entrada é o nome do produto como aparece na NF: texto curto, em caixa alta, \
com abreviações e sem acentuação.

Regras:
1. Primeiro determine se o item é alimentício.
2. Se NÃO for alimentício, retorne alimenticio=false e deixe produto e marca \
como null. Não tente extrair nada nesse caso.
3. Se for alimentício, expanda as abreviações do nome e identifique a marca.
4. Extraia a marca apenas se ela estiver presente no texto. Nunca deduza a marca \
a partir do tipo de produto. Se não houver marca identificável, use null.
5. Não invente informação que não esteja no texto de entrada."""

examples = [
    ("ARROZ TIO JOAO T1 5KG",        {"alimenticio": True,  "produto": "Arroz Branco Tipo 1", "marca": "Tio João"}),
    ("LEITE COND MOCA 395G",         {"alimenticio": True,  "produto": "Leite Condensado", "marca": "Moça"}),
    ("REFRIG COCA COLA LT 350ML",    {"alimenticio": True,  "produto": "Refrigerante de Cola", "marca": "Coca-Cola"}),
    ("BISC REC CHOC BAUDUCCO 140G",  {"alimenticio": True,  "produto": "Biscoito Recheado de Chocolate", "marca": "Bauducco"}),
    ("TOMATE ITALIANO KG",           {"alimenticio": True,  "produto": "Tomate Italiano", "marca": None}),
    ("CAFE TORR MOIDO 500G",         {"alimenticio": True,  "produto": "Café Torrado e Moído", "marca": None}),
    ("DETERG LIQ YPE NEUTRO 500ML",  {"alimenticio": False, "produto": None, "marca": None}),
    ("AGUA SANITARIA QBOA 1L",       {"alimenticio": False, "produto": None, "marca": None}),
    ("SHAMPOO SEDA ANTICASPA 325ML", {"alimenticio": False, "produto": None, "marca": None}),
    ("RACAO PEDIGREE ADULTO 3KG",    {"alimenticio": False, "produto": None, "marca": None}),    
]


template_example = CPT.from_messages([
    ("human", "Nome na NF: {entrada}"),
    ("ai", "{saída}")
])

few_shot = FewShotChatMessagePromptTemplate(
    example_prompt=template_example,
    examples=[
        {"entrada": e, "saída": json.dumps(s, ensure_ascii=False)}
        for e, s in examples
    ],
)

prompt = CPT.from_messages([
    ("system", prompt_text),
    few_shot,
    ("human", "Nome na NF: {entrada}")
])


llm = llm_choice(2)

chain = prompt | llm.with_structured_output(ItemNotaFiscal, include_raw=True)

evaluate("golden_set_dev.jsonl", "output_golden_set_dev.jsonl", chain)