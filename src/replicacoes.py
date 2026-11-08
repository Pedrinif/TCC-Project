"""
Réplicas independentes (uma semente por réplica), intervalo de confiança de 95% e
varredura do número de trabalhadores de um pool.
"""
import math
from typing import Callable, Dict, List, Optional, Sequence

import pandas as pd

from src.motor import MotorProcesso
from src.processo import Processo

# t de Student bilateral, 95%, para 1..30 graus de liberdade
_T95 = [12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228, 2.201, 2.179, 2.160,
        2.145, 2.131, 2.120, 2.110, 2.101, 2.093, 2.086, 2.080, 2.074, 2.069, 2.064, 2.060, 2.056,
        2.052, 2.048, 2.045, 2.042]


def t_critico(gl: int) -> float:
    if gl < 1:
        return float("nan")
    if gl <= 30:
        return _T95[gl - 1]
    if gl <= 40:
        return 2.021
    if gl <= 60:
        return 2.000
    if gl <= 120:
        return 1.980
    return 1.960


def ic95(valores: Sequence[float]) -> tuple:
    """(média, semi-largura do IC de 95%). Com 1 valor só, a semi-largura é NaN."""
    v = [x for x in valores if x is not None]
    n = len(v)
    if n == 0:
        return (float("nan"), float("nan"))
    media = sum(v) / n
    if n < 2:
        return (media, float("nan"))
    var = sum((x - media) ** 2 for x in v) / (n - 1)
    return (media, t_critico(n - 1) * math.sqrt(var / n))


def executar_replicas(proc: Processo, n: int = 20, seed_base: int = 1000, descartar: float = 0.0) -> List[dict]:
    """Roda n réplicas independentes e devolve o resumo de cada uma."""
    resumos = []
    for i in range(n):
        res = MotorProcesso(proc.copia(), seed=seed_base + i).executar()
        resumos.append(res.resumo(descartar))
    return resumos


def agregar(resumos: List[dict], extratores: Dict[str, Callable[[dict], Optional[float]]]) -> Dict[str, float]:
    """Média e semi-largura do IC de cada métrica. Ex.: {'vazao': lambda r: r['vazao']}."""
    linha = {}
    for nome, f in extratores.items():
        media, meia = ic95([f(r) for r in resumos])
        linha[nome] = media
        linha[nome + "_ic"] = meia
    return linha


def varrer_pool(proc: Processo, pool_id: str, valores: Sequence[int], replicas: int = 20,
                seed_base: int = 1000, descartar: float = 0.0) -> pd.DataFrame:
    """
    Para cada quantidade de trabalhadores do pool, roda réplicas e resume:
    vazão, tempo médio no sistema, espera média no pool, utilização e último término.
    """
    linhas = []
    for q in valores:
        p = proc.copia()
        p.definir_quantidade(pool_id, q)
        resumos = executar_replicas(p, replicas, seed_base, descartar)
        linha = {"quantidade": q}
        linha.update(agregar(resumos, {
            "vazao": lambda r: r["vazao"],
            "tempo_sistema": lambda r: r["tempo_sistema_medio"],
            "espera_pool": lambda r, pid=pool_id: r["por_pool"][pid]["espera_media"],
            "utilizacao": lambda r, pid=pool_id: r["por_pool"][pid]["utilizacao"],
            "ultimo_fim": lambda r: r["ultimo_fim"],
        }))
        linhas.append(linha)
    return pd.DataFrame(linhas)


def recomendar(df: pd.DataFrame, limite_espera: float) -> Optional[int]:
    """
    Menor quantidade de trabalhadores cujo limite SUPERIOR do IC da espera média no pool
    fica abaixo de 'limite_espera' (mesma unidade de tempo do processo).
    """
    for _, linha in df.sort_values("quantidade").iterrows():
        ic = linha["espera_pool_ic"]
        superior = linha["espera_pool"] + (0.0 if math.isnan(ic) else ic)
        if superior <= limite_espera:
            return int(linha["quantidade"])
    return None


def resumo_medio(resumos: List[dict]) -> dict:
    """
    Resumo "típico" de várias réplicas, no mesmo formato de ResultadoProcesso.resumo():
    números viram a média das réplicas e o gargalo é o mais frequente. Serve para pintar o grafo.
    """
    def media(valores):
        v = [x for x in valores if x is not None]
        return sum(v) / len(v) if v else None

    def mesclar(itens):
        primeiro = itens[0]
        if isinstance(primeiro, dict):
            return {k: mesclar([i[k] for i in itens]) for k in primeiro}
        if isinstance(primeiro, bool) or primeiro is None and all(i is None for i in itens):
            return primeiro
        if isinstance(primeiro, (int, float)) or any(isinstance(i, (int, float)) for i in itens):
            return media(itens)
        return primeiro

    base = {k: mesclar([r[k] for r in resumos]) for k in resumos[0] if k != "gargalo"}
    contagem = {}
    for r in resumos:
        contagem[r["gargalo"]] = contagem.get(r["gargalo"], 0) + 1
    base["gargalo"] = max(contagem, key=contagem.get)
    base["gargalo_frequencia"] = contagem[base["gargalo"]] / len(resumos)
    return base
