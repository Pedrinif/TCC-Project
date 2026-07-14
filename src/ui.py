from typing import Dict, List, Optional, Any
import streamlit as st
import altair as alt
import streamlit.components.v1 as components
from pyvis.network import Network

from src.domain import ResultadoSimulacao
from src.rede import LinhaProducao

# ═══════════════════════════════════════════════════════════════════════════════
# COMPONENTES VISUAIS AUXILIARES
# ═══════════════════════════════════════════════════════════════════════════════

def render_metric_card(
    label: str,
    value: str,
    delta: str = "",
    delta_tipo: str = "",
    cor: str = "default",
):
    """
    Renderiza os cards de métricas simples com bordas elegantes, exatamente como
    nas capturas de tela (caixas cinzas escuras integradas ao tema sem barras de cor).
    """
    delta_class = f"delta-{delta_tipo}" if delta_tipo else ""
    st.markdown(f"""
    <div class="metric-card-tcc">
      <div class="metric-label-tcc">{label}</div>
      <div class="metric-value-tcc">{value}</div>
      <div class="metric-delta-tcc {delta_class}">{delta}</div>
    </div>
    """, unsafe_allow_html=True)


def render_section_header(icon: str, titulo: str, badge: str = ""):
    """Cabeçalho de seção correspondente ao visual das imagens."""
    badge_html = f'<span class="section-badge-tcc">{badge}</span>' if badge else ""
    st.markdown(f"""
    <div class="section-header-tcc">
      <span class="section-icon-tcc">{icon}</span>
      <span class="section-title-tcc">{titulo}</span>
      {badge_html}
    </div>
    """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# VISUALIZADOR DE GRAFOS COM PYVIS
# ═══════════════════════════════════════════════════════════════════════════════

class VisualizadorGrafo:
    def __init__(self, linha: LinhaProducao, resultado: Optional[ResultadoSimulacao]):
        self.linha = linha
        self.resultado = resultado

    def gerar_html(self) -> str:
        net = Network(
            height="520px",
            width="100%",
            bgcolor="#0d1117",
            font_color="#e6edf3",
            directed=True,
        )

        net.set_options("""
        {
          "physics": {
            "enabled": false
          },
          "edges": {
            "smooth": {
              "type": "curvedCW",
              "roundness": 0.15
            },
            "font": {
              "size": 12,
              "color": "#8b949e",
              "strokeWidth": 0,
              "background": "#161b22"
            }
          },
          "nodes": {
            "font": {
              "multi": true,
              "size": 13,
              "bold": {
                "size": 14
              }
            },
            "shadow": {
              "enabled": true,
              "color": "rgba(0,0,0,0.6)",
              "size": 15,
              "x": 3,
              "y": 3
            }
          },
          "interaction": {
            "hover": true,
            "tooltipDelay": 200
          }
        }
        """)

        tamanho_por_tipo = {
            "doca": 55, "triagem": 48, "estoque": 38, "inspecao": 45
        }

        # Vértices
        for no_id, no in self.linha.nos.items():
            tamanho = tamanho_por_tipo.get(no.tipo, 40)
            tooltip = (
                f"<b>Estação:</b> {no_id}<br>"
                f"<b>Tipo:</b> {no.tipo.capitalize()}<br>"
                f"<b>Capacidade:</b> {no.capacidade_interna} paletes<br>"
                f"<b>T. Proc. Base:</b> {no.tempo_proc_base} min"
            )

            net.add_node(
                no_id,
                label=no.rotulo,
                color={
                    "background": no.cor,
                    "border": "#e6edf3",
                    "highlight": {"background": "#ffffff", "border": "#58a6ff"},
                    "hover": {"background": no.cor, "border": "#58a6ff"},
                },
                size=tamanho,
                x=no.x,
                y=no.y,
                physics=False,
                title=tooltip,
                borderWidth=2,
                borderWidthSelected=3,
            )

        # Arestas
        for (orig, dest), aresta in self.linha.arestas.items():
            saturada = (
                (orig, dest) == self.linha.aresta_critica
                and self.resultado is not None
                and self.resultado.gargalo_ativado
            )

            cor_aresta   = "#f85149" if saturada else "#388bfd"
            largura      = 5 if saturada else 3

            utilizacao_pct = min(100, int((aresta.fluxo_atual / aresta.capacidade) * 100)) \
                if aresta.capacidade > 0 else 0

            rotulo_aresta = (
                f"c={aresta.capacidade}\n"
                f"f={aresta.fluxo_atual}\n"
                f"({utilizacao_pct}%)"
            )

            tooltip_aresta = (
                f"<b>Aresta:</b> ({orig} → {dest})<br>"
                f"<b>Capacidade c(u,v):</b> {aresta.capacidade}<br>"
                f"<b>Fluxo f(u,v):</b> {aresta.fluxo_atual}<br>"
                f"<b>Utilização:</b> {utilizacao_pct}%<br>"
                f"{'⚠️ GARGALO ATIVO' if saturada else '✅ Fluxo normal'}"
            )

            net.add_edge(
                orig, dest,
                label=rotulo_aresta,
                color={"color": cor_aresta, "hover": "#ffffff"},
                width=largura,
                title=tooltip_aresta,
                arrows={"to": {"enabled": True, "scaleFactor": 1.2}},
            )

        return net.generate_html()


def _render_grafo(linha: LinhaProducao, resultado: Optional[ResultadoSimulacao]):
    render_section_header("🕸️", "Grafo Logístico G=(V,E)", "VIS INTERATIVO")

    leg_col1, leg_col2, leg_col3 = st.columns(3)
    with leg_col1:
        st.markdown("🔵 **Aresta normal** — fluxo dentro da capacidade c(u,v) ❓")
    with leg_col2:
        st.markdown("🔴 **Aresta crítica** — gargalo detectado f(u,v) ≥ c(u,v) ❓")
    with leg_col3:
        st.markdown("⚪ **Interativo** — hover nos nós/arestas para detalhes ❓")

    visualizador = VisualizadorGrafo(linha, resultado)
    html_grafo = visualizador.gerar_html()

    st.markdown('<div class="graph-container">', unsafe_allow_html=True)
    components.html(html_grafo, height=540, scrolling=False)
    st.markdown('</div>', unsafe_allow_html=True)


def _render_analise_comparativa(resultados_batch: List[Dict[str, Any]], volume: int, preset: str):
    render_section_header("📈", "Análise Comparativa — Curvas de Saturação", "BATCH")

    st.markdown(f"""
    <div class="comparison-container">
      <div class="comparison-label">
        {len(resultados_batch)} cenários executados ·
        N = {volume} paletes · Topologia: {preset}
      </div>
    </div>
    """, unsafe_allow_html=True)

    g1_col, g2_col = st.columns(2)

    with g1_col:
        st.markdown("<div style='color:#8b949e;font-size:12px;margin-bottom:4px'>Tempo Médio de Espera × Capacidade c(u,v)</div>", unsafe_allow_html=True)
        chart1 = (
            alt.Chart(alt.Data(values=resultados_batch))
            .mark_line(point=True, strokeWidth=2, color="#f85149")
            .encode(
                x=alt.X("capacidade:Q", title="Capacidade c(u,v)"),
                y=alt.Y("tempo_medio_espera:Q", title="Tempo Médio (u.t.)"),
                tooltip=[
                    alt.Tooltip("capacidade:Q", title="c(u,v)"),
                    alt.Tooltip("tempo_medio_espera:Q", title="T. Médio", format=".2f"),
                    alt.Tooltip("gargalo:N", title="Gargalo"),
                ],
            )
            .properties(height=280)
            .configure_view(strokeWidth=0)
            .configure_axis(labelColor="#8b949e", titleColor="#c9d1d9", gridColor="#21262d", domainColor="#30363d")
        )
        st.altair_chart(chart1, use_container_width=True)

    with g2_col:
        st.markdown("<div style='color:#8b949e;font-size:12px;margin-bottom:4px'>% Paletes com Espera × Capacidade c(u,v)</div>", unsafe_allow_html=True)
        chart2 = (
            alt.Chart(alt.Data(values=resultados_batch))
            .mark_area(
                line={"color": "#d29922", "strokeWidth": 2},
                color=alt.Gradient(
                    gradient="linear",
                    stops=[
                        alt.GradientStop(color="#d2992200", offset=0),
                        alt.GradientStop(color="#d2992244", offset=1),
                    ],
                    x1=1, x2=1, y1=1, y2=0,
                ),
                point={"color": "#d29922", "filled": True, "size": 40},
            )
            .encode(
                x=alt.X("capacidade:Q", title="Capacidade c(u,v)"),
                y=alt.Y("pct_com_espera:Q", title="% com Espera"),
                tooltip=[
                    alt.Tooltip("capacidade:Q", title="c(u,v)"),
                    alt.Tooltip("pct_com_espera:Q", title="% Espera", format=".1f"),
                ],
            )
            .properties(height=280)
            .configure_view(strokeWidth=0)
            .configure_axis(labelColor="#8b949e", titleColor="#c9d1d9", gridColor="#21262d", domainColor="#30363d")
        )
        st.altair_chart(chart2, use_container_width=True)
