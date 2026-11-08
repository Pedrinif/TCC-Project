"""
Análise estrutural (sem simular): onde o processo é limitado só pela sua estrutura.

- capacidade por pool: quantas entidades por unidade de tempo cada grupo de
  trabalhadores consegue atender (quantidade ÷ carga de trabalho por entidade);
- caminho crítico e folgas (CPM) com as durações médias;
- corte mínimo por separação de nós, para processos em cadeia. Cada atividade vira
  um par de vértices (entrada → saída) cuja aresta tem a capacidade da atividade,
  então o corte mínimo aponta o gargalo sozinho, sem o usuário escolher a aresta.
"""
from typing import Dict, List, Optional

import networkx as nx
from networkx.algorithms.flow import edmonds_karp

from src.processo import ILIMITADO, Processo

INF = float("inf")


def carga_por_pool(proc: Processo) -> Dict[str, float]:
    """Trabalho (trabalhador × tempo) que cada entidade exige de cada pool."""
    carga = {pid: 0.0 for pid in proc.trabalhadores}
    for a in proc.atividades.values():
        if a.trabalhador is not None:
            t = proc.trabalhadores[a.trabalhador]
            carga[a.trabalhador] += a.duracao.media() / t.eficiencia * a.qtd_trabalhadores
    return carga


def capacidade_por_pool(proc: Processo) -> Dict[str, float]:
    """Entidades por unidade de tempo que o pool aguenta (infinito se ilimitado ou sem uso)."""
    cap = {}
    for pid, c in carga_por_pool(proc).items():
        t = proc.trabalhadores[pid]
        cap[pid] = INF if (t.ilimitado or c <= 0) else t.quantidade / c
    return cap


def gargalo_por_capacidade(proc: Processo) -> dict:
    """Lei do gargalo: a vazão máxima do processo é a menor capacidade entre os pools."""
    cap = capacidade_por_pool(proc)
    limitados = {p: c for p, c in cap.items() if c != INF}
    if not limitados:
        return {"vazao_max": INF, "pool": None, "capacidades": cap}
    pool = min(limitados, key=limitados.get)
    return {"vazao_max": limitados[pool], "pool": pool, "capacidades": cap}


# ---------------------------------------------------------------- caminho crítico (CPM)
def cpm(proc: Processo) -> dict:
    """Início/fim mais cedo e mais tarde, folga e caminho crítico com durações médias."""
    dur = {i: a.duracao.media() / (proc.trabalhadores[a.trabalhador].eficiencia if a.trabalhador else 1.0)
           for i, a in proc.atividades.items()}
    ordem = proc.ordem_topologica()
    es, ef = {}, {}
    for i in ordem:
        es[i] = max((ef[p] for p in proc.atividades[i].predecessoras), default=0.0)
        ef[i] = es[i] + dur[i]
    fim = max(ef.values())
    sucessoras = {i: [j for j, a in proc.atividades.items() if i in a.predecessoras] for i in proc.atividades}
    ls, lf = {}, {}
    for i in reversed(ordem):
        lf[i] = min((ls[s] for s in sucessoras[i]), default=fim)
        ls[i] = lf[i] - dur[i]
    folga = {i: ls[i] - es[i] for i in proc.atividades}
    critico = [i for i in ordem if abs(folga[i]) < 1e-9]
    return {"duracao_minima": fim, "es": es, "ef": ef, "folga": folga, "atividades_criticas": critico,
            "duracoes_medias": dur}


# ---------------------------------------------------------------- fluxo máximo / corte mínimo
def eh_cadeia(proc: Processo) -> bool:
    """True se cada atividade tem no máximo 1 predecessora e 1 sucessora."""
    suc = {i: 0 for i in proc.atividades}
    for a in proc.atividades.values():
        if len(a.predecessoras) > 1:
            return False
        for p in a.predecessoras:
            suc[p] += 1
    return all(n <= 1 for n in suc.values())


def corte_minimo(proc: Processo) -> Optional[dict]:
    """
    Fluxo máximo (Edmonds-Karp) na rede com separação de nós. Só vale para cadeias:
    em processos com tarefas em paralelo, TODAS as ramificações precisam acontecer
    (junção AND), e somar capacidades de ramos em paralelo daria um resultado errado.
    Nesses casos devolve None; use gargalo_por_capacidade() e cpm().
    """
    if not eh_cadeia(proc):
        return None
    cap_pool = capacidade_por_pool(proc)
    G = nx.DiGraph()
    for i, a in proc.atividades.items():
        c = cap_pool[a.trabalhador] if a.trabalhador else INF
        # capacidade infinita: nx exige ausência do atributo 'capacity' (= sem limite)
        if c == INF:
            G.add_edge(f"{i}_ent", f"{i}_sai")
        else:
            G.add_edge(f"{i}_ent", f"{i}_sai", capacity=c)
        for p in a.predecessoras:
            G.add_edge(f"{p}_sai", f"{i}_ent")
    raizes = [i for i, a in proc.atividades.items() if not a.predecessoras]
    folhas = [i for i in proc.atividades if not any(i in a.predecessoras for a in proc.atividades.values())]
    for r in raizes:
        G.add_edge("FONTE", f"{r}_ent")
    for f in folhas:
        G.add_edge(f"{f}_sai", "SORVEDOURO")
    try:
        valor, (lado_s, lado_t) = nx.minimum_cut(G, "FONTE", "SORVEDOURO", flow_func=edmonds_karp)
    except nx.NetworkXUnbounded:  # nenhuma atividade limita o fluxo
        return {"vazao_max": INF, "corte": [], "metodo": "fluxo máximo (Edmonds-Karp)"}
    corte = [u[:-4] for u, v in G.edges() if u in lado_s and v in lado_t and u.endswith("_ent") and v.endswith("_sai")]
    return {"vazao_max": valor, "corte": corte, "metodo": "fluxo máximo (Edmonds-Karp)"}


def analise_estrutural(proc: Processo) -> dict:
    """Junta tudo para exibir/exportar."""
    return {
        "capacidades": capacidade_por_pool(proc),
        "gargalo_capacidade": gargalo_por_capacidade(proc),
        "cpm": cpm(proc),
        "corte_minimo": corte_minimo(proc),
    }
