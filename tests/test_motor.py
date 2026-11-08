"""Casos com resposta conhecida: se estes falham, o motor está errado."""
import math
import random

from src.estrutural import cpm
from src.motor import MotorProcesso
from src.processo import dist_de_dict
from src.replicacoes import executar_replicas, ic95
from tests.helpers import proc_simples


def test_distribuicoes_tem_media_teorica():
    specs = [
        {"tipo": "constante", "valor": 4}, {"tipo": "uniforme", "min": 3, "max": 5},
        {"tipo": "triangular", "min": 1, "moda": 2, "max": 6}, {"tipo": "exponencial", "media": 3},
        {"tipo": "weibull", "media": 9, "forma": 5}, {"tipo": "lognormal", "media": 5, "cv": 0.3},
        {"tipo": "normal", "media": 10, "dp": 1},
    ]
    rng = random.Random(1)
    for s in specs:
        d = dist_de_dict(s)
        emp = sum(d.amostra(rng) for _ in range(40000)) / 40000
        assert abs(emp - d.media()) / d.media() < 0.02, (s, emp, d.media())


def test_cadeia_deterministica():
    p = proc_simples([
        {"id": "a", "duracao": 2}, {"id": "b", "duracao": 3, "predecessoras": ["a"]},
    ])
    r = MotorProcesso(p).executar()
    s = r.resumo()
    assert s["ultimo_fim"] == 5 and s["n_concluidas"] == 1
    assert r.caminho_critico_empirico(0) == ["a", "b"]


def test_dag_paralelo_e_juncao_and():
    p = proc_simples([
        {"id": "a", "duracao": 5}, {"id": "b", "duracao": 3},
        {"id": "c", "duracao": 2, "predecessoras": ["a", "b"]},
    ])
    s = MotorProcesso(p).executar().resumo()
    assert s["ultimo_fim"] == 7                      # c só começa quando a (5) e b (3) terminam
    assert s["criticidade"] == {"a": 1.0, "b": 0.0, "c": 1.0}
    assert abs(cpm(p)["duracao_minima"] - 7) < 1e-9


def test_pool_serializa_trabalho():
    ativ = [{"id": "x", "duracao": 2, "trabalhador": "w"}]
    cheg = {"tipo": "lotes", "tamanhos": [3], "n_lotes": 1}
    p1 = proc_simples(ativ, [{"id": "w", "quantidade": 1}], cheg)
    s1 = MotorProcesso(p1).executar().resumo()
    assert s1["ultimo_fim"] == 6                      # 3 entidades x 2, uma por vez
    assert abs(s1["por_pool"]["w"]["espera_media"] - 2.0) < 1e-9    # esperas 0, 2, 4
    assert abs(s1["por_pool"]["w"]["utilizacao"] - 1.0) < 1e-9
    assert s1["gargalo"] == "w"
    p3 = proc_simples(ativ, [{"id": "w", "quantidade": 3}], cheg)
    s3 = MotorProcesso(p3).executar().resumo()
    assert s3["ultimo_fim"] == 2 and s3["gargalo"] is None


def test_eficiencia_acelera_trabalho():
    p = proc_simples([{"id": "x", "duracao": 6, "trabalhador": "w"}], [{"id": "w", "quantidade": 1, "eficiencia": 2.0}])
    assert MotorProcesso(p).executar().resumo()["ultimo_fim"] == 3


def test_reproducibilidade_por_semente():
    p = proc_simples([{"id": "x", "duracao": {"tipo": "exponencial", "media": 1}, "trabalhador": "w"}],
                     [{"id": "w", "quantidade": 1}],
                     {"tipo": "poisson", "n_entidades": 200, "intervalo": {"tipo": "exponencial", "media": 1.5}})
    a = MotorProcesso(p.copia(), seed=7).executar().resumo()["tempo_sistema_medio"]
    b = MotorProcesso(p.copia(), seed=7).executar().resumo()["tempo_sistema_medio"]
    c = MotorProcesso(p.copia(), seed=8).executar().resumo()["tempo_sistema_medio"]
    assert a == b and a != c


def _fila_mmc(lam, mu, c, n=6000, replicas=12):
    p = proc_simples([{"id": "s", "duracao": {"tipo": "exponencial", "media": 1 / mu}, "trabalhador": "w"}],
                     [{"id": "w", "quantidade": c}],
                     {"tipo": "poisson", "n_entidades": n, "intervalo": {"tipo": "exponencial", "media": 1 / lam}})
    rs = executar_replicas(p, replicas, seed_base=100, descartar=0.1)
    return ic95([r["por_pool"]["w"]["espera_media"] for r in rs])


def test_mm1_confere_com_formula():
    lam, mu = 0.7, 1.0
    teorico = lam / (mu * (mu - lam))                 # Wq = ρ/(μ-λ) = 2.333
    media, meia = _fila_mmc(lam, mu, 1)
    assert abs(media - teorico) / teorico < 0.10, (media, meia, teorico)


def test_mmc_confere_com_erlang_c():
    lam, mu, c = 1.4, 1.0, 2
    a, rho = lam / mu, lam / (c * mu)
    soma = sum(a ** k / math.factorial(k) for k in range(c))
    termo = a ** c / (math.factorial(c) * (1 - rho))
    erlang_c = termo / (soma + termo)
    teorico = erlang_c / (c * mu - lam)               # Wq do M/M/2
    media, meia = _fila_mmc(lam, mu, c)
    assert abs(media - teorico) / teorico < 0.10, (media, meia, teorico)


def test_lei_de_little_nos_registros():
    p = proc_simples([{"id": "s", "duracao": {"tipo": "exponencial", "media": 1.0}, "trabalhador": "w"}],
                     [{"id": "w", "quantidade": 1}],
                     {"tipo": "poisson", "n_entidades": 3000, "intervalo": {"tipo": "exponencial", "media": 1.4}})
    r = MotorProcesso(p, seed=3).executar()
    # L (média no tempo do nº de entidades no sistema), integrando chegadas e saídas
    eventos = sorted([(t, +1) for t in r.chegada.values()] + [(t, -1) for t in r.fim.values()])
    area, n_sis, t_ant = 0.0, 0, 0.0
    for t, d in eventos:
        area += n_sis * (t - t_ant)
        n_sis += d
        t_ant = t
    L = area / t_ant
    lam = len(r.fim) / t_ant
    W = sum(r.fim[e] - r.chegada[e] for e in r.fim) / len(r.fim)
    assert abs(L - lam * W) / L < 0.01
