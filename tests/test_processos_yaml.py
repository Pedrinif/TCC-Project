import glob

from src.motor import MotorProcesso
from src.processo import carregar_processo


def test_todos_os_yaml_carregam_e_rodam():
    arquivos = glob.glob("processos/*.yaml")
    assert len(arquivos) >= 2
    for f in arquivos:
        p = carregar_processo(f)
        assert p.fonte, f"{f}: preencha o campo fonte"
        s = MotorProcesso(p, seed=1).executar().resumo()
        assert s["n_concluidas"] == s["n_entidades"] > 0, f


def test_ciclo_da_empilhadeira_dentro_da_faixa_do_artigo():
    p = carregar_processo("processos/recebimento_saderova.yaml")
    media = p.atividades["ciclo_empilhadeira"].duracao.media()
    assert 25 <= media <= 43        # artigo: ciclo entre 25 e 43 s


def test_variantes_do_turnaround_mudam_so_embarque_e_desembarque():
    base = carregar_processo("processos/turnaround_b737.yaml")
    v75 = carregar_processo("processos/turnaround_b737.yaml", "ocupacao_75")
    assert (base.atividades["desembarque"].duracao.media(), base.atividades["embarque"].duracao.media()) == (9, 14)
    assert (v75.atividades["desembarque"].duracao.media(), v75.atividades["embarque"].duracao.media()) == (7, 10)
    assert base.atividades["limpeza"].duracao.media() == v75.atividades["limpeza"].duracao.media() == 11
