"""
Página "Processos reais" (modelos M4 e M5): processos em YAML, trabalhadores com nome e réplicas.

  - o grafo é interativo (arraste, use a roda do mouse para ampliar/reduzir);
  - mude a quantidade de cada trabalhador na barra lateral e o grafo ganha A_1, A_2...;
  - depois de simular, as cores mostram a utilização e a borda vermelha o gargalo.
"""
import io
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
import yaml
from pyvis.network import Network

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src import ui  # noqa: E402
from src.estrutural import analise_estrutural  # noqa: E402
from src.grafo_processo import COR, montar_grafo  # noqa: E402
from src.motor import MotorProcesso  # noqa: E402
from src.processo import carregar_processo  # noqa: E402
from src.replicacoes import agregar, executar_replicas, recomendar, resumo_medio, varrer_pool  # noqa: E402

st.set_page_config(page_title="Processos reais · ECOMUP", page_icon=":material/hub:", layout="wide")
with open(RAIZ / "style.css", encoding="utf-8") as f:
    ui.html(f"<style>{ui.css_do_tema()}{f.read()}</style>")


# ---------------------------------------------------------------- barra lateral
def _arquivos():
    return sorted(str(p) for p in (RAIZ / "processos").glob("*.yaml"))


def _info_yaml(caminho: str) -> dict:
    with open(caminho, encoding="utf-8") as f:
        return yaml.safe_load(f)


def barra_lateral():
    """Escolhe o processo e deixa editar trabalhadores, tempos e chegadas. Devolve (proc, opções)."""
    with st.sidebar:
        ui.html(f'<div class="sidebar-title">{ui.ico("tune")} Processo e variáveis</div>')
        ui.botao_tema()

        arquivos = _arquivos()
        if not arquivos:
            st.error("Nenhum arquivo .yaml em processos/.")
            st.stop()
        arq = st.selectbox("Processo", arquivos, format_func=lambda a: _info_yaml(a)["nome"])
        variantes = list(_info_yaml(arq).get("variantes", {}))
        var = None
        if variantes:
            var = st.selectbox("Variante", [None] + variantes, format_func=lambda v: "base" if v is None else v)
        proc = carregar_processo(arq, var)
        chave = f"{Path(arq).stem}|{var}"

        st.markdown("**Trabalhadores**")
        st.caption("Aumente a quantidade e o grafo ganha um círculo para cada trabalhador (A_1, A_2...).")
        for pid, t in proc.trabalhadores.items():
            if not any(a.trabalhador == pid for a in proc.atividades.values()):
                continue
            q = st.number_input(t.funcao, 1, 200, int(t.quantidade), 1, key=f"q|{chave}|{pid}")
            ef = st.number_input(f"Eficiência — {t.funcao}", 0.5, 2.0, float(t.eficiencia), 0.05,
                                 key=f"ef|{chave}|{pid}", help="1,2 = trabalha 20% mais rápido")
            proc.definir_quantidade(pid, q)
            t.eficiencia = ef

        with st.expander("Tempos das atividades"):
            st.caption("Fator sobre o tempo original (1,0 = como na fonte).")
            for aid, a in proc.atividades.items():
                f = st.slider(a.nome, 0.5, 2.0, 1.0, 0.05, key=f"t|{chave}|{aid}")
                if abs(f - 1.0) > 1e-9:
                    proc.escalar_duracao(aid, f)

        if proc.chegadas.tipo in ("poisson", "determinista"):
            proc.chegadas.n_entidades = st.number_input("Número de entidades", 10, 5000, int(proc.chegadas.n_entidades),
                                                        10, key=f"n|{chave}")

        st.markdown("**Simulação**")
        replicas = st.slider("Réplicas", 1, 100, 20, help="Cada réplica usa uma semente diferente; "
                             "com 2 ou mais réplicas aparece o intervalo de confiança de 95%.")
        seed = st.number_input("Semente base", 1, 100000, 1000, 1)
        executar = st.button(":material/play_arrow: Executar simulação", type="primary", width="stretch")
    return proc, dict(arquivo=arq, variante=var, replicas=int(replicas), seed=int(seed), executar=executar)


def assinatura(proc, op) -> str:
    """Resumo da configuração atual; serve para saber se o resultado guardado ainda vale."""
    return repr((op["arquivo"], op["variante"], op["replicas"], op["seed"],
                 [(p, t.quantidade, t.eficiencia) for p, t in proc.trabalhadores.items()],
                 [(i, round(a.duracao.media(), 6)) for i, a in proc.atividades.items()],
                 proc.chegadas.n_entidades))


# ---------------------------------------------------------------- desenho
def desenhar(g: dict, altura: int = 560):
    p = ui.paleta()
    net = Network(height=f"{altura}px", width="100%", bgcolor=p["surface"], font_color=p["text-strong"], directed=True)
    net.set_options("""{
      "physics": {"enabled": false},
      "edges": {"smooth": {"type": "cubicBezier", "forceDirection": "horizontal", "roundness": 0.4}},
      "nodes": {"font": {"size": 13}},
      "interaction": {"hover": true, "tooltipDelay": 150, "zoomView": true, "dragView": true}
    }""")
    claros = (COR["neutro"], COR["alta"], COR["trabalhador"])
    for n in g["nos"]:
        net.add_node(n["id"], label=n["label"], title=n["title"], x=n["x"], y=n["y"], physics=False,
                     shape=n["forma"], borderWidth=n["borda_largura"],
                     color={"background": n["cor"], "border": n["borda"]},
                     font={"color": "#ffffff" if n["cor"] in claros else "#0b0f14", "size": 13})
    for a in g["arestas"]:
        net.add_edge(a["origem"], a["destino"], color=a["cor"], width=a["largura"], dashes=a["tracejada"])
    st.iframe(net.generate_html(), height=altura + 20)


def legenda(tem_resultado: bool):
    itens = [
        (COR["neutro"], "Atividade (sem resultado ainda)" if not tem_resultado else "Atividade sem pool"),
        (COR["trabalhador"], "Trabalhador"),
        (COR["critico"], "Seta vermelha = caminho crítico (CPM)"),
        (COR["estrutural"], "Borda laranja = gargalo estrutural (menor capacidade)"),
    ]
    if tem_resultado:
        itens += [(COR["baixa"], "Utilização < 60%"), (COR["media"], "60% a 85%"), (COR["alta"], "≥ 85%"),
                  (COR["gargalo"], "Borda vermelha grossa = gargalo dinâmico (onde mais se espera)")]
    ui.html('<div class="legend-row">' + "".join(
        f'<span><i class="dot" style="background:{c}"></i>{t}</span>' for c, t in itens) + "</div>")


# ---------------------------------------------------------------- abas
def aba_grafo(proc, resumo):
    ui.titulo_secao("hub", "Grafo do processo", "INTERATIVO",
                    "Retângulos são <b>atividades</b> (setas = precedência); círculos são <b>trabalhadores</b> "
                    "(linhas tracejadas ligam cada um às atividades que executa). Arraste e use a roda do mouse.")
    if resumo is None:
        st.caption("Mostrando só a estrutura. Clique em **Executar simulação** para colorir utilização e gargalo.")
    legenda(resumo is not None)
    desenhar(montar_grafo(proc, resumo))


def aba_resultados(proc, resumos, op):
    un = proc.unidade_tempo
    ag = agregar(resumos, {
        "ts": lambda r: r["tempo_sistema_medio"], "fim": lambda r: r["ultimo_fim"],
        "vazao": lambda r: r["vazao"],
    })
    medio = resumo_medio(resumos)

    def pm(chave, casas=2):
        ic = ag[chave + "_ic"]
        return f"{ag[chave]:.{casas}f}" + (f" ± {ic:.{casas}f}" if ic == ic else "")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        ui.card("Tempo médio no sistema", pm("ts"), f"{un} por entidade (IC 95%)", "good")
    with c2:
        ui.card("Último término", pm("fim"), f"{un} até a última entidade", "good")
    with c3:
        ui.card("Vazão", f"{ag['vazao']:.4g}", f"entidades por {un} (sobre o tempo simulado)", "good")
    g = medio["gargalo"]
    with c4:
        if g is None:
            ui.card("Gargalo dinâmico", "nenhum", "ninguém esperou", "good")
        else:
            ui.card("Gargalo dinâmico", proc.trabalhadores[g].funcao,
                    f"onde mais se espera ({medio['gargalo_frequencia']:.0%} das réplicas)", "bad", pequeno=True)

    ui.titulo_secao("groups", "Trabalhadores", "UTILIZAÇÃO",
                    "Fração do tempo simulado em que cada trabalhador esteve ocupado. Utilização alta sozinha não "
                    "basta para apontar o gargalo: veja também a espera.")
    linhas_pool, linhas_trab = [], []
    for pid, t in proc.trabalhadores.items():
        if pid not in medio["por_pool"] or not any(a.trabalhador == pid for a in proc.atividades.values()):
            continue
        ap = agregar(resumos, {
            "util": lambda r, p=pid: r["por_pool"][p]["utilizacao"],
            "esp": lambda r, p=pid: r["por_pool"][p]["espera_media"],
            "fila": lambda r, p=pid: r["por_pool"][p]["fila_max"],
        })
        linhas_pool.append({"Pool": t.funcao, "Quantidade": t.quantidade,
                            "Utilização (%)": None if ap["util"] is None else round(100 * ap["util"], 1),
                            f"Espera média ({un})": round(ap["esp"], 3),
                            f"± IC95 ({un})": None if ap["esp_ic"] != ap["esp_ic"] else round(ap["esp_ic"], 3),
                            "Fila máxima": round(ap["fila"], 1)})
        for nome, u in medio["por_pool"][pid]["trabalhadores"].items():
            linhas_trab.append({"Trabalhador": nome, "Pool": t.funcao, "Utilização (%)": round(100 * u, 1)})
    st.dataframe(pd.DataFrame(linhas_pool), hide_index=True, width="stretch")
    if linhas_trab:
        df = pd.DataFrame(linhas_trab)
        graf = alt.Chart(df).mark_bar().encode(
            x=alt.X("Utilização (%):Q", scale=alt.Scale(domain=[0, 100])), y=alt.Y("Trabalhador:N", sort=None),
            color=alt.Color("Pool:N"), tooltip=["Trabalhador", "Pool", "Utilização (%)"])
        st.altair_chart(ui._estilo(graf, 40 + 28 * len(df)), width="stretch")

    ui.titulo_secao("account_tree", "Atividades", "ESPERA E CAMINHO CRÍTICO",
                    "Espera = tempo entre estar pronta (predecessoras terminadas) e começar. "
                    "% crítico = fração das entidades em que a atividade determinou o término.")
    st.dataframe(pd.DataFrame([{
        "Atividade": a.nome, f"Duração média ({un})": round(medio["por_atividade"][i]["duracao_media"], 3),
        f"Espera média ({un})": round(medio["por_atividade"][i]["espera_media"], 3),
        "% no caminho crítico": round(100 * medio["criticidade"][i], 1),
    } for i, a in proc.atividades.items()]), hide_index=True, width="stretch")

    with st.expander("Exportar para Excel"):
        st.download_button("Baixar resultados (.xlsx)", data=excel(proc, resumos, op),
                           file_name="resultados_processo.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def aba_estrutural(proc):
    est = analise_estrutural(proc)
    un = proc.unidade_tempo
    ui.titulo_secao("architecture", "Análise estrutural", "SEM SIMULAR",
                    "O que a estrutura do processo já limita: capacidade de cada grupo de trabalhadores, "
                    "caminho crítico (CPM) e, para cadeias, o corte mínimo.")
    cap = est["capacidades"]
    st.dataframe(pd.DataFrame([{
        "Pool": proc.trabalhadores[p].funcao, "Quantidade": proc.trabalhadores[p].quantidade,
        f"Capacidade (entidades/{un})": "ilimitada" if c == float("inf") else round(c, 5),
    } for p, c in cap.items()]), hide_index=True, width="stretch")
    gc = est["gargalo_capacidade"]
    if gc["pool"]:
        ui.banner("bad", f"Gargalo estrutural: <b>{proc.trabalhadores[gc['pool']].funcao}</b> — limita a vazão "
                         f"a {gc['vazao_max']:.4g} entidades por {un}.", compacto=True)
    cm = est["cpm"]
    st.markdown(f"**Caminho crítico (durações médias):** {cm['duracao_minima']:.2f} {un} — "
                + " → ".join(proc.atividades[i].nome for i in cm["atividades_criticas"]))
    st.dataframe(pd.DataFrame([{
        "Atividade": a.nome, "Início mais cedo": round(cm["es"][i], 2), "Fim mais cedo": round(cm["ef"][i], 2),
        "Folga": round(cm["folga"][i], 2), "Crítica": "sim" if i in cm["atividades_criticas"] else "",
    } for i, a in proc.atividades.items()]), hide_index=True, width="stretch")
    corte = est["corte_minimo"]
    if corte is None:
        st.info("Corte mínimo não se aplica: o processo tem atividades em paralelo (todas precisam acontecer), "
                "e somar ramos em paralelo daria um fluxo máximo errado. Use a capacidade por pool e o caminho crítico.")
    else:
        st.markdown(f"**Fluxo máximo / corte mínimo ({corte['metodo']}):** {corte['vazao_max']:.4g} entidades por "
                    f"{un}; atividade(s) no corte: {', '.join(proc.atividades[i].nome for i in corte['corte'])}")


def aba_varredura(proc, op):
    un = proc.unidade_tempo
    ui.titulo_secao("tune", "Quantos trabalhadores?", "VARREDURA",
                    "Repete a simulação variando o número de trabalhadores de um grupo e mostra a espera média "
                    "com intervalo de confiança. A recomendação é o menor número cujo IC fica abaixo do limite.")
    usados = [p for p in proc.trabalhadores if any(a.trabalhador == p for a in proc.atividades.values())]
    c1, c2, c3, c4, c5 = st.columns(5)
    pool = c1.selectbox("Grupo", usados, format_func=lambda p: proc.trabalhadores[p].funcao)
    de = c2.number_input("De", 1, 100, 1, 1)
    ate = c3.number_input("Até", 1, 100, 6, 1)
    reps = c4.number_input("Réplicas por ponto", 2, 100, 10, 1)
    limite = c5.number_input(f"Espera máxima aceita ({un})", 0.0, 1e6, 0.0, 1.0)
    if st.button(":material/play_arrow: Executar varredura"):
        if ate < de:
            st.error("'Até' precisa ser maior ou igual a 'De'.")
            return
        with st.spinner("Simulando..."):
            df = varrer_pool(proc, pool, list(range(int(de), int(ate) + 1)), int(reps), op["seed"])
        st.session_state["varredura"] = (pool, df, limite)
    if "varredura" in st.session_state:
        pool_v, df, lim = st.session_state["varredura"]
        mostra = df.rename(columns={"quantidade": "Quantidade", "espera_pool": f"Espera média ({un})",
                                    "espera_pool_ic": "± IC95", "utilizacao": "Utilização",
                                    "tempo_sistema": f"Tempo no sistema ({un})", "ultimo_fim": f"Último término ({un})"})
        st.dataframe(mostra[["Quantidade", f"Espera média ({un})", "± IC95", "Utilização",
                             f"Tempo no sistema ({un})", f"Último término ({un})"]].round(3),
                     hide_index=True, width="stretch")
        d = df.copy()
        d["inf"] = (d["espera_pool"] - d["espera_pool_ic"].fillna(0)).clip(lower=0)
        d["sup"] = d["espera_pool"] + d["espera_pool_ic"].fillna(0)
        base = alt.Chart(d).encode(x=alt.X("quantidade:O", title="Quantidade de trabalhadores"))
        graf = base.mark_area(opacity=0.25).encode(y=alt.Y("inf:Q", title=f"Espera média ({un})"), y2="sup:Q") \
            + base.mark_line(point=True).encode(y="espera_pool:Q")
        st.altair_chart(ui._estilo(graf, 300), width="stretch")
        if lim > 0:
            rec = recomendar(df, lim)
            if rec is None:
                ui.banner("bad", f"Nenhuma quantidade testada mantém a espera média ≤ {lim:g} {un}.", compacto=True)
            else:
                ui.banner("ok", f"Menor quantidade com espera média ≤ {lim:g} {un}: <b>{rec}</b> "
                                "(limite superior do IC de 95%).", compacto=True)


def aba_fonte(proc):
    st.markdown(f"**Fonte:** {proc.fonte or 'não informada'}")
    if proc.premissas:
        st.markdown("**Premissas (o que NÃO vem da fonte):**")
        for p in proc.premissas:
            st.markdown(f"- {p}")


def excel(proc, resumos, op) -> bytes:
    medio = resumo_medio(resumos)
    un = proc.unidade_tempo
    resumo = pd.DataFrame({"Métrica": ["Processo", "Réplicas", "Semente base", f"Tempo médio no sistema ({un})",
                                       f"Último término ({un})", "Gargalo dinâmico"],
                           "Valor": [proc.nome, len(resumos), op["seed"], round(medio["tempo_sistema_medio"], 4),
                                     round(medio["ultimo_fim"], 4),
                                     proc.trabalhadores[medio["gargalo"]].funcao if medio["gargalo"] else "nenhum"]})
    pools = pd.DataFrame([{"Pool": p, "Trabalhador": n, "Utilização": u}
                          for p, d in medio["por_pool"].items() for n, u in d["trabalhadores"].items()])
    ativ = pd.DataFrame([{"Atividade": i, **{k: v for k, v in d.items()}} for i, d in medio["por_atividade"].items()])
    regs = MotorProcesso(proc.copia(), seed=op["seed"]).executar().registros_df()
    saida = io.BytesIO()
    with pd.ExcelWriter(saida, engine="openpyxl") as w:
        resumo.to_excel(w, sheet_name="Resumo", index=False)
        pools.to_excel(w, sheet_name="Trabalhadores", index=False)
        ativ.to_excel(w, sheet_name="Atividades", index=False)
        regs.to_excel(w, sheet_name="Registros (1 réplica)", index=False)
    return saida.getvalue()


# ---------------------------------------------------------------- página
ui.html(f"""
<div class="main-title">
  <div class="eyebrow">Modelos M4 e M5 · processos documentados</div>
  <h1>Processos reais</h1>
  <div class="subtitle">Escolha um processo, mude a quantidade de trabalhadores e os tempos, e veja
  <b>onde está o gargalo</b> no grafo.</div>
</div>""")

proc, op = barra_lateral()
sig = assinatura(proc, op)

if op["executar"]:
    try:
        with st.spinner(f"Simulando {op['replicas']} réplica(s)..."):
            resumos = executar_replicas(proc, op["replicas"], op["seed"])
        st.session_state["proc_resultado"] = (sig, resumos, proc.copia(), dict(op))
    except Exception as erro:  # mostra o erro na tela em vez de quebrar a página
        st.error(f"Erro na simulação: {erro}")

guardado = st.session_state.get("proc_resultado")
valido = guardado is not None and guardado[0] == sig
if guardado is not None and not valido:
    st.warning("Você mudou as variáveis depois da última simulação. As cores do grafo foram desligadas; "
               "clique em Executar simulação para atualizar.")

resumo_grafo = resumo_medio(guardado[1]) if valido else None
abas = st.tabs([":material/hub: Grafo", ":material/dashboard: Resultados", ":material/architecture: Estrutura",
                ":material/tune: Quantos trabalhadores?", ":material/menu_book: Fonte e premissas"])
with abas[0]:
    aba_grafo(proc, resumo_grafo)
with abas[1]:
    if valido:
        aba_resultados(guardado[2], guardado[1], guardado[3])
    else:
        st.info("Clique em **Executar simulação** na barra lateral.")
with abas[2]:
    aba_estrutural(proc)
with abas[3]:
    aba_varredura(proc, op)
with abas[4]:
    aba_fonte(proc)
