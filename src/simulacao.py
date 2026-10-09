import random
import time
import tracemalloc
from typing import List, Dict, Any
import simpy

from src.domain import ResultadoSimulacao
from src.rede import LinhaProducao


class MotorDES:
    """
    Simulação de eventos discretos (SimPy) da linha.

    Cada estação vira um Resource com capacidade limitada. Os paletes chegam em
    intervalos exponenciais (processo de Poisson) e o tempo de processamento em
    cada estação segue uma Normal. Quando a estação está cheia, o palete entra na fila.
    """

    def __init__(self, linha: LinhaProducao, volume_paletes: int, seed: int = 42):
        self.linha = linha
        self.volume_paletes = volume_paletes
        random.seed(seed)  # mesma seed = mesmo resultado

        self.env = simpy.Environment()
        self.estacao_critica = linha.aresta_critica[1]

        # A estação no fim da aresta crítica atende no máximo c(u,v) paletes ao mesmo tempo
        self.recursos: Dict[str, simpy.Resource] = {}
        for no_id, no in linha.nos.items():
            if no_id == self.estacao_critica:
                capacidade = max(1, linha.arestas[linha.aresta_critica].capacidade)
            else:
                capacidade = no.capacidade_interna
            self.recursos[no_id] = simpy.Resource(self.env, capacity=capacidade)

        self.estoques = [nid for nid, no in linha.nos.items() if no.tipo == "estoque"]
        self._tempos_espera: List[float] = []
        self._gargalo_ativado = False
        self.logs_detalhados: List[Dict[str, Any]] = []

    def _log(self, palete_id: int, estacao: str, evento: str):
        self.logs_detalhados.append({
            "palete_id": palete_id,
            "estacao": estacao,
            "evento": evento,
            "tempo": self.env.now,
            "tamanho_fila": len(self.recursos[estacao].queue),
        })

    def _processar_palete(self, palete_id: int):
        """Caminho de um palete: sorteia o estoque de destino e passa por cada estação."""
        caminho = self.linha.obter_caminho_lote(random.choice(self.estoques))

        for i, estacao_id in enumerate(caminho):
            no = self.linha.nos[estacao_id]
            chegada = self.env.now
            self._log(palete_id, estacao_id, "chegada_fila")

            with self.recursos[estacao_id].request() as pedido:
                yield pedido  # espera aqui se a estação estiver lotada

                # só a espera na estação crítica entra nas métricas
                if estacao_id == self.estacao_critica:
                    self._tempos_espera.append(self.env.now - chegada)
                self._log(palete_id, estacao_id, "inicio_processamento")

                tempo_proc = max(0.1, random.gauss(no.tempo_proc_base, no.tempo_proc_base * 0.25))
                yield self.env.timeout(tempo_proc)

                if i < len(caminho) - 1:
                    proxima = caminho[i + 1]
                    saturou = self.linha.registrar_passagem(estacao_id, proxima)
                    if saturou and (estacao_id, proxima) == self.linha.aresta_critica:
                        self._gargalo_ativado = True

                self._log(palete_id, estacao_id, "saida_estacao")

    def _gerador_paletes(self):
        """Solta um palete por vez com intervalo exponencial entre eles (média 1 u.t.)."""
        for i in range(self.volume_paletes):
            self.env.process(self._processar_palete(i))
            yield self.env.timeout(random.expovariate(1.0))

    def executar(self) -> ResultadoSimulacao:
        """Roda a simulação inteira e mede tempo de execução e pico de memória."""
        tracemalloc.start()
        inicio = time.perf_counter()

        self.env.process(self._gerador_paletes())
        self.env.run()

        duracao = time.perf_counter() - inicio
        _, pico_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        esperas = self._tempos_espera
        return ResultadoSimulacao(
            paletes_entregues=self.volume_paletes,
            paletes_com_espera=sum(1 for t in esperas if t > 0.01),
            tempo_total_espera=sum(esperas),
            tempo_max_espera=max(esperas, default=0.0),
            tempos_espera=esperas,
            gargalo_ativado=self._gargalo_ativado,
            tempo_execucao_seg=duracao,
            pico_memoria_kb=pico_bytes / 1024,
        )


def executar_analise_comparativa(volume: int, cap_min: int, cap_max: int, cap_step: int,
                                 preset: str = "simples") -> List[Dict[str, Any]]:
    """Roda a simulação para várias capacidades da aresta crítica (curva de saturação)."""
    resultados = []
    for cap in range(cap_min, cap_max + 1, cap_step):
        res = MotorDES(LinhaProducao(preset, cap), volume).executar()
        resultados.append({
            "capacidade": cap,
            "tempo_medio_espera": res.tempo_medio_espera,
            "tempo_max_espera": res.tempo_max_espera,
            "pct_com_espera": res.pct_com_espera,
            "gargalo": res.gargalo_ativado,
        })
    return resultados
