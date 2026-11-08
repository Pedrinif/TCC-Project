"""
Motor de simulação de eventos discretos (SimPy) para qualquer Processo.

Cada entidade (palete, avião, produto) percorre o grafo de atividades. Uma
atividade só começa quando TODAS as suas predecessoras terminaram (junção AND) e
quando há trabalhadores livres no pool que ela usa. Atividades sem relação de
precedência rodam em paralelo.

Cada trabalhador tem nome (pool_1, pool_2...) e a utilização é medida por trabalhador.

Atenção: se uma atividade ocupa vários trabalhadores ao mesmo tempo
(qtd_trabalhadores > 1), pools muito disputados podem travar por espera circular.
Para os processos deste projeto isso não acontece (todas usam 1 por vez).
"""
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import pandas as pd
import simpy

from src.processo import Processo

LIMIAR_UTILIZACAO = 0.85  # acima disso o pool é considerado "no limite"


def nomes_trabalhadores(pool_id: str, quantidade: int) -> List[str]:
    """Nome de cada trabalhador do pool: empilhadeira_1, empilhadeira_2, ..."""
    return [f"{pool_id}_{i + 1}" for i in range(max(1, quantidade))]


class _Pool:
    """
    Pool de trabalhadores com nome. Quem está livre fica numa fila (Store); quem termina
    volta para o fim dela, então o trabalho se reparte por igual entre os trabalhadores.
    Pools "ilimitados" não têm fila nem nomes: a atividade só consome tempo.
    """
    def __init__(self, env, cfg):
        self.cfg = cfg
        self.nomes = [] if cfg.ilimitado else nomes_trabalhadores(cfg.id, cfg.quantidade)
        self.livres = simpy.Store(env)
        self.livres.items.extend(self.nomes)
        self.ocupado = {n: 0.0 for n in self.nomes}   # tempo ocupado de cada trabalhador
        self.tempo_ocupado = 0.0
        self.fila_max = 0


@dataclass
class ResultadoProcesso:
    proc: Processo
    seed: int
    tempo_total: float
    chegada: Dict[int, float]
    fim: Dict[int, float]
    reg: Dict[int, Dict[str, Tuple[float, float, float]]]   # eid -> atividade -> (pronto, início, fim)
    pools: Dict[str, dict] = field(default_factory=dict)    # tempo_ocupado, fila_max, quantidade, ilimitado

    # -------------------------------------------------------------- métricas
    def _concluidas(self, descartar: float = 0.0) -> List[int]:
        ids = sorted(e for e in self.fim)
        corte = int(len(ids) * descartar)
        return ids[corte:]

    def caminho_critico_empirico(self, eid: int) -> List[str]:
        """Cadeia de atividades que determinou o instante de término da entidade."""
        r = self.reg[eid]
        atual = max(r, key=lambda a: r[a][2])
        cadeia = [atual]
        while self.proc.atividades[atual].predecessoras:
            atual = max(self.proc.atividades[atual].predecessoras, key=lambda a: r[a][2])
            cadeia.append(atual)
        return list(reversed(cadeia))

    def resumo(self, descartar: float = 0.0) -> dict:
        """
        Estatísticas da rodada. 'descartar' = fração inicial de entidades ignorada nas
        médias (aquecimento). Utilização é sempre sobre o tempo total simulado.
        """
        ids = self._concluidas(descartar)
        n = len(ids)
        tempos_sistema = [self.fim[e] - self.chegada[e] for e in ids]

        por_ativ = {}
        for aid, a in self.proc.atividades.items():
            esperas = [self.reg[e][aid][1] - self.reg[e][aid][0] for e in ids]
            duracoes = [self.reg[e][aid][2] - self.reg[e][aid][1] for e in ids]
            por_ativ[aid] = {
                "espera_media": sum(esperas) / n if n else 0.0,
                "espera_max": max(esperas, default=0.0),
                "duracao_media": sum(duracoes) / n if n else 0.0,
                "espera_total": sum(esperas),
            }

        por_pool = {}
        for pid, info in self.pools.items():
            usa = [aid for aid, a in self.proc.atividades.items() if a.trabalhador == pid]
            espera_total = sum(por_ativ[a]["espera_total"] for a in usa)
            esperas_todas = [self.reg[e][a][1] - self.reg[e][a][0] for e in ids for a in usa]
            capacidade_tempo = info["quantidade"] * self.tempo_total
            por_pool[pid] = {
                "quantidade": info["quantidade"],
                "ilimitado": info["ilimitado"],
                "trabalhadores": {n: (t / self.tempo_total if self.tempo_total > 0 else 0.0)
                                  for n, t in info["ocupado"].items()},
                "utilizacao": None if info["ilimitado"] or capacidade_tempo <= 0
                else info["tempo_ocupado"] / capacidade_tempo,
                "espera_media": (sum(esperas_todas) / len(esperas_todas)) if esperas_todas else 0.0,
                "espera_max": max(esperas_todas, default=0.0),
                "espera_total": espera_total,
                "fila_max": info["fila_max"],
            }

        # frequência com que cada atividade esteve no caminho crítico (como em San Antonio et al., 2017)
        contagem = {aid: 0 for aid in self.proc.atividades}
        for e in ids:
            for aid in self.caminho_critico_empirico(e):
                contagem[aid] += 1
        criticidade = {aid: (c / n if n else 0.0) for aid, c in contagem.items()}

        limitados = {p: d for p, d in por_pool.items() if not d["ilimitado"]}
        gargalo = None
        if limitados:
            cand = max(limitados, key=lambda p: limitados[p]["espera_total"])
            if limitados[cand]["espera_total"] > 0:
                gargalo = cand

        return {
            "n_entidades": len(self.chegada),
            "n_concluidas": len(self.fim),
            "n_consideradas": n,
            "tempo_total": self.tempo_total,
            "ultimo_fim": max(self.fim.values(), default=0.0),
            "vazao": (len(self.fim) / self.tempo_total) if self.tempo_total > 0 else 0.0,
            "tempo_sistema_medio": sum(tempos_sistema) / n if n else 0.0,
            "tempo_sistema_max": max(tempos_sistema, default=0.0),
            "por_atividade": por_ativ,
            "por_pool": por_pool,
            "criticidade": criticidade,
            "gargalo": gargalo,
        }

    def registros_df(self) -> pd.DataFrame:
        linhas = []
        for eid, atividades in self.reg.items():
            for aid, (pronto, ini, fim) in atividades.items():
                linhas.append({"entidade": eid, "atividade": aid, "pronto": pronto, "inicio": ini,
                               "fim": fim, "espera": ini - pronto, "duracao": fim - ini})
        return pd.DataFrame(linhas)


class MotorProcesso:
    def __init__(self, proc: Processo, seed: int = 42):
        proc.validar()
        self.proc = proc
        self.seed = seed
        self.rng = random.Random(seed)        # gerador próprio: réplicas não interferem entre si
        self.env = simpy.Environment()
        self.pools = {pid: _Pool(self.env, t) for pid, t in proc.trabalhadores.items()}
        self.chegada: Dict[int, float] = {}
        self.fim: Dict[int, float] = {}
        self.reg: Dict[int, Dict[str, Tuple[float, float, float]]] = {}
        self._proximo_id = 0

    # ------------------------------------------------------------ entidades
    def _nova_entidade(self):
        eid = self._proximo_id
        self._proximo_id += 1
        self.env.process(self._entidade(eid))

    def _entidade(self, eid: int):
        self.chegada[eid] = self.env.now
        self.reg[eid] = {}
        feito = {aid: self.env.event() for aid in self.proc.atividades}
        procs = [self.env.process(self._atividade(eid, a, feito)) for a in self.proc.atividades.values()]
        yield self.env.all_of(procs)
        self.fim[eid] = self.env.now

    def _atividade(self, eid: int, a, feito):
        env = self.env
        if a.predecessoras:
            yield env.all_of([feito[p] for p in a.predecessoras])
        pronto = env.now

        pool = self.pools[a.trabalhador] if a.trabalhador is not None else None
        if pool is None or pool.cfg.ilimitado:
            inicio = env.now
            ef = pool.cfg.eficiencia if pool is not None else 1.0
            yield env.timeout(a.duracao.amostra(self.rng) / ef)
        else:
            pedidos = [pool.livres.get() for _ in range(a.qtd_trabalhadores)]
            pool.fila_max = max(pool.fila_max, len(pool.livres.get_queue))
            yield env.all_of(pedidos)
            inicio = env.now
            escalados = [p.value for p in pedidos]
            yield env.timeout(a.duracao.amostra(self.rng) / pool.cfg.eficiencia)
            duracao = env.now - inicio
            for nome in escalados:
                pool.ocupado[nome] += duracao
                pool.livres.put(nome)
            pool.tempo_ocupado += duracao * len(escalados)

        self.reg[eid][a.id] = (pronto, inicio, env.now)
        feito[a.id].succeed()

    # ------------------------------------------------------------ chegadas
    def _gerador(self):
        c = self.proc.chegadas
        if c.tipo == "unica":
            for _ in range(c.n_entidades):
                self._nova_entidade()
        elif c.tipo in ("poisson", "determinista"):
            for i in range(c.n_entidades):
                self._nova_entidade()
                if i < c.n_entidades - 1:
                    yield self.env.timeout(c.intervalo.amostra(self.rng))
        elif c.tipo == "lotes":
            for k in range(c.n_lotes):
                if c.instantes is not None:
                    espera = c.instantes[k] - self.env.now
                elif k > 0:
                    espera = c.intervalo.amostra(self.rng)
                else:
                    espera = 0.0
                if espera > 0:
                    yield self.env.timeout(espera)
                tamanho = c.tamanhos[k] if c.tamanhos else int(c.tamanho_lote.amostra(self.rng))
                for _ in range(tamanho):
                    self._nova_entidade()
        else:
            raise ValueError(f"Tipo de chegada desconhecido: {c.tipo!r}")

    # ------------------------------------------------------------ execução
    def executar(self) -> ResultadoProcesso:
        self.env.process(self._gerador())
        self.env.run(until=self.proc.horizonte)  # None = roda até esvaziar
        return ResultadoProcesso(
            proc=self.proc, seed=self.seed, tempo_total=self.env.now,
            chegada=dict(self.chegada), fim=dict(self.fim), reg={e: dict(r) for e, r in self.reg.items()},
            pools={pid: {"tempo_ocupado": p.tempo_ocupado, "fila_max": p.fila_max, "ocupado": dict(p.ocupado),
                         "quantidade": p.cfg.quantidade, "ilimitado": p.cfg.ilimitado}
                   for pid, p in self.pools.items()},
        )
