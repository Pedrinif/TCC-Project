import random
import time
import tracemalloc
from typing import List, Dict, Any
import simpy

from src.domain import ResultadoSimulacao
from src.rede import LinhaProducao

class MotorDES:
    def __init__(self, linha: LinhaProducao, volume_paletes: int, seed: int = 42):
        self.linha = linha
        self.volume_paletes = volume_paletes
        self.seed = seed
        random.seed(seed)

        self.env = simpy.Environment()
        
        self.recursos: Dict[str, simpy.Resource] = {}
        for no_id, est in linha.nos.items():
            if linha.aresta_critica and no_id == linha.aresta_critica[1]:
                cap_aresta = linha.arestas.get(linha.aresta_critica)
                capacidade = max(1, cap_aresta.capacidade) if cap_aresta else est.capacidade_interna
            else:
                capacidade = est.capacidade_interna
            
            self.recursos[no_id] = simpy.Resource(self.env, capacity=capacidade)

        self._tempos_espera: List[float] = []
        self._gargalo_ativado: bool = False
        self.logs_detalhados: List[Dict[str, Any]] = []

    def _processar_palete(self, palete_id: int):
        sorvedouros = [nid for nid, est in self.linha.nos.items() if est.tipo == "estoque"]
        destino = random.choice(sorvedouros) if sorvedouros else "Estoque_A"
        caminho = self.linha.obter_caminho_lote(destino)

        for i, estacao_id in enumerate(caminho):
            est = self.linha.nos[estacao_id]
            recurso = self.recursos[estacao_id]
            
            tempo_chegada = self.env.now
            self.logs_detalhados.append({
                "palete_id": palete_id,
                "estacao": estacao_id,
                "evento": "chegada_fila",
                "tempo": tempo_chegada,
                "tamanho_fila": len(recurso.queue)
            })

            with recurso.request() as req:
                yield req
                
                tempo_inicio = self.env.now
                espera = tempo_inicio - tempo_chegada
                
                if self.linha.aresta_critica and estacao_id == self.linha.aresta_critica[1]:
                    self._tempos_espera.append(espera)
                
                self.logs_detalhados.append({
                    "palete_id": palete_id,
                    "estacao": estacao_id,
                    "evento": "inicio_processamento",
                    "tempo": tempo_inicio,
                    "tamanho_fila": len(recurso.queue)
                })

                proc_time = max(0.1, random.gauss(est.tempo_proc_base, est.tempo_proc_base * 0.25))
                yield self.env.timeout(proc_time)
                
                if i < len(caminho) - 1:
                    prox_id = caminho[i + 1]
                    self.linha.atualizar_fluxo_aresta(estacao_id, prox_id)
                    if (estacao_id, prox_id) == self.linha.aresta_critica:
                        if self.linha.aresta_em_capacidade(estacao_id, prox_id):
                            self._gargalo_ativado = True

                self.logs_detalhados.append({
                    "palete_id": palete_id,
                    "estacao": estacao_id,
                    "evento": "saida_estacao",
                    "tempo": self.env.now,
                    "tamanho_fila": len(recurso.queue)
                })

    def _gerador_paletes(self):
        for i in range(self.volume_paletes):
            self.env.process(self._processar_palete(i))
            intervalo = random.expovariate(1.0)
            yield self.env.timeout(intervalo)

    def executar(self) -> ResultadoSimulacao:
        tracemalloc.start()
        t_inicio = time.perf_counter()

        self.env.process(self._gerador_paletes())
        self.env.run()

        t_fim = time.perf_counter()
        _, pico_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()

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


def executar_analise_comparativa(
    volume: int,
    cap_min: int,
    cap_max: int,
    cap_step: int,
    preset: str = "simples",
) -> List[Dict[str, Any]]:
    resultados = []
    for cap in range(cap_min, cap_max + 1, cap_step):
        linha = LinhaProducao(preset=preset, cap_aresta_critica=cap)
        motor = MotorDES(linha, volume)
        res = motor.executar()

        resultados.append({
            "capacidade": cap,
            "tempo_medio_espera": res.tempo_medio_espera,
            "tempo_max_espera": res.tempo_max_espera,
            "paletes_com_espera": res.paletes_com_espera,
            "pct_com_espera": (
                res.paletes_com_espera / res.paletes_entregues * 100
                if res.paletes_entregues > 0 else 0
            ),
            "throughput": res.paletes_entregues / (res.tempo_execucao_seg * 1000 + 1e-9),
            "tempo_execucao_ms": res.tempo_execucao_seg * 1000,
            "gargalo": res.gargalo_ativado,
        })
    return resultados
