"""
Verificação do motor contra filas com fórmula conhecida (Tabela 6 do texto):
M/M/1 e M/M/c, com chegadas de Poisson e serviço exponencial.
"""
import math

from src.processo import Processo, processo_de_dict
from src.replicacoes import executar_replicas, ic95


def processo_fila(lam: float, mu: float, servidores: int, n: int = 6000) -> Processo:
    """Um único serviço exponencial (taxa mu) com 'servidores' atendentes e chegadas de taxa lam."""
    return processo_de_dict({
        "nome": f"fila_M/M/{servidores}", "unidade_tempo": "u.t.",
        "chegadas": {"tipo": "poisson", "n_entidades": n, "intervalo": {"tipo": "exponencial", "media": 1 / lam}},
        "trabalhadores": [{"id": "w", "quantidade": servidores}],
        "atividades": [{"id": "s", "duracao": {"tipo": "exponencial", "media": 1 / mu}, "trabalhador": "w"}],
    })


def espera_teorica(lam: float, mu: float, servidores: int) -> float:
    """Wq de uma M/M/c pela fórmula de Erlang C (para c = 1 vira ρ/(μ−λ))."""
    a, rho = lam / mu, lam / (servidores * mu)
    soma = sum(a ** k / math.factorial(k) for k in range(servidores))
    termo = a ** servidores / (math.factorial(servidores) * (1 - rho))
    return termo / (soma + termo) / (servidores * mu - lam)


def espera_simulada(lam: float, mu: float, servidores: int, n: int = 6000, replicas: int = 12,
                    seed_base: int = 100):
    """(média, semi-largura do IC 95%) da espera média na fila; descarta os 10% iniciais."""
    rs = executar_replicas(processo_fila(lam, mu, servidores, n), replicas, seed_base=seed_base, descartar=0.1)
    return ic95([r["por_pool"]["w"]["espera_media"] for r in rs])
