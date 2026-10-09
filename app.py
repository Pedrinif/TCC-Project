"""
TCC - Estudo Computacional de Otimização em Metodologias Industriais
Miguel de Paula e Pedro Nassif

Tela principal (Streamlit). A lógica fica em src/:
  rede.py      -> grafo do armazém e fluxo máximo / corte mínimo
  simulacao.py -> simulação de eventos discretos com SimPy
  analise.py   -> estatísticas por estação e exportação para Excel
  ui.py        -> cards, gráficos e desenho do grafo
"""

import pandas as pd
import streamlit as st

from src.rede import LinhaProducao, PRESETS
from src.simulacao import MotorDES, executar_analise_comparativa
from src.analise import AnalisadorResultados
from src import ui

st.set_page_config(page_title="ECOMUP Project", page_icon=":material/hub:", layout="wide")
with open("style.css") as f:
    ui.html(f"<style>{ui.css_do_tema()}{f.read()}</style>")


def cabecalho():
    ui.html("""
    <div class="main-title">
      <div class="eyebrow">Trabalho de Graduação · Engenharia de Computação</div>
      <h1>ECOMUP Project</h1>
      <div class="subtitle">
        Simulador de fluxo de paletes em um armazém industrial — encontra
        <b>onde o processo trava (gargalo)</b> e <b>quanto isso custa em tempo de espera</b>.
      </div>
      <div class="authors">Miguel de Paula · Pedro Nassif</div>
    </div>""")


def passo(numero: int, titulo: str, ajuda: str = ""):
    ui.html(f'<div class="step-title"><span class="step-num">{numero}</span>{titulo}</div>'
            f'<div class="step-help">{ajuda}</div>')


def barra_lateral() -> dict:
    """Monta o painel de controle e devolve tudo que o usuário escolheu."""
    with st.sidebar:
        ui.html(f'<div class="sidebar-title">{ui.ico("tune")} Painel de Controle</div>')
        ui.botao_tema()

        passo(1, "Layout do armazém", "Qual configuração de estações será simulada.")
        preset = st.selectbox("Topologia", list(PRESETS), format_func=lambda p: PRESETS[p]["nome"],
                              label_visibility="collapsed")
        ui.html(f'<div class="topology-info">{PRESETS[preset]["descricao"]}</div>')

        passo(2, "Carga e capacidade", "Quanto menor a capacidade, maior a chance de formar fila.")
        volume = st.slider(":material/inventory_2: Volume de paletes (N)", 10, 1000, 150, 10)
        capacidade = st.slider(":material/link: Capacidade da aresta crítica", 1, 20, 4, 1,
                               help="c(u,v): quantos paletes a estação crítica atende ao mesmo tempo.")

        # aviso antecipado: chega 1 palete por u.t. e cada um ocupa a estação por tempo_proc_base,
        # então a carga média é tempo_proc_base paletes ao mesmo tempo. Perto da capacidade, forma fila.
        linha_prev = LinhaProducao(preset, capacidade)
        carga = linha_prev.nos[linha_prev.aresta_critica[1]].tempo_proc_base
        razao = carga / capacidade
        tipo, texto = ("bad", "Gargalo previsto — vai formar fila.") if razao >= 0.8 else ("ok", "Sistema deve operar sem fila.")
        ui.banner(tipo, f"Carga ÷ Capacidade = <b>{razao:.2f}</b><br>{texto}", compacto=True)

        passo(3, "Rodar")
        executar = st.button(":material/play_arrow: Executar Simulação", type="primary", width="stretch")
        ui.html('<div class="sidebar-divider"></div>')

        with st.expander(":material/casino: Avançado — Seed aleatória"):
            seed = st.slider("Seed", 1, 100, 42, help="Mesma seed gera sempre o mesmo resultado.")

        with st.expander(":material/query_stats: Análise de sensibilidade (batch)"):
            st.caption("Repete a simulação para várias capacidades e gera curvas de saturação.")
            cap_min = st.number_input("Capacidade mínima", 1, 19, 1, 1)
            cap_max = st.number_input("Capacidade máxima", 2, 20, 10, 1)
            passo_cap = st.number_input("Passo", 1, 5, 1, 1)
            executar_batch = st.button(":material/play_arrow: Executar Análise", width="stretch")

    return dict(preset=preset, volume=volume, capacidade=capacidade, seed=seed,
                executar=executar, executar_batch=executar_batch,
                batch=(cap_min, cap_max, passo_cap))


def como_funciona():
    """Aba explicativa do projeto (serve de roteiro para a apresentação)."""
    ico = ui.ico
    ui.html(f"""
    <div class="explain-grid">
      <div class="explain-card"><div class="explain-icon">{ico("error")}</div><h4>O problema</h4>
        <p>Em um armazém, paletes chegam na doca, passam por triagem/inspeção e vão para o estoque.
        Se uma etapa tem capacidade menor que a demanda, forma-se <b>fila</b> — é o <b>gargalo</b>,
        que aumenta custo, tempo e desperdício.</p></div>
      <div class="explain-card"><div class="explain-icon">{ico("psychology")}</div><h4>A solução</h4>
        <p>Modelamos o armazém como um <b>grafo</b> (estações = vértices, caminhos = arestas) e
        rodamos uma <b>simulação de eventos discretos</b> palete por palete, com chegadas e
        tempos aleatórios realistas.</p></div>
      <div class="explain-card"><div class="explain-icon">{ico("trending_up")}</div><h4>O resultado</h4>
        <p>O sistema mostra <b>qual aresta é o gargalo</b>, quanto tempo os paletes esperam e
        <b>qual capacidade mínima</b> resolve o problema — antes de mexer na operação real.</p></div>
    </div>""")

    col_a, col_b = st.columns(2, gap="large")
    with col_a:
        ui.titulo_secao("science", "As duas técnicas usadas", "BASE TEÓRICA")
        st.markdown("""
**1. Fluxo Máximo / Corte Mínimo (determinístico)** — algoritmo de *Edmonds-Karp* (via NetworkX).
Só pela estrutura do grafo, calcula o máximo de paletes que a rede comporta e
*qual aresta* limita esse fluxo (o **corte mínimo** = gargalo teórico).

**2. Simulação de Eventos Discretos (estocástico)** — biblioteca *SimPy*.
- chegadas seguem um **processo de Poisson** (intervalos exponenciais);
- o tempo em cada estação segue uma **distribuição Normal**;
- cada estação tem capacidade limitada, então as filas aparecem sozinhas.

A teoria diz *onde* está o gargalo; a simulação mostra *o impacto* dele.
        """)
    with col_b:
        ui.titulo_secao("explore", "Como usar em 3 passos", "GUIA RÁPIDO")
        st.markdown("""
1. **Escolha a topologia** do armazém na barra lateral.
2. **Ajuste o volume de paletes e a capacidade** da aresta crítica.
   O indicador *Volume ÷ Capacidade* já avisa se vai formar gargalo.
3. Clique em **:material/play_arrow: Executar Simulação** e navegue pelas abas.

**Dica para a apresentação:** rode com capacidade bem baixa para mostrar o gargalo
em vermelho, depois aumente para mostrar o sistema estável. A *análise de
sensibilidade* gera a curva completa.
        """)

    ui.titulo_secao("menu_book", "Glossário rápido", "TERMOS")
    st.dataframe(pd.DataFrame([
        ("Grafo G=(V,E)", "Representação da rede: V = estações, E = caminhos entre elas."),
        ("Capacidade c(u,v)", "Quantos paletes a estação crítica atende ao mesmo tempo."),
        ("Fluxo f(u,v)", "Quantos paletes de fato passaram pela aresta."),
        ("Gargalo", "Ponto da rede que limita o fluxo e faz os paletes esperarem em fila."),
        ("Corte mínimo", "Menor conjunto de arestas que separa origem e destino — o gargalo teórico."),
        ("Seed", "Semente do gerador aleatório. Mesma seed = mesmo resultado."),
        ("u.t.", "Unidade de tempo simulada (abstrata, ex.: minutos)."),
    ], columns=["Termo", "Significado"]), hide_index=True, width="stretch")


def aba_resumo(resultado, linha, logs):
    ui.titulo_secao("factory", "Desempenho da Operação", "O QUE ACONTECEU",
                    "Quantos paletes passaram pela linha e quanto tempo esperaram na estação crítica.")
    pct, media, pior = resultado.pct_com_espera, resultado.tempo_medio_espera, resultado.tempo_max_espera
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        ui.card("Paletes processados", resultado.paletes_entregues, "100% do volume simulado", "good")
    with c2:
        ui.card("Paletes que esperaram", resultado.paletes_com_espera, f"{pct:.1f}% do total",
                "bad" if pct > 50 else "warn" if pct > 20 else "good")
    with c3:
        ui.card("Espera média na fila", f"{media:.2f}", "unidades de tempo (u.t.)",
                "bad" if media > 5 else "warn" if media > 2 else "good")
    with c4:
        ui.card("Pior espera", f"{pior:.2f}", "u.t. — pior caso observado", "bad" if pior > 10 else "warn")

    ui.titulo_secao("science", "Gargalo Teórico — Fluxo Máximo & Corte Mínimo", "TEORIA DOS GRAFOS",
                    "Calculado só pela estrutura da rede (Edmonds-Karp): o limite de paletes que ela "
                    "suporta e qual aresta segura esse limite.")
    fluxo_max, corte = linha.calcular_corte_minimo()
    c1, c2 = st.columns(2)
    with c1:
        ui.card("Fluxo máximo teórico", f"{fluxo_max:.0f}", "Edmonds-Karp (NetworkX)", "good")
    with c2:
        ui.card("Aresta do corte mínimo", " → ".join(corte[0]) if corte else "—",
                f"{len(corte)} aresta(s) no corte", "warn", pequeno=True)

    ui.utilizacao_estacoes(AnalisadorResultados(logs, linha, resultado).obter_estatisticas(), linha)


def aba_rede(resultado, linha):
    ui.grafo(linha, resultado)
    with st.expander(":material/table_chart: Tabela do grafo — vértices e arestas"):
        st.dataframe(pd.DataFrame([
            {"Vértice": no.id, "Tipo": no.tipo, "Capacidade": no.capacidade_interna,
             "T. processamento": f"{no.tempo_proc_base} min"}
            for no in linha.nos.values()
        ]), hide_index=True, width="stretch")
        st.dataframe(pd.DataFrame([
            {"Aresta": f"{u} → {v}", "Capacidade c(u,v)": a.capacidade, "Fluxo f(u,v)": a.fluxo_atual,
             "Status": "Saturada" if (u, v) == linha.aresta_critica and resultado.gargalo_ativado else "Normal"}
            for (u, v), a in linha.arestas.items()
        ]), hide_index=True, width="stretch")


def aba_tecnico(resultado, linha, logs, params):
    ui.titulo_secao("bolt", "Desempenho Computacional", "FOCO DO TCC",
                    "Quão rápido e leve é o simulador — mostra que a abordagem escala.")
    ms = resultado.tempo_execucao_seg * 1000
    c1, c2, c3 = st.columns(3)
    with c1:
        ui.card("Tempo de execução", f"{ms:.2f} ms", f"N = {params['volume']} paletes", "good" if ms < 1000 else "warn")
    with c2:
        ui.card("Pico de RAM", f"{resultado.pico_memoria_kb:.1f} KB", "medido com tracemalloc", "good")
    with c3:
        ui.card("Throughput", f"{resultado.paletes_entregues / max(ms, 1e-6):.0f}", "paletes processados por ms", "good")

    st.dataframe(pd.DataFrame({
        "Parâmetro": ["Topologia", "Volume N", "Capacidade c(u,v)", "Seed", "Gargalo"],
        "Valor": [PRESETS[params["preset"]]["nome"], params["volume"], params["capacidade"],
                  params["seed"], "SIM" if resultado.gargalo_ativado else "NÃO"],
    }).astype(str), hide_index=True)

    ui.titulo_secao("download", "Exportar Relatórios", "EXPORTAR",
                    "Excel com resumo, desempenho por estação e todos os eventos — bom para anexar no TCC.")
    nome = f"ecomup_{params['preset']}"
    c1, c2 = st.columns(2)
    c1.download_button(":material/download: Relatório completo (.xlsx)", AnalisadorResultados(logs, linha, resultado).gerar_excel(),
                       f"{nome}_relatorio.xlsx", width="stretch")
    c2.download_button(":material/download: Logs de eventos (.csv)", pd.DataFrame(logs).to_csv(index=False).encode("utf-8"),
                       f"{nome}_logs.csv", "text/csv", width="stretch")


def main():
    cabecalho()
    p = barra_lateral()
    estado = st.session_state

    if p["executar"]:
        linha = LinhaProducao(p["preset"], p["capacidade"])
        motor = MotorDES(linha, p["volume"], seed=p["seed"])
        estado.resultado = motor.executar()
        estado.linha, estado.logs = linha, motor.logs_detalhados
        estado.params = {k: p[k] for k in ("preset", "volume", "capacidade", "seed")}

    if p["executar_batch"]:
        cap_min, cap_max, passo_cap = p["batch"]
        estado.batch = (executar_analise_comparativa(p["volume"], cap_min, cap_max, passo_cap, p["preset"]),
                        p["volume"], p["preset"])

    batch = estado.get("batch")

    # Antes da primeira execução: só a prévia do grafo e a explicação
    if "resultado" not in estado:
        inicio, explicacao = st.tabs([":material/home: Início", ":material/lightbulb: Como funciona"])
        with inicio:
            ui.html(f"""
            <div class="empty-state"><div class="empty-icon">{ui.ico("monitoring")}</div><h3>Pronto para simular</h3>
              <p>Configure os parâmetros na barra lateral e clique em <b>Executar Simulação</b>.<br>
              Abaixo está uma prévia do armazém escolhido. Primeira vez aqui? Veja a aba <b>Como funciona</b>.</p>
            </div>""")
            ui.grafo(LinhaProducao(p["preset"], p["capacidade"]), None)
            if batch:
                ui.curvas_saturacao(*batch)
        with explicacao:
            como_funciona()
        return

    resultado, linha, logs, params = estado.resultado, estado.linha, estado.logs, estado.params

    if any(params[k] != p[k] for k in params):
        st.info("Os parâmetros mudaram. Os resultados abaixo são da última execução — "
                "clique em **Executar Simulação** para atualizar.", icon=":material/info:")

    # Veredito geral, sempre visível acima das abas
    u, v = linha.aresta_critica
    if resultado.gargalo_ativado:
        impacto = f" <b>{resultado.pct_com_espera:.0f}% dos paletes</b> esperaram na fila." if resultado.paletes_com_espera else ""
        ui.banner("bad", f"<b>GARGALO DETECTADO</b> — a aresta <b>{u} → {v}</b> formou fila "
                         f"(capacidade c(u,v) = {linha.arestas[(u, v)].capacidade}).{impacto}")
    else:
        ui.banner("ok", f"<b>Fluxo estável</b> — nenhum palete esperou na aresta {u} → {v}.")

    abas = st.tabs([":material/dashboard: Resumo", ":material/hub: Rede", ":material/timeline: Filas & Espera",
                    ":material/compare_arrows: Comparativos", ":material/terminal: Técnico & Exportar",
                    ":material/lightbulb: Como funciona"])
    with abas[0]:
        aba_resumo(resultado, linha, logs)
    with abas[1]:
        aba_rede(resultado, linha)
    with abas[2]:
        ui.histograma_espera(resultado.tempos_espera)
        ui.evolucao_filas(logs, linha)
    with abas[3]:
        ui.comparativo_topologias(params["volume"], params["capacidade"], params["seed"], PRESETS)
        if batch:
            ui.curvas_saturacao(*batch)
        else:
            ui.html(f'<div class="hint-box">{ui.ico("show_chart")} <b>Quer ver a curva completa?</b> Abra <i>Análise de '
                    'sensibilidade (batch)</i> na barra lateral e clique em <b>Executar Análise</b>.</div>')
    with abas[4]:
        aba_tecnico(resultado, linha, logs, params)
    with abas[5]:
        como_funciona()


main()
