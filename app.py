"""
================================================================================
  TCC - Estudo Computacional de Otimização em Metodologias Industriais
  Autor: Pedro Nassif
  Disciplina: Teoria dos Grafos aplicada à Pesquisa Operacional
================================================================================
"""

import math
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
# EXECUÇÃO DO FLUXO PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    st.markdown("""
    <div class="main-title">
      <h1>ECOMUP Project</h1>
      <div class="authors">Miguel de Paula, Pedro Nassif</div>
      <div class="subtitle">Simulação de Eventos Discretos · Teoria dos Grafos · Pesquisa Operacional</div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")

    # ── SIDEBAR (Painel de Controle) ──
    with st.sidebar:
        st.markdown("## ⚙️ Parâmetros da Simulação")
        st.markdown("Ajuste os parâmetros e clique em **Executar** para rodar a simulação.")
        st.markdown("---")

        # Seletor de Topologia
        st.markdown("#### 🗺️ Topologia do Grafo G=(V,E)")
        preset_opcoes = list(LinhaProducao.PRESETS_INFO.keys())
        preset_nomes = [LinhaProducao.PRESETS_INFO[p]["nome"] for p in preset_opcoes]
        preset_idx = st.selectbox(
            "Selecione a topologia",
            range(len(preset_opcoes)),
            format_func=lambda i: preset_nomes[i],
            help="Cada topologia define uma configuração diferente de G=(V,E).",
        )
        preset_selecionado = preset_opcoes[preset_idx]

        # Info card da topologia
        info = LinhaProducao.PRESETS_INFO[preset_selecionado]
        st.markdown(f'<div class="topology-info">{info["descricao"]}</div>', unsafe_allow_html=True)
        st.markdown("---")

        # Volume N
        st.markdown("#### 📦 Volume Total de Paletes")
        st.markdown("<small style='color:#8b949e'>Número de instâncias N simuladas — aumentar aqui estressa o sistema.</small>", unsafe_allow_html=True)
        volume_paletes = st.slider(
            label="N (instâncias)", min_value=10, max_value=1000, value=150, step=10,
        )
        st.markdown("---")

        # Capacidade c(u,v) da aresta crítica
        linha_temp = LinhaProducao(preset=preset_selecionado, cap_aresta_critica=100)
        aresta_crit_nome = f"{linha_temp.aresta_critica[0]} → {linha_temp.aresta_critica[1]}"
        st.markdown(
            f"<small style='color:#8b949e'>c(u,v) da aresta <b>{aresta_crit_nome}</b>. Se Volume > Capacidade, o gargalo é induzido.</small>",
            unsafe_allow_html=True
        )
        capacidade_aresta = st.slider(
            label=f"c({aresta_crit_nome})", min_value=10, max_value=500, value=100, step=10,
        )
        st.markdown("---")

        # Razão V/C (Box vermelha ou verde)
        razao = volume_paletes / capacidade_aresta
        if razao > 1.0:
            st.markdown(f"""
            <div class="bottleneck-banner" style="margin:0">
              <span class="icon">⚠️</span>
              <span class="text">Razão Volume/Capacidade = <b>{razao:.1f}x</b><br>Gargalo previsto → fila esperada!</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="ok-banner" style="margin:0">
              <span class="icon">✅</span>
              <span class="text">Razão V/C = <b>{razao:.2f}</b> — sistema estável.</span>
            </div>
            """, unsafe_allow_html=True)
        st.markdown("---")

        # Botão Executar
        executar = st.button("▶ Executar Simulação", type="primary")
        st.markdown("---")

        # Modo Batch
        st.markdown("#### 📊 Análise Comparativa")
        modo_batch = st.checkbox("Ativar modo batch")
        executar_batch = False
        batch_cap_min, batch_cap_max, batch_cap_step = 10, 200, 10

        if modo_batch:
            st.markdown('<div class="batch-indicator">🔄 Modo batch ativo — varrer capacidades</div>', unsafe_allow_html=True)
            batch_cap_min = st.number_input("c(u,v) mínimo", min_value=5, max_value=400, value=10, step=5)
            batch_cap_max = st.number_input("c(u,v) máximo", min_value=10, max_value=500, value=200, step=10)
            batch_cap_step = st.number_input("Passo", min_value=5, max_value=50, value=10, step=5)
            executar_batch = st.button("▶ Executar Análise Comparativa")

    # ── ESTADO DA SESSÃO ──
    for key in ["resultado", "linha", "resultados_batch", "logs_detalhados"]:
        if key not in st.session_state:
            st.session_state[key] = None

    # ── EXECUÇÃO DA SIMULAÇÃO INDIVIDUAL ──
    if executar:
        with st.spinner("⚙️ Executando simulação DES..."):
            linha = LinhaProducao(preset=preset_selecionado, cap_aresta_critica=capacidade_aresta)
            motor = MotorDES(linha, volume_paletes)
            resultado = motor.executar()

            st.session_state.resultado = resultado
            st.session_state.linha = linha
            st.session_state.logs_detalhados = motor.logs_detalhados
        st.success("Simulação concluída com sucesso!")

    # ── EXECUÇÃO DA SIMULAÇÃO COMPARATIVA ──
    if executar_batch and modo_batch:
        n_cenarios = len(range(batch_cap_min, batch_cap_max + 1, batch_cap_step))
        with st.spinner(f"📊 Executando {n_cenarios} cenários batch..."):
            resultados_batch = executar_analise_comparativa(
                volume=volume_paletes, cap_min=batch_cap_min,
                cap_max=batch_cap_max, cap_step=batch_cap_step, preset=preset_selecionado
            )
            st.session_state.resultados_batch = resultados_batch
        st.success(f"✅ Análise comparativa concluída — {n_cenarios} cenários!")

    resultado: Optional[ResultadoSimulacao] = st.session_state.resultado
    linha: Optional[LinhaProducao] = st.session_state.linha
    logs_detalhados: Optional[List[Dict[str, Any]]] = st.session_state.logs_detalhados
    resultados_batch: Optional[List[Dict[str, Any]]] = st.session_state.resultados_batch

    # ── TELA INICIAL (SE VAZIO) ──
    if resultado is None:
        linha_inicial = LinhaProducao(preset=preset_selecionado, cap_aresta_critica=capacidade_aresta)
        _render_grafo(linha_inicial, None)
        st.markdown('<div style="text-align:center;padding:40px;color:#8b949e"><div style="font-size:48px;margin-bottom:16px">📊</div><h3 style="color:#e6edf3">Dashboard pronto</h3><p>Ajuste os parâmetros na barra lateral e execute a simulação.</p></div>', unsafe_allow_html=True)
        return

    # ── RENDERIZAÇÃO DOS RESULTADOS ──
    # Banner de Gargalo
    aresta_crit = linha.aresta_critica
    cap_crit_val = linha.arestas.get(aresta_crit).capacidade
    
    # Corte Mínimo do NetworkX (Gargalo Teórico)
    fluxo_maximo_teorico, arestas_corte = linha.calcular_corte_minimo()
    gargalo_teorico_str = " → ".join(arestas_corte[0]) if arestas_corte else "Desconhecido"

    if resultado.gargalo_ativado:
        st.markdown(f"""
        <div class="bottleneck-banner">
          <span class="icon">🚨</span>
          <span class="text"><b>GARGALO DETECTADO</b> — A aresta crítica <b>{aresta_crit[0]} → {aresta_crit[1]}</b> atingiu a capacidade máxima c(u,v) = {cap_crit_val}. O fluxo foi restrito e filas foram geradas na Área de Triagem.</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="ok-banner"><span class="icon">✅</span><span class="text"><b>Fluxo estável</b> — A aresta {aresta_crit[0]} → {aresta_crit[1]} operou dentro da capacidade.</span></div>', unsafe_allow_html=True)

    # Seção 1: Operacional
    render_section_header("🏭", "Visão Operacional", "MÉTRICAS DE FLUXO")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_metric_card("Paletes Entregues", str(resultado.paletes_entregues), "100% do volume simulado", "good")
    with col2:
        pct_fila = (resultado.paletes_com_espera / resultado.paletes_entregues * 100) if resultado.paletes_entregues > 0 else 0
        tipo_delta = "bad" if pct_fila > 50 else ("warn" if pct_fila > 20 else "good")
        render_metric_card("Paletes com Espera na Fila", str(resultado.paletes_com_espera), f"{pct_fila:.1f}% do total", tipo_delta)
    with col3:
        med = resultado.tempo_medio_espera
        tipo_delta = "bad" if med > 5 else ("warn" if med > 2 else "good")
        render_metric_card("Tempo Médio na Fila", f"{med:.2f}", "unidades de tempo simuladas", tipo_delta)
    with col4:
        render_metric_card("Tempo Máximo de Espera", f"{resultado.tempo_max_espera:.2f}", "pior caso observado", "bad" if resultado.tempo_max_espera > 10 else "warn")

    # Seção 2: Estrutural (TG & Teoria das Restrições)
    render_section_header("🔬", "Visão Estrutural — Desempenho Algorítmico", "FOCO DO TCC")
    col5, col6, col7 = st.columns(3)
    with col5:
        render_metric_card("Tempo Total de Execução", f"{resultado.tempo_execucao_seg*1000:.2f} ms", f"O(N log K) · N={volume_paletes} paletes", "good" if resultado.tempo_execucao_seg < 1 else "warn")
    with col6:
        render_metric_card("Pico de Consumo de RAM", f"{resultado.pico_memoria_kb:.1f} KB", f"≈ {resultado.pico_memoria_kb/1024:.2f} MB — tracemalloc", "good")
    with col7:
        throughput = resultado.paletes_entregues / (resultado.tempo_execucao_seg * 1000 + 1e-9)
        render_metric_card("Throughput do Algoritmo", f"{throughput:.0f}", "paletes processados por ms", "good")

    # Seção 3: Detalhes Técnicos — Análise de Complexidade (LADO A LADO)
    with st.expander("📐 Detalhes Técnicos — Análise de Complexidade"):
        col_det1, col_det2 = st.columns(2)
        with col_det1:
            st.markdown("**Parâmetros da execução:**")
            df_params = pd.DataFrame({
                "Parâmetro": ["Volume N", "Cap. c(u,v)", "Razão V/C", "Gargalo", "Seed RNG"],
                "Valor": [
                    f"{volume_paletes} paletes",
                    f"{capacidade_aresta}",
                    f"{razao:.2f}x",
                    "SIM ⚠️" if resultado.gargalo_ativado else "NÃO",
                    "42 (reprodutível)"
                ]
            })
            st.table(df_params)
            
        with col_det2:
            st.markdown("**Métricas de desempenho:**")
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
            st.table(df_perf)

    # Seção 4: Comparativa (Batch)
    if resultados_batch:
        _render_analise_comparativa(resultados_batch, volume_paletes, preset_selecionado)

    # Seção 5: Exportação (Excel & CSV)
    render_section_header("💾", "Exportar Relatórios Industriais", "EXPORTAR")
    analisador = AnalisadorResultados(logs_detalhados, linha, resultado)
    
    exp_col1, exp_col2 = st.columns(2)
    with exp_col1:
        excel_data = analisador.gerar_excel()
        st.download_button(
            label="⬇️ Baixar Relatório Completo em Excel (.xlsx)",
            data=excel_data,
            file_name=f"optigraph_{preset_selecionado}_relatorio.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            help="Relatório estruturado com indicadores, métricas de estações e logs em abas separadas."
        )
    with exp_col2:
        csv_data = pd.DataFrame(logs_detalhados).to_csv(index=False).encode("utf-8")
        st.download_button(
            label="⬇️ Baixar Logs de Eventos em CSV",
            data=csv_data,
            file_name=f"optigraph_{preset_selecionado}_logs.csv",
            mime="text/csv"
        )

    # Seção 6: Grafo
    _render_grafo(linha, resultado)

    # Seção 7: Representação do Grafo — Lista de Adjacência G=(V,E)
    with st.expander("📋 Representação do Grafo — Lista de Adjacência G=(V,E)"):
        st.markdown("**Vértices V:**")
        nos_data = [
            {
                "ID do Vértice": no_id,
                "Tipo": no.tipo.capitalize(),
                "Capacidade Interna": no.capacidade_interna,
                "T. Processamento (base)": f"{no.tempo_proc_base:.1f} min",
            }
            for no_id, no in linha.nos.items()
        ]
        st.table(nos_data)

        st.markdown("**Arestas E (com fluxos):**")
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
        st.table(arestas_data)


if __name__ == "__main__":
    main()
