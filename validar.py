"""
Validação dos processos reais contra os números publicados.

Uso (a partir da raiz do projeto):
  python validar.py recebimento                      # artigo de Saderova et al. (2022)
  python validar.py turnaround                       # artigo de San Antonio et al. (2017)
  python validar.py salbp --arquivo processos/salbp/P25_14_ROSZIEG.alb --otimo 10
  python validar.py varredura --processo processos/recebimento_saderova.yaml \
         --pool empilhadeira --de 1 --ate 4 --limite-espera 120
  python validar.py intervencoes --replicas 200      # Tabela 16 (turnaround)
  python validar.py filas                            # Tabela 6 (M/M/1 e M/M/2)

Opções comuns: --replicas N (padrão 30), --seed S (padrão 1000).
Cada comando imprime uma tabela e grava um CSV em resultados/.
"""
import argparse
import os

import pandas as pd

from src.estrutural import analise_estrutural
from src.processo import carregar_processo
from src.replicacoes import agregar, executar_replicas, ic95, recomendar, varrer_pool
from src.salbp import atribuir_estacoes, ler_instancia, limite_inferior, processo_da_linha
from src.otimizacao import busca_otimizada
from src.escalabilidade import executar_benchmark, expoentes
from src.filas import espera_simulada, espera_teorica
from src.rede import LinhaProducao
from src.simulacao import MotorDES

PASTA = "resultados"


def _salvar(df: pd.DataFrame, nome: str):
    os.makedirs(PASTA, exist_ok=True)
    caminho = os.path.join(PASTA, nome)
    df.to_csv(caminho, index=False)
    print(f"\n[salvo em {caminho}]")


def _fmt(media, meia, casas=1):
    return f"{media:.{casas}f} ± {meia:.{casas}f}" if meia == meia else f"{media:.{casas}f}"


def calcular_basico(replicas, seed):
    """Tabelas 12 e 13: espera por capacidade nos modelos M1–M3 (300 paletes por réplica)."""
    linhas = []
    presets = {
        "simples": ("M1 Simples", range(1, 9)),
        "multiplas_docas": ("M2 Multiplas Docas", range(3, 6)),
        "pipeline": ("M3 Pipeline", range(3, 6)),
    }
    for preset, (modelo, capacidades) in presets.items():
        for capacidade in capacidades:
            resultados = []
            for replica in range(replicas):
                resultado = MotorDES(
                    LinhaProducao(preset, capacidade),
                    300,
                    seed=seed + replica,
                    medir_memoria=False,
                ).executar()
                resultados.append(resultado)

            esperas = [r.tempo_total_espera for r in resultados]
            paletes_com_espera = [r.paletes_com_espera for r in resultados]
            esperas_maximas = [r.tempo_max_espera for r in resultados]
            espera, ic_espera = ic95(esperas)
            paletes, ic_paletes = ic95(paletes_com_espera)
            pior, ic_pior = ic95(esperas_maximas)
            linhas.append({
                "modelo": modelo,
                "capacidade": capacidade,
                "espera_total": espera,
                "espera_total_ic": ic_espera,
                "paletes_com_espera": paletes,
                "paletes_com_espera_ic": ic_paletes,
                "pior_espera": pior,
                "pior_espera_ic": ic_pior,
            })

    return pd.DataFrame(linhas)


def cmd_basico(a):
    print(f"MODELOS BASE — 300 paletes por replica, seeds {a.seed}–{a.seed + a.replicas - 1}")
    df = calcular_basico(a.replicas, a.seed)
    print(df.round(1).to_string(index=False))
    _salvar(df, "modelos_base.csv")


def calcular_recebimento(replicas, seed):
    """Tabela 7: tempo até a última conferência no M4, contra o publicado por Saderova et al."""
    publicado = {"exp1": (88, 176), "exp2": (128, 188), "exp3": (99, 174)}  # (paletes, minutos)
    linhas = []
    for variante, (paletes, ref) in publicado.items():
        proc = carregar_processo("processos/recebimento_saderova.yaml", variante)
        rs = executar_replicas(proc, replicas, seed)
        ag = agregar(rs, {
            "ciclo_s": lambda r: r["por_atividade"]["ciclo_empilhadeira"]["duracao_media"],
            "ultimo_aceito_min": lambda r: r["ultimo_fim"] / 60.0,
            "espera_empilhadeira_min": lambda r: r["por_pool"]["empilhadeira"]["espera_media"] / 60.0,
            "util_empilhadeira": lambda r: r["por_pool"]["empilhadeira"]["utilizacao"],
        })
        linhas.append({"experimento": variante, "paletes": paletes, "publicado_min": ref,
                       "simulado_min": ag["ultimo_aceito_min"], "ic95_min": ag["ultimo_aceito_min_ic"],
                       "ciclo_medio_s": ag["ciclo_s"], "espera_media_empilhadeira_min": ag["espera_empilhadeira_min"],
                       "util_empilhadeira": ag["util_empilhadeira"]})
    df = pd.DataFrame(linhas)
    df["diferenca_min"] = df["simulado_min"] - df["publicado_min"]
    return df


def cmd_recebimento(a):
    print("RECEBIMENTO DE PALETES — comparação com Saderova et al. (2022)")
    df = calcular_recebimento(a.replicas, a.seed)
    print(df.round(2).to_string(index=False))
    print("\nLeitura: o ciclo médio deve ficar entre 25 e 43 s (faixa medida no artigo).")
    print("O tempo total depende do intervalo entre caminhões (38 min é HIPÓTESE nossa, não está no artigo):")
    print("se a diferença for grande, confira esse intervalo e o nº de conferentes no artigo.")
    _salvar(df, "validacao_recebimento.csv")


def calcular_turnaround(replicas, seed):
    """Tabela 8 (30 réplicas) e Seção 4.1.4 (200): tempo total e criticidade do caminho dos passageiros."""
    publicado = {None: ("100%", 34, 99.91), "ocupacao_90": ("90%", 31, 99.08), "ocupacao_75": ("75%", 28, 94.66)}
    linhas = []
    for variante, (rotulo, ref_total, ref_crit) in publicado.items():
        proc = carregar_processo("processos/turnaround_b737.yaml", variante)
        rs = executar_replicas(proc, replicas, seed)
        ag = agregar(rs, {
            "total": lambda r: r["ultimo_fim"],
            "crit_limpeza": lambda r: 100 * r["criticidade"]["limpeza"],
            "crit_bagagem": lambda r: 100 * r["criticidade"]["carga_bagagem"],
        })
        linhas.append({"ocupacao": rotulo, "publicado_min": ref_total, "simulado_min": ag["total"],
                       "ic95_min": ag["total_ic"], "critico_caminho_passageiros_pct": ag["crit_limpeza"],
                       "publicado_pct": ref_crit, "critico_bagagem_pct": ag["crit_bagagem"]})
    return pd.DataFrame(linhas)


def cmd_turnaround(a):
    print("TURNAROUND B737-800 — comparação com San Antonio et al. (2017)")
    df = calcular_turnaround(a.replicas, a.seed)
    print(df.round(2).to_string(index=False))
    est = analise_estrutural(carregar_processo("processos/turnaround_b737.yaml"))
    print(f"\nCPM (durações médias, 100%): {est['cpm']['duracao_minima']:.1f} min; "
          f"atividades críticas: {est['cpm']['atividades_criticas']}")
    print("Premissas nossas que influenciam a comparação: forma da Weibull (=7, calibrada na Tabela 2) e a estrutura dos 5 caminhos (confira na Figura 2 do artigo).")
    # o arquivo leva o nº de réplicas no nome: validacao_turnaround.csv (200) é lido por gerar_graficos.py
    _salvar(df, f"validacao_turnaround_{a.replicas}rep.csv")


# (rótulo da Tabela 16, intervenção sobre o turnaround base)
INTERVENCOES = [
    ("Base (100% de ocupação)", lambda p: None),
    ("Equipe de limpeza de 1 para 2", lambda p: p.definir_quantidade("equipe_limpeza", 2)),
    ("Abastecimento 50% mais rápido", lambda p: p.escalar_duracao("combustivel", 0.5)),
    ("Limpeza 20% mais rápida", lambda p: p.escalar_duracao("limpeza", 0.8)),
    ("Embarque 20% mais rápido", lambda p: p.escalar_duracao("embarque", 0.8)),
    ("Catering 50% mais lento (22,5 min)", lambda p: p.escalar_duracao("catering", 1.5)),
    ("Catering 150% mais lento (37,5 min)", lambda p: p.escalar_duracao("catering", 2.5)),
]


def calcular_intervencoes(replicas, seed):
    """Tabela 16: efeito de cada intervenção no tempo total e em quanto o caminho dos passageiros e o catering são críticos."""
    linhas = []
    for rotulo, aplicar in INTERVENCOES:
        proc = carregar_processo("processos/turnaround_b737.yaml")
        aplicar(proc)
        ag = agregar(executar_replicas(proc, replicas, seed), {
            "total": lambda r: r["ultimo_fim"],
            "passageiros": lambda r: 100 * r["criticidade"]["limpeza"],
            "catering": lambda r: 100 * r["criticidade"]["catering"],
        })
        linhas.append({"intervencao": rotulo, "tempo_total_min": ag["total"], "tempo_total_ic": ag["total_ic"],
                       "pct_passageiros_critico": ag["passageiros"], "pct_catering_critico": ag["catering"]})
    return pd.DataFrame(linhas)


def cmd_intervencoes(a):
    print(f"TURNAROUND B737-800 — intervenções por atividade ({a.replicas} réplicas, semente base {a.seed})")
    df = calcular_intervencoes(a.replicas, a.seed)
    print(df.round(2).to_string(index=False))
    _salvar(df, "intervencoes_turnaround.csv")


def calcular_filas(replicas=12, n=6000, seed_base=100):
    """Tabela 6: espera média na fila, simulada contra a fórmula (M/M/1 e M/M/2)."""
    linhas = []
    for lam, mu, c in ((0.7, 1.0, 1), (1.4, 1.0, 2)):
        teorico = espera_teorica(lam, mu, c)
        media, meia = espera_simulada(lam, mu, c, n, replicas, seed_base)
        linhas.append({"lambda": lam, "mu": mu, "servidores": c, "rho": lam / (c * mu),
                       "wq_teorico": teorico, "wq_simulado": media, "wq_simulado_ic": meia,
                       "erro_relativo_pct": 100 * abs(media - teorico) / teorico})
    return pd.DataFrame(linhas)


def cmd_filas(a):
    print("VERIFICAÇÃO DAS FILAS — M/M/1 e M/M/2 (6.000 entidades, 12 réplicas, semente base 100)")
    df = calcular_filas()
    print(df.round(3).to_string(index=False))
    _salvar(df, "verificacao_filas.csv")


def calcular_salbp(arquivo, ciclo, variabilidade, n_produtos, replicas, seed, otimo):
    """Seção 4.1.6: estações pela heurística RPW e simulação da linha. Devolve (tabela, vazão/tempo, estações, limite, ciclo)."""
    inst = ler_instancia(arquivo)
    ciclo = ciclo or inst["ciclo"]
    if not ciclo:
        raise SystemExit("Informe --ciclo (a instância não traz o tempo de ciclo)")
    est = atribuir_estacoes(inst["tempos"], inst["precedencias"], ciclo)
    lb = limite_inferior(inst["tempos"], ciclo)
    proc = processo_da_linha(inst["tempos"], est, ciclo, variabilidade, n_produtos,
                             nome=os.path.basename(arquivo), fonte="Instância SALBP (Scholl)")
    rs = executar_replicas(proc, replicas, seed, descartar=0.1)
    linhas = []
    for k, tarefas in enumerate(est):
        pid, aid = f"op_E{k+1}", f"E{k+1}"
        ag = agregar(rs, {"util": lambda r, p=pid: r["por_pool"][p]["utilizacao"],
                          "espera": lambda r, x=aid: r["por_atividade"][x]["espera_media"]})
        linhas.append({"estacao": k + 1, "tarefas": ",".join(map(str, tarefas)),
                       "carga_nominal": sum(inst["tempos"][t] for t in tarefas),
                       "utilizacao": ag["util"], "espera_media_na_fila": ag["espera"]})
    df = pd.DataFrame(linhas)
    v = agregar(rs, {"vazao": lambda r: r["vazao"], "ts": lambda r: r["tempo_sistema_medio"]})
    # dados da instância em todas as linhas, para o CSV se explicar sozinho (Figura 13 do texto)
    df.insert(0, "instancia", os.path.splitext(os.path.basename(arquivo))[0])
    df.insert(1, "tempo_ciclo", ciclo)
    df.insert(2, "estacoes_heuristica", len(est))
    df.insert(3, "numero_otimo", otimo)
    df.insert(4, "limite_inferior", lb)
    df["vazao_simulada"], df["vazao_simulada_ic"], df["vazao_teorica"] = v["vazao"], v["vazao_ic"], 1 / ciclo
    return df, v, est, lb, ciclo


def cmd_salbp(a):
    df, v, est, lb, ciclo = calcular_salbp(a.arquivo, a.ciclo, a.variabilidade, a.n_produtos,
                                           a.replicas, a.seed, a.otimo)
    print(f"LINHA DE MONTAGEM — {os.path.basename(a.arquivo)}  (ciclo = {ciclo})")
    print(f"Estações pela heurística RPW: {len(est)}  |  limite inferior (soma/ciclo): {lb}")
    print("Compare com o número ótimo de estações da instância no site (assembly-line-balancing.de).")
    print(df[["estacao", "tarefas", "carga_nominal", "utilizacao", "espera_media_na_fila"]].round(3).to_string(index=False))
    print(f"\nVazão simulada: {_fmt(v['vazao'], v['vazao_ic'], 4)} produtos/u.t. (meta 1/ciclo = {1/ciclo:.4f})")
    print(f"Tempo médio no sistema: {_fmt(v['ts'], v['ts_ic'], 2)} u.t.")
    print("Estação com maior espera na fila = gargalo dinâmico; compare com a de maior carga nominal.")
    _salvar(df, "validacao_salbp.csv")


def cmd_varredura(a):
    proc = carregar_processo(a.processo, a.variante)
    valores = list(range(a.de, a.ate + 1))
    print(f"VARREDURA de '{a.pool}' em {proc.nome}: {valores}  ({a.replicas} réplicas por ponto)")
    df = varrer_pool(proc, a.pool, valores, a.replicas, a.seed)
    print(df.round(3).to_string(index=False))
    if a.limite_espera is not None:
        rec = recomendar(df, a.limite_espera)
        un = proc.unidade_tempo
        print(f"\nMenor quantidade com espera média ≤ {a.limite_espera} {un} (limite superior do IC 95%): "
              f"{rec if rec is not None else 'nenhuma no intervalo testado'}")
    _salvar(df, f"varredura_{a.pool}.csv")


def cmd_otimizar(a):
    proc = carregar_processo(a.processo, a.variante)
    metodos = ("gulosa", "exaustiva", "recozimento")
    linhas = []
    sementes_sa = []
    inicio = 0
    for metodo in metodos:
        resultado = busca_otimizada(
            proc,
            a.limite_espera,
            max_por_pool=a.max_por_pool,
            replicas=a.replicas,
            seed=a.seed,
            metodo=metodo,
        )
        alocacao = ", ".join(f"{p}={q}" for p, q in resultado["alocacao"].items())
        linhas.append({
            "Método": metodo.capitalize(),
            "Alocação": alocacao,
            "Custo": resultado["custo"],
            "Espera média": f"{resultado['espera']:.2f}",
            "Viável": "sim" if resultado["viavel"] else "não",
            "Avaliações": resultado["avaliacoes"],
            "Tempo (s)": f"{resultado['tempo']:.2f}",
        })
        if metodo == "recozimento" and a.sa_sementes > 0:
            sementes_sa = []
            for semente in range(a.seed, a.seed + a.sa_sementes):
                resultado_sa = busca_otimizada(
                    proc,
                    a.limite_espera,
                    max_por_pool=a.max_por_pool,
                    replicas=a.replicas,
                    seed=semente,
                    metodo="recozimento",
                )
                alocacao = ", ".join(
                    f"{p}={q}" for p, q in resultado_sa["alocacao"].items()
                )
                sementes_sa.append({
                    "Semente": semente,
                    "Alocação": alocacao,
                    "Custo": resultado_sa["custo"],
                    "Espera média": f"{resultado_sa['espera']:.2f}",
                    "Viável": "sim" if resultado_sa["viavel"] else "não",
                    "Avaliações": resultado_sa["avaliacoes"],
                })
    print(pd.DataFrame(linhas).to_string(index=False))
    _salvar(pd.DataFrame(linhas), f"otimizacao_{a.variante or 'default'}_{a.limite_espera:g}.csv")
    if sementes_sa:
        df_sementes = pd.DataFrame(sementes_sa)
        print("\nRecozimento por semente:")
        print(df_sementes.to_string(index=False))
        viaveis = df_sementes[df_sementes["Viável"] == "sim"]
        if not viaveis.empty:
            print(f"Custo médio das {len(viaveis)} execuções viáveis: {viaveis['Custo'].mean():.2f}")
        print(f"Soluções viáveis: {len(viaveis)} de {len(df_sementes)}")
        _salvar(df_sementes, f"recozimento_{a.variante or 'default'}_{a.limite_espera:g}_{a.sa_sementes}sementes.csv")


def cmd_escalabilidade(a):
    atividades, entidades = executar_benchmark()
    _salvar(atividades, "escalabilidade_atividades.csv")
    _salvar(entidades, "escalabilidade_entidades.csv")
    exp = expoentes(atividades, entidades)
    print("\nExpoentes de crescimento (inclinação log-log):")
    print(exp.to_string(index=False))
    _salvar(exp, "exponentes_escalabilidade.csv")


def main():
    pai = argparse.ArgumentParser(add_help=False)
    pai.add_argument("--replicas", type=int, default=30)
    pai.add_argument("--seed", type=int, default=1000)
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("basico", parents=[pai]).set_defaults(f=cmd_basico)
    sub.add_parser("recebimento", parents=[pai]).set_defaults(f=cmd_recebimento)
    sub.add_parser("turnaround", parents=[pai]).set_defaults(f=cmd_turnaround)
    i = sub.add_parser("intervencoes")
    i.add_argument("--replicas", type=int, default=200)
    i.add_argument("--seed", type=int, default=1000)
    i.set_defaults(f=cmd_intervencoes)
    sub.add_parser("filas").set_defaults(f=cmd_filas)
    s = sub.add_parser("salbp", parents=[pai])
    s.add_argument("--arquivo", required=True)
    s.add_argument("--ciclo", type=float)
    s.add_argument("--variabilidade", type=float, default=0.2)
    s.add_argument("--n-produtos", type=int, default=500)
    s.add_argument("--otimo", type=int, help="nº ótimo de estações publicado para a instância (só para o CSV)")
    s.set_defaults(f=cmd_salbp)
    v = sub.add_parser("varredura", parents=[pai])
    v.add_argument("--processo", required=True)
    v.add_argument("--variante")
    v.add_argument("--pool", required=True)
    v.add_argument("--de", type=int, default=1)
    v.add_argument("--ate", type=int, default=6)
    v.add_argument("--limite-espera", type=float)
    v.set_defaults(f=cmd_varredura)
    o = sub.add_parser("otimizar", parents=[pai])
    o.add_argument("--processo", required=True)
    o.add_argument("--variante")
    o.add_argument("--limite-espera", type=float, required=True)
    o.add_argument("--max-por-pool", type=int, default=24)
    o.add_argument("--sa-sementes", type=int, default=0)
    o.set_defaults(f=cmd_otimizar)
    sub.add_parser("escalabilidade", parents=[pai]).set_defaults(f=cmd_escalabilidade)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
