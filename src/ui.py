from typing import Dict, List, Optional, Any
import pandas as pd
import streamlit as st
import altair as alt
from pyvis.network import Network

from src.domain import ResultadoSimulacao
from src.rede import LinhaProducao
from src.simulacao import MotorDES

VERDE, AMARELO, VERMELHO, AZUL = "#3fb950", "#d29922", "#f85149", "#388bfd"
COR_POR_TIPO = {"doca": "#1f6feb", "triagem": AMARELO, "estoque": VERDE, "inspecao": "#f0883e"}


def html(conteudo: str):
    st.markdown(conteudo, unsafe_allow_html=True)


def card(label: str, valor: str, detalhe: str = "", status: str = "", pequeno: bool = False):
    """Card de métrica. status = good / warn / bad (muda a cor da borda e do detalhe)."""
    classe_valor = "metric-value-tcc small" if pequeno else "metric-value-tcc"
    html(f"""
    <div class="metric-card-tcc delta-{status}">
      <div class="metric-label-tcc">{label}</div>
      <div class="{classe_valor}">{valor}</div>
      <div class="metric-delta-tcc delta-{status}">{detalhe}</div>
    </div>""")


def titulo_secao(icone: str, titulo: str, badge: str = "", descricao: str = ""):
    """Título de seção com uma frase curta explicando o que o bloco mostra."""
    badge_html = f'<span class="section-badge-tcc">{badge}</span>' if badge else ""
    desc_html = f'<div class="section-desc-tcc">{descricao}</div>' if descricao else ""
    html(f"""
    <div class="section-header-tcc">
      <span class="section-icon-tcc">{icone}</span>
      <span class="section-title-tcc">{titulo}</span>{badge_html}
    </div>{desc_html}""")


def _tema_escuro(grafico: alt.Chart, altura: int = 280) -> alt.Chart:
    """Aplica as mesmas cores de eixo/grade em todos os gráficos."""
    return (
        grafico.properties(height=altura)
        .configure_view(strokeWidth=0)
        .configure_axis(labelColor="#8b949e", titleColor="#c9d1d9", gridColor="#21262d", domainColor="#30363d")
        .configure_legend(labelColor="#c9d1d9", titleColor="#8b949e", orient="bottom")
    )


def grafo(linha: LinhaProducao, resultado: Optional[ResultadoSimulacao]):
    """Desenha o grafo com pyvis. A aresta crítica fica vermelha quando o gargalo é ativado."""
    titulo_secao(
        "🕸️", "Mapa da Rede Logística — Grafo G=(V,E)", "INTERATIVO",
        "Cada <b>círculo (vértice)</b> é uma estação do armazém e cada <b>seta (aresta)</b> é o caminho "
        "que o palete percorre. Nas setas: <b>c</b> = capacidade máxima, <b>f</b> = paletes que passaram.",
    )
    html(f"""
    <div class="legend-row">
      <span><i class="dot" style="background:{AZUL}"></i>Fluxo normal (f &lt; c)</span>
      <span><i class="dot" style="background:{VERMELHO}"></i>Gargalo — aresta saturada (f ≥ c)</span>
      <span>🖱️ Passe o mouse nos nós e setas para ver detalhes</span>
    </div>""")

    net = Network(height="520px", width="100%", bgcolor="#0d1117", font_color="#e6edf3", directed=True)
    net.set_options("""{
      "physics": {"enabled": false},
      "edges": {"smooth": {"type": "curvedCW", "roundness": 0.15},
                "font": {"size": 12, "color": "#8b949e", "strokeWidth": 0, "background": "#161b22"}},
      "nodes": {"font": {"multi": true, "size": 13}},
      "interaction": {"hover": true, "tooltipDelay": 200}
    }""")

    tamanho = {"doca": 55, "triagem": 48, "inspecao": 45, "estoque": 38}
    for no in linha.nos.values():
        dica = (f"<b>{no.id}</b><br>Tipo: {no.tipo}<br>Capacidade: {no.capacidade_interna} paletes"
                f"<br>T. proc. base: {no.tempo_proc_base} min")
        net.add_node(no.id, label=no.rotulo, title=dica, size=tamanho.get(no.tipo, 40),
                     x=no.x, y=no.y, physics=False, borderWidth=2,
                     color={"background": no.cor, "border": "#e6edf3"})

    gargalo = resultado is not None and resultado.gargalo_ativado
    for (orig, dest), aresta in linha.arestas.items():
        saturada = gargalo and (orig, dest) == linha.aresta_critica
        uso = min(100, int(aresta.fluxo_atual / aresta.capacidade * 100))
        net.add_edge(orig, dest,
                     label=f"c={aresta.capacidade}\nf={aresta.fluxo_atual}\n({uso}%)",
                     title=f"{orig} → {dest}<br>c={aresta.capacidade} · f={aresta.fluxo_atual} · {uso}%",
                     color=VERMELHO if saturada else AZUL, width=5 if saturada else 3)

    st.iframe(net.generate_html(), height=540)


def histograma_espera(tempos_espera: List[float]):
    titulo_secao(
        "📊", "Distribuição dos Tempos de Espera", "HISTOGRAMA",
        "Quantos paletes esperaram quanto tempo na fila da estação crítica. "
        "Barras concentradas à esquerda = sistema saudável; cauda longa à direita = gargalo.",
    )
    if all(t <= 0.01 for t in tempos_espera):
        html(f'<div class="hint-box" style="color:{VERDE}">✅ Nenhuma espera significativa — '
             'o sistema fluiu sem filas.</div>')
        return

    grafico = alt.Chart(pd.DataFrame({"espera": tempos_espera})).mark_bar(color=VERMELHO).encode(
        x=alt.X("espera:Q", bin=alt.Bin(maxbins=25), title="Tempo de espera (u.t.)"),
        y=alt.Y("count()", title="Paletes"),
    )
    st.altair_chart(_tema_escuro(grafico, 300), width="stretch")


def utilizacao_estacoes(estatisticas: Dict[str, Dict[str, Any]], linha: LinhaProducao):
    titulo_secao(
        "🏗️", "Utilização por Estação de Trabalho", "OCUPAÇÃO",
        "Percentual do tempo em que cada estação ficou ocupada. "
        "🟢 &lt; 50% folga · 🟡 50–80% atenção · 🔴 &gt; 80% sobrecarregada.",
    )
    dados = []
    for est_id, m in estatisticas.items():
        u = m["utilizacao"]
        dados.append({
            "estacao": linha.nos[est_id].rotulo.replace("\n", " "),
            "utilizacao": round(u, 2),
            "cor": VERDE if u < 50 else AMARELO if u < 80 else VERMELHO,
        })

    grafico = alt.Chart(pd.DataFrame(dados)).mark_bar(cornerRadiusEnd=4).encode(
        y=alt.Y("estacao:N", title=None, sort="-x"),
        x=alt.X("utilizacao:Q", title="Utilização (%)", scale=alt.Scale(domain=[0, 100])),
        color=alt.Color("cor:N", scale=None),
        tooltip=["estacao", "utilizacao"],
    )
    st.altair_chart(_tema_escuro(grafico, max(180, len(dados) * 50)), width="stretch")


def evolucao_filas(logs_detalhados: List[Dict[str, Any]], linha: LinhaProducao):
    """Tamanho da fila de cada estação ao longo do tempo (agrupado em intervalos de 0,5 u.t.)."""
    titulo_secao(
        "⏱️", "Evolução das Filas ao Longo do Tempo", "TIMELINE",
        "Tamanho da fila em cada estação durante a simulação. Uma linha que só sobe indica "
        "que a estação não dá conta da demanda.",
    )
    df = pd.DataFrame(logs_detalhados)
    df = df[df["evento"] == "chegada_fila"].copy()
    df["tempo"] = (df["tempo"] * 2).round() / 2
    df = df.groupby(["tempo", "estacao"])["tamanho_fila"].max().reset_index()

    nomes = {nid: no.rotulo.replace("\n", " ") for nid, no in linha.nos.items()}
    df["nome"] = df["estacao"].map(nomes)
    cores = [COR_POR_TIPO.get(linha.nos[nid].tipo, "#8b949e") for nid in nomes]

    grafico = alt.Chart(df).mark_line(strokeWidth=2, interpolate="monotone").encode(
        x=alt.X("tempo:Q", title="Tempo simulado (u.t.)"),
        y=alt.Y("tamanho_fila:Q", title="Tamanho da fila"),
        color=alt.Color("nome:N", title="Estação", scale=alt.Scale(domain=list(nomes.values()), range=cores)),
        tooltip=["tempo", "nome", "tamanho_fila"],
    )
    st.altair_chart(_tema_escuro(grafico, 350), width="stretch")


def comparativo_topologias(volume: int, capacidade: int, seed: int, presets: Dict[str, Dict]):
    """Roda as 3 topologias com os mesmos parâmetros e compara lado a lado."""
    titulo_secao(
        "🔄", "Comparativo Entre as 3 Topologias", "MESMOS PARÂMETROS",
        "As três configurações de armazém rodadas com o mesmo volume, capacidade e seed — "
        "mostra qual layout lida melhor com a mesma carga.",
    )
    linhas = []
    for preset, info in presets.items():
        linha = LinhaProducao(preset, capacidade)
        res = MotorDES(linha, volume, seed=seed).executar()
        fluxo_max, _ = linha.calcular_corte_minimo()
        linhas.append({
            "Topologia": info["nome"],
            "Nós": len(linha.nos),
            "Arestas": len(linha.arestas),
            "Gargalo": "⚠️ SIM" if res.gargalo_ativado else "✅ NÃO",
            "Espera média (u.t.)": round(res.tempo_medio_espera, 3),
            "Espera máx (u.t.)": round(res.tempo_max_espera, 3),
            "% com espera": round(res.pct_com_espera, 1),
            "Fluxo máx. teórico": int(fluxo_max),
            "Exec. (ms)": round(res.tempo_execucao_seg * 1000, 1),
        })
    df = pd.DataFrame(linhas)
    st.dataframe(df, hide_index=True, width="stretch")

    grafico = alt.Chart(df).mark_bar(cornerRadiusEnd=4, color=AZUL).encode(
        x=alt.X("Topologia:N", title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("Espera média (u.t.):Q"),
    )
    st.altair_chart(_tema_escuro(grafico), width="stretch")


def curvas_saturacao(resultados_batch: List[Dict[str, Any]], volume: int, preset: str):
    """Gráficos da análise em lote: espera e % de paletes com espera conforme a capacidade cresce."""
    titulo_secao(
        "📈", "Curvas de Saturação — variando a capacidade", "BATCH",
        "A mesma simulação foi repetida para várias capacidades da aresta crítica. "
        "O ponto onde a curva “despenca” é a capacidade mínima que elimina o gargalo.",
    )
    html(f'<div class="comparison-label">{len(resultados_batch)} cenários · '
         f'N = {volume} paletes · topologia: {preset}</div>')

    df = pd.DataFrame(resultados_batch)
    col1, col2 = st.columns(2)
    for col, campo, titulo, cor in [
        (col1, "tempo_medio_espera", "Tempo médio de espera (u.t.)", VERMELHO),
        (col2, "pct_com_espera", "% de paletes com espera", AMARELO),
    ]:
        grafico = alt.Chart(df).mark_line(point=True, color=cor).encode(
            x=alt.X("capacidade:Q", title="Capacidade c(u,v)"),
            y=alt.Y(f"{campo}:Q", title=titulo),
            tooltip=["capacidade", campo, "gargalo"],
        )
        col.altair_chart(_tema_escuro(grafico), width="stretch")
