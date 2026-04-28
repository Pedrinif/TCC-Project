"""
================================================================================
  TCC - Prova de Conceito: Fluxo Logístico como Grafo Direcionado G=(V,E)
  Autor: Pedro Nassif e Miguel de Paula
  Disciplina: Teoria dos Grafos aplicada à Pesquisa Operacional
================================================================================

DESCRIÇÃO ACADÊMICA
-------------------
Este módulo implementa a modelagem de um sistema logístico industrial como um
grafo direcionado G = (V, E), onde:
  - V (Vértices) = Nós operacionais do processo (Doca, Triagem, Estoques)
  - E (Arestas) = Fluxos de paletes entre os nós, com capacidades c(u,v)

A simulação utiliza Eventos Discretos (SimPy) para modelar o comportamento
dinâmico do sistema sob diferentes cargas de trabalho, estressando a aresta
crítica Doca → Triagem e induzindo gargalos mensuráveis.

COMPLEXIDADE ASSINTÓTICA
------------------------
  - Construção do grafo:     O(V + E)   → Linear no tamanho da topologia
  - Simulação de N paletes:  O(N)       → Linear no volume de instâncias
  - Calculo de métricas:     O(N)       → Varredura única dos resultados
  - Renderização do grafo:   O(V + E)   → Proporcional ao tamanho do grafo

COMO EXECUTAR
-------------
  $ pip install streamlit networkx simpy pyvis
  $ streamlit run app.py
"""

# ─────────────────────────────────────────────────────────────────────────────
# IMPORTAÇÕES
# ─────────────────────────────────────────────────────────────────────────────
import time                    # Medição de tempo de execução wall-clock
import tracemalloc             # Rastreamento de pico de alocação de memória RAM
import random                  # Geração de variação estocástica no processo
import math
import io
import csv
from dataclasses import dataclass, field
from typing import List, Optional

import streamlit as st         # Framework de dashboard web interativo
import networkx as nx          # Modelagem e algoritmos de grafos (G = (V, E))
import simpy                   # Motor de simulação de eventos discretos (DES)

# PyVis → renderização interativa HTML do grafo
from pyvis.network import Network

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURAÇÃO GLOBAL DA PÁGINA STREAMLIT
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="OptiGraph — Otimização de Fluxo em Redes Logísticas",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# CARREGAMENTO DE ESTILOS — lê style.css externo (código limpo)
# ─────────────────────────────────────────────────────────────────────────────
def _load_css(path: str = "style.css"):
    """Injeta o arquivo CSS externo no Streamlit. Complexidade: O(1)."""
    try:
        with open(path) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass  # Continua sem estilos se o arquivo não existir

_load_css()


# ─────────────────────────────────────────────────────────────────────────────
# HELPER — Gera CSV dos resultados em memória
# ─────────────────────────────────────────────────────────────────────────────
def _gerar_csv(resultado, volume: int, capacidade: int) -> bytes:
    """
    Serializa ResultadoSimulacao em formato CSV para download.
    Complexidade: O(N) — itera sobre todos os tempos de espera.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["# OptiGraph — Relatório de Simulação"])
    writer.writerow(["Parâmetro", "Valor"])
    writer.writerow(["Volume N", volume])
    writer.writerow(["Capacidade c(u,v)", capacidade])
    writer.writerow(["Gargalo detectado", "SIM" if resultado.gargalo_ativado else "NAO"])
    writer.writerow(["Paletes entregues", resultado.paletes_entregues])
    writer.writerow(["Paletes com espera", resultado.paletes_com_espera])
    writer.writerow(["Tempo medio de espera", f"{resultado.tempo_medio_espera:.4f}"])
    writer.writerow(["Tempo maximo de espera", f"{resultado.tempo_max_espera:.4f}"])
    writer.writerow(["Tempo de execucao (ms)", f"{resultado.tempo_execucao_seg * 1000:.3f}"])
    writer.writerow(["Pico de RAM (KB)", f"{resultado.pico_memoria_kb:.2f}"])
    writer.writerow([])
    writer.writerow(["# Dados Brutos — Tempo de espera por palete"])
    writer.writerow(["Palete ID", "Tempo de Espera (u.t.)"])
    for i, t in enumerate(resultado.tempos_espera):
        writer.writerow([i + 1, f"{t:.4f}"])
    return output.getvalue().encode("utf-8")


# ═══════════════════════════════════════════════════════════════════════════════
# CAMADA DE DOMÍNIO — Estrutura de Dados do Grafo
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class No:
    """
    Representa um vértice v ∈ V do grafo G=(V,E).

    Cada nó é um ponto operacional do processo logístico com suas
    características de processamento e posição no layout visual.

    Complexidade de criação: O(1)
    """
    id: str                        # Identificador único do vértice
    rotulo: str                    # Nome exibido no grafo
    tipo: str                      # Categoria: 'doca', 'triagem', 'estoque'
    tempo_proc_base: float         # Tempo médio de processamento (minutos sim)
    capacidade_interna: int        # Capacidade máxima de paletes simultâneos
    cor: str = "#58a6ff"           # Cor de renderização PyVis
    x: float = 0.0                 # Posição X no layout
    y: float = 0.0                 # Posição Y no layout


@dataclass
class Aresta:
    """
    Representa uma aresta dirigida (u, v) ∈ E do grafo G=(V,E).

    Modela o fluxo logístico entre dois nós, com capacidade máxima c(u,v)
    que reflete a largura de banda do canal de transporte entre os pontos.

    Complexidade de criação: O(1)
    """
    origem: str                    # Vértice de origem u
    destino: str                   # Vértice de destino v
    capacidade: int                # c(u,v): fluxo máximo permitido
    fluxo_atual: int = 0          # Fluxo corrente f(u,v) ≤ c(u,v)
    peso: float = 1.0             # Peso w(u,v) para algoritmos de caminho


@dataclass
class ResultadoSimulacao:
    """
    Estrutura de dados agregados retornada pela simulação DES.
    Encapsula todas as métricas de desempenho coletadas em O(N).
    """
    paletes_entregues: int = 0
    paletes_com_espera: int = 0
    tempo_total_espera: float = 0.0
    tempo_max_espera: float = 0.0
    tempos_espera: List[float] = field(default_factory=list)
    gargalo_ativado: bool = False
    tempo_execucao_seg: float = 0.0
    pico_memoria_kb: float = 0.0

    @property
    def tempo_medio_espera(self) -> float:
        """Média aritmética dos tempos de espera. Complexidade: O(1)"""
        if not self.tempos_espera:
            return 0.0
        return self.tempo_total_espera / len(self.tempos_espera)


# ═══════════════════════════════════════════════════════════════════════════════
# CAMADA DE MODELAGEM — Construção do Grafo G=(V,E)
# ═══════════════════════════════════════════════════════════════════════════════

class GrafoLogistico:
    """
    Modela a topologia do fluxo logístico como um grafo direcionado G=(V,E)
    utilizando a biblioteca NetworkX.

    COMPLEXIDADE ESPACIAL: O(V + E), proporcional ao número de vértices
    e arestas do grafo. Para a topologia definida: O(4 + 4) = O(1) constante,
    mas o modelo generaliza para qualquer G=(V,E).

    Atributos
    ----------
    G : nx.DiGraph
        Grafo direcionado do NetworkX subjacente.
    nos : dict[str, No]
        Mapeamento id → No dos vértices.
    arestas : dict[tuple, Aresta]
        Mapeamento (origem, destino) → Aresta.
    """

    def __init__(self, capacidade_doca_triagem: int):
        """
        Inicializa e constrói a topologia logística completa.

        Parâmetros
        ----------
        capacidade_doca_triagem : int
            c(u,v) da aresta crítica Doca_Recebimento → Area_Triagem.

        Complexidade: O(V + E) para inserção de todos os nós e arestas.
        """
        self.G = nx.DiGraph()
        self.nos: dict = {}
        self.arestas: dict = {}
        self._construir_topologia(capacidade_doca_triagem)

    def _construir_topologia(self, cap_doca_triagem: int):
        """
        Define os vértices V e arestas E do grafo logístico.

        Topologia:
            Doca_Recebimento → Area_Triagem → Estoque_A
                                           → Estoque_B

        Esta é a representação formal do processo industrial onde:
          - Paletes chegam na Doca de Recebimento (fonte)
          - São triados na Área de Triagem (nó intermediário crítico)
          - São distribuídos para os Estoques A ou B (sorvedouros)

        Complexidade: O(V + E) = O(4 + 4) no caso concreto.
        """
        # ── Definição dos Vértices V ─────────────────────────────────────────
        nos_config = [
            No(
                id="Doca_Recebimento",
                rotulo="🚛 Doca\nRecebimento",
                tipo="doca",
                tempo_proc_base=2.0,
                capacidade_interna=100,
                cor="#1f6feb",
                x=-350, y=0
            ),
            No(
                id="Area_Triagem",
                rotulo="🔀 Área de\nTriagem",
                tipo="triagem",
                tempo_proc_base=3.5,
                capacidade_interna=20,
                cor="#d29922",
                x=0, y=0
            ),
            No(
                id="Estoque_A",
                rotulo="📦 Estoque A\n(Giro Alto)",
                tipo="estoque",
                tempo_proc_base=1.5,
                capacidade_interna=500,
                cor="#3fb950",
                x=300, y=-150
            ),
            No(
                id="Estoque_B",
                rotulo="📦 Estoque B\n(Giro Baixo)",
                tipo="estoque",
                tempo_proc_base=1.5,
                capacidade_interna=500,
                cor="#3d8b40",
                x=300, y=150
            ),
        ]

        # Inserção de vértices no grafo: O(V)
        for no in nos_config:
            self.nos[no.id] = no
            self.G.add_node(
                no.id,
                label=no.rotulo,
                tipo=no.tipo,
                capacidade=no.capacidade_interna,
                cor=no.cor,
            )

        # ── Definição das Arestas E ──────────────────────────────────────────
        arestas_config = [
            Aresta(
                origem="Doca_Recebimento",
                destino="Area_Triagem",
                capacidade=cap_doca_triagem,   # ARESTA CRÍTICA — gargalo potencial
                peso=1.0,
            ),
            Aresta(
                origem="Area_Triagem",
                destino="Estoque_A",
                capacidade=999,
                peso=1.2,
            ),
            Aresta(
                origem="Area_Triagem",
                destino="Estoque_B",
                capacidade=999,
                peso=1.8,
            ),
        ]

        # Inserção de arestas no grafo: O(E)
        for aresta in arestas_config:
            chave = (aresta.origem, aresta.destino)
            self.arestas[chave] = aresta
            self.G.add_edge(
                aresta.origem,
                aresta.destino,
                capacidade=aresta.capacidade,
                peso=aresta.peso,
            )

    def atualizar_fluxo_aresta(self, origem: str, destino: str, delta: int = 1):
        """
        Incrementa o fluxo f(u,v) de uma aresta em Δ unidades.

        Complexidade: O(1) — acesso direto por chave de dicionário.
        """
        chave = (origem, destino)
        if chave in self.arestas:
            self.arestas[chave].fluxo_atual += delta

    def aresta_em_capacidade(self, origem: str, destino: str) -> bool:
        """
        Verifica se f(u,v) ≥ c(u,v) (saturação da aresta).

        Condição de gargalo: fluxo corrente atingiu a capacidade máxima.
        Complexidade: O(1).
        """
        chave = (origem, destino)
        if chave in self.arestas:
            a = self.arestas[chave]
            return a.fluxo_atual >= a.capacidade
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# CAMADA DE SIMULAÇÃO — Motor de Eventos Discretos (SimPy)
# ═══════════════════════════════════════════════════════════════════════════════

class SimuladorLogistico:
    """
    Implementa a Simulação de Eventos Discretos (DES — Discrete Event Simulation)
    do fluxo de paletes através do grafo G=(V,E).

    O SimPy modela recursos finitos (nós com capacidade limitada) e processa
    eventos ordenados por tempo em uma fila de prioridade (heap binário).

    COMPLEXIDADE TEMPORAL DA SIMULAÇÃO:
      - O(N log K) onde N = número de paletes e K = número de recursos SimPy
      - Na prática N ≫ K, aproximando-se de O(N log N) no pior caso com
        muitas colisões de tempo, mas O(N) no caso médio com distribuição
        uniforme de chegadas.

    Parâmetros
    ----------
    grafo : GrafoLogistico
        Topologia do grafo G=(V,E) já construída.
    volume_paletes : int
        N — número de instâncias de paletes a simular.
    seed : int
        Semente para reprodutibilidade estocástica.
    """

    def __init__(self, grafo: GrafoLogistico, volume_paletes: int, seed: int = 42):
        self.grafo = grafo
        self.volume_paletes = volume_paletes
        self.seed = seed
        random.seed(seed)

        # Motor de simulação SimPy
        self.env = simpy.Environment()

        # Recursos SimPy modelam os nós V com suas capacidades internas
        # Resource é um semáforo de N slots → modela fila M/M/c
        self.recursos: dict = {
            no_id: simpy.Resource(
                self.env,
                capacity=no.capacidade_interna
            )
            for no_id, no in grafo.nos.items()
        }

        # ── CONEXÃO CRÍTICA: slider → gargalo real na simulação ──────────────
        # A capacidade da aresta c(Doca → Triagem) definida pelo usuário na
        # sidebar SOBRESCREVE o Resource SimPy da Triagem.
        # Sem isto, o SimPy usaria capacidade_interna=20 fixo e nunca geraria
        # fila — desconectando a UI da simulação.
        #
        # Modelo de fila resultante: M/G/c onde c = c(u,v) do slider.
        # Utilização ρ = λ / (μ × c). Quando ρ → 1, filas explodem (Little's Law).
        cap_aresta = grafo.arestas.get(("Doca_Recebimento", "Area_Triagem"))
        if cap_aresta:
            self.recursos["Area_Triagem"] = simpy.Resource(
                self.env,
                capacity=max(1, cap_aresta.capacidade)   # c = slider, mínimo 1
            )

        # Coletor de métricas: lista de tempos de espera por palete
        self._tempos_espera: List[float] = []
        self._gargalo_ativado: bool = False


    def _processar_palete(self, palete_id: int):
        """
        Processo SimPy que modela o ciclo de vida completo de um palete.

        Percorre o caminho:
            Doca_Recebimento → Area_Triagem → Estoque_A ou Estoque_B

        A aresta Doca → Triagem é monitorada para detecção de gargalo.
        Se o fluxo acumulado superar a capacidade c(u,v), o Resource da
        Triagem estará saturado, gerando filas mensuráveis.

        Complexidade por palete: O(|caminho|) = O(E) no pior caso.
        Como o caminho é fixo na topologia definida: O(1) constante.
        """
        # ── PASSO 1: Doca de Recebimento ─────────────────────────────────────
        chegada_doca = self.env.now
        with self.recursos["Doca_Recebimento"].request() as req:
            yield req
            proc_doca = random.uniform(1.5, 2.5)
            yield self.env.timeout(proc_doca)

        # ── PASSO 2: Transitar pela aresta crítica Doca → Triagem ────────────
        # Registra o fluxo cumulativo nesta aresta
        self.grafo.atualizar_fluxo_aresta("Doca_Recebimento", "Area_Triagem")

        # Verifica saturação: f(u,v) ≥ c(u,v) → gargalo detectado
        if self.grafo.aresta_em_capacidade("Doca_Recebimento", "Area_Triagem"):
            self._gargalo_ativado = True

        # ── PASSO 3: Área de Triagem (nó de potencial gargalo) ───────────────
        entrada_triagem = self.env.now
        with self.recursos["Area_Triagem"].request() as req:
            yield req                               # Aguarda slot disponível
            espera = self.env.now - entrada_triagem  # Δt de espera na fila
            self._tempos_espera.append(espera)

            proc_triagem = random.uniform(2.5, 4.5)
            yield self.env.timeout(proc_triagem)

        # ── PASSO 4: Roteamento para Estoque_A ou Estoque_B ──────────────────
        # Distribuição 60/40 representando diferença de giro de estoque
        destino_final = "Estoque_A" if random.random() < 0.60 else "Estoque_B"
        self.grafo.atualizar_fluxo_aresta("Area_Triagem", destino_final)

        with self.recursos[destino_final].request() as req:
            yield req
            proc_estoque = random.uniform(1.0, 2.0)
            yield self.env.timeout(proc_estoque)

    def _gerador_paletes(self):
        """
        Gera N paletes com chegadas distribuídas no tempo (processo de Poisson).

        O intervalo entre chegadas segue distribuição exponencial para
        modelar um processo estocástico de Poisson clássico — padrão em
        filas de teoria M/M/1.

        Complexidade: O(N) iterações, cada uma com yield O(1).
        """
        for i in range(self.volume_paletes):
            self.env.process(self._processar_palete(i))
            # Intervalo de chegada exponencial: λ = 1/1.0 = 1 palete/unidade de tempo
            intervalo = random.expovariate(1.0)
            yield self.env.timeout(intervalo)

    def executar(self) -> ResultadoSimulacao:
        """
        Ponto de entrada público da simulação.

        Instrumenta a execução com:
          - tracemalloc: rastreamento granular de alocações de heap Python
          - time.perf_counter: medição de alta resolução do tempo wall-clock

        Retorna ResultadoSimulacao com todas as métricas agregadas.

        COMPLEXIDADE TOTAL: O(N log K) ≈ O(N) para K << N
        """
        # ── Instrumentação: início da medição de memória e tempo ─────────────
        tracemalloc.start()
        t_inicio = time.perf_counter()

        # ── Execução da simulação DES ─────────────────────────────────────────
        self.env.process(self._gerador_paletes())
        self.env.run()

        # ── Instrumentação: captura das métricas finais ──────────────────────
        t_fim = time.perf_counter()
        _, pico_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # ── Agregação dos resultados em O(N) ─────────────────────────────────
        paletes_com_espera = sum(1 for t in self._tempos_espera if t > 0.01)
        tempo_total = sum(self._tempos_espera)
        tempo_max = max(self._tempos_espera) if self._tempos_espera else 0.0

        return ResultadoSimulacao(
            paletes_entregues=self.volume_paletes,
            paletes_com_espera=paletes_com_espera,
            tempo_total_espera=tempo_total,
            tempo_max_espera=tempo_max,
            tempos_espera=self._tempos_espera,
            gargalo_ativado=self._gargalo_ativado,
            tempo_execucao_seg=t_fim - t_inicio,
            pico_memoria_kb=pico_bytes / 1024.0,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# CAMADA DE VISUALIZAÇÃO — Renderização do Grafo com PyVis
# ═══════════════════════════════════════════════════════════════════════════════

class VisualizadorGrafo:
    """
    Gera a representação visual interativa do grafo G=(V,E) usando PyVis.

    PyVis encapsula a biblioteca vis.js para renderização WebGL/Canvas,
    exportando um arquivo HTML autocontido incorporável no Streamlit via
    componente iframe.

    COMPLEXIDADE DE RENDERIZAÇÃO: O(V + E), proporcional ao tamanho do grafo.
    """

    def __init__(self, grafo: GrafoLogistico, resultado: Optional[ResultadoSimulacao]):
        self.grafo = grafo
        self.resultado = resultado

    def gerar_html(self) -> str:
        """
        Constrói a rede PyVis com layout físico e codificação visual semântica.

        Regras de codificação visual:
          - Nós: coloridos por tipo operacional
          - Aresta crítica saturada: vermelha (gargalo) | cinza (normal)
          - Tamanho dos nós: proporcional à importância na topologia
          - Rótulos incluem métricas de fluxo atuais

        Complexidade: O(V + E) para iteração e inserção.
        """
        net = Network(
            height="520px",
            width="100%",
            bgcolor="#0d1117",
            font_color="#e6edf3",
            directed=True,
        )

        # ── Configurações físicas do layout (simulação de forças) ────────────
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

        # ── Inserção dos Vértices V ──────────────────────────────────────────
        for no_id, no in self.grafo.nos.items():
            tamanho = {"doca": 55, "triagem": 48, "estoque": 38}.get(no.tipo, 40)

            # Tooltip acadêmico exibido no hover
            tooltip = (
                f"<b>Vértice:</b> {no_id}<br>"
                f"<b>Tipo:</b> {no.tipo.capitalize()}<br>"
                f"<b>Cap. Interna:</b> {no.capacidade_interna} paletes<br>"
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

        # ── Inserção das Arestas E com codificação de gargalo ────────────────
        aresta_critica = ("Doca_Recebimento", "Area_Triagem")

        for (orig, dest), aresta in self.grafo.arestas.items():
            saturada = (
                (orig, dest) == aresta_critica
                and self.resultado is not None
                and self.resultado.gargalo_ativado
            )

            cor_aresta   = "#f85149" if saturada else "#388bfd"
            largura      = 5 if saturada else 3
            estilo       = "dashed" if not saturada else "solid"

            # Percentual de utilização da capacidade
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


# ═══════════════════════════════════════════════════════════════════════════════
# COMPONENTES DE UI — Helpers de Renderização Streamlit
# ═══════════════════════════════════════════════════════════════════════════════

def render_metric_card(
    label: str,
    value: str,
    delta: str = "",
    delta_tipo: str = "",
    cor: str = "blue",
):
    """
    Renderiza um card de métrica com design premium customizado.

    Parâmetros
    ----------
    label     : Rótulo superior do card
    value     : Valor principal (grande, em destaque)
    delta     : Texto secundário abaixo do valor
    delta_tipo: 'good' | 'warn' | 'bad' → cor do delta
    cor       : Cor do gradiente superior ('blue'|'green'|'orange'|'red'|'purple')
    """
    delta_html = f'<div class="metric-delta {delta_tipo}">{delta}</div>' if delta else ""
    st.markdown(f"""
    <div class="metric-card {cor}">
      <div class="metric-label">{label}</div>
      <div class="metric-value">{value}</div>
      {delta_html}
    </div>
    """, unsafe_allow_html=True)


def render_section_header(icon: str, titulo: str, badge: str = ""):
    """Renderiza cabeçalho de seção com ícone, título e badge opcional."""
    badge_html = f'<span class="section-badge">{badge}</span>' if badge else ""
    st.markdown(f"""
    <div class="section-header">
      <span style="font-size:20px">{icon}</span>
      <h2>{titulo}</h2>
      {badge_html}
    </div>
    """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PONTO DE ENTRADA PRINCIPAL — Orquestração do Dashboard
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """
    Função principal que orquestra todas as camadas da aplicação:
      1. Interface (Sidebar) → coleta parâmetros do usuário
      2. Backend (SimPy)     → executa simulação DES
      3. Frontend (Streamlit)→ renderiza resultados e grafo

    O fluxo de dados é unidirecional:
      Sidebar → GrafoLogistico → SimuladorLogistico → ResultadoSimulacao
      → VisualizadorGrafo + Cards de Métricas

    Complexidade total da pipeline: O(N log K + V + E) ≈ O(N)
    """

    # ── Cabeçalho Principal ──────────────────────────────────────────────────
    st.markdown("""
    <div class="main-title">
      <div style="font-size:13px;font-weight:600;letter-spacing:3px;text-transform:uppercase;color:#8b949e;margin-bottom:10px">Prova de Conceito — TCC</div>
      <h1>⚡ OptiGraph</h1>
      <div style="font-size:17px;font-weight:400;color:#c9d1d9;margin:6px 0 4px 0">Otimização de Fluxo em Redes Logísticas Industriais</div>
      <p>Simulação de Eventos Discretos · Teoria dos Grafos · Pesquisa Operacional</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # ════════════════════════════════════════════════════════════════════════
    # SIDEBAR — Painel de Controle Paramétrico
    # ════════════════════════════════════════════════════════════════════════
    with st.sidebar:
        st.markdown("## ⚙️ Parâmetros da Simulação")
        st.markdown("Ajuste os parâmetros e clique em **Executar** para rodar a simulação.")
        st.markdown("---")

        # Slider 1: Volume de paletes (instâncias N da simulação)
        st.markdown("#### 📦 Volume Total de Paletes")
        st.markdown(
            "<small>Número de instâncias N simuladas — aumentar aqui estressa o sistema.</small>",
            unsafe_allow_html=True
        )
        volume_paletes = st.slider(
            label="N (instâncias)",
            min_value=10,
            max_value=1000,
            value=150,
            step=10,
            help="Complexidade da simulação: O(N). Quanto maior N, maior o tempo de execução.",
        )

        st.markdown("---")

        # Slider 2: Capacidade da aresta crítica c(Doca → Triagem)
        st.markdown("#### 🔗 Capacidade da Aresta Crítica")
        st.markdown(
            "<small>c(u,v) da aresta <b>Doca → Triagem</b>. "
            "Se Volume > Capacidade, o gargalo é induzido.</small>",
            unsafe_allow_html=True
        )
        capacidade_aresta = st.slider(
            label="c(Doca → Triagem)",
            min_value=10,
            max_value=500,
            value=100,
            step=10,
            help="Quando o fluxo f(u,v) ≥ c(u,v), a aresta satura e gera filas.",
        )

        st.markdown("---")

        # Indicador de carga antecipada
        razao = volume_paletes / capacidade_aresta
        if razao > 1.0:
            st.markdown(f"""
            <div class="bottleneck-banner" style="margin:0">
              <span class="icon">⚠️</span>
              <span class="text">
                Razão Volume/Capacidade = <b>{razao:.1f}x</b><br>
                Gargalo previsto → fila esperada!
              </span>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="ok-banner" style="margin:0">
              <span class="icon">✅</span>
              <span class="text">
                Razão V/C = <b>{razao:.2f}</b> — sistema dentro da capacidade.
              </span>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("---")

        # Botão de execução
        executar = st.button("▶ Executar Simulação", type="primary")

        st.markdown("---")
        st.markdown("""
        <small style="color:#8b949e">
        <b>Complexidades Assintóticas:</b><br>
        • Construção do grafo: <code>O(V+E)</code><br>
        • Simulação DES: <code>O(N log K)</code><br>
        • Métricas: <code>O(N)</code><br>
        • Renderização: <code>O(V+E)</code>
        </small>
        """, unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════════════
    # ESTADO DA SESSÃO — Persistência entre re-renders do Streamlit
    # ════════════════════════════════════════════════════════════════════════
    if "resultado" not in st.session_state:
        st.session_state.resultado = None
    if "grafo" not in st.session_state:
        st.session_state.grafo = None

    # ════════════════════════════════════════════════════════════════════════
    # EXECUÇÃO DO BACKEND — SimPy + Grafo
    # ════════════════════════════════════════════════════════════════════════
    if executar:
        with st.spinner("⚙️ Executando simulação DES... aguarde."):
            # Constrói o grafo com a capacidade definida na sidebar
            grafo = GrafoLogistico(capacidade_doca_triagem=capacidade_aresta)

            # Instancia e executa o simulador (instrumentado com tempo e memória)
            simulador = SimuladorLogistico(
                grafo=grafo,
                volume_paletes=volume_paletes,
            )
            resultado = simulador.executar()

            # Persiste no estado da sessão para re-renders sem re-execução
            st.session_state.resultado = resultado
            st.session_state.grafo = grafo

        st.success("✅ Simulação concluída com sucesso!")

    resultado: Optional[ResultadoSimulacao] = st.session_state.resultado
    grafo: Optional[GrafoLogistico] = st.session_state.grafo

    # ════════════════════════════════════════════════════════════════════════
    # FRONTEND — Se ainda não rodou, mostra estado inicial
    # ════════════════════════════════════════════════════════════════════════
    if resultado is None:
        # Mostra grafo vazio com topologia inicial
        grafo_inicial = GrafoLogistico(capacidade_doca_triagem=capacidade_aresta)
        _render_grafo(grafo_inicial, None)

        st.markdown("""
        <div style="text-align:center;padding:40px;color:#8b949e">
          <div style="font-size:48px;margin-bottom:16px">📊</div>
          <h3 style="color:#e6edf3">Dashboard pronto para simulação</h3>
          <p>Configure os parâmetros na barra lateral e clique em <b>Executar Simulação</b></p>
        </div>
        """, unsafe_allow_html=True)
        return

    # ════════════════════════════════════════════════════════════════════════
    # BANNER DE GARGALO
    # ════════════════════════════════════════════════════════════════════════
    if resultado.gargalo_ativado:
        st.markdown(f"""
        <div class="bottleneck-banner">
          <span class="icon">🚨</span>
          <span class="text">
            <b>GARGALO DETECTADO</b> — A aresta crítica <b>Doca → Triagem</b> atingiu
            a capacidade máxima c(u,v) = {grafo.arestas[('Doca_Recebimento','Area_Triagem')].capacidade}.
            O fluxo foi restrito e filas foram geradas na Área de Triagem.
          </span>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="ok-banner">
          <span class="icon">✅</span>
          <span class="text">
            <b>Fluxo estável</b> — A aresta Doca → Triagem operou dentro da capacidade máxima.
            Nenhum gargalo estrutural detectado.
          </span>
        </div>
        """, unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════════════
    # SEÇÃO 1: VISÃO OPERACIONAL
    # ════════════════════════════════════════════════════════════════════════
    render_section_header("🏭", "Visão Operacional", "MÉTRICAS DE FLUXO")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        render_metric_card(
            label="Paletes Entregues",
            value=str(resultado.paletes_entregues),
            delta="100% do volume simulado",
            delta_tipo="good",
            cor="blue",
        )

    with col2:
        pct_fila = (resultado.paletes_com_espera / resultado.paletes_entregues * 100) \
                   if resultado.paletes_entregues > 0 else 0
        tipo_delta = "bad" if pct_fila > 50 else ("warn" if pct_fila > 20 else "good")
        render_metric_card(
            label="Paletes com Espera na Fila",
            value=str(resultado.paletes_com_espera),
            delta=f"{pct_fila:.1f}% do total",
            delta_tipo=tipo_delta,
            cor="orange" if pct_fila > 0 else "green",
        )

    with col3:
        med = resultado.tempo_medio_espera
        tipo_delta = "bad" if med > 5 else ("warn" if med > 2 else "good")
        render_metric_card(
            label="Tempo Médio na Fila",
            value=f"{med:.2f}",
            delta="unidades de tempo simuladas",
            delta_tipo=tipo_delta,
            cor="red" if med > 5 else "green",
        )

    with col4:
        render_metric_card(
            label="Tempo Máximo de Espera",
            value=f"{resultado.tempo_max_espera:.2f}",
            delta="pior caso observado",
            delta_tipo="bad" if resultado.tempo_max_espera > 10 else "warn",
            cor="red" if resultado.tempo_max_espera > 10 else "orange",
        )

    # ════════════════════════════════════════════════════════════════════════
    # SEÇÃO 2: VISÃO ESTRUTURAL (FOCO DO TCC)
    # ════════════════════════════════════════════════════════════════════════
    render_section_header("🔬", "Visão Estrutural — Desempenho Algorítmico", "FOCO DO TCC")

    col5, col6, col7 = st.columns(3)

    with col5:
        t = resultado.tempo_execucao_seg
        render_metric_card(
            label="Tempo Total de Execução",
            value=f"{t * 1000:.2f} ms",
            delta=f"O(N log K) · N={volume_paletes} paletes",
            delta_tipo="good" if t < 1 else "warn",
            cor="purple",
        )

    with col6:
        mem_kb = resultado.pico_memoria_kb
        mem_mb = mem_kb / 1024
        render_metric_card(
            label="Pico de Consumo de RAM",
            value=f"{mem_kb:.1f} KB",
            delta=f"≈ {mem_mb:.2f} MB — tracemalloc",
            delta_tipo="good" if mem_mb < 50 else "warn",
            cor="purple",
        )

    with col7:
        # Cálculo da eficiência: razão de paletes por ms
        throughput = resultado.paletes_entregues / (resultado.tempo_execucao_seg * 1000 + 1e-9)
        render_metric_card(
            label="Throughput do Algoritmo",
            value=f"{throughput:.0f}",
            delta="paletes processados por ms",
            delta_tipo="good",
            cor="blue",
        )

    # Detalhes técnicos expansível
    with st.expander("📐 Detalhes Técnicos — Análise de Complexidade"):
        c_a, c_b = st.columns(2)
        with c_a:
            st.markdown(f"""
            **Parâmetros da execução:**
            | Parâmetro | Valor |
            |-----------|-------|
            | Volume N  | `{volume_paletes}` paletes |
            | Cap. c(u,v) | `{capacidade_aresta}` |
            | Razão V/C | `{volume_paletes/capacidade_aresta:.2f}x` |
            | Gargalo | `{'SIM ⚠️' if resultado.gargalo_ativado else 'NÃO ✅'}` |
            | Seed RNG | `42` (reprodutível) |
            """)
        with c_b:
            st.markdown(f"""
            **Métricas de desempenho:**
            | Métrica | Valor |
            |---------|-------|
            | Exec. Wall-clock | `{resultado.tempo_execucao_seg*1000:.3f} ms` |
            | Pico de Heap | `{resultado.pico_memoria_kb:.2f} KB` |
            | Throughput | `{throughput:.1f} paletes/ms` |
            | T. Total Fila | `{resultado.tempo_total_espera:.2f} u.t.` |
            | P. com espera | `{resultado.paletes_com_espera}` |
            """)

    # ════════════════════════════════════════════════════════════════════════
    # SEÇÃO 3: HISTOGRAMA DE TEMPOS DE ESPERA
    # ════════════════════════════════════════════════════════════════════════
    render_section_header("📊", "Distribuição dos Tempos de Espera", "ANÁLISE ESTATÍSTICA")

    if resultado.tempos_espera:
        # Calcula bins do histograma em O(N) — sem pandas
        n_bins = min(20, max(5, int(math.sqrt(len(resultado.tempos_espera)))))
        t_min  = min(resultado.tempos_espera)
        t_max  = max(resultado.tempos_espera) + 1e-9
        larg   = (t_max - t_min) / n_bins

        contagens = [0] * n_bins
        for t in resultado.tempos_espera:
            idx = min(int((t - t_min) / larg), n_bins - 1)
            contagens[idx] += 1

        rotulos = [
            f"{t_min + i * larg:.1f}–{t_min + (i+1) * larg:.1f}"
            for i in range(n_bins)
        ]

        ch_col, info_col = st.columns([3, 1])

        with ch_col:
            st.markdown(
                "<div style='color:#8b949e;font-size:12px;margin-bottom:4px'>"
                "Frequência de paletes por faixa de tempo de espera na Área de Triagem"
                "</div>",
                unsafe_allow_html=True,
            )
            st.bar_chart(
                {rotulos[i]: contagens[i] for i in range(n_bins)},
                color="#388bfd",
                height=260,
            )

        with info_col:
            sem_espera = sum(1 for t in resultado.tempos_espera if t <= 0.01)
            com_espera = len(resultado.tempos_espera) - sem_espera
            render_metric_card(
                label="Sem espera",
                value=str(sem_espera),
                delta=f"{sem_espera/len(resultado.tempos_espera)*100:.0f}%",
                delta_tipo="good",
                cor="green",
            )
            render_metric_card(
                label="Com espera",
                value=str(com_espera),
                delta=f"{com_espera/len(resultado.tempos_espera)*100:.0f}%",
                delta_tipo="bad" if com_espera > sem_espera else "warn",
                cor="red" if com_espera > sem_espera else "orange",
            )
    else:
        st.info("Nenhum dado de espera disponível. Execute a simulação primeiro.")

    # ════════════════════════════════════════════════════════════════════════
    # SEÇÃO 4: EXPORTAR RESULTADOS EM CSV
    # ════════════════════════════════════════════════════════════════════════
    render_section_header("💾", "Exportar Resultados", "CSV")

    csv_bytes = _gerar_csv(resultado, volume_paletes, capacidade_aresta)
    st.download_button(
        label="⬇️ Baixar resultados em CSV",
        data=csv_bytes,
        file_name=f"optigraph_N{volume_paletes}_C{capacidade_aresta}.csv",
        mime="text/csv",
        help="Relatório completo: parâmetros, métricas e dados brutos de espera por palete.",
    )
    st.markdown(
        "<small style='color:#8b949e'>O arquivo inclui parâmetros da simulação, "
        "métricas agregadas e o tempo de espera individual de cada palete.</small>",
        unsafe_allow_html=True,
    )

    # ════════════════════════════════════════════════════════════════════════
    # SEÇÃO 5: GRAFO VISUAL
    # ════════════════════════════════════════════════════════════════════════
    _render_grafo(grafo, resultado)



def _render_grafo(grafo: GrafoLogistico, resultado: Optional[ResultadoSimulacao]):
    """
    Renderiza a seção do grafo visual na interface Streamlit.

    Utiliza PyVis para gerar HTML interativo (vis.js) embutido via
    st.components.v1.html() — permite zoom, drag e hover nos nós/arestas.

    Complexidade: O(V + E) para construção + renderização HTML.
    """
    import streamlit.components.v1 as components

    render_section_header("🕸️", "Grafo Logístico G=(V,E)", "VIS INTERATIVO")

    # Legenda
    leg_col1, leg_col2, leg_col3 = st.columns(3)
    with leg_col1:
        st.markdown(
            "🔵 **Aresta normal** — fluxo dentro da capacidade c(u,v)",
            help="Cor azul indica operação normal"
        )
    with leg_col2:
        st.markdown(
            "🔴 **Aresta crítica** — gargalo detectado f(u,v) ≥ c(u,v)",
            help="Cor vermelha indica saturação e gargalo"
        )
    with leg_col3:
        st.markdown(
            "🖱️ **Interativo** — hover nos nós/arestas para detalhes",
            help="Zoom com scroll, arrastar para mover"
        )

    # Geração e renderização do HTML PyVis
    visualizador = VisualizadorGrafo(grafo, resultado)
    html_grafo = visualizador.gerar_html()

    st.markdown('<div class="graph-container">', unsafe_allow_html=True)
    components.html(html_grafo, height=540, scrolling=False)
    st.markdown('</div>', unsafe_allow_html=True)

    # Tabela de adjacência do grafo (representação matricial)
    with st.expander("📋 Representação do Grafo — Lista de Adjacência G=(V,E)"):
        st.markdown("**Vértices V:**")
        nos_data = [
            {
                "ID do Vértice": no_id,
                "Tipo": no.tipo.capitalize(),
                "Capacidade Interna": no.capacidade_interna,
                "T. Processamento (base)": f"{no.tempo_proc_base} min",
            }
            for no_id, no in grafo.nos.items()
        ]
        st.table(nos_data)

        st.markdown("**Arestas E (com fluxos):**")
        arestas_data = [
            {
                "Aresta (u → v)": f"{orig} → {dest}",
                "Capacidade c(u,v)": aresta.capacidade,
                "Fluxo f(u,v)": aresta.fluxo_atual,
                "Utilização (%)": f"{min(100, int(aresta.fluxo_atual/aresta.capacidade*100))}%" if aresta.capacidade > 0 else "0%",
                "Status": "🔴 SATURADA" if (grafo.aresta_em_capacidade(orig, dest) and resultado and resultado.gargalo_ativado and (orig, dest) == ("Doca_Recebimento", "Area_Triagem")) else "✅ Normal",
            }
            for (orig, dest), aresta in grafo.arestas.items()
        ]
        st.table(arestas_data)


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    main()
