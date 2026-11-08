from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from src.escalabilidade import inclinacao_log_log


PASTA = Path("resultados")
ARQUIVO_SAIDA = PASTA / "escalabilidade.xlsx"


def cabecalho(ws, linha=1):
    for cell in ws[linha]:
        if cell.value is not None:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="1F4E78")
            cell.alignment = Alignment(horizontal="center", vertical="center")


def ajustar_colunas(ws):
    for coluna in range(1, ws.max_column + 1):
        largura = max(len(str(ws.cell(linha, coluna).value or "")) for linha in range(1, ws.max_row + 1))
        ws.column_dimensions[get_column_letter(coluna)].width = min(max(largura + 2, 12), 22)


def escrever_dataframe(ws, df):
    for coluna, nome in enumerate(df.columns, 1):
        ws.cell(1, coluna, nome)
    for linha, valores in enumerate(df.itertuples(index=False, name=None), 2):
        for coluna, valor in enumerate(valores, 1):
            ws.cell(linha, coluna, valor)
    cabecalho(ws)
    ajustar_colunas(ws)
    ws.freeze_panes = "A2"


def main():
    atividades = pd.read_csv(PASTA / "escalabilidade_atividades.csv")
    entidades = pd.read_csv(PASTA / "escalabilidade_entidades.csv")

    wb = Workbook()
    resumo = wb.active
    resumo.title = "Resumo"

    resumo.append(["Cenário", "Variável independente", "Inclinação do tempo (p)", "Inclinação da memória (p)"])
    linhas = []
    for estrutura in ("cadeia", "camadas"):
        dados = atividades[atividades["estrutura"] == estrutura]
        linhas.append([
            estrutura.capitalize(),
            "Número de atividades",
            inclinacao_log_log(dados["n_atividades"], dados["tempo_s"]),
            inclinacao_log_log(dados["n_atividades"], dados["memoria_mb"]),
        ])
    linhas.append([
        "Entidades",
        "Número de entidades",
        inclinacao_log_log(entidades["n_entidades"], entidades["tempo_s"]),
        inclinacao_log_log(entidades["n_entidades"], entidades["memoria_mb"]),
    ])
    for linha in linhas:
        resumo.append(linha)

    cabecalho(resumo)
    for linha in range(2, resumo.max_row + 1):
        for coluna in range(3, 5):
            resumo.cell(linha, coluna).number_format = "0.00"
    resumo["A6"] = "Observação"
    resumo["A6"].font = Font(bold=True, color="FFFFFF")
    resumo["A6"].fill = PatternFill("solid", fgColor="1F4E78")
    resumo.merge_cells("A7:D8")
    resumo["A7"] = (
        "As inclinações foram calculadas por regressão linear nos gráficos log-log: "
        "p = d log(métrica) / d log(tamanho). Valores próximos de 1 indicam crescimento aproximadamente linear."
    )
    resumo["A7"].alignment = Alignment(wrap_text=True, vertical="top")
    resumo.conditional_formatting.add(
        "C2:D4",
        ColorScaleRule(start_type="min", start_color="DDEBF7",
                       mid_type="percentile", mid_value=50, mid_color="FFFFFF",
                       end_type="max", end_color="F4B183"),
    )
    ajustar_colunas(resumo)
    resumo.freeze_panes = "A2"

    ws_atividades = wb.create_sheet("Atividades")
    escrever_dataframe(ws_atividades, atividades)
    ws_entidades = wb.create_sheet("Entidades")
    escrever_dataframe(ws_entidades, entidades)

    wb.save(ARQUIVO_SAIDA)
    print(f"Excel salvo em {ARQUIVO_SAIDA}")


if __name__ == "__main__":
    main()
