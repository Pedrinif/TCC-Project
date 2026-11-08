"""
Escalabilidade (Seção 3.11): processos sintéticos de tamanho crescente, medindo o tempo da
análise estrutural, o tempo da simulação e o pico de memória.

O tempo é medido com o tracemalloc DESLIGADO; a memória, numa execução à parte com ele ligado
(o tracemalloc deixa o Python mais lento e distorceria o tempo).
"""
import math
import time
import tracemalloc

import pandas as pd

from src.estrutural import analise_estrutural
from src.motor import MotorProcesso
from src.processo import processo_de_dict

TAMANHOS_ATIVIDADES = [10, 20, 40, 80, 160]
TAMANHOS_ENTIDADES = [100, 500, 1000, 2500, 5000]


def _processo_sintetico(n: int, forma: str, entidades: int = 100):
    """
    'cadeia': a0 → a1 → ... → a(n-1).
    'camadas': a0 abre n-2 atividades em paralelo, que se juntam na última (DAG em camadas).
    """
    atividades = []
    for i in range(n):
        item = {"id": f"a{i}", "duracao": 1.0}
        if forma == "cadeia" and i > 0:
            item["predecessoras"] = [f"a{i - 1}"]
        elif forma == "camadas" and 0 < i < n - 1:
            item["predecessoras"] = ["a0"]
        elif forma == "camadas" and i == n - 1:
            item["predecessoras"] = [f"a{j}" for j in range(1, n - 1)]
        atividades.append(item)
    return processo_de_dict({
        "nome": f"sintetico_{forma}_{n}", "unidade_tempo": "u.t.",
        "chegadas": {"tipo": "lotes", "tamanhos": [entidades], "n_lotes": 1},
        "atividades": atividades,
    })


def _medir(processo, repeticoes_estrutural: int = 20):
    """(tempo da análise estrutural, tempo da simulação, pico de memória da simulação em MB)."""
    inicio = time.perf_counter()
    for _ in range(repeticoes_estrutural):  # é rápida demais para uma medição só
        analise_estrutural(processo)
    t_estrutural = (time.perf_counter() - inicio) / repeticoes_estrutural

    inicio = time.perf_counter()
    MotorProcesso(processo.copia(), seed=1000).executar()
    t_simulacao = time.perf_counter() - inicio

    tracemalloc.start()
    MotorProcesso(processo.copia(), seed=1000).executar()
    _, pico = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return t_estrutural, t_simulacao, pico / (1024 * 1024)


def executar_benchmark():
    """Mede os processos sintéticos. Devolve (variando atividades, variando entidades)."""
    por_atividades = []
    for forma in ("cadeia", "camadas"):
        for n in TAMANHOS_ATIVIDADES:
            t_est, t_sim, mem = _medir(_processo_sintetico(n, forma))
            por_atividades.append({"estrutura": forma, "n_atividades": n, "tempo_estrutural_s": t_est,
                                   "tempo_s": t_sim, "memoria_mb": mem})

    por_entidades = []
    for n in TAMANHOS_ENTIDADES:
        t_est, t_sim, mem = _medir(_processo_sintetico(10, "cadeia", entidades=n))
        por_entidades.append({"n_entidades": n, "tempo_s": t_sim, "memoria_mb": mem})

    return pd.DataFrame(por_atividades), pd.DataFrame(por_entidades)


def inclinacao_log_log(x, y) -> float:
    """Expoente p da lei de crescimento: inclinação da reta de regressão em log(y) × log(x)."""
    lx = [math.log(float(v)) for v in x]
    ly = [math.log(float(v)) for v in y]
    mx, my = sum(lx) / len(lx), sum(ly) / len(ly)
    return (sum((a - mx) * (b - my) for a, b in zip(lx, ly))
            / sum((a - mx) ** 2 for a in lx))


def expoentes(df_atividades: pd.DataFrame, df_entidades: pd.DataFrame) -> pd.DataFrame:
    """Expoente medido de cada grandeza, ao lado do esperado pela Tabela 9 (crescimento linear)."""
    linhas = []
    for forma in ("cadeia", "camadas"):
        d = df_atividades[df_atividades["estrutura"] == forma]
        for coluna, grandeza in (("tempo_estrutural_s", "analise_estrutural"),
                                 ("tempo_s", "tempo_simulacao"), ("memoria_mb", "memoria")):
            linhas.append({"forma_processo": forma, "dimensao": "numero_atividades", "grandeza": grandeza,
                           "expoente_medido": round(inclinacao_log_log(d["n_atividades"], d[coluna]), 2),
                           "expoente_esperado": 1.00})
    for coluna, grandeza in (("tempo_s", "tempo_simulacao"), ("memoria_mb", "memoria")):
        linhas.append({"forma_processo": "cadeia", "dimensao": "numero_entidades", "grandeza": grandeza,
                       "expoente_medido": round(inclinacao_log_log(df_entidades["n_entidades"],
                                                                   df_entidades[coluna]), 2),
                       "expoente_esperado": 1.00})
    return pd.DataFrame(linhas)
