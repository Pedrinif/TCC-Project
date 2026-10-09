from typing import Dict, List, Optional, Any
import pandas as pd
import streamlit as st
import altair as alt
from pyvis.network import Network

from src.domain import ResultadoSimulacao
from src.rede import LinhaProducao
from src.simulacao import MotorDES

# Cores de cada tema. O Streamlit cuida dos widgets (config.toml);
# estas aqui valem para os nossos cards, banners e gráficos.
PALETAS = {
    "dark": {
        "bg": "#0b0f14", "sidebar": "#0d1117", "surface": "#161b22", "border": "#30363d",
        "border-soft": "#21262d", "text": "#c9d1d9", "text-strong": "#f0f6fc", "muted": "#8b949e",
        "accent": "#58a6ff", "good": "#3fb950", "warn": "#d29922", "bad": "#f85149", "blue": "#388bfd",
        "bad-bg": "#2b0f14", "bad-text": "#ffa198", "ok-bg": "#0e2a14", "ok-text": "#7ee787",
        "glow": "rgba(88,166,255,0.10)", "shadow": "rgba(0,0,0,0.18)",
    },
    "light": {
        "bg": "#f6f8fa", "sidebar": "#ffffff", "surface": "#ffffff", "border": "#d0d7de",
        "border-soft": "#e5e9ee", "text": "#424a53", "text-strong": "#1f2328", "muted": "#656d76",
        "accent": "#0969da", "good": "#1a7f37", "warn": "#9a6700", "bad": "#cf222e", "blue": "#0969da",
        "bad-bg": "#ffebe9", "bad-text": "#a40e26", "ok-bg": "#dafbe1", "ok-text": "#116329",
        "glow": "rgba(9,105,218,0.08)", "shadow": "rgba(31,35,40,0.08)",
    },
}


def tema() -> str:
    """Tema ativo no Streamlit: 'dark' ou 'light'."""
    return st.context.theme.type or "dark"


def paleta() -> Dict[str, str]:
    return PALETAS[tema()]


def css_do_tema() -> str:
    """Transforma a paleta em variáveis CSS (--bg, --surface...) usadas no style.css."""
    return ":root{" + ";".join(f"--{k}:{v}" for k, v in paleta().items()) + "}"


def html(conteudo: str):
    st.markdown(conteudo, unsafe_allow_html=True)


def ico(nome: str) -> str:
    """Ícone do Material Symbols (nome em https://fonts.google.com/icons) para usar dentro de HTML."""
    return f'<span class="ico">{nome}</span>'


def botao_tema():
    """
    Botão claro/escuro. O Streamlit guarda a escolha de tema no localStorage do navegador,
    então gravamos lá e recarregamos a página (um iframe pequeno roda esse script).
    """
    p = paleta()
    escuro = tema() == "dark"
    novo = "Light" if escuro else "Dark"
    st.iframe(f"""
    <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded&family=Inter:wght@500&display=swap" rel="stylesheet">
    <style>
      body {{ margin: 0; }}
      button {{ width: 100%; height: 36px; display: flex; align-items: center; justify-content: center; gap: 8px;
               background: {p['surface']}; color: {p['text-strong']}; border: 1px solid {p['border']};
               border-radius: 8px; font: 500 13px Inter, sans-serif; cursor: pointer; }}
      button:hover {{ border-color: {p['accent']}; color: {p['accent']}; }}
      .i {{ font-family: 'Material Symbols Rounded'; font-size: 18px; }}
    </style>
    <button id="b"><span class="i">{'light_mode' if escuro else 'dark_mode'}</span>{'Modo claro' if escuro else 'Modo escuro'}</button>
    <script>
      document.getElementById('b').onclick = () => {{
        parent.localStorage.setItem('stActiveTheme-/-v2', JSON.stringify('{novo}'));
        parent.location.reload();
      }};
    </script>""", height=40)


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
    """Título de seção com ícone e uma frase curta explicando o que o bloco mostra."""
    badge_html = f'<span class="section-badge-tcc">{badge}</span>' if badge else ""
    desc_html = f'<div class="section-desc-tcc">{descricao}</div>' if descricao else ""
    html(f"""
    <div class="section-header-tcc">
      <span class="section-icon-tcc">{ico(icone)}</span>
      <span class="section-title-tcc">{titulo}</span>{badge_html}
    </div>{desc_html}""")


def banner(tipo: str, texto: str, compacto: bool = False):
    """Faixa de aviso: tipo 'bad' (gargalo) ou 'ok' (fluxo estável)."""
    classe = "bottleneck-banner" if tipo == "bad" else "ok-banner"
    icone = "warning" if tipo == "bad" else "check_circle"
    html(f'<div class="{classe}{" compact" if compacto else ""}">'
         f'<span class="icon">{ico(icone)}</span><span class="text">{texto}</span></div>')


def _estilo(grafico: alt.Chart, altura: int = 280) -> alt.Chart:
    """Aplica as cores do tema ativo (eixos, grade, legenda) em todos os gráficos."""
    p = paleta()
    return (
        grafico.properties(height=altura)
        .configure_view(strokeWidth=0)
        .configure_axis(labelColor=p["muted"], titleColor=p["text"], gridColor=p["border-soft"], domainColor=p["border"])
        .configure_legend(labelColor=p["text"], titleColor=p["muted"], orient="bottom")
    )


def grafo(linha: LinhaProducao, resultado: Optional[ResultadoSimulacao]):
    """Desenha o grafo com pyvis. A aresta crítica fica vermelha quando o gargalo é ativado."""
    p = paleta()
    titulo_secao(
        "hub", "Mapa da Rede Logística — Grafo G=(V,E)", "INTERATIVO",
        "Cada <b>círculo (vértice)</b> é uma estação do armazém e cada <b>seta (aresta)</b> é o caminho "
        "que o palete percorre. Nas setas: <b>c</b> = capacidade máxima, <b>f</b> = paletes que passaram.",
    )
    html(f"""
    <div class="legend-row">
      <span><i class="dot" style="background:{p['blue']}"></i>Fluxo normal (f &lt; c)</span>
      <span><i class="dot" style="background:{p['bad']}"></i>Gargalo — aresta saturada (f ≥ c)</span>
      <span>{ico('mouse')} Passe o mouse nos nós e setas para ver detalhes</span>
    </div>""")

    net = Network(height="520px", width="100%", bgcolor=p["surface"], font_color=p["text-strong"], directed=True)
    net.set_options("""{
      "physics": {"enabled": false},
      "edges": {"smooth": {"type": "curvedCW", "roundness": 0.15},
                "font": {"size": 12, "color": "%s", "strokeWidth": 0, "background": "%s"}},
      "nodes": {"font": {"multi": true, "size": 13}},
      "interaction": {"hover": true, "tooltipDelay": 200}
    }""" % (p["muted"], p["surface"]))

    tamanho = {"doca": 55, "triagem": 48, "inspecao": 45, "estoque": 38}
    for no in linha.nos.values():
        dica = (f"<b>{no.id}</b><br>Tipo: {no.tipo}<br>Capacidade: {no.capacidade_interna} paletes"
                f"<br>T. proc. base: {no.tempo_proc_base} min")
        net.add_node(no.id, label=no.rotulo, title=dica, size=tamanho.get(no.tipo, 40),
                     x=no.x, y=no.y, physics=False, borderWidth=2,
                     color={"background": no.cor, "border": p["border"]})

    gargalo = resultado is not None and resultado.gargalo_ativado
    for (orig, dest), aresta in linha.arestas.items():
        saturada = gargalo and (orig, dest) == linha.aresta_critica
        uso = min(100, int(aresta.fluxo_atual / aresta.capacidade * 100))
        net.add_edge(orig, dest,
                     label=f"c={aresta.capacidade}\nf={aresta.fluxo_atual}\n({uso}%)",
                     title=f"{orig} → {dest}<br>c={aresta.capacidade} · f={aresta.fluxo_atual} · {uso}%",
                     color=p["bad"] if saturada else p["blue"], width=5 if saturada else 3)

    st.iframe(net.generate_html(), height=540)


def histograma_espera(tempos_espera: List[float]):
    p = paleta()
    titulo_secao(
        "bar_chart", "Distribuição dos Tempos de Espera", "HISTOGRAMA",
        "Quantos paletes esperaram quanto tempo na fila da estação crítica. "
        "Barras concentradas à esquerda = sistema saudável; cauda longa à direita = gargalo.",
    )
    if all(t <= 0.01 for t in tempos_espera):
        html(f'<div class="hint-box" style="color:{p["good"]}">{ico("check_circle")} Nenhuma espera '
             'significativa — o sistema fluiu sem filas.</div>')
        return

    grafico = alt.Chart(pd.DataFrame({"espera": tempos_espera})).mark_bar(color=p["bad"]).encode(
        x=alt.X("espera:Q", bin=alt.Bin(maxbins=25), title="Tempo de espera (u.t.)"),
        y=alt.Y("count()", title="Paletes"),
    )
    st.altair_chart(_estilo(grafico, 300), width="stretch")


def utilizacao_estacoes(estatisticas: Dict[str, Dict[str, Any]], linha: LinhaProducao):
    p = paleta()
    titulo_secao(
        "speed", "Utilização por Estação de Trabalho", "OCUPAÇÃO",
        "Percentual do tempo em que cada estação ficou ocupada. "
        f'<i class="dot" style="background:{p["good"]}"></i>&lt; 50% folga · '
        f'<i class="dot" style="background:{p["warn"]}"></i>50–80% atenção · '
        f'<i class="dot" style="background:{p["bad"]}"></i>&gt; 80% sobrecarregada.',
    )
    dados = []
    for est_id, m in estatisticas.items():
        u = m["utilizacao"]
        dados.append({
            "estacao": linha.nos[est_id].rotulo.replace("\n", " "),
            "utilizacao": round(u, 2),
            "cor": p["good"] if u < 50 else p["warn"] if u < 80 else p["bad"],
        })

    grafico = alt.Chart(pd.DataFrame(dados)).mark_bar(cornerRadiusEnd=4).encode(
        y=alt.Y("estacao:N", title=None, sort="-x"),
        x=alt.X("utilizacao:Q", title="Utilização (%)", scale=alt.Scale(domain=[0, 100])),
        color=alt.Color("cor:N", scale=None),
        tooltip=["estacao", "utilizacao"],
    )
    st.altair_chart(_estilo(grafico, max(180, len(dados) * 50)), width="stretch")


def evolucao_filas(logs_detalhados: List[Dict[str, Any]], linha: LinhaProducao):
    """Tamanho da fila de cada estação ao longo do tempo (agrupado em intervalos de 0,5 u.t.)."""
    p = paleta()
    titulo_secao(
        "timeline", "Evolução das Filas ao Longo do Tempo", "TIMELINE",
        "Tamanho da fila em cada estação durante a simulação. Uma linha que só sobe indica "
        "que a estação não dá conta da demanda.",
    )
    df = pd.DataFrame(logs_detalhados)
    df = df[df["evento"] == "chegada_fila"].copy()
    df["tempo"] = (df["tempo"] * 2).round() / 2
    df = df.groupby(["tempo", "estacao"])["tamanho_fila"].max().reset_index()

    nomes = {nid: no.rotulo.replace("\n", " ") for nid, no in linha.nos.items()}
    df["nome"] = df["estacao"].map(nomes)
    cor_por_tipo = {"doca": p["blue"], "triagem": p["warn"], "estoque": p["good"], "inspecao": "#f0883e"}
    cores = [cor_por_tipo.get(linha.nos[nid].tipo, p["muted"]) for nid in nomes]

    grafico = alt.Chart(df).mark_line(strokeWidth=2, interpolate="monotone").encode(
        x=alt.X("tempo:Q", title="Tempo simulado (u.t.)"),
        y=alt.Y("tamanho_fila:Q", title="Tamanho da fila"),
        color=alt.Color("nome:N", title="Estação", scale=alt.Scale(domain=list(nomes.values()), range=cores)),
        tooltip=["tempo", "nome", "tamanho_fila"],
    )
    st.altair_chart(_estilo(grafico, 350), width="stretch")


def comparativo_topologias(volume: int, capacidade: int, seed: int, presets: Dict[str, Dict]):
    """Roda as 3 topologias com os mesmos parâmetros e compara lado a lado."""
    titulo_secao(
        "compare_arrows", "Comparativo Entre as 3 Topologias", "MESMOS PARÂMETROS",
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
            "Gargalo": "Sim" if res.gargalo_ativado else "Não",
            "Espera média (u.t.)": round(res.tempo_medio_espera, 3),
            "Espera máx (u.t.)": round(res.tempo_max_espera, 3),
            "% com espera": round(res.pct_com_espera, 1),
            "Fluxo máx. teórico": int(fluxo_max),
            "Exec. (ms)": round(res.tempo_execucao_seg * 1000, 1),
        })
    df = pd.DataFrame(linhas)
    st.dataframe(df, hide_index=True, width="stretch")

    grafico = alt.Chart(df).mark_bar(cornerRadiusEnd=4, color=paleta()["blue"]).encode(
        x=alt.X("Topologia:N", title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("Espera média (u.t.):Q"),
    )
    st.altair_chart(_estilo(grafico), width="stretch")


def curvas_saturacao(resultados_batch: List[Dict[str, Any]], volume: int, preset: str):
    """Gráficos da análise em lote: espera e % de paletes com espera conforme a capacidade cresce."""
    p = paleta()
    titulo_secao(
        "show_chart", "Curvas de Saturação — variando a capacidade", "BATCH",
        "A mesma simulação foi repetida para várias capacidades da aresta crítica. "
        "O ponto onde a curva “despenca” é a capacidade mínima que elimina o gargalo.",
    )
    html(f'<div class="comparison-label">{len(resultados_batch)} cenários · '
         f'N = {volume} paletes · topologia: {preset}</div>')

    df = pd.DataFrame(resultados_batch)
    col1, col2 = st.columns(2)
    for col, campo, titulo, cor in [
        (col1, "tempo_medio_espera", "Tempo médio de espera (u.t.)", p["bad"]),
        (col2, "pct_com_espera", "% de paletes com espera", p["warn"]),
    ]:
        grafico = alt.Chart(df).mark_line(point=True, color=cor).encode(
            x=alt.X("capacidade:Q", title="Capacidade c(u,v)"),
            y=alt.Y(f"{campo}:Q", title=titulo),
            tooltip=["capacidade", campo, "gargalo"],
        )
        col.altair_chart(_estilo(grafico), width="stretch")
