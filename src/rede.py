import networkx as nx
from networkx.algorithms.flow import edmonds_karp
from typing import Dict, List, Optional, Tuple
from src.domain import No, Aresta

# Capacidade "infinita" das arestas que não são o foco do estudo
SEM_LIMITE = 999

# Cada topologia: estações (nós), caminhos (arestas) e qual aresta é a crítica.
# A aresta crítica fica com capacidade None e recebe o valor escolhido na tela.
PRESETS = {
    "simples": {
        "nome": "M1 Simples — Fluxo Linear",
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
        "nome": "M2 Múltiplas Docas — Hub Central",
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
        "nome": "M3 Pipeline com Inspeção",
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

    @property
    def fontes(self) -> List[str]:
        """Todas as docas: os paletes podem entrar por qualquer uma delas."""
        return [nid for nid, no in self.nos.items() if no.tipo == "doca"]

    def capacidade_efetiva(self, no_id: str) -> int:
        """
        Quantos paletes a estação atende ao mesmo tempo na simulação. A estação no fim da
        aresta crítica usa a capacidade da aresta (valor escolhido na tela); as demais usam
        a capacidade interna do nó. Simulação e análise devem usar esta mesma função.
        """
        if no_id == self.aresta_critica[1]:
            return max(1, self.arestas[self.aresta_critica].capacidade)
        return self.nos[no_id].capacidade_interna

    def calcular_corte_minimo(self) -> Tuple[float, List[Tuple[str, str]]]:
        """
        Fluxo máximo da doca principal até o estoque A, pelo algoritmo de Edmonds-Karp
        (informado explicitamente: o padrão do NetworkX é o preflow-push). Pelo teorema do
        fluxo máximo e corte mínimo, as arestas que ligam os dois lados do corte são o
        gargalo teórico da rede.
        Atenção: aqui as capacidades das arestas são parâmetros escolhidos na tela, então o
        corte tende a coincidir com a aresta crítica. Para descobrir o gargalo a partir de
        trabalhadores e tempos de serviço, use src/estrutural.py.
        """
        valor, (lado_fonte, lado_destino) = nx.minimum_cut(self.G, self.fonte, self.sorvedouro,
                                                           flow_func=edmonds_karp)
        corte = [(u, v) for u, v in self.G.edges() if u in lado_fonte and v in lado_destino]
        return valor, corte

    def obter_caminho_lote(self, destino: str, fonte: Optional[str] = None) -> List[str]:
        """Sequência de estações que o palete percorre da doca de entrada até o estoque de destino."""
        return nx.shortest_path(self.G, fonte or self.fonte, destino)

    def registrar_passagem(self, origem: str, destino: str):
        """Soma 1 no fluxo da aresta (conta quantos paletes já passaram por ela)."""
        self.arestas[(origem, destino)].fluxo_atual += 1
