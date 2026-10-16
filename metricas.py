import json, unicodedata, re
from sklearn.metrics import confusion_matrix, classification_report
from rapidfuzz import fuzz

def normalizar(s):
    if not s: return ""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", s.lower())).strip()


def analisar(products, y_true, y_pred, limiar=85):
    # 1. JSON Pass
    ok = [r for r in products if r.get("json_pass")]
    print(f"JSON Pass: {len(ok)/len(products):.1%}  ({len(products)-len(ok)} falhas)")

    # 2. Classificação binária
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[False, True]).ravel()

    print(f"\nTP={tp}  FP={fp}  FN={fn}  TN={tn}")
    print(classification_report(y_true, y_pred, labels=[False, True],
          target_names=["nao-alimenticio", "alimenticio"], digits=3))

    # 3. Extração (só onde a referência é alimentícia)
    alim = [r for r in ok if r["esperado"]["alimenticio"]]
    acertos_m = acertos_p = perfeitos = fieis = com_marca = 0

    for r in alim:
        e, p = r["esperado"], r["previsto"]
        m_ok = normalizar(p["marca"]) == normalizar(e["marca"])
        p_ok = fuzz.token_sort_ratio(normalizar(p["produto"]),
                                     normalizar(e["produto"])) >= limiar
        acertos_m += m_ok
        acertos_p += p_ok
        perfeitos += (m_ok and p_ok and p["alimenticio"] == e["alimenticio"])
        if p["marca"]:
            com_marca += 1
            fieis += normalizar(p["marca"]) in normalizar(r["descricao_nf"])

    n = len(alim)
    print(f"Value Accuracy (marca):   {acertos_m/n:.1%}")
    print(f"Value Accuracy (produto): {acertos_p/n:.1%}")
    print(f"Faithfulness:             {fieis/com_marca:.1%}" if com_marca else "")
    print(f"Perfect Response:         {perfeitos/n:.1%}")

    # 4. Onde errou — a parte que guia o próximo prompt
    print("\nFalsos negativos (sumiram da tela):")
    for r in ok:
        if r["esperado"]["alimenticio"] and not r["previsto"]["alimenticio"]:
            print(f'  {r["descricao_nf"]}')


y_true = []

y_pred = []

products = []

with open("output_golden_set_dev.jsonl", "r", encoding="utf-8") as input:
    for linha in input:
        linha.strip()
        linha = json.loads(linha)
        products.append(linha)
        y_true.append(linha["esperado"]["alimenticio"])
        y_pred.append(linha["previsto"]["alimenticio"])

for i, pred in enumerate(y_pred):
    if y_pred[i] != y_true[i]:
        print(products[i])
            


analisar(products, y_true, y_pred)