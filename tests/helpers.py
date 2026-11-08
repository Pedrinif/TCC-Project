from src.processo import processo_de_dict


def proc_simples(atividades, trabalhadores=None, chegadas=None, nome="teste"):
    return processo_de_dict({
        "nome": nome, "unidade_tempo": "u.t.",
        "chegadas": chegadas or {"tipo": "unica", "n_entidades": 1},
        "trabalhadores": trabalhadores or [],
        "atividades": atividades,
    })
