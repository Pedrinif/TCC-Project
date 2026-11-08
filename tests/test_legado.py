"""Correções do código original (rede.py / simulacao.py / analise.py)."""
from src.analise import AnalisadorResultados
from src.rede import LinhaProducao
from src.simulacao import MotorDES


def _rodar(preset, cap, volume=300, seed=42):
    linha = LinhaProducao(preset, cap)
    motor = MotorDES(linha, volume, seed=seed, medir_memoria=False)
    res = motor.executar()
    return linha, motor, res


def test_doca_sul_agora_recebe_paletes():
    _, motor, _ = _rodar("multiplas_docas", 4)
    estacoes_vistas = {l["estacao"] for l in motor.logs_detalhados}
    assert {"Doca_Norte", "Doca_Sul"} <= estacoes_vistas


def test_utilizacao_da_estacao_critica_usa_a_capacidade_da_simulacao():
    linha, motor, res = _rodar("simples", 4)
    est = AnalisadorResultados(motor.logs_detalhados, linha, res).obter_estatisticas()
    crit = linha.aresta_critica[1]
    assert linha.capacidade_efetiva(crit) == 4          # e não a capacidade_interna (20) do nó
    assert linha.nos[crit].capacidade_interna == 20
    # recalcula à mão a partir dos logs: tempo ocupado / (tempo total x 4)
    import pandas as pd
    df = pd.DataFrame(motor.logs_detalhados)
    d = df[df.estacao == crit]
    ini = d[d.evento == "inicio_processamento"].set_index("palete_id")["tempo"]
    sai = d[d.evento == "saida_estacao"].set_index("palete_id")["tempo"]
    esperado = (sai - ini).sum() / (df["tempo"].max() * 4) * 100
    assert abs(est[crit]["utilizacao"] - min(100.0, esperado)) < 1e-6


def test_mesma_semente_mesmo_resultado_e_sem_estado_global():
    import random
    random.seed(999)
    a = _rodar("simples", 4, seed=7)[2].tempo_total_espera
    random.random()                      # mexer no gerador global não pode alterar o resultado
    b = _rodar("simples", 4, seed=7)[2].tempo_total_espera
    assert a == b


def test_corte_minimo_usa_edmonds_karp():
    linha = LinhaProducao("simples", 7)
    valor, corte = linha.calcular_corte_minimo()
    assert valor == 7 and corte == [("Doca_Recebimento", "Area_Triagem")]
