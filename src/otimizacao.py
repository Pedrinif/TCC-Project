import math
import random
import time
from itertools import product

from src.replicacoes import agregar, executar_replicas


def _avaliar(proc, alocacao, replicas, seed):
    candidato = proc.copia()
    for pool_id, quantidade in alocacao.items():
        candidato.definir_quantidade(pool_id, quantidade)
    resumos = executar_replicas(candidato, replicas, seed)
    espera = agregar(
        resumos,
        {pid: lambda r, pool=pid: r["por_pool"][pool]["espera_media"] for pid in alocacao},
    )
    espera_media = sum(espera[pid] for pid in alocacao) / len(alocacao)
    return espera_media, sum(alocacao.values())


def busca_otimizada(proc, limite_espera, max_por_pool=24, replicas=30, seed=1000, metodo="exaustiva"):
    inicio = time.perf_counter()
    pools = list(proc.trabalhadores)
    rng = random.Random(seed)
    avaliacoes = 0

    def avaliar(alocacao):
        nonlocal avaliacoes
        avaliacoes += 1
        espera, custo = _avaliar(proc, dict(zip(pools, alocacao)), replicas, seed)
        return espera <= limite_espera, espera, custo

    if metodo == "gulosa":
        atual = [1] * len(pools)
        viavel, espera, custo = avaliar(atual)
        while True:
            if viavel:
                break
            candidatos = []
            for pos in range(len(pools)):
                if atual[pos] >= max_por_pool:
                    continue
                alocacao = list(atual)
                alocacao[pos] += 1
                viavel, espera, custo = avaliar(alocacao)
                candidatos.append((custo, espera, tuple(alocacao), viavel))
            if not candidatos:
                break
            _, _, melhor_alocacao, _ = min(candidatos, key=lambda c: (c[1], c[0], c[2]))
            atual = list(melhor_alocacao)
            viavel, espera, custo = avaliar(atual)
        alocacao = tuple(atual)
        viavel, espera, custo = avaliar(alocacao)

    elif metodo == "recozimento":
        atual = tuple(rng.randint(1, max_por_pool) for _ in pools)
        melhor = atual
        resultado_atual = avaliar(atual)
        resultado_melhor = resultado_atual
        temperatura = 5.0
        for passo in range(max(80, len(pools) * 20)):
            vizinho = list(atual)
            pos = rng.randrange(len(pools))
            vizinho[pos] = max(1, min(max_por_pool, vizinho[pos] + rng.choice([-1, 1])))
            resultado_vizinho = avaliar(tuple(vizinho))
            custo_atual = sum(atual) + (0 if resultado_atual[0] else 10000)
            custo_vizinho = sum(vizinho) + (0 if resultado_vizinho[0] else 10000)
            delta = custo_vizinho - custo_atual
            if delta <= 0 or rng.random() < math.exp(-delta / max(temperatura, 0.001)):
                atual = tuple(vizinho)
                resultado_atual = resultado_vizinho
            temperatura *= 0.92
            if resultado_atual[0] and sum(atual) < sum(melhor):
                melhor = atual
                resultado_melhor = resultado_atual
            elif sum(atual) < sum(melhor) and resultado_melhor[0] == False and not resultado_atual[0]:
                melhor = atual
                resultado_melhor = resultado_atual
        alocacao = melhor
        viavel, espera, custo = resultado_melhor if sum(melhor) == sum(alocacao) else avaliar(alocacao)

    else:
        melhor = None
        melhor_espera = None
        melhor_viavel = None
        for alocacao in product(range(1, max_por_pool + 1), repeat=len(pools)):
            viavel, espera, custo = avaliar(alocacao)
            if viavel and (melhor is None or (custo, espera, alocacao) < (sum(melhor), melhor_espera, melhor)):
                melhor = alocacao
                melhor_espera = espera
                melhor_viavel = viavel
        alocacao = melhor if melhor is not None else tuple([1] * len(pools))
        viavel, espera, custo = avaliar(alocacao)

    tempo = time.perf_counter() - inicio
    return {
        "alocacao": dict(zip(pools, alocacao)),
        "custo": sum(alocacao),
        "espera": espera,
        "viavel": viavel,
        "avaliacoes": avaliacoes,
        "tempo": tempo,
    }
