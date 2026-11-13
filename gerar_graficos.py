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


def _salvar(fig, arquivo: str) -> None:
    fig.tight_layout()
    fig.savefig(os.path.join(PASTA_GRAFICOS, arquivo), dpi=300, bbox_inches="tight")
    plt.close(fig)


def figura_espera_conferentes() -> None:
    """Figura 12: espera média em função do número de conferentes (M4, experimento 2), com faixa de IC."""
    v = pd.read_csv(os.path.join(PASTA_RESULTADOS, "varredura_conferente.csv"))
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(v["quantidade"], v["espera_pool"], marker="o", linewidth=2, color="#4C78A8")
    ax.fill_between(v["quantidade"], v["espera_pool"] - v["espera_pool_ic"],
                    v["espera_pool"] + v["espera_pool_ic"], alpha=0.25, color="#4C78A8", label="IC 95%")
    ax.set_xlabel("Número de conferentes")
    ax.set_ylabel("Espera média na conferência (s)")
    ax.set_title("M4 - Espera média em função do número de conferentes")
    ax.legend()
    ax.grid(alpha=0.3)
    _salvar(fig, "fig12_espera_conferentes.png")


def figura_alocacao() -> None:
    """Figura 9: custo (soma de trabalhadores) e número de avaliações de cada método, nos limites de 120 s e 200 s."""
    fig, eixos = plt.subplots(2, 2, figsize=(9, 6))
    for coluna, limite in enumerate((120, 200)):
        d = pd.read_csv(os.path.join(PASTA_RESULTADOS, f"otimizacao_exp2_{limite}.csv"))
        eixos[0][coluna].bar(d["Método"], d["Custo"], color="#4C78A8")
        eixos[0][coluna].set_title(f"Limite de {limite} s")
        eixos[0][coluna].set_ylabel("Custo (trabalhadores)")
        eixos[1][coluna].bar(d["Método"], d["Avaliações"], color="#F58518")
        eixos[1][coluna].set_ylabel("Avaliações")
        eixos[1][coluna].set_yscale("log")
        eixos[1][coluna].set_ylim(bottom=1)  # barras partem de 1, senão a escala log corta as menores
        for linha in (0, 1):
            eixos[linha][coluna].grid(axis="y", alpha=0.3)
    fig.suptitle("M4 - Alocação de trabalhadores: custo e avaliações por método")
    _salvar(fig, "fig09_alocacao_custo_avaliacoes.png")


def figura_estacoes_m6() -> None:
    """Figura 13: utilização e espera média na fila de cada estação da linha de montagem (M6)."""
    d = pd.read_csv(os.path.join(PASTA_RESULTADOS, "validacao_salbp.csv"))
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.5))
    ax1.bar(d["estacao"], 100 * d["utilizacao"], color="#4C78A8")
    ax1.set_xlabel("Estação")
    ax1.set_ylabel("Utilização (%)")
    ax1.set_title("Utilização por estação")
    ax2.bar(d["estacao"], d["espera_media_na_fila"], color="#F58518")
    ax2.set_xlabel("Estação")
    ax2.set_ylabel("Espera média na fila (u.t.)")
    ax2.set_title("Espera por estação")
    for ax in (ax1, ax2):
        ax.set_xticks(list(d["estacao"]))
        ax.grid(axis="y", alpha=0.3)
    _salvar(fig, "fig13_estacoes_m6.png")


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

    figura_espera_conferentes()
    figura_alocacao()
    figura_estacoes_m6()

    print(f"Gráficos salvos em {PASTA_GRAFICOS}")


if __name__ == "__main__":
    main()
