"""
Estudo Computacional de Otimização em Metodologias Utilizadas em Processos Industriais
Miguel de Paulo Leite de Oliveira e Pedro Lauria Nassif · Orientador: Prof. Me. Julio Cesar Gonçalves

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

st.set_page_config(page_title="ECOMUP", page_icon=":material/hub:", layout="wide")
with open("style.css", encoding="utf-8") as f:
    ui.html(f"<style>{ui.css_do_tema()}{f.read()}</style>")


def cabecalho():
    ui.html("""
    <div class="main-title">
      <div class="eyebrow">ECOMUP · Trabalho de Graduação · Engenharia de Computação</div>
      <h1>Estudo Computacional de Otimização em Metodologias Utilizadas em Processos Industriais</h1>
      <div class="subtitle">
        Simulador de fluxo de paletes em um armazém industrial — encontra
        <b>onde o processo trava (gargalo)</b> e <b>quanto isso custa em tempo de espera</b>.
      </div>
      <div class="authors">Miguel de Paulo Leite de Oliveira · Pedro Lauria Nassif · Orientador: Prof. Me. Julio Cesar Gonçalves</div>
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
        volume = st.slider(":material/inventory_2: Volume de paletes (N)", 10, 1000, 300, 10)
        capacidade = st.slider(":material/link: Capacidade da aresta crítica", 1, 20, 4, 1,
                               help="c(u,v): quantos paletes a estação crítica atende ao mesmo tempo.")

        # aviso antecipado: chega 1 palete por u.t. e cada um ocupa a estação por tempo_proc_base,
        # então a carga média é tempo_proc_base paletes ao mesmo tempo. Carga >= capacidade = instável.
        linha_prev = LinhaProducao(preset, capacidade)
        carga = linha_prev.nos[linha_prev.aresta_critica[1]].tempo_proc_base
        razao = carga / capacidade
        tipo, texto = (("bad", "Instável: a carga supera a capacidade e a fila cresce.") if razao >= 1
                       else ("ok", "Estável em média; a variabilidade ainda pode formar filas."))
        ui.banner(tipo, f"Carga ÷ Capacidade = <b>{razao:.2f}</b><br>{texto}", compacto=True)

        passo(3, "Rodar")
        executar = st.button(":material/play_arrow: Executar Simulação", type="primary", width="stretch")
        ui.html('<div class="sidebar-divider"></div>')

        with st.expander(":material/casino: Avançado — Semente aleatória"):
            seed = st.number_input("Semente", 1, 100000, 1000, 1,
                                   help="Mesma semente gera sempre o mesmo resultado. Os experimentos do texto usam sementes consecutivas a partir de 1000.")

        with st.expander(":material/query_stats: Análise de sensibilidade (batch)"):
            st.caption("Repete a simulação para várias capacidades e gera curvas de saturação.")
            cap_min = st.number_input("Capacidade mínima", 1, 19, 1, 1)
            cap_max = st.number_input("Capacidade máxima", 2, 20, 8, 1)
            passo_cap = st.number_input("Passo", 1, 5, 1, 1)
            executar_batch = st.button(":material/play_arrow: Executar Análise", width="stretch")

    return dict(preset=preset, volume=volume, capacidade=capacidade, seed=seed,
                executar=executar, executar_batch=executar_batch,
                batch=(cap_min, cap_max, passo_cap))


def como_funciona():
    """Aba explicativa do projeto (segue o texto do TG; serve de roteiro para a apresentação)."""
    ico = ui.ico
    ui.html(f"""
    <div class="explain-grid">
      <div class="explain-card"><div class="explain-icon">{ico("error")}</div><h4>O problema</h4>
        <p>Em processos com muitas etapas, dependências e trabalhadores, é difícil saber
        <b>antes</b> onde o fluxo vai travar. A etapa de menor capacidade vira o <b>gargalo</b>
        e forma <b>fila</b>, aumentando tempo e custo.</p></div>
      <div class="explain-card"><div class="explain-icon">{ico("psychology")}</div><h4>A abordagem</h4>
        <p>Cada processo vira um <b>grafo direcionado</b> G=(V,E): vértices são atividades e
        trabalhadores, arestas são precedências. Sobre ele rodam uma <b>análise estrutural</b>
        (sem simular) e uma <b>simulação de eventos discretos</b> com réplicas.</p></div>
      <div class="explain-card"><div class="explain-icon">{ico("trending_up")}</div><h4>O resultado</h4>
        <p>O sistema aponta o <b>gargalo estrutural</b> e o <b>dinâmico</b>, o caminho crítico e
        <b>quantos trabalhadores</b> alocar em cada grupo para manter a espera abaixo de um limite.</p></div>
    </div>""")

    col_a, col_b = st.columns(2, gap="large")
    with col_a:
        ui.titulo_secao("science", "Técnicas usadas", "BASE TEÓRICA")
        st.markdown("""
**Análise estrutural (determinística)**
- capacidade por grupo de trabalhadores: o menor valor é o gargalo estrutural;
- caminho crítico (CPM): sequência de atividades sem folga;
- fluxo máximo / corte mínimo pelo algoritmo de *Edmonds-Karp* (processos em cadeia).

**Simulação de eventos discretos (estocástica)**, com *SimPy*
- chegadas de Poisson, em lotes ou únicas; tempos normais, uniformes, Weibull...;
- várias réplicas com sementes diferentes e intervalo de confiança de 95%;
- gargalo dinâmico = grupo onde as entidades mais esperam.

**Alocação de trabalhadores**: busca exaustiva (exata), gulosa (heurística) e
recozimento simulado (metaheurística).
        """)
    with col_b:
        ui.titulo_secao("explore", "Onde está cada modelo", "MODELOS M1–M6")
        st.dataframe(pd.DataFrame([
            ("M1, M2, M3", "Modelos base de armazém (protótipo)", "Esta página"),
            ("M4", "Recebimento de paletes — Saderova et al. (2022)", "Página Processos reais"),
            ("M5", "Turnaround de Boeing 737 — San Antonio et al. (2017)", "Página Processos reais"),
            ("M6", "Linha de montagem (instâncias SALBP)", "python validar.py salbp"),
        ], columns=["Modelo", "Processo", "Onde usar"]), hide_index=True, width="stretch")
        st.markdown("""
**Nesta página:** escolha a topologia, ajuste a capacidade da aresta crítica
(o indicador *Carga ÷ Capacidade* avisa quando vai formar fila) e clique em
**:material/play_arrow: Executar Simulação**.

**Dica para a apresentação:** capacidade 3 mostra o gargalo, capacidade 8 mostra
o sistema estável. A *análise de sensibilidade* gera a curva completa (Tabela 12 do texto).
        """)

    ui.titulo_secao("menu_book", "Glossário rápido", "TERMOS")
    st.dataframe(pd.DataFrame([
        ("Grafo G=(V,E)", "V = atividades/estações, E = precedências ou caminhos entre elas."),
        ("Capacidade c(u,v)", "Quantos paletes a estação crítica atende ao mesmo tempo."),
        ("Gargalo estrutural", "Grupo/etapa de menor capacidade, calculado sem simular."),
        ("Gargalo dinâmico", "Grupo onde as entidades mais esperaram na simulação."),
        ("Caminho crítico", "Atividades sem folga: atrasar qualquer uma atrasa o processo todo."),
        ("Corte mínimo", "Menor conjunto de arestas que separa origem e destino — o gargalo teórico."),
        ("Réplica / semente", "Cada réplica é uma execução com semente própria; mesma semente = mesmo resultado."),
        ("IC 95%", "Intervalo de confiança: faixa onde a média verdadeira deve estar."),
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

    ui.titulo_secao("science", "Fluxo Máximo & Corte Mínimo (protótipo)", "TEORIA DOS GRAFOS",
                    "Nos modelos base a capacidade da aresta crítica é escolhida na tela, então o corte mínimo "
                    "apenas devolve essa aresta. O gargalo estrutural calculado a partir de trabalhadores e "
                    "tempos está na página <b>Processos reais</b>.")
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
            {"Vértice": no.id, "Tipo": no.tipo, "Capacidade": linha.capacidade_efetiva(no.id),
             "T. processamento": f"{no.tempo_proc_base} u.t."}
            for no in linha.nos.values()
        ]), hide_index=True, width="stretch")
        st.dataframe(pd.DataFrame([
            {"Aresta": f"{u} → {v}", "Capacidade c(u,v)": a.capacidade, "Fluxo f(u,v)": a.fluxo_atual,
             "Status": "Saturada" if (u, v) == linha.aresta_critica and resultado.gargalo_ativado else "Normal"}
            for (u, v), a in linha.arestas.items()
        ]), hide_index=True, width="stretch")


def aba_tecnico(resultado, linha, logs, params):
    ui.titulo_secao("bolt", "Desempenho Computacional", "ESCALABILIDADE",
                    "Quão rápido e leve é o simulador — mostra que a abordagem escala.")
    ms = resultado.tempo_execucao_seg * 1000
    c1, c2, c3 = st.columns(3)
    with c1:
        ui.card("Tempo de execução", f"{ms:.2f} ms", f"N = {params['volume']} paletes", "good" if ms < 1000 else "warn")
    with c2:
        ui.card("Pico de RAM", f"{resultado.pico_memoria_kb:.1f} KB", "medido com tracemalloc", "good")
    with c3:
        ui.card("Paletes simulados por ms", f"{resultado.paletes_entregues / max(ms, 1e-6):.0f}", "velocidade do simulador", "good")

    st.dataframe(pd.DataFrame({
        "Parâmetro": ["Topologia", "Volume N", "Capacidade c(u,v)", "Semente", "Gargalo"],
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
        estado.batch = (executar_analise_comparativa(p["volume"], cap_min, cap_max, passo_cap, p["preset"], p["seed"]),
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
