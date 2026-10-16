import matplotlib.pyplot as plt
import numpy as np
 
 
def plot_matriz_confusao(
    vp: int,
    fp: int,
    vn: int,
    fn: int,
    labels=("Negativo", "Positivo"),
    titulo="Matriz de Confusão",
    caminho_saida=None,
):
    # Convenção: linha = classe real, coluna = classe prevista
    matriz = np.array([
        [vn, fp],
        [fn, vp],
    ])
 
    total = matriz.sum()
    acuracia = (vp + vn) / total if total else 0
 
    fig, ax = plt.subplots(figsize=(5, 5))
    im = ax.imshow(matriz, cmap="Blues")
 
    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xticklabels(labels)
    ax.set_yticklabels(labels)
    ax.set_xlabel("Previsto")
    ax.set_ylabel("Real")
    ax.set_title(f"{titulo}\nAcurácia: {acuracia:.1%}")
 
    # Anota cada célula com o valor absoluto e o percentual do total
    for i in range(2):
        for j in range(2):
            valor = matriz[i, j]
            percentual = valor / total if total else 0
            cor_texto = "white" if valor > matriz.max() / 2 else "black"
            ax.text(
                j, i,
                f"{valor}\n({percentual:.1%})",
                ha="center", va="center",
                color=cor_texto, fontsize=12,
            )
 
    fig.colorbar(im, ax=ax, label="Quantidade")
    fig.tight_layout()
 
    if caminho_saida:
        fig.savefig(caminho_saida, dpi=150, bbox_inches="tight")
 
    return fig, ax
 
 
plot_matriz_confusao(
    vp=298, fp=1, vn=201, fn=0,
    labels=("Não-alimentício", "Alimentício"),
    titulo="Classificação de Produtos",
    caminho_saida="matriz_confusao.png",
)
plt.show()