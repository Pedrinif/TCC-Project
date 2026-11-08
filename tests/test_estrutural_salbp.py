from src.estrutural import analise_estrutural, corte_minimo, cpm, gargalo_por_capacidade
from src.salbp import atribuir_estacoes, ler_instancia, limite_inferior, processo_da_linha
from src.motor import MotorProcesso
from tests.helpers import proc_simples


def test_corte_minimo_acha_o_gargalo_sozinho():
    p = proc_simples(
        [{"id": "a", "duracao": 1, "trabalhador": "w1"},
         {"id": "b", "duracao": 4, "trabalhador": "w2", "predecessoras": ["a"]},
         {"id": "c", "duracao": 1, "trabalhador": "w3", "predecessoras": ["b"]}],
        [{"id": "w1", "quantidade": 1}, {"id": "w2", "quantidade": 2}, {"id": "w3", "quantidade": 1}])
    c = corte_minimo(p)
    assert c["corte"] == ["b"] and abs(c["vazao_max"] - 0.5) < 1e-9      # 2 trabalhadores / 4 u.t.
    g = gargalo_por_capacidade(p)
    assert g["pool"] == "w2" and abs(g["vazao_max"] - 0.5) < 1e-9


def test_corte_minimo_nao_se_aplica_a_ramos_paralelos():
    p = proc_simples([{"id": "a", "duracao": 1}, {"id": "b", "duracao": 1},
                      {"id": "c", "duracao": 1, "predecessoras": ["a", "b"]}])
    assert corte_minimo(p) is None
    assert "cpm" in analise_estrutural(p)


def test_folga_no_cpm():
    p = proc_simples([{"id": "a", "duracao": 5}, {"id": "b", "duracao": 3},
                      {"id": "c", "duracao": 2, "predecessoras": ["a", "b"]}])
    r = cpm(p)
    assert r["folga"]["b"] == 2 and r["folga"]["a"] == 0
    assert r["atividades_criticas"] == ["a", "c"]


def test_salbp_respeita_ciclo_e_precedencias():
    inst = ler_instancia("processos/salbp/exemplo_didatico.in2")
    ciclo = 10
    est = atribuir_estacoes(inst["tempos"], inst["precedencias"], ciclo)
    onde = {t: k for k, tarefas in enumerate(est) for t in tarefas}
    assert sorted(onde) == sorted(inst["tempos"])
    for tarefas in est:
        assert sum(inst["tempos"][t] for t in tarefas) <= ciclo + 1e-9
    for a, b in inst["precedencias"]:
        assert onde[a] <= onde[b]
    assert len(est) >= limite_inferior(inst["tempos"], ciclo)


def test_linha_salbp_roda_e_aponta_estacao_mais_carregada():
    inst = ler_instancia("processos/salbp/exemplo_didatico.in2")
    est = atribuir_estacoes(inst["tempos"], inst["precedencias"], 10)
    proc = processo_da_linha(inst["tempos"], est, 10, variabilidade=0.2, n_produtos=300)
    s = MotorProcesso(proc, seed=5).executar().resumo()
    assert s["n_concluidas"] == 300
    carga = {f"op_E{k+1}": sum(inst["tempos"][t] for t in tarefas) for k, tarefas in enumerate(est)}
    mais_carregada = max(carga, key=carga.get)
    util = {p: d["utilizacao"] for p, d in s["por_pool"].items()}
    assert max(util, key=util.get) == mais_carregada
