import os

import matplotlib.pyplot as plt
import pandas as pd


PASTA_RESULTADOS = "resultados"
PASTA_GRAFICOS = os.path.join(PASTA_RESULTADOS, "graficos")


def barras_agrupadas(
    df: pd.DataFrame,
    categorias: list[str],
    publicado: pd.Series,
    simulado: pd.Series,
    ic95: pd.Series,
    titulo: str,
    arquivo: str,
) -> None:
    x = range(len(categorias))
    largura = 0.34

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar([i - largura / 2 for i in x], publicado, largura, label="Publicado", color="#4C78A8")
    ax.bar(
        [i + largura / 2 for i in x],
        simulado,
        largura,
        yerr=ic95,
        capsize=5,
        label="Simulado",
        color="#F58518",
    )

    ax.set_xticks(list(x), categorias)
    ax.set_ylabel("Tempo total (minutos)")
    ax.set_title(titulo)
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(PASTA_GRAFICOS, arquivo), dpi=300, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    os.makedirs(PASTA_GRAFICOS, exist_ok=True)

    recebimento = pd.read_csv(os.path.join(PASTA_RESULTADOS, "validacao_recebimento.csv"))
    recebimento["categoria"] = recebimento.apply(
        lambda linha: f"{linha['experimento']} ({int(linha['paletes'])} paletes)",
        axis=1,
    )
    barras_agrupadas(
        recebimento,
        recebimento["categoria"].tolist(),
        recebimento["publicado_min"],
        recebimento["simulado_min"],
        recebimento["ic95_min"],
        "M4 - Recebimento de paletes: publicado e simulado",
        "m4_recebimento.png",
    )

    turnaround = pd.read_csv(os.path.join(PASTA_RESULTADOS, "validacao_turnaround.csv"))
    barras_agrupadas(
        turnaround,
        turnaround["ocupacao"].astype(str).tolist(),
        turnaround["publicado_min"],
        turnaround["simulado_min"],
        turnaround["ic95_min"],
        "M5 - Turnaround: publicado e simulado",
        "m5_turnaround.png",
    )

    modelos_base = pd.read_csv(os.path.join(PASTA_RESULTADOS, "modelos_base.csv"))
    modelos = [
        ("M1 Simples", "#4C78A8"),
        ("M2 Multiplas Docas", "#F58518"),
        ("M3 Pipeline", "#54A24B"),
    ]

    fig, ax = plt.subplots(figsize=(8, 5))
    for modelo, cor in modelos:
        dados = modelos_base.loc[modelos_base["modelo"] == modelo]
        ax.errorbar(
            dados["capacidade"],
            dados["espera_total"],
            yerr=dados["espera_total_ic"],
            marker="o",
            linewidth=2,
            capsize=4,
            label=modelo,
            color=cor,
        )

    ax.axvline(3.5, color="#888888", linestyle="--", linewidth=1.2)
    ax.annotate(
        "Carga/servidor = 1\n(em capacidade 3,5)",
        xy=(3.5, ax.get_ylim()[0]),
        xytext=(4.1, 0.035),
        textcoords="axes fraction",
        ha="left",
        va="bottom",
    )
    ax.set_yscale("log")
    ax.set_xlabel("Capacidade da etapa crítica")
    ax.set_ylabel("Espera total (u.t., escala logarítmica)")
    ax.set_title("Modelos base M1–M3: espera em função da capacidade")
    ax.set_xticks([1, 2, 3, 4, 5, 6, 8])
    ax.legend()
    ax.grid(axis="both", which="both", alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(PASTA_GRAFICOS, "m1_m2_m3_modelos_base.png"), dpi=300, bbox_inches="tight")
    plt.close(fig)

    print(f"Gráficos salvos em {PASTA_GRAFICOS}")


if __name__ == "__main__":
    main()
