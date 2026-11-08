"""
Especificação de um processo (lida de um arquivo YAML em processos/).

Um processo é um grafo de atividades com precedências (um DAG). Cada atividade
tem uma duração (distribuição de probabilidade) e pode exigir trabalhadores de
um "pool" (por exemplo: 1 operador de empilhadeira, 3 conferentes).

Todas as durações do arquivo usam a mesma unidade de tempo (campo unidade_tempo).
"""
import copy
import math
import random
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import yaml


# ---------------------------------------------------------------- distribuições
class Dist:
    """Distribuição de probabilidade de uma duração (ou de um tamanho de lote)."""

    def __init__(self, tipo: str, **p):
        self.tipo = tipo
        self.p = p
        self._valida()

    def _valida(self):
        t, p = self.tipo, self.p
        exigidos = {
            "constante": ["valor"], "uniforme": ["min", "max"], "uniforme_int": ["min", "max"],
            "triangular": ["min", "moda", "max"], "normal": ["media", "dp"],
            "exponencial": ["media"], "weibull": ["media", "forma"], "lognormal": ["media", "cv"],
            "soma": ["componentes"],
        }
        if t not in exigidos:
            raise ValueError(f"Distribuição desconhecida: {t!r}. Opções: {sorted(exigidos)}")
        faltam = [k for k in exigidos[t] if k not in p]
        if faltam:
            raise ValueError(f"Distribuição {t!r} sem os campos: {faltam}")

    def amostra(self, rng: random.Random) -> float:
        t, p = self.tipo, self.p
        if t == "constante":
            return float(p["valor"])
        if t == "uniforme":
            return rng.uniform(p["min"], p["max"])
        if t == "uniforme_int":
            return float(rng.randint(int(p["min"]), int(p["max"])))
        if t == "triangular":
            return rng.triangular(p["min"], p["max"], p["moda"])
        if t == "normal":
            # truncada em "minimo" (padrão 0.1% da média) para não gerar tempo negativo
            minimo = p.get("minimo", 0.001 * abs(p["media"]))
            return max(minimo, rng.gauss(p["media"], p["dp"]))
        if t == "exponencial":
            return rng.expovariate(1.0 / p["media"])
        if t == "weibull":
            escala = p["media"] / math.gamma(1.0 + 1.0 / p["forma"])
            return rng.weibullvariate(escala, p["forma"])
        if t == "lognormal":
            sigma2 = math.log(1.0 + p["cv"] ** 2)
            mu = math.log(p["media"]) - sigma2 / 2.0
            return rng.lognormvariate(mu, math.sqrt(sigma2))
        if t == "soma":
            return sum(c.amostra(rng) for c in p["componentes"])
        raise AssertionError(t)

    def media(self) -> float:
        """Média teórica (a normal truncada é aproximada pela média nominal)."""
        t, p = self.tipo, self.p
        if t == "constante":
            return float(p["valor"])
        if t in ("uniforme", "uniforme_int"):
            return (p["min"] + p["max"]) / 2.0
        if t == "triangular":
            return (p["min"] + p["moda"] + p["max"]) / 3.0
        if t in ("normal", "exponencial", "weibull", "lognormal"):
            return float(p["media"])
        if t == "soma":
            return sum(c.media() for c in p["componentes"])
        raise AssertionError(t)

    def escalonar(self, fator: float) -> "Dist":
        """Nova distribuição com a duração multiplicada por 'fator' (ex.: 1.2 = 20% mais lenta)."""
        t, q = self.tipo, dict(self.p)
        if t == "constante":
            q["valor"] *= fator
        elif t == "uniforme":
            q["min"] *= fator; q["max"] *= fator
        elif t == "triangular":
            q["min"] *= fator; q["moda"] *= fator; q["max"] *= fator
        elif t == "normal":
            q["media"] *= fator; q["dp"] *= fator
            if "minimo" in q:
                q["minimo"] *= fator
        elif t in ("exponencial", "weibull", "lognormal"):
            q["media"] *= fator
        elif t == "soma":
            q["componentes"] = [c.escalonar(fator) for c in q["componentes"]]
        # uniforme_int (tamanho de lote) não é uma duração: fica como está
        return Dist(t, **q)

    def __repr__(self):
        return f"Dist({self.tipo}, {self.p})"


def dist_de_dict(d) -> Dist:
    """Converte {tipo: ..., ...} do YAML em Dist (aceita número puro = constante)."""
    if isinstance(d, (int, float)):
        return Dist("constante", valor=d)
    d = dict(d)
    tipo = d.pop("tipo")
    if tipo == "soma":
        d["componentes"] = [dist_de_dict(c) for c in d["componentes"]]
    return Dist(tipo, **d)


# ---------------------------------------------------------------- dados do processo
@dataclass
class Trabalhador:
    id: str
    funcao: str
    quantidade: int = 1
    eficiencia: float = 1.0      # 1.2 = trabalha 20% mais rápido
    ilimitado: bool = False      # True = sem restrição de capacidade (só atraso)


@dataclass
class Atividade:
    id: str
    nome: str
    duracao: Dist
    trabalhador: Optional[str] = None   # id do pool; None = não consome trabalhador
    qtd_trabalhadores: int = 1          # quantos do pool a atividade ocupa ao mesmo tempo
    predecessoras: List[str] = field(default_factory=list)


@dataclass
class Chegadas:
    tipo: str                            # unica | poisson | determinista | lotes
    n_entidades: int = 1
    intervalo: Optional[Dist] = None     # poisson/determinista: entre entidades; lotes: entre lotes
    tamanho_lote: Optional[Dist] = None
    tamanhos: Optional[List[int]] = None     # lotes de tamanho fixo (lista)
    instantes: Optional[List[float]] = None  # instante de cada lote (lista)
    n_lotes: int = 1


@dataclass
class Processo:
    nome: str
    fonte: str
    unidade_tempo: str
    chegadas: Chegadas
    trabalhadores: Dict[str, Trabalhador]
    atividades: Dict[str, Atividade]
    horizonte: Optional[float] = None
    premissas: List[str] = field(default_factory=list)

    def copia(self) -> "Processo":
        return copy.deepcopy(self)

    def definir_quantidade(self, pool_id: str, quantidade: int):
        self.trabalhadores[pool_id].quantidade = int(quantidade)

    def escalar_duracao(self, atividade_id: str, fator: float):
        """Multiplica a duração de uma atividade por 'fator'."""
        a = self.atividades[atividade_id]
        a.duracao = a.duracao.escalonar(fator)

    def validar(self):
        for a in self.atividades.values():
            for p in a.predecessoras:
                if p not in self.atividades:
                    raise ValueError(f"Atividade {a.id!r} depende de {p!r}, que não existe")
            if a.trabalhador is not None and a.trabalhador not in self.trabalhadores:
                raise ValueError(f"Atividade {a.id!r} usa o pool {a.trabalhador!r}, que não existe")
        ordem = self.ordem_topologica()  # falha se houver ciclo
        if len(ordem) != len(self.atividades):
            raise ValueError("O grafo de atividades tem ciclo")

    def sucessoras(self) -> Dict[str, List[str]]:
        """Atividades que dependem de cada uma (o inverso de 'predecessoras'), em O(V + E)."""
        suc = {i: [] for i in self.atividades}
        for a in self.atividades.values():
            for p in a.predecessoras:
                suc[p].append(a.id)
        return suc

    def ordem_topologica(self) -> List[str]:
        """Algoritmo de Kahn em O(V + E): tira quem não tem predecessora pendente, uma por vez."""
        grau = {i: len(a.predecessoras) for i, a in self.atividades.items()}
        suc = self.sucessoras()
        prontos = deque(i for i, g in grau.items() if g == 0)
        ordem = []
        while prontos:
            i = prontos.popleft()
            ordem.append(i)
            for j in suc[i]:
                grau[j] -= 1
                if grau[j] == 0:
                    prontos.append(j)
        if len(ordem) != len(self.atividades):
            raise ValueError("O grafo de atividades tem ciclo")
        return ordem


# ---------------------------------------------------------------- leitura do YAML
def _chegadas_de_dict(d: dict) -> Chegadas:
    return Chegadas(
        tipo=d["tipo"],
        n_entidades=int(d.get("n_entidades", 1)),
        intervalo=dist_de_dict(d["intervalo"]) if "intervalo" in d else None,
        tamanho_lote=dist_de_dict(d["tamanho_lote"]) if "tamanho_lote" in d else None,
        tamanhos=d.get("tamanhos"),
        instantes=d.get("instantes"),
        n_lotes=int(d.get("n_lotes", len(d["tamanhos"]) if d.get("tamanhos") else 1)),
    )


def processo_de_dict(cfg: dict, variante: Optional[str] = None) -> Processo:
    cfg = copy.deepcopy(cfg)
    if variante:
        variantes = cfg.get("variantes", {})
        if variante not in variantes:
            raise ValueError(f"Variante {variante!r} não existe. Opções: {sorted(variantes)}")
        for ativ_id, nova in variantes[variante].get("duracoes", {}).items():
            for a in cfg["atividades"]:
                if a["id"] == ativ_id:
                    a["duracao"] = nova
        novas = variantes[variante].get("chegadas")
        if novas:
            cfg["chegadas"].update(novas)
            if "tamanhos" in novas:  # lista fixa de lotes substitui o sorteio do tamanho
                cfg["chegadas"].pop("tamanho_lote", None)
                cfg["chegadas"]["n_lotes"] = len(novas["tamanhos"])
    trabalhadores = {
        t["id"]: Trabalhador(t["id"], t.get("funcao", t["id"]), int(t.get("quantidade", 1)),
                             float(t.get("eficiencia", 1.0)), bool(t.get("ilimitado", False)))
        for t in cfg.get("trabalhadores", [])
    }
    atividades = {}
    for a in cfg["atividades"]:
        atividades[a["id"]] = Atividade(
            id=a["id"], nome=a.get("nome", a["id"]), duracao=dist_de_dict(a["duracao"]),
            trabalhador=a.get("trabalhador"), qtd_trabalhadores=int(a.get("qtd_trabalhadores", 1)),
            predecessoras=list(a.get("predecessoras", [])),
        )
    proc = Processo(
        nome=cfg["nome"], fonte=cfg.get("fonte", ""), unidade_tempo=cfg.get("unidade_tempo", "u.t."),
        chegadas=_chegadas_de_dict(cfg["chegadas"]), trabalhadores=trabalhadores, atividades=atividades,
        horizonte=cfg.get("horizonte"), premissas=list(cfg.get("premissas", [])),
    )
    proc.validar()
    return proc


def carregar_processo(caminho: str, variante: Optional[str] = None) -> Processo:
    with open(caminho, encoding="utf-8") as f:
        return processo_de_dict(yaml.safe_load(f), variante)
