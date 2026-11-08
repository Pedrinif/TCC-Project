"""
Dados do desenho do grafo de um Processo (sem depender do Streamlit, para poder testar).

Dois tipos de vértice:
  - atividade: retângulo, ligado às suas predecessoras por setas;
  - trabalhador: círculo, ligado por linhas tracejadas às atividades que ele executa.
    Um pool com 2 trabalhadores vira dois círculos (A_1 e A_2).

Cores (quando há resultado de simulação):
  - preenchimento da atividade e dos trabalhadores = utilização (verde → amarelo → vermelho);
  - borda vermelha grossa = gargalo dinâmico (onde as entidades mais esperaram);
  - borda laranja = gargalo estrutural (menor capacidade);
  - setas vermelhas = caminho crítico (CPM, durações médias).
"""
from typing import Dict, List, Optional

from src.estrutural import capacidade_por_pool, cpm
from src.motor import nomes_trabalhadores
from src.processo import Processo

LARG_X = 280          # distância horizontal entre níveis
ALT_Y = 120           # distância vertical entre atividades do mesmo nível
ESPACO_TRAB = 90      # distância horizontal entre trabalhadores do mesmo pool
MAX_VISIVEIS = 8      # acima disso o pool vira um único círculo "×N"
LIMIAR_MEDIA = 0.60   # utilização a partir da qual o vértice fica amarelo
LIMIAR_ALTA = 0.85    # ... e vermelho (só colore o grafo; o gargalo é decidido pela espera)

COR = {
    "neutro": "#388bfd", "baixa": "#3fb950", "media": "#d29922", "alta": "#f85149",
    "trabalhador": "#8b949e", "borda": "#30363d", "gargalo": "#f85149", "estrutural": "#f0883e",
    "critico": "#f85149", "seta": "#58a6ff", "pool_seta": "#6e7681",
}


def cor_utilizacao(u: Optional[float]) -> str:
    if u is None:
        return COR["neutro"]
    return COR["baixa"] if u < LIMIAR_MEDIA else COR["media"] if u < LIMIAR_ALTA else COR["alta"]


def niveis(proc: Processo) -> Dict[str, int]:
    """Nível de cada atividade = maior número de setas desde uma atividade sem predecessora."""
    nivel: Dict[str, int] = {}
    for i in proc.ordem_topologica():
        preds = proc.atividades[i].predecessoras
        nivel[i] = 1 + max(nivel[p] for p in preds) if preds else 0
    return nivel


def _pool_visiveis(proc: Processo, pid: str) -> List[str]:
    t = proc.trabalhadores[pid]
    if t.ilimitado or t.quantidade > MAX_VISIVEIS:
        return [f"{pid}_x"]                       # círculo único "×N"
    return nomes_trabalhadores(pid, t.quantidade)


def montar_grafo(proc: Processo, resumo: Optional[dict] = None, estrutural: bool = True) -> dict:
    """Devolve {'nos': [...], 'arestas': [...]} prontos para desenhar (pyvis/vis.js)."""
    un = proc.unidade_tempo
    nivel = niveis(proc)
    ordem = proc.ordem_topologica()

    # --- posições das atividades
    por_nivel: Dict[int, List[str]] = {}
    for i in ordem:
        por_nivel.setdefault(nivel[i], []).append(i)
    pos: Dict[str, tuple] = {}
    max_pista = 0
    for n, ids in por_nivel.items():
        for k, i in enumerate(ids):
            pos[i] = (n * LARG_X, k * ALT_Y)
        max_pista = max(max_pista, len(ids) - 1)

    # --- destaques
    gargalo_dinamico = resumo["gargalo"] if resumo else None
    cap = capacidade_por_pool(proc)
    finitos = {p: c for p, c in cap.items() if c != float("inf")}
    gargalo_estrutural = min(finitos, key=finitos.get) if (estrutural and finitos) else None
    criticas = set(cpm(proc)["atividades_criticas"])

    nos: List[dict] = []
    for i in ordem:
        a = proc.atividades[i]
        pool_res = resumo["por_pool"].get(a.trabalhador) if (resumo and a.trabalhador) else None
        util = pool_res["utilizacao"] if pool_res else None
        ativ_res = resumo["por_atividade"][i] if resumo else None
        label = f"{a.nome}\n{a.duracao.media():.1f} {un}"
        if ativ_res:
            label += f"\nespera {ativ_res['espera_media']:.1f} {un}"
        dica = f"<b>{a.nome}</b><br>Duração média: {a.duracao.media():.2f} {un}"
        if a.trabalhador:
            t = proc.trabalhadores[a.trabalhador]
            dica += f"<br>Trabalhador: {t.funcao} (×{t.quantidade})<br>Capacidade do pool: " \
                    f"{cap[a.trabalhador]:.4g} entidades/{un}"
        if pool_res and util is not None:
            dica += f"<br>Utilização do pool: {util:.0%}"
        if resumo:
            dica += f"<br>No caminho crítico em {resumo['criticidade'][i]:.0%} das entidades"
        eh_din = bool(a.trabalhador) and a.trabalhador == gargalo_dinamico
        eh_est = bool(a.trabalhador) and a.trabalhador == gargalo_estrutural
        if eh_din:
            dica += "<br><b>⚠ Gargalo dinâmico</b> (onde mais se espera)"
        if eh_est:
            dica += "<br><b>⚠ Gargalo estrutural</b> (menor capacidade)"
        nos.append({
            "id": i, "tipo": "atividade", "label": label, "title": dica, "x": pos[i][0], "y": pos[i][1],
            "forma": "box", "cor": cor_utilizacao(util) if resumo else COR["neutro"],
            "borda": COR["gargalo"] if eh_din else COR["estrutural"] if eh_est else COR["borda"],
            "borda_largura": 5 if eh_din else 4 if eh_est else 2,
            "critica": i in criticas,
        })

    # --- trabalhadores: um bloco por pool, em linhas abaixo das atividades
    blocos = []
    for pid, t in proc.trabalhadores.items():
        servidas = [i for i, a in proc.atividades.items() if a.trabalhador == pid]
        if not servidas:
            continue
        visiveis = _pool_visiveis(proc, pid)
        xs = [pos[i][0] for i in servidas]
        centro = sum(xs) / len(xs)
        largura = max(1, len(visiveis)) * ESPACO_TRAB
        blocos.append((pid, t, servidas, visiveis, centro, largura))
    blocos.sort(key=lambda b: b[4])

    linhas_ocupadas: List[List[tuple]] = []   # cada linha guarda os intervalos [x0, x1] já usados
    y_base = (max_pista + 1) * ALT_Y + 40
    for pid, t, servidas, visiveis, centro, largura in blocos:
        x0, x1 = centro - largura / 2, centro + largura / 2
        linha = next((k for k, usados in enumerate(linhas_ocupadas)
                      if all(x1 + 20 < u0 or x0 - 20 > u1 for u0, u1 in usados)), None)
        if linha is None:
            linhas_ocupadas.append([])
            linha = len(linhas_ocupadas) - 1
        linhas_ocupadas[linha].append((x0, x1))
        y = y_base + linha * 100

        pool_res = resumo["por_pool"].get(pid) if resumo else None
        for k, nome in enumerate(visiveis):
            x = x0 + ESPACO_TRAB * (k + 0.5)
            util = None
            if pool_res:
                util = (pool_res["trabalhadores"].get(nome) if nome in pool_res["trabalhadores"]
                        else pool_res["utilizacao"])
            if nome.endswith("_x"):
                rotulo = f"{t.funcao}\n×{t.quantidade}" if not t.ilimitado else f"{t.funcao}\n(ilimitado)"
            else:
                rotulo = nome
            dica = f"<b>{t.funcao}</b>" + (f"<br>{nome}" if not nome.endswith("_x") else "")
            if util is not None:
                dica += f"<br>Utilização: {util:.0%}"
            nos.append({
                "id": nome, "tipo": "trabalhador", "label": rotulo, "title": dica, "x": x, "y": y,
                "forma": "ellipse", "cor": cor_utilizacao(util) if util is not None else COR["trabalhador"],
                "borda": COR["gargalo"] if pid == gargalo_dinamico else COR["borda"],
                "borda_largura": 4 if pid == gargalo_dinamico else 2, "critica": False, "pool": pid,
            })

    # --- arestas
    arestas: List[dict] = []
    for i in ordem:
        for p in proc.atividades[i].predecessoras:
            critica = p in criticas and i in criticas
            arestas.append({"origem": p, "destino": i, "tipo": "precedencia",
                            "cor": COR["critico"] if critica else COR["seta"],
                            "largura": 4 if critica else 2, "tracejada": False, "critica": critica})
    for pid, t, servidas, visiveis, centro, largura in blocos:
        for nome in visiveis:
            for i in servidas:
                arestas.append({"origem": nome, "destino": i, "tipo": "trabalhador", "cor": COR["pool_seta"],
                                "largura": 1, "tracejada": True, "critica": False})
    return {"nos": nos, "arestas": arestas, "unidade": un}
