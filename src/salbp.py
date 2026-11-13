"""
Linha de montagem (SALBP-1): dado o tempo de ciclo, quantas estações (= operadores)
são necessárias para executar todas as tarefas respeitando as precedências?

Instâncias de referência: https://assembly-line-balancing.de/ (Scholl). Os tempos delas
são determinísticos; aqui acrescentamos variabilidade (triangular) para simular.

Formatos aceitos por ler_instancia():
  - formato simples (.IN2):  n / n tempos (um por linha) / pares "i,j" / "0,0" ou "-1,-1"
  - formato ALB (.alb) com seções <number of tasks>, <task times>, <precedence relations>
"""
import math
import re
from typing import Dict, List, Set, Tuple

from src.processo import (Atividade, Chegadas, Dist, Processo, Trabalhador)


# ---------------------------------------------------------------- leitura
def ler_instancia(caminho: str) -> dict:
    with open(caminho, encoding="utf-8", errors="ignore") as f:
        texto = f.read()
    if "<number of tasks>" in texto:
        return _ler_alb(texto)
    return _ler_simples(texto)


def _ler_simples(texto: str) -> dict:
    linhas = [l.strip() for l in texto.splitlines() if l.strip()]
    n = int(linhas[0])
    tempos = {i + 1: float(linhas[1 + i]) for i in range(n)}
    prec = []
    for l in linhas[1 + n:]:
        a, b = [int(x) for x in re.split(r"[,\s]+", l) if x != ""][:2]
        if (a, b) in ((0, 0), (-1, -1)):
            break
        prec.append((a, b))
    return {"n": n, "tempos": tempos, "precedencias": prec, "ciclo": None}


def _ler_alb(texto: str) -> dict:
    secoes: Dict[str, List[str]] = {}
    atual = None
    for l in texto.splitlines():
        l = l.strip()
        m = re.match(r"<(.+)>$", l)
        if m:
            atual = m.group(1).strip().lower()
            secoes[atual] = []
        elif l and atual:
            secoes[atual].append(l)
    n = int(secoes["number of tasks"][0])
    tempos = {}
    for l in secoes["task times"]:
        i, t = l.split()[:2]
        tempos[int(i)] = float(t)
    prec = []
    for l in secoes.get("precedence relations", []):
        a, b = [int(x) for x in re.split(r"[,\s]+", l) if x != ""][:2]
        prec.append((a, b))
    ciclo = float(secoes["cycle time"][0]) if "cycle time" in secoes else None
    return {"n": n, "tempos": tempos, "precedencias": prec, "ciclo": ciclo}


# ---------------------------------------------------------------- atribuição (SALBP-1)
def limite_inferior(tempos: Dict[int, float], ciclo: float) -> int:
    return math.ceil(sum(tempos.values()) / ciclo - 1e-9)


def atribuir_estacoes(tempos: Dict[int, float], prec: List[Tuple[int, int]], ciclo: float) -> List[List[int]]:
    """
    Heurística de pesos posicionais (RPW): abre uma estação por vez e a enche com as
    tarefas elegíveis de maior peso (tempo da tarefa + tempo de todas as sucessoras).
    """
    if max(tempos.values()) > ciclo + 1e-9:
        raise ValueError("Existe tarefa mais longa que o tempo de ciclo; a instância é inviável")
    pred: Dict[int, Set[int]] = {i: set() for i in tempos}
    suc: Dict[int, Set[int]] = {i: set() for i in tempos}
    for a, b in prec:
        pred[b].add(a)
        suc[a].add(b)

    def descendentes(i, vistos=None):
        vistos = set() if vistos is None else vistos
        for j in suc[i]:
            if j not in vistos:
                vistos.add(j)
                descendentes(j, vistos)
        return vistos

    peso = {i: tempos[i] + sum(tempos[j] for j in descendentes(i)) for i in tempos}
    feitas: Set[int] = set()
    estacoes: List[List[int]] = []
    while len(feitas) < len(tempos):
        estacao, restante = [], ciclo
        while True:
            cands = [i for i in tempos if i not in feitas and pred[i] <= feitas and tempos[i] <= restante + 1e-9]
            if not cands:
                break
            i = max(cands, key=lambda k: (peso[k], -k))
            estacao.append(i)
            feitas.add(i)
            restante -= tempos[i]
        estacoes.append(estacao)
    return estacoes


# ---------------------------------------------------------------- conversão para Processo
def processo_da_linha(tempos: Dict[int, float], estacoes: List[List[int]], ciclo: float,
                      variabilidade: float = 0.2, n_produtos: int = 500,
                      nome: str = "Linha de montagem (SALBP)", fonte: str = "") -> Processo:
    """
    Cada estação vira uma atividade (soma dos tempos das suas tarefas) servida por 1 operador.
    Produtos chegam a cada 'ciclo' (ritmo da linha). variabilidade=0.2 → cada tarefa varia
    de -20% a +20% do tempo nominal (triangular). Sem buffers: a fila antes da estação cresce.
    """
    trabalhadores = {f"op_E{k+1}": Trabalhador(f"op_E{k+1}", f"Operador da estação {k+1}", 1)
                     for k in range(len(estacoes))}
    atividades = {}
    anterior = None
    for k, tarefas in enumerate(estacoes):
        comps = []
        for t in tarefas:
            nominal = tempos[t]
            if variabilidade > 0:
                comps.append(Dist("triangular", min=nominal * (1 - variabilidade), moda=nominal,
                                  max=nominal * (1 + variabilidade)))
            else:
                comps.append(Dist("constante", valor=nominal))
        aid = f"E{k+1}"
        atividades[aid] = Atividade(
            id=aid, nome=f"Estação {k+1} (tarefas {', '.join(str(t) for t in tarefas)})",
            duracao=Dist("soma", componentes=comps), trabalhador=f"op_E{k+1}",
            predecessoras=[anterior] if anterior else [],
        )
        anterior = aid
    chegadas = Chegadas(tipo="determinista", n_entidades=n_produtos, intervalo=Dist("constante", valor=ciclo))
    proc = Processo(nome=nome, fonte=fonte, unidade_tempo="u.t.", chegadas=chegadas,
                    trabalhadores=trabalhadores, atividades=atividades,
                    premissas=[f"Variabilidade triangular de ±{variabilidade:.0%} sobre os tempos determinísticos "
                               "da instância (acréscimo nosso)."])
    proc.validar()
    return proc
