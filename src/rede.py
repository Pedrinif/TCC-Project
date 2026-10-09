import networkx as nx
from typing import Dict, List, Tuple
from src.domain import No, Aresta

# Capacidade "infinita" das arestas que não são o foco do estudo
SEM_LIMITE = 999

# Cada topologia: estações (nós), caminhos (arestas) e qual aresta é a crítica.
# A aresta crítica fica com capacidade None e recebe o valor escolhido na tela.
PRESETS = {
    "simples": {
        "nome": "Simples — Fluxo Linear",
        "descricao": "Doca → Triagem → 2 Estoques (4 nós, 3 arestas). "
                     "Topologia clássica com aresta crítica Doca→Triagem.",
        "nos": [
            No("Doca_Recebimento", "Doca\nRecebimento", "doca", 2.0, 100, "#1f6feb", -350, 0),
            No("Area_Triagem", "Área de\nTriagem", "triagem", 3.5, 20, "#d29922", 0, 0),
            No("Estoque_A", "Estoque A\n(Giro Alto)", "estoque", 1.5, 500, "#3fb950", 300, -150),
            No("Estoque_B", "Estoque B\n(Giro Baixo)", "estoque", 1.5, 500, "#3d8b40", 300, 150),
        ],
        "arestas": [
            ("Doca_Recebimento", "Area_Triagem", None, 1.0),
            ("Area_Triagem", "Estoque_A", SEM_LIMITE, 1.2),
            ("Area_Triagem", "Estoque_B", SEM_LIMITE, 1.8),
        ],
        "fonte": "Doca_Recebimento",
    },
    "multiplas_docas": {
        "nome": "Múltiplas Docas — Hub Central",
        "descricao": "2 Docas → Hub Triagem → 3 Estoques (6 nós, 5 arestas). "
                     "Simula recebimento paralelo convergindo em um hub central.",
        "nos": [
            No("Doca_Norte", "Doca Norte\n(Principal)", "doca", 2.0, 100, "#1f6feb", -400, -120),
            No("Doca_Sul", "Doca Sul\n(Secundária)", "doca", 2.5, 80, "#388bfd", -400, 120),
            No("Hub_Triagem", "Hub Central\nTriagem", "triagem", 3.5, 20, "#d29922", 0, 0),
            No("Estoque_A", "Estoque A\n(Perecíveis)", "estoque", 1.5, 400, "#3fb950", 350, -180),
            No("Estoque_B", "Estoque B\n(Geral)", "estoque", 1.5, 500, "#2ea043", 350, 0),
            No("Estoque_C", "Estoque C\n(Volumosos)", "estoque", 2.0, 300, "#3d8b40", 350, 180),
        ],
        "arestas": [
            ("Doca_Norte", "Hub_Triagem", None, 1.0),
            ("Doca_Sul", "Hub_Triagem", SEM_LIMITE, 1.5),
            ("Hub_Triagem", "Estoque_A", SEM_LIMITE, 1.0),
            ("Hub_Triagem", "Estoque_B", SEM_LIMITE, 1.3),
            ("Hub_Triagem", "Estoque_C", SEM_LIMITE, 2.0),
        ],
        "fonte": "Doca_Norte",
    },
    "pipeline": {
        "nome": "Pipeline com Inspeção",
        "descricao": "Doca → Inspeção → Triagem → 2 Estoques (5 nós, 4 arestas). "
                     "Cadeia linear com etapa de inspeção de qualidade.",
        "nos": [
            No("Doca_Recebimento", "Doca\nRecebimento", "doca", 2.0, 100, "#1f6feb", -500, 0),
            No("Inspecao_Qualidade", "Inspeção\nQualidade", "inspecao", 4.0, 15, "#f0883e", -180, 0),
            No("Area_Triagem", "Área de\nTriagem", "triagem", 3.0, 25, "#d29922", 140, 0),
            No("Estoque_A", "Estoque A\n(Aprovados)", "estoque", 1.5, 500, "#3fb950", 420, -130),
            No("Estoque_B", "Estoque B\n(Reprocesso)", "estoque", 2.0, 200, "#da3633", 420, 130),
        ],
        "arestas": [
            ("Doca_Recebimento", "Inspecao_Qualidade", SEM_LIMITE, 1.0),
            ("Inspecao_Qualidade", "Area_Triagem", None, 1.0),
            ("Area_Triagem", "Estoque_A", SEM_LIMITE, 1.0),
            ("Area_Triagem", "Estoque_B", SEM_LIMITE, 2.5),
        ],
        "fonte": "Doca_Recebimento",
    },
}


class LinhaProducao:
    """Monta o grafo G=(V,E) do armazém a partir de uma das topologias acima."""

    def __init__(self, preset: str = "simples", cap_aresta_critica: int = 100):
        config = PRESETS[preset]
        self.preset = preset
        self.fonte = config["fonte"]
        self.sorvedouro = "Estoque_A"
        self.G = nx.DiGraph()
        # copia os nós para não alterar o preset original
        self.nos: Dict[str, No] = {n.id: No(**vars(n)) for n in config["nos"]}
        self.arestas: Dict[Tuple[str, str], Aresta] = {}

        for no in self.nos.values():
            self.G.add_node(no.id)

        for origem, destino, cap, peso in config["arestas"]:
            if cap is None:
                cap = cap_aresta_critica
                self.aresta_critica = (origem, destino)
            self.arestas[(origem, destino)] = Aresta(origem, destino, cap, peso=peso)
            self.G.add_edge(origem, destino, capacity=cap)

    def calcular_corte_minimo(self) -> Tuple[float, List[Tuple[str, str]]]:
        """
        Fluxo máximo da doca até o estoque A (o NetworkX usa Edmonds-Karp por baixo).
        Pelo teorema do fluxo máximo / corte mínimo, as arestas que ligam os dois lados
        do corte são o gargalo teórico da rede.
        """
        valor, (lado_fonte, lado_destino) = nx.minimum_cut(self.G, self.fonte, self.sorvedouro)
        corte = [(u, v) for u, v in self.G.edges() if u in lado_fonte and v in lado_destino]
        return valor, corte

    def obter_caminho_lote(self, destino: str) -> List[str]:
        """Sequência de estações que o palete percorre até o estoque de destino."""
        return nx.shortest_path(self.G, self.fonte, destino)

    def registrar_passagem(self, origem: str, destino: str):
        """Soma 1 no fluxo da aresta (conta quantos paletes já passaram por ela)."""
        self.arestas[(origem, destino)].fluxo_atual += 1
