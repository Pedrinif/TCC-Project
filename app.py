"""
================================================================================
  TCC - Estudo Computacional de Otimização em Metodologias Industriais
  Autor: Pedro Nassif
  Disciplina: Teoria dos Grafos aplicada à Pesquisa Operacional
================================================================================
"""

import pandas as pd
from typing import Optional, List, Dict, Any

import streamlit as st

# Importações dos módulos locais da pasta /src
from src.domain import ResultadoSimulacao
from src.rede import LinhaProducao
from src.simulacao import MotorDES, executar_analise_comparativa
from src.analise import AnalisadorResultados
from src.ui import (
    render_metric_card,
    render_section_header,
    _render_grafo,
    _render_analise_comparativa,
    _render_histograma_espera,
    _render_utilizacao_estacoes,
    _render_evolucao_filas,
    _render_comparativo_topologias,
)

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURAÇÃO GLOBAL DA PÁGINA STREAMLIT
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ECOMUP Project",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

def _load_css(path: str = "style.css"):
    try:
        with open(path) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass

_load_css()


# ═══════════════════════════════════════════════════════════════════════════════
# BLOCOS DE TEXTO / EXPLICAÇÃO
# ═══════════════════════════════════════════════════════════════════════════════

def _render_cabecalho():
    st.markdown("""
    <div class="main-title">
      <div class="eyebrow">Trabalho de Graduação · Engenharia de Computação</div>
      <h1>ECOMUP Project</h1>
      <div class="subtitle">
        Simulador de fluxo de paletes em um armazém industrial — encontra
        <b>onde o processo trava (gargalo)</b> e <b>quanto isso custa em tempo de espera</b>.
      </div>
      <div class="authors">Miguel de Paula · Pedro Nassif</div>
    </div>
    """, unsafe_allow_html=True)


def _render_sidebar_step(numero: int, titulo: str, ajuda: str = ""):
    ajuda_html = f'<div class="step-help">{ajuda}</div>' if ajuda else ""
    st.markdown(
        f'<div class="step-title"><span class="step-num">{numero}</span>{titulo}</div>{ajuda_html}',
        unsafe_allow_html=True,
    )


def _render_como_funciona():
    """Aba explicativa: o que é o projeto, para que serve, como ler o dashboard."""
    st.markdown("""
    <div class="explain-grid">
      <div class="explain-card">
        <div class="explain-icon">🎯</div>
        <h4>O problema</h4>
        <p>Em um armazém, paletes chegam na doca, passam por triagem/inspeção e vão para o estoque.
        Se uma etapa tem capacidade menor que a demanda, forma-se <b>fila</b> — é o <b>gargalo</b>,
        que aumenta custo, tempo e desperdício.</p>
      </div>
      <div class="explain-card">
        <div class="explain-icon">🧠</div>
        <h4>A solução</h4>
        <p>Modelamos o armazém como um <b>grafo</b> (estações = vértices, caminhos = arestas) e
        rodamos uma <b>simulação de eventos discretos</b> palete por palete, com chegadas e
        tempos aleatórios realistas.</p>
      </div>
      <div class="explain-card">
        <div class="explain-icon">📈</div>
        <h4>O resultado</h4>
        <p>O sistema mostra <b>qual aresta é o gargalo</b>, quanto tempo os paletes esperam e
        <b>qual capacidade mínima</b> resolve o problema — apoiando a decisão antes de mexer na
        operação real.</p>
      </div>
    </div>
    """, unsafe_allow_html=True)

    col_a, col_b = st.columns(2, gap="large")
    with col_a:
        render_section_header("🔬", "As duas técnicas usadas", "BASE TEÓRICA")
        st.markdown("""
**1. Fluxo Máximo / Corte Mínimo (determinístico)** — algoritmo de *Edmonds-Karp* (via NetworkX).
Calcula, só pela estrutura do grafo, o máximo de paletes que a rede comporta e
*qual conjunto de arestas* limita esse fluxo (o **corte mínimo** = gargalo teórico).

**2. Simulação de Eventos Discretos — DES (estocástico)** — biblioteca *SimPy*.
- Chegadas dos paletes seguem um **processo de Poisson** (intervalos exponenciais);
- Tempo de processamento em cada estação segue uma **distribuição Normal**;
- Cada estação é um recurso com capacidade limitada → filas surgem naturalmente.

A teoria diz *onde* está o gargalo; a simulação mostra *o impacto real* dele (espera, filas, ocupação).
        """)
    with col_b:
        render_section_header("🧭", "Como usar em 3 passos", "GUIA RÁPIDO")
        st.markdown("""
1. **Escolha a topologia** do armazém na barra lateral (3 layouts prontos).
2. **Ajuste o volume de paletes e a capacidade** da aresta crítica.
   O indicador *Volume ÷ Capacidade* já avisa se vai formar gargalo.
3. Clique em **▶ Executar Simulação** e navegue pelas abas de resultados.

**Dica para a apresentação:** rode com capacidade baixa (ex.: 30) para mostrar o gargalo
em vermelho, depois aumente (ex.: 200) para mostrar o sistema estável. Use a
*Análise de Sensibilidade* para gerar a curva completa.
        """)

    render_section_header("📖", "Glossário rápido", "TERMOS")
    glossario = pd.DataFrame([
        ("Grafo G=(V,E)", "Representação da rede: V = estações, E = caminhos entre elas."),
        ("Capacidade c(u,v)", "Máximo de paletes que a aresta de u para v suporta."),
        ("Fluxo f(u,v)", "Quantos paletes de fato passaram pela aresta."),
        ("Gargalo", "Ponto da rede que limita o fluxo e gera fila (f ≥ c)."),
        ("Corte mínimo", "Menor conjunto de arestas que, se removidas, desconecta origem e destino — é o gargalo teórico."),
        ("Seed", "Semente do gerador aleatório. Mesma seed = mesmo resultado (reprodutibilidade)."),
        ("u.t.", "Unidade de tempo simulada (abstrata, ex.: minutos)."),
    ], columns=["Termo", "Significado"])
    st.dataframe(glossario, hide_index=True, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# EXECUÇÃO DO FLUXO PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    _render_cabecalho()

    # ── SIDEBAR (Painel de Controle) ──
    with st.sidebar:
        st.markdown('<div class="sidebar-title">⚙️ Painel de Controle</div>', unsafe_allow_html=True)

        # 1. Seletor de Topologia
        _render_sidebar_step(1, "Layout do armazém", "Qual configuração de estações será simulada.")
        preset_opcoes = list(LinhaProducao.PRESETS_INFO.keys())
        preset_nomes = [LinhaProducao.PRESETS_INFO[p]["nome"] for p in preset_opcoes]
        preset_idx = st.selectbox(
            "Topologia",
            range(len(preset_opcoes)),
            format_func=lambda i: preset_nomes[i],
            help="Cada topologia define uma configuração diferente de G=(V,E).",
            label_visibility="collapsed",
        )
        preset_selecionado = preset_opcoes[preset_idx]
        info = LinhaProducao.PRESETS_INFO[preset_selecionado]
        st.markdown(f'<div class="topology-info">{info["descricao"]}</div>', unsafe_allow_html=True)

        # 2. Volume N e capacidade c(u,v) da aresta crítica
        linha_temp = LinhaProducao(preset=preset_selecionado, cap_aresta_critica=100)
        aresta_crit_nome = f"{linha_temp.aresta_critica[0]} → {linha_temp.aresta_critica[1]}"

        _render_sidebar_step(2, "Carga e capacidade", "Volume maior que a capacidade induz o gargalo.")
        volume_paletes = st.slider(
            "📦 Volume de paletes (N)", min_value=10, max_value=1000, value=150, step=10,
            help="Número de paletes que chegam durante a simulação.",
        )
        capacidade_aresta = st.slider(
            "🔗 Capacidade da aresta crítica", min_value=10, max_value=500, value=100, step=10,
            help=f"c(u,v) da aresta {aresta_crit_nome} — quantos paletes ela suporta.",
        )

        # Razão V/C
        razao = volume_paletes / capacidade_aresta
        if razao > 1.0:
            st.markdown(f"""
            <div class="bottleneck-banner compact">
              <span class="icon">⚠️</span>
              <span class="text">Volume ÷ Capacidade = <b>{razao:.1f}×</b><br>Gargalo previsto — vai formar fila.</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="ok-banner compact">
              <span class="icon">✅</span>
              <span class="text">Volume ÷ Capacidade = <b>{razao:.2f}</b><br>Sistema deve operar estável.</span>
            </div>
            """, unsafe_allow_html=True)

        # 3. Executar
        _render_sidebar_step(3, "Rodar")
        executar = st.button("▶ Executar Simulação", type="primary", use_container_width=True)

        st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)

        # Opções avançadas
        with st.expander("🌱 Avançado — Seed aleatória"):
            seed_valor = st.slider(
                "Seed RNG", min_value=1, max_value=100, value=42, step=1,
                help="Altere para verificar se os resultados são estáveis com outra sequência aleatória.",
            )

        with st.expander("📈 Análise de sensibilidade (batch)"):
            st.caption("Repete a simulação para várias capacidades e gera curvas de saturação.")
            batch_cap_min = st.number_input("Capacidade mínima", min_value=5, max_value=400, value=10, step=5)
            batch_cap_max = st.number_input("Capacidade máxima", min_value=10, max_value=500, value=200, step=10)
            batch_cap_step = st.number_input("Passo", min_value=5, max_value=50, value=10, step=5)
            executar_batch = st.button("▶ Executar Análise", use_container_width=True)

    # ── ESTADO DA SESSÃO ──
    for key in ["resultado", "linha", "resultados_batch", "logs_detalhados", "params"]:
        if key not in st.session_state:
            st.session_state[key] = None

    # ── EXECUÇÃO DA SIMULAÇÃO INDIVIDUAL ──
    if executar:
        with st.spinner("⚙️ Executando simulação DES..."):
            linha = LinhaProducao(preset=preset_selecionado, cap_aresta_critica=capacidade_aresta)
            motor = MotorDES(linha, volume_paletes, seed=seed_valor)
            resultado = motor.executar()

            st.session_state.resultado = resultado
            st.session_state.linha = linha
            st.session_state.logs_detalhados = motor.logs_detalhados
            st.session_state.params = {
                "preset": preset_selecionado,
                "volume": volume_paletes,
                "capacidade": capacidade_aresta,
                "seed": seed_valor,
            }
        st.toast("Simulação concluída!", icon="✅")

    # ── EXECUÇÃO DA SIMULAÇÃO COMPARATIVA ──
    if executar_batch:
        n_cenarios = len(range(batch_cap_min, batch_cap_max + 1, batch_cap_step))
        with st.spinner(f"📊 Executando {n_cenarios} cenários batch..."):
            resultados_batch = executar_analise_comparativa(
                volume=volume_paletes, cap_min=batch_cap_min,
                cap_max=batch_cap_max, cap_step=batch_cap_step, preset=preset_selecionado
            )
            st.session_state.resultados_batch = {
                "dados": resultados_batch,
                "volume": volume_paletes,
                "preset": preset_selecionado,
            }
        st.toast(f"Análise concluída — {n_cenarios} cenários!", icon="📈")

    resultado: Optional[ResultadoSimulacao] = st.session_state.resultado
    linha: Optional[LinhaProducao] = st.session_state.linha
    logs_detalhados: Optional[List[Dict[str, Any]]] = st.session_state.logs_detalhados
    batch: Optional[Dict[str, Any]] = st.session_state.resultados_batch
    params: Optional[Dict[str, Any]] = st.session_state.params

    # ── TELA INICIAL (SE VAZIO) ──
    if resultado is None:
        tab_inicio, tab_como = st.tabs(["🏁 Início", "💡 Como funciona"])
        with tab_inicio:
            st.markdown("""
            <div class="empty-state">
              <div class="empty-icon">📊</div>
              <h3>Pronto para simular</h3>
              <p>Configure os parâmetros na barra lateral e clique em <b>▶ Executar Simulação</b>.<br>
              Abaixo está uma prévia do armazém escolhido. Primeira vez aqui? Veja a aba <b>💡 Como funciona</b>.</p>
            </div>
            """, unsafe_allow_html=True)
            linha_inicial = LinhaProducao(preset=preset_selecionado, cap_aresta_critica=capacidade_aresta)
            _render_grafo(linha_inicial, None)
            if batch:
                _render_analise_comparativa(batch["dados"], batch["volume"], batch["preset"])
        with tab_como:
            _render_como_funciona()
        return

    # Os resultados refletem os parâmetros do último "Executar", não os sliders atuais
    if params and (params["preset"], params["volume"], params["capacidade"], params["seed"]) != (
        preset_selecionado, volume_paletes, capacidade_aresta, seed_valor
    ):
        st.info("Você alterou os parâmetros. Os resultados abaixo são da última execução — "
                "clique em **▶ Executar Simulação** para atualizar.", icon="ℹ️")

    volume_exec = params["volume"]
    capacidade_exec = params["capacidade"]
    seed_exec = params["seed"]
    preset_exec = params["preset"]
    razao_exec = volume_exec / capacidade_exec

    aresta_crit = linha.aresta_critica
    cap_crit_val = linha.arestas.get(aresta_crit).capacidade

    # Corte Mínimo do NetworkX (Gargalo Teórico)
    fluxo_maximo_teorico, arestas_corte = linha.calcular_corte_minimo()
    gargalo_teorico_str = " → ".join(arestas_corte[0]) if arestas_corte else "Desconhecido"

    pct_fila = (resultado.paletes_com_espera / resultado.paletes_entregues * 100) if resultado.paletes_entregues > 0 else 0
    throughput = resultado.paletes_entregues / (resultado.tempo_execucao_seg * 1000 + 1e-9)

    # Banner de Gargalo (veredito, sempre visível)
    if resultado.gargalo_ativado:
        impacto = (
            f" <b>{pct_fila:.0f}% dos paletes</b> precisaram esperar na fila."
            if resultado.paletes_com_espera > 0 else ""
        )
        st.markdown(f"""
        <div class="bottleneck-banner">
          <span class="icon">🚨</span>
          <span class="text"><b>GARGALO DETECTADO</b> — A aresta <b>{aresta_crit[0]} → {aresta_crit[1]}</b> atingiu a
          capacidade máxima c(u,v) = {cap_crit_val}.{impacto}</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="ok-banner">
          <span class="icon">✅</span>
          <span class="text"><b>Fluxo estável</b> — A aresta {aresta_crit[0]} → {aresta_crit[1]} operou dentro da
          capacidade ({cap_crit_val}).</span>
        </div>
        """, unsafe_allow_html=True)

    tab_resumo, tab_rede, tab_filas, tab_comp, tab_tec, tab_como = st.tabs([
        "📋 Resumo", "🕸️ Rede", "⏱️ Filas & Espera", "🔄 Comparativos", "🧪 Técnico & Exportar", "💡 Como funciona",
    ])

    # ── ABA 1: RESUMO ──
    with tab_resumo:
        render_section_header(
            "🏭", "Desempenho da Operação", "O QUE ACONTECEU",
            "Indicadores do ponto de vista do armazém: quantos paletes passaram e quanto esperaram.",
        )
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            render_metric_card("Paletes Processados", str(resultado.paletes_entregues), "100% do volume simulado", "good")
        with col2:
            tipo_delta = "bad" if pct_fila > 50 else ("warn" if pct_fila > 20 else "good")
            render_metric_card("Paletes que Esperaram", str(resultado.paletes_com_espera), f"{pct_fila:.1f}% do total", tipo_delta)
        with col3:
            med = resultado.tempo_medio_espera
            tipo_delta = "bad" if med > 5 else ("warn" if med > 2 else "good")
            render_metric_card("Espera Média na Fila", f"{med:.2f}", "unidades de tempo (u.t.)", tipo_delta)
        with col4:
            render_metric_card("Pior Espera", f"{resultado.tempo_max_espera:.2f}", "u.t. — pior caso observado", "bad" if resultado.tempo_max_espera > 10 else "warn")

        render_section_header(
            "🔬", "Gargalo Teórico — Fluxo Máximo & Corte Mínimo", "TEORIA DOS GRAFOS",
            "Calculado só pela estrutura da rede (Edmonds-Karp): o limite de paletes que ela suporta e "
            "qual aresta segura esse limite.",
        )
        col_fm1, col_fm2, col_fm3 = st.columns(3)
        with col_fm1:
            render_metric_card("Fluxo Máximo Teórico", f"{fluxo_maximo_teorico:.0f}", "Edmonds-Karp (NetworkX)", "good")
        with col_fm2:
            render_metric_card(
                "Aresta do Corte Mínimo", gargalo_teorico_str,
                f"{len(arestas_corte)} aresta(s) no corte",
                "warn" if len(arestas_corte) > 0 else "good",
                cor="small",
            )
        with col_fm3:
            razao_fluxo = (resultado.paletes_entregues / fluxo_maximo_teorico * 100) if fluxo_maximo_teorico > 0 else 0
            render_metric_card(
                "Demanda / Capacidade Teórica", f"{razao_fluxo:.1f}%",
                f"{resultado.paletes_entregues} paletes / {fluxo_maximo_teorico:.0f} de capacidade",
                "bad" if razao_fluxo > 100 else "good",
            )

        _render_utilizacao_estacoes(
            AnalisadorResultados(logs_detalhados, linha, resultado).obter_estatisticas(), linha
        )

    # ── ABA 2: REDE ──
    with tab_rede:
        _render_grafo(linha, resultado)

        with st.expander("📋 Tabela do grafo — vértices e arestas"):
            st.markdown("**Vértices V (estações):**")
            nos_data = [
                {
                    "ID do Vértice": no_id,
                    "Tipo": no.tipo.capitalize(),
                    "Capacidade Interna": no.capacidade_interna,
                    "T. Processamento (base)": f"{no.tempo_proc_base:.1f} min",
                }
                for no_id, no in linha.nos.items()
            ]
            st.dataframe(nos_data, hide_index=True, use_container_width=True)

            st.markdown("**Arestas E (caminhos, com fluxos):**")
            arestas_data = []
            for (orig, dest), aresta in linha.arestas.items():
                utilizacao_pct = min(100, int((aresta.fluxo_atual / aresta.capacidade) * 100)) if aresta.capacidade > 0 else 0
                saturada = (
                    (orig, dest) == linha.aresta_critica
                    and resultado.gargalo_ativado
                )
                arestas_data.append({
                    "Aresta (u -> v)": f"{orig} → {dest}",
                    "Capacidade c(u,v)": aresta.capacidade,
                    "Fluxo f(u,v)": aresta.fluxo_atual,
                    "Utilização (%)": f"{utilizacao_pct}%",
                    "Status": "🔴 SATURADA" if saturada else "✅ Normal",
                })
            st.dataframe(arestas_data, hide_index=True, use_container_width=True)

    # ── ABA 3: FILAS & ESPERA ──
    with tab_filas:
        _render_histograma_espera(resultado.tempos_espera)
        _render_evolucao_filas(logs_detalhados, linha)

    # ── ABA 4: COMPARATIVOS ──
    with tab_comp:
        _render_comparativo_topologias(volume_exec, capacidade_exec, seed_exec)
        if batch:
            _render_analise_comparativa(batch["dados"], batch["volume"], batch["preset"])
        else:
            st.markdown("""
            <div class="hint-box">📈 <b>Quer ver a curva completa?</b> Abra <i>Análise de sensibilidade (batch)</i>
            na barra lateral e clique em <b>Executar Análise</b> para testar várias capacidades de uma vez.</div>
            """, unsafe_allow_html=True)

    # ── ABA 5: TÉCNICO & EXPORTAR ──
    with tab_tec:
        render_section_header(
            "⚡", "Desempenho Computacional do Algoritmo", "FOCO DO TCC",
            "Quão rápido e leve é o simulador — importante para mostrar que a abordagem escala.",
        )
        col5, col6, col7 = st.columns(3)
        with col5:
            render_metric_card("Tempo de Execução", f"{resultado.tempo_execucao_seg*1000:.2f} ms", f"O(N log K) · N={volume_exec} paletes", "good" if resultado.tempo_execucao_seg < 1 else "warn")
        with col6:
            render_metric_card("Pico de RAM", f"{resultado.pico_memoria_kb:.1f} KB", f"≈ {resultado.pico_memoria_kb/1024:.2f} MB — tracemalloc", "good")
        with col7:
            render_metric_card("Throughput", f"{throughput:.0f}", "paletes processados por ms", "good")

        col_det1, col_det2 = st.columns(2)
        with col_det1:
            st.markdown("**Parâmetros da execução**")
            df_params = pd.DataFrame({
                "Parâmetro": ["Topologia", "Volume N", "Cap. c(u,v)", "Razão V/C", "Gargalo", "Seed RNG"],
                "Valor": [
                    LinhaProducao.PRESETS_INFO[preset_exec]["nome"],
                    f"{volume_exec} paletes",
                    f"{capacidade_exec}",
                    f"{razao_exec:.2f}x",
                    "SIM ⚠️" if resultado.gargalo_ativado else "NÃO",
                    f"{seed_exec} (reprodutível)"
                ]
            })
            st.dataframe(df_params, hide_index=True, use_container_width=True)
        with col_det2:
            st.markdown("**Métricas de desempenho**")
            df_perf = pd.DataFrame({
                "Métrica": ["Exec. Wall-clock", "Pico de Heap", "Throughput", "T. Total Fila", "P. com espera"],
                "Valor": [
                    f"{resultado.tempo_execucao_seg * 1000:.3f} ms",
                    f"{resultado.pico_memoria_kb:.2f} KB",
                    f"{throughput:.1f} paletes/ms",
                    f"{resultado.tempo_total_espera:.2f} u.t.",
                    f"{resultado.paletes_com_espera}"
                ]
            })
            st.dataframe(df_perf, hide_index=True, use_container_width=True)

        render_section_header(
            "💾", "Exportar Relatórios", "EXPORTAR",
            "Excel com resumo, desempenho por estação e todos os eventos — bom para anexar no TCC.",
        )
        analisador = AnalisadorResultados(logs_detalhados, linha, resultado)
        exp_col1, exp_col2 = st.columns(2)
        with exp_col1:
            st.download_button(
                label="⬇️ Relatório completo (.xlsx)",
                data=analisador.gerar_excel(),
                file_name=f"optigraph_{preset_exec}_relatorio.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                help="Relatório estruturado com indicadores, métricas de estações e logs em abas separadas.",
                use_container_width=True,
            )
        with exp_col2:
            st.download_button(
                label="⬇️ Logs de eventos (.csv)",
                data=pd.DataFrame(logs_detalhados).to_csv(index=False).encode("utf-8"),
                file_name=f"optigraph_{preset_exec}_logs.csv",
                mime="text/csv",
                use_container_width=True,
            )

    # ── ABA 6: COMO FUNCIONA ──
    with tab_como:
        _render_como_funciona()


if __name__ == "__main__":
    main()
