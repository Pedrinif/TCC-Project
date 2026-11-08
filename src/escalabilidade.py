import time
import tracemalloc

import pandas as pd

from src.motor import MotorProcesso
from tests.helpers import proc_simples


def _medir(processo):
    tracemalloc.start()
    inicio = time.perf_counter()
    MotorProcesso(processo, seed=1000).executar()
    duracao = time.perf_counter() - inicio
    _, pico = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return duracao, pico / (1024 * 1024)


def _processo_atividade(n, tipo, entidades=100):
    atividades = []
    for i in range(n):
        item = {"id": f"a{i}", "duracao": 1.0}
        if tipo == "cadeia":
            if i > 0:
                item["predecessoras"] = [f"a{i - 1}"]
        elif i == 0:
            pass
        elif i < n - 1:
            item["predecessoras"] = ["a0"]
        else:
            item["predecessoras"] = [f"a{i - 1 - j}" for j in range(i - 1)]
        atividades.append(item)
    return proc_simples(
        atividades,
        chegadas={"tipo": "lotes", "tamanhos": [entidades], "n_lotes": 1},
    )


def executar_benchmark():
    atividades_csv = []
    entidades_csv = []

    for tipo, tamanhos in (
        ("cadeia", [10, 20, 40, 80, 160]),
        ("camadas", [10, 20, 40, 80, 160]),
    ):
        for n in tamanhos:
            processo = _processo_atividade(n, tipo)
            tempo, memoria = _medir(processo)
            atividades_csv.append({
                "estrutura": tipo,
                "n_atividades": n,
                "tempo_s": tempo,
                "memoria_mb": memoria,
            })

    for n in [100, 500, 1000, 2500, 5000]:
        processo = _processo_atividade(10, "cadeia", entidades=n)
        tempo, memoria = _medir(processo)
        entidades_csv.append({
            "n_entidades": n,
            "tempo_s": tempo,
            "memoria_mb": memoria,
        })

    return pd.DataFrame(atividades_csv), pd.DataFrame(entidades_csv)


def imprimir_inclinacoes(df_atividades, df_entidades):
    print("\nInclinacoes log-log (p = dlog(metrica)/dlog(tamanho))")
    for estrutura in ("cadeia", "camadas"):
        dados = df_atividades[df_atividades["estrutura"] == estrutura]
        for coluna, rotulo in (("tempo_s", "tempo"), ("memoria_mb", "memoria")):
            p = dados["n_atividades"].apply(__import__("math").log).to_frame("x")
            p["y"] = dados[coluna].apply(__import__("math").log)
            inclinacao = (p["x"].corr(p["y"]) * p["y"].std() / p["x"].std())
            print(f"{estrutura} - {rotulo}: {inclinacao:.2f}")
    for coluna, rotulo in (("tempo_s", "tempo"), ("memoria_mb", "memoria")):
        x = df_entidades["n_entidades"].apply(__import__("math").log)
        y = df_entidades[coluna].apply(__import__("math").log)
        inclinacao = x.corr(y) * y.std() / x.std()
        print(f"entidades - {rotulo}: {inclinacao:.2f}")
