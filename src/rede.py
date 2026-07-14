import networkx as nx
from typing import Dict, List, Tuple
from src.domain import No, Aresta

class LinhaProducao:
    PRESETS_INFO = {
        "simples": {
            "nome": "🔹 Simples — Fluxo Linear",
            "descricao": "Doca → Triagem → 2 Estoques (4 nós, 3 arestas). "
                         "Topologia clássica com aresta crítica Doca→Triagem.",
        },
        "multiplas_docas": {
            "nome": "🔷 Múltiplas Docas — Hub Central",
            "descricao": "2 Docas → Hub Triagem → 3 Estoques (6 nós, 5 arestas). "
                         "Simula recebimento paralelo convergindo em um hub central.",
        },
        "pipeline": {
            "nome": "🔶 Pipeline com Inspeção",
            "descricao": "Doca → Inspeção → Triagem → 2 Estoques (5 nós, 4 arestas). "
                         "Cadeia linear com etapa de inspeção de qualidade.",
        },
    }

    def __init__(self, preset: str = "simples", cap_aresta_critica: int = 100):
        self.G = nx.DiGraph()
        self.nos: Dict[str, No] = {}
        self.arestas: Dict[Tuple[str, str], Aresta] = {}
        self.aresta_critica: Tuple[str, str] = ("", "")
        self.preset = preset
        self.construir_rede(preset, cap_aresta_critica)

    def _inserir_nos(self, nos_config: List[No]):
        for no in nos_config:
            self.nos[no.id] = no
            self.G.add_node(
                no.id,
                label=no.rotulo,
                tipo=no.tipo,
                capacidade=no.capacidade_interna,
                cor=no.cor,
            )

    def _inserir_arestas(self, arestas_config: List[Aresta]):
        for aresta in arestas_config:
            chave = (aresta.origem, aresta.destino)
            self.arestas[chave] = aresta
            self.G.add_edge(
                aresta.origem,
                aresta.destino,
                capacity=aresta.capacidade,
                peso=aresta.peso,
            )

    def construir_rede(self, preset: str, cap_aresta_critica: int):
        if preset == "simples":
            self.aresta_critica = ("Doca_Recebimento", "Area_Triagem")
            self._inserir_nos([
                No("Doca_Recebimento", "🚛 Doca\nRecebimento", "doca", 2.0, 100, "#1f6feb", -350, 0),
                No("Area_Triagem", "🔀 Área de\nTriagem", "triagem", 3.5, 20, "#d29922", 0, 0),
                No("Estoque_A", "📦 Estoque A\n(Giro Alto)", "estoque", 1.5, 500, "#3fb950", 300, -150),
                No("Estoque_B", "📦 Estoque B\n(Giro Baixo)", "estoque", 1.5, 500, "#3d8b40", 300, 150),
            ])
            self._inserir_arestas([
                Aresta("Doca_Recebimento", "Area_Triagem", cap_aresta_critica, peso=1.0),
                Aresta("Area_Triagem", "Estoque_A", 999, peso=1.2),
                Aresta("Area_Triagem", "Estoque_B", 999, peso=1.8),
            ])
            self.fonte = "Doca_Recebimento"
            self.sorvedouro = "Estoque_A"

        elif preset == "multiplas_docas":
            self.aresta_critica = ("Doca_Norte", "Hub_Triagem")
            self._inserir_nos([
                No("Doca_Norte", "🚛 Doca Norte\n(Principal)", "doca", 2.0, 100, "#1f6feb", -400, -120),
                No("Doca_Sul", "🚛 Doca Sul\n(Secundária)", "doca", 2.5, 80, "#388bfd", -400, 120),
                No("Hub_Triagem", "🔀 Hub Central\nTriagem", "triagem", 3.5, 20, "#d29922", 0, 0),
                No("Estoque_A", "📦 Estoque A\n(Perecíveis)", "estoque", 1.5, 400, "#3fb950", 350, -180),
                No("Estoque_B", "📦 Estoque B\n(Geral)", "estoque", 1.5, 500, "#2ea043", 350, 0),
                No("Estoque_C", "📦 Estoque C\n(Volumosos)", "estoque", 2.0, 300, "#3d8b40", 350, 180),
            ])
            self._inserir_arestas([
                Aresta("Doca_Norte", "Hub_Triagem", cap_aresta_critica, peso=1.0),
                Aresta("Doca_Sul", "Hub_Triagem", 999, peso=1.5),
                Aresta("Hub_Triagem", "Estoque_A", 999, peso=1.0),
                Aresta("Hub_Triagem", "Estoque_B", 999, peso=1.3),
                Aresta("Hub_Triagem", "Estoque_C", 999, peso=2.0),
            ])
            self.fonte = "Doca_Norte"
            self.sorvedouro = "Estoque_A"

        elif preset == "pipeline":
            self.aresta_critica = ("Inspecao_Qualidade", "Area_Triagem")
            self._inserir_nos([
                No("Doca_Recebimento", "🚛 Doca\nRecebimento", "doca", 2.0, 100, "#1f6feb", -500, 0),
                No("Inspecao_Qualidade", "🔍 Inspeção\nQualidade", "inspecao", 4.0, 15, "#f0883e", -180, 0),
                No("Area_Triagem", "🔀 Área de\nTriagem", "triagem", 3.0, 25, "#d29922", 140, 0),
                No("Estoque_A", "📦 Estoque A\n(Aprovados)", "estoque", 1.5, 500, "#3fb950", 420, -130),
                No("Estoque_B", "📦 Estoque B\n(Reprocesso)", "estoque", 2.0, 200, "#da3633", 420, 130),
            ])
            self._inserir_arestas([
                Aresta("Doca_Recebimento", "Inspecao_Qualidade", 999, peso=1.0),
                Aresta("Inspecao_Qualidade", "Area_Triagem", cap_aresta_critica, peso=1.0),
                Aresta("Area_Triagem", "Estoque_A", 999, peso=1.0),
                Aresta("Area_Triagem", "Estoque_B", 999, peso=2.5),
            ])
            self.fonte = "Doca_Recebimento"
            self.sorvedouro = "Estoque_A"

    def calcular_corte_minimo(self) -> Tuple[float, List[Tuple[str, str]]]:
        try:
            valor_corte, (particao_a, particao_b) = nx.minimum_cut(
                self.G, self.fonte, self.sorvedouro, capacity="capacity"
            )
            arestas_corte = []
            for u, v in self.G.edges():
                if u in particao_a and v in particao_b:
                    arestas_corte.append((u, v))
            return valor_corte, arestas_corte
        except:
            return 0.0, []

    def obter_caminho_lote(self, destino: str) -> List[str]:
        return nx.shortest_path(self.G, self.fonte, destino)

    def atualizar_fluxo_aresta(self, origem: str, destino: str, delta: int = 1):
        chave = (origem, destino)
        if chave in self.arestas:
            self.arestas[chave].fluxo_atual += delta

    def aresta_em_capacidade(self, origem: str, destino: str) -> bool:
        chave = (origem, destino)
        if chave in self.arestas:
            a = self.arestas[chave]
            return a.fluxo_atual >= a.capacidade
        return False
