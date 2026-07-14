from dataclasses import dataclass, field
from typing import List

@dataclass
class No:
    id: str
    rotulo: str
    tipo: str
    tempo_proc_base: float
    capacidade_interna: int
    cor: str = "#58a6ff"
    x: float = 0.0
    y: float = 0.0

@dataclass
class Aresta:
    origem: str
    destino: str
    capacidade: int
    fluxo_atual: int = 0
    peso: float = 1.0

@dataclass
class ResultadoSimulacao:
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
        if not self.tempos_espera:
            return 0.0
        return self.tempo_total_espera / len(self.tempos_espera)
