from src.grafo_processo import COR, MAX_VISIVEIS, montar_grafo
from src.motor import MotorProcesso
from src.processo import carregar_processo, dist_de_dict
from src.replicacoes import executar_replicas, resumo_medio


def _ids(g, tipo):
    return [n["id"] for n in g["nos"] if n["tipo"] == tipo]


def test_pool_com_2_trabalhadores_vira_dois_circulos():
    p = carregar_processo("processos/recebimento_saderova.yaml")
    assert "empilhadeira_1" in _ids(montar_grafo(p), "trabalhador")
    p.definir_quantidade("empilhadeira", 2)
    g = montar_grafo(p)
    assert {"empilhadeira_1", "empilhadeira_2"} <= set(_ids(g, "trabalhador"))
    ligacoes = [a for a in g["arestas"] if a["tipo"] == "trabalhador" and a["destino"] == "ciclo_empilhadeira"]
    assert len(ligacoes) == 2


def test_pool_grande_vira_um_circulo_unico():
    p = carregar_processo("processos/recebimento_saderova.yaml")      # conferente = 99
    assert 99 > MAX_VISIVEIS
    ids = _ids(montar_grafo(p), "trabalhador")
    assert "conferente_x" in ids and "conferente_1" not in ids


def test_posicoes_nao_se_sobrepoem_e_arestas_batem_com_o_processo():
    p = carregar_processo("processos/turnaround_b737.yaml")
    g = montar_grafo(p)
    pos = [(n["x"], n["y"]) for n in g["nos"]]
    assert len(pos) == len(set(pos))
    esperado = sum(len(a.predecessoras) for a in p.atividades.values())
    assert len([a for a in g["arestas"] if a["tipo"] == "precedencia"]) == esperado
    assert {n["id"] for n in g["nos"] if n["tipo"] == "atividade"} == set(p.atividades)
    criticas = [n["id"] for n in g["nos"] if n["tipo"] == "atividade" and n["critica"]]
    assert criticas == ["desembarque", "limpeza", "embarque"]


def test_cores_refletem_gargalo_e_utilizacao():
    p = carregar_processo("processos/recebimento_saderova.yaml", "exp2")
    resumo = resumo_medio(executar_replicas(p, 4, 1))
    g = montar_grafo(p, resumo)
    ciclo = next(n for n in g["nos"] if n["id"] == "ciclo_empilhadeira")
    assert resumo["gargalo"] == "empilhadeira" and ciclo["borda"] == COR["gargalo"]
    assert ciclo["borda_largura"] > 2 and "espera" in ciclo["label"]


def test_utilizacao_por_trabalhador_soma_com_a_do_pool():
    p = carregar_processo("processos/recebimento_saderova.yaml", "exp2")
    p.definir_quantidade("empilhadeira", 3)
    s = MotorProcesso(p, seed=2).executar().resumo()["por_pool"]["empilhadeira"]
    assert set(s["trabalhadores"]) == {"empilhadeira_1", "empilhadeira_2", "empilhadeira_3"}
    assert abs(sum(s["trabalhadores"].values()) / 3 - s["utilizacao"]) < 1e-9


def test_escalonar_duracao_multiplica_a_media():
    for spec in ({"tipo": "constante", "valor": 4}, {"tipo": "uniforme", "min": 2, "max": 6},
                 {"tipo": "triangular", "min": 1, "moda": 2, "max": 6}, {"tipo": "normal", "media": 10, "dp": 1},
                 {"tipo": "exponencial", "media": 3}, {"tipo": "weibull", "media": 9, "forma": 5},
                 {"tipo": "lognormal", "media": 5, "cv": 0.3},
                 {"tipo": "soma", "componentes": [{"tipo": "constante", "valor": 1}, {"tipo": "uniforme", "min": 1, "max": 3}]}):
        d = dist_de_dict(spec)
        assert abs(d.escalonar(1.5).media() - 1.5 * d.media()) < 1e-9, spec


def test_escalar_atividade_no_processo():
    p = carregar_processo("processos/turnaround_b737.yaml")
    antes = p.atividades["limpeza"].duracao.media()
    p.escalar_duracao("limpeza", 2.0)
    assert abs(p.atividades["limpeza"].duracao.media() - 2 * antes) < 1e-9
