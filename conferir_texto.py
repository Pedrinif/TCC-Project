"""
Confere se o programa ainda reproduz os números publicados no texto do TG.

  python conferir_texto.py              # conferências rápidas (Tabelas 6, 7, 8, 12 a 16, Seção 4.1.6, estrutura, testes)
  python conferir_texto.py --completo   # acrescenta a Tabela 17 (5 réplicas) e o recozimento com 10 sementes

Cada linha sai como OK ou DIFERENTE, com as casas decimais do texto. Nada é gravado em resultados/:
a escalabilidade é só lida de resultados/exponentes_escalabilidade.csv, sem rodar nada.
"""
import argparse
import math
import re
import subprocess
import sys

import pandas as pd

from src.estrutural import analise_estrutural
from src.otimizacao import busca_otimizada
from src.processo import carregar_processo
from src.replicacoes import varrer_pool
from validar import (calcular_basico, calcular_filas, calcular_intervencoes, calcular_recebimento,
                     calcular_salbp, calcular_turnaround)

RECEBIMENTO = "processos/recebimento_saderova.yaml"
resultados = []  # (ok, linha)


def _registrar(ok: bool, rotulo: str, obtido, esperado, nota: str = ""):
    resultados.append(ok)
    print(f"{'OK       ' if ok else 'DIFERENTE'}  {rotulo}: obtido {obtido} | texto {esperado}{nota}")


def conferir(rotulo, obtido, esperado, casas, tolerancia=None, dupla=False):
    """
    Compara 'obtido' com o valor do texto nas casas decimais do texto (esperado=None vale '≈0': < 0,01).
    dupla=True imita o texto da Tabela 13, que arredonda primeiro para 1 casa e depois para inteiro
    (o IC do M3 com capacidade 4 é 39,45, vira 39,5 e aparece como 40).
    """
    if dupla:
        obtido = math.floor(round(obtido, 1) + 0.5)
    if esperado is None:
        _registrar(abs(obtido) < 0.01, rotulo, f"{obtido:.4f}", "≈0")
        return
    if tolerancia is None:
        ok = abs(round(obtido, casas) - esperado) < 0.5 * 10 ** -casas
        nota = ""
    else:
        ok = abs(obtido - esperado) <= tolerancia
        nota = f" (tolerância de {tolerancia})"
    _registrar(ok, rotulo, f"{obtido:.{casas}f}", f"{esperado:.{casas}f}", nota)


def conferir_igual(rotulo, obtido, esperado):
    _registrar(obtido == esperado, rotulo, obtido, esperado)


def titulo(texto):
    print(f"\n== {texto}")


# ------------------------------------------------------------------ conferências
def tabela_6():
    titulo("Tabela 6 — filas M/M/1 e M/M/2 (12 réplicas, semente base 100)")
    df = calcular_filas()
    texto = [(2.333, 2.459, 0.123, 5.35), (0.961, 1.026, 0.102, 6.77)]
    for (_, l), (teorico, sim, ic, erro) in zip(df.iterrows(), texto):
        nome = f"M/M/{int(l['servidores'])}"
        conferir(f"{nome} Wq teórico", l["wq_teorico"], teorico, 3)
        conferir(f"{nome} Wq simulado", l["wq_simulado"], sim, 3)
        conferir(f"{nome} IC 95%", l["wq_simulado_ic"], ic, 3)
        # o texto calcula o erro em cima de valores um pouco diferentes dos impressos (5,38 e 6,80 com os mesmos)
        conferir(f"{nome} erro relativo (%)", l["erro_relativo_pct"], erro, 2, tolerancia=0.05)


def tabela_7():
    titulo("Tabela 7 — M4, tempo até a última conferência (30 réplicas)")
    df = calcular_recebimento(30, 1000).set_index("experimento")
    texto = {"exp1": (179.12, 0.11, 3.12, 35.39), "exp2": (178.10, 0.13, -9.90, 35.49),
             "exp3": (175.06, 0.08, 1.06, 35.42)}
    for exp, (sim, ic, dif, ciclo) in texto.items():
        l = df.loc[exp]
        conferir(f"{exp} simulado (min)", l["simulado_min"], sim, 2)
        conferir(f"{exp} IC 95%", l["ic95_min"], ic, 2)
        conferir(f"{exp} diferença (min)", l["diferenca_min"], dif, 2)
        conferir(f"{exp} ciclo médio (s)", l["ciclo_medio_s"], ciclo, 2)


def tabelas_8_e_secao_411():
    titulo("Tabela 8 (30 réplicas) e Seção 4.1.1 (200 réplicas) — M5, tempo total")
    for replicas, esperado in ((30, [(34.79, 1.01), (31.83, 0.93), (28.80, 0.81)]),
                               (200, [(34.27, 0.43), (31.32, 0.39), (28.48, 0.34)])):
        df = calcular_turnaround(replicas, 1000)
        for (_, l), (media, ic) in zip(df.iterrows(), esperado):
            conferir(f"{replicas} réplicas, {l['ocupacao']} tempo total", l["simulado_min"], media, 2)
            conferir(f"{replicas} réplicas, {l['ocupacao']} IC 95%", l["ic95_min"], ic, 2)
        if replicas == 30:
            for _, l in df.iterrows():
                conferir(f"30 réplicas, {l['ocupacao']} caminho dos passageiros crítico (%)",
                         l["critico_caminho_passageiros_pct"], 100.0, 1)
        else:
            for (_, l), pct in zip(df.iterrows(), (99.5, 99.0, 96.5)):
                conferir(f"200 réplicas, {l['ocupacao']} caminho dos passageiros crítico (%)",
                         l["critico_caminho_passageiros_pct"], pct, 1)


def tabelas_12_e_13():
    titulo("Tabelas 12 e 13 — modelos base (20 réplicas, 300 paletes)")
    df = calcular_basico(20, 1000)
    m1 = [(111440.3, 2004.8), (32800.7, 1913.4), (7967.8, 1263.3), (578.7, 193.4),
          (160.2, 29.8), (43.5, 8.4), (12.7, 4.2), (2.7, 1.2)]
    d = df[df["modelo"] == "M1 Simples"].set_index("capacidade")
    for cap, (media, ic) in enumerate(m1, start=1):
        conferir(f"M1 capacidade {cap} espera total", d.loc[cap, "espera_total"], media, 1)
        conferir(f"M1 capacidade {cap} IC 95%", d.loc[cap, "espera_total_ic"], ic, 1)
    m23 = {"M2 Multiplas Docas": [(6698, 1079), (612, 167), (147, 27)],
           "M3 Pipeline": [(2050, 603), (234, 40), (56, 14)]}
    for modelo, valores in m23.items():
        d = df[df["modelo"] == modelo].set_index("capacidade")
        for cap, (media, ic) in zip((3, 4, 5), valores):
            conferir(f"{modelo[:2]} capacidade {cap} espera total", d.loc[cap, "espera_total"], media, 0, dupla=True)
            conferir(f"{modelo[:2]} capacidade {cap} IC 95%", d.loc[cap, "espera_total_ic"], ic, 0, dupla=True)


def tabela_14():
    titulo("Tabela 14 — M4 exp2, empilhadeiras (20 réplicas)")
    proc = carregar_processo(RECEBIMENTO, "exp2")
    df = varrer_pool(proc, "empilhadeira", [1, 2, 3, 4], 20, 1000).set_index("quantidade")
    texto = {1: (444.4, 1.8, 31.6, 178.2), 2: (213.3, 0.9, 15.8, 170.3),
             3: (136.4, 0.5, 10.5, 167.5), 4: (97.9, 0.4, 7.9, 166.2)}
    for q, (espera, ic, util, fim) in texto.items():
        conferir(f"{q} empilhadeira(s) espera (s)", df.loc[q, "espera_pool"], espera, 1)
        conferir(f"{q} empilhadeira(s) IC 95%", df.loc[q, "espera_pool_ic"], ic, 1)
        conferir(f"{q} empilhadeira(s) utilização (%)", 100 * df.loc[q, "utilizacao"], util, 1)
        conferir(f"{q} empilhadeira(s) último término (min)", df.loc[q, "ultimo_fim"] / 60, fim, 1)


def tabela_15():
    titulo("Tabela 15 — M4 exp2, conferentes (20 réplicas)")
    proc = carregar_processo(RECEBIMENTO, "exp2")
    df = varrer_pool(proc, "conferente", [8, 12, 14, 16, 17, 18, 20], 20, 1000).set_index("quantidade")
    texto = {8: (366.15, 1.35, 193.78), 12: (108.10, 1.09, 183.78), 14: (46.93, 0.98, 179.77),
             16: (11.46, 0.90, 178.54), 17: (1.10, 0.39, 178.20), 18: (None, None, 178.16),
             20: (None, None, 178.16)}
    for q, (espera, ic, fim) in texto.items():
        conferir(f"{q} conferentes espera (s)", df.loc[q, "espera_pool"], espera, 2)
        if ic is not None:
            conferir(f"{q} conferentes IC 95%", df.loc[q, "espera_pool_ic"], ic, 2)
        conferir(f"{q} conferentes último término (min)", df.loc[q, "ultimo_fim"] / 60, fim, 2)
    conferir("8 conferentes utilização (%)", 100 * df.loc[8, "utilizacao"], 66.7, 1)
    conferir("16 conferentes utilização (%)", 100 * df.loc[16, "utilizacao"], 33.3, 1)


def tabela_16():
    titulo("Tabela 16 — M5, intervenções (200 réplicas)")
    df = calcular_intervencoes(200, 1000)
    texto = [(34.27, 0.43, 99.5, 0.0), (34.27, 0.43, 99.5, 0.0), (34.27, 0.43, 99.5, 0.0),
             (32.07, 0.40, 99.5, 0.0), (31.42, 0.39, 99.5, 0.0), (34.27, 0.43, 99.0, 0.5),
             (38.50, 0.60, 29.0, 71.0)]
    for (_, l), (tempo, ic, pas, cat) in zip(df.iterrows(), texto):
        r = l["intervencao"]
        conferir(f"{r} tempo total", l["tempo_total_min"], tempo, 2)
        conferir(f"{r} IC 95%", l["tempo_total_ic"], ic, 2)
        conferir(f"{r} passageiros crítico (%)", l["pct_passageiros_critico"], pas, 1)
        conferir(f"{r} catering crítico (%)", l["pct_catering_critico"], cat, 1)


def secao_416():
    titulo("Seção 4.1.6 — linha de montagem P25_14_ROSZIEG (30 réplicas, 500 produtos)")
    df, v, est, lb, ciclo = calcular_salbp("processos/salbp/P25_14_ROSZIEG.alb", None, 0.2, 500, 30, 1000, 10)
    conferir_igual("estações pela heurística (ótimo 10)", len(est), 10)
    conferir_igual("limite inferior", lb, 9)
    conferir("vazão simulada", v["vazao"], 0.0699, 4)
    conferir("meta de vazão (1/ciclo)", 1 / ciclo, 0.0714, 4)
    conferir("tempo no sistema", v["ts"], 152.55, 2)
    conferir("tempo no sistema, IC 95%", v["ts_ic"], 2.09, 2)
    util = df.set_index("estacao")["utilizacao"]
    conferir("utilização da estação 1 (%)", 100 * util[1], 49, 0)
    conferir("menor utilização das demais (%)", 100 * util.drop(1).min(), 84, 0)
    conferir("maior utilização das demais (%)", 100 * util.drop(1).max(), 98, 0)
    espera = df.set_index("estacao")["espera_media_na_fila"]
    for est_id, valor in ((2, 11.38), (4, 8.73), (6, 6.32)):
        conferir(f"espera na estação {est_id}", espera[est_id], valor, 2)
    maiores = sorted(espera.sort_values(ascending=False).index[:3])
    conferir_igual("três maiores esperas nas estações", maiores, [2, 4, 6])


def estrutura():
    titulo("Análise estrutural")
    m4 = carregar_processo(RECEBIMENTO, "exp2")
    est = analise_estrutural(m4)
    conferir("M4 ciclo médio da empilhadeira (s)", m4.atividades["ciclo_empilhadeira"].duracao.media(), 35.5, 1)
    conferir("M4 capacidade da empilhadeira (paletes/s)", est["capacidades"]["empilhadeira"], 0.0282, 4)
    conferir_igual("M4 conferentes para não limitar", est["trabalhadores_necessarios"]["conferente"], 17)
    m5 = analise_estrutural(carregar_processo("processos/turnaround_b737.yaml"))
    conferir("M5 caminho crítico (min)", m5["cpm"]["duracao_minima"], 34.0, 1)
    conferir_igual("M5 atividades críticas", m5["cpm"]["atividades_criticas"], ["desembarque", "limpeza", "embarque"])


def testes():
    titulo("Testes automatizados")
    saida = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q"],
                           capture_output=True, text=True).stdout
    achou = re.search(r"(\d+) tests? collected", saida)
    conferir_igual("testes coletados pelo pytest", int(achou.group(1)) if achou else None, 28)


def escalabilidade():
    titulo("Escalabilidade (só leitura de resultados/exponentes_escalabilidade.csv)")
    df = pd.read_csv("resultados/exponentes_escalabilidade.csv")

    def expoente(forma, dimensao, grandeza):
        l = df[(df["forma_processo"] == forma) & (df["dimensao"] == dimensao) & (df["grandeza"] == grandeza)]
        return float(l["expoente_medido"].iloc[0])

    for forma, dim, grandeza, valor in (
            ("cadeia", "numero_atividades", "tempo_simulacao", 1.02), ("cadeia", "numero_atividades", "memoria", 0.93),
            ("camadas", "numero_atividades", "tempo_simulacao", 1.02), ("camadas", "numero_atividades", "memoria", 1.02),
            ("cadeia", "numero_entidades", "tempo_simulacao", 1.10), ("cadeia", "numero_entidades", "memoria", 1.01)):
        conferir(f"{forma}, {dim}, {grandeza}", expoente(forma, dim, grandeza), valor, 2)


# ---- Tabela 17 e recozimento com várias sementes (só com --completo)
def tabela_17():
    titulo("Tabela 17 — alocação no M4 exp2 (5 réplicas, máximo de 24 por grupo)")
    proc = carregar_processo(RECEBIMENTO, "exp2")
    texto = {
        120: {"gulosa": (4, 18, 22, 114.55, 62), "exaustiva": (4, 18, 22, 114.55, 577),
              "recozimento": (5, 17, 22, 118.28, 81)},
        200: {"gulosa": (3, 13, 16, 185.25, 44), "exaustiva": (3, 13, 16, 185.25, 577),
              "recozimento": (3, 13, 16, 185.25, 81)},
    }
    for limite, metodos in texto.items():
        for metodo, (emp, conf, custo, espera, aval) in metodos.items():
            r = busca_otimizada(proc, limite, 24, 5, 1000, metodo)
            rotulo = f"{limite} s, {metodo}"
            conferir_igual(f"{rotulo} alocação (empilhadeiras, conferentes)",
                           (r["alocacao"]["empilhadeira"], r["alocacao"]["conferente"]), (emp, conf))
            conferir_igual(f"{rotulo} custo", r["custo"], custo)
            conferir(f"{rotulo} espera (s)", r["espera"], espera, 2)
            conferir_igual(f"{rotulo} avaliações (simulações distintas: {r['simulacoes_distintas']})",
                           r["avaliacoes"], aval)


def recozimento_sementes():
    titulo("Recozimento simulado com as sementes 1000 a 1009 (5 réplicas)")
    proc = carregar_processo(RECEBIMENTO, "exp2")
    for limite, viaveis_texto, custos_texto, media_texto in ((120, 4, [22, 22, 24, 24], 23.0),
                                                              (200, 6, None, 16.67)):
        rs = [busca_otimizada(proc, limite, 24, 5, semente, "recozimento") for semente in range(1000, 1010)]
        custos = sorted(r["custo"] for r in rs if r["viavel"])
        conferir_igual(f"{limite} s, soluções viáveis (de 10)", len(custos), viaveis_texto)
        if custos_texto:
            conferir_igual(f"{limite} s, custos das viáveis", custos, custos_texto)
        conferir(f"{limite} s, custo médio das viáveis", sum(custos) / len(custos), media_texto, 2)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--completo", action="store_true", help="inclui a Tabela 17 e o recozimento com 10 sementes (demora)")
    a = ap.parse_args()

    for conferencia in (tabela_6, tabela_7, tabelas_8_e_secao_411, tabelas_12_e_13, tabela_14, tabela_15,
                        tabela_16, secao_416, estrutura, testes, escalabilidade):
        conferencia()
    if a.completo:
        tabela_17()
        recozimento_sementes()

    print(f"\n{sum(resultados)} de {len(resultados)} conferem.")
    sys.exit(0 if all(resultados) else 1)


if __name__ == "__main__":
    main()
