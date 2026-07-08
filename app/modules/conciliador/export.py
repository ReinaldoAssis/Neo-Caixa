from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

from app.modules.conciliador.constants import (
    CATEGORY_LABELS_POSTO,
    CATEGORIAS_RESTAURANTE_LABELS,
    DENOMINATIONS,
)
from app.modules.conciliador.services import (
    format_money,
    build_conciliation_rows_posto,
    build_conciliation_rows_restaurante,
    consolidate_contagens,
)


def _date_br(iso_date: str) -> str:
    try:
        dt = datetime.strptime(iso_date, "%Y-%m-%d")
        return dt.strftime("%d/%m/%Y")
    except ValueError:
        return iso_date


def generate_conciliation_pdf_bytes(caixa: dict, posto_config: dict | None = None) -> bytes:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError:
        raise RuntimeError("Instale reportlab para exportar PDF.")

    tipo = caixa.get("tipo", "posto")
    data_br = _date_br(caixa.get("data", ""))
    title = "Neo Caixa - Auto Posto Lagoa Cafe"
    subtitle = f"Data: {data_br}"

    buf = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp_path = buf.name
    buf.close()

    try:
        doc = SimpleDocTemplate(tmp_path, pagesize=A4, rightMargin=1.5 * cm, leftMargin=1.5 * cm)
        styles = getSampleStyleSheet()
        story = [
            Paragraph(title, styles["Title"]),
            Paragraph(subtitle, styles["Normal"]),
            Spacer(1, 0.4 * cm),
            Paragraph("Resultado da Conciliacao", styles["Heading2"]),
        ]

        avulsos = caixa.get("lancamentos_avulsos") or []
        contagens = caixa.get("contagens_dinheiro") or []

        if tipo == "posto":
            from app.modules.conciliador.config_posto import (
                default_config,
                config_category_keys,
                config_labels,
            )
            cfg = posto_config or default_config()
            posto_keys = config_category_keys(cfg)
            posto_labels = config_labels(cfg)
            table_data = [["Categoria", "Sistema", "Site", "Diferenca", "Status"]]
            for row in build_conciliation_rows_posto(
                caixa.get("categorias", {}), avulsos, posto_keys, posto_labels
            ):
                table_data.append([
                    row["label"],
                    format_money(row["sistema"]),
                    format_money(row["site"]),
                    format_money(row["diferenca"]),
                    row["status"],
                ])
            story.append(_styled_table(table_data))

            story.extend([
                Spacer(1, 0.4 * cm),
                Paragraph("Informacoes Complementares", styles["Heading2"]),
                _styled_table([
                    ["Sangria", format_money(caixa.get("sangria", 0))],
                    ["Notas a Prazo", format_money(caixa.get("notas_a_prazo", 0))],
                    ["Despesas do Posto", format_money(caixa.get("despesas", 0))],
                ]),
            ])
        else:
            geral = next((c for c in contagens if c.get("label") == "Geral"), None)
            dinheiro_real = round(geral.get("total", 0) if geral else 0, 2)
            table_data = [["Categoria", "Classif.", "Sistema", "Real", "Diferenca", "Status"]]
            for row in build_conciliation_rows_restaurante(
                caixa.get("categorias", {}), avulsos, dinheiro_real
            ):
                table_data.append([
                    row["label"],
                    row["classificacao"],
                    format_money(row["sistema"]),
                    format_money(row["real"]),
                    format_money(row["diferenca"]),
                    row["status"],
                ])

        # Lancamentos avulsos
        if avulsos:
            story.extend([
                Spacer(1, 0.4 * cm),
                Paragraph("Lancamentos Avulsos", styles["Heading2"]),
            ])
            avulso_data = [["Tipo", "Descricao", "Valor", "Categoria"]]
            if tipo == "posto":
                from app.modules.conciliador.config_posto import default_config, config_labels
                labels = config_labels(posto_config or default_config())
            else:
                labels = CATEGORIAS_RESTAURANTE_LABELS
            for item in avulsos:
                if item.get("categoria_vinculada"):
                    cat_label = labels.get(item["categoria_vinculada"], item["categoria_vinculada"])
                else:
                    cat_label = item.get("categoria_nova", "")
                avulso_data.append([
                    item.get("tipo", ""),
                    item.get("descricao", ""),
                    format_money(item.get("valor", 0)),
                    cat_label,
                ])
            avulso_table = Table(avulso_data, hAlign="LEFT")
            avulso_table.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#adb5bd")),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9ecef")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (2, 1), (2, -1), "RIGHT"),
            ]))
            story.append(avulso_table)

        # Contagem de dinheiro
        story.extend([
            Spacer(1, 0.4 * cm),
            Paragraph("Contagem de Dinheiro", styles["Heading2"]),
        ])
        if not contagens:
            story.append(Paragraph("Nenhuma contagem registrada.", styles["Normal"]))
        else:
            geral_consolidado = consolidate_contagens(contagens)
            for contagem in contagens:
                story.append(Paragraph(
                    contagem.get("label", "Contagem"), styles["Heading3"]
                ))
                rows = [["Cedula", "Quantidade", "Subtotal"]]
                notas = contagem.get("notas", {})
                for denom in DENOMINATIONS:
                    qty = int(notas.get(str(denom), 0) or 0)
                    rows.append([f"R$ {denom}", str(qty), format_money(qty * denom)])
                rows.append(["Moedas", "", format_money(contagem.get("moedas", 0))])
                total = contagem.get("total", 0)
                rows.append(["Total", "", format_money(total)])
                tbl = Table(rows, hAlign="LEFT")
                tbl.setStyle(TableStyle([
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#adb5bd")),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9ecef")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ]))
                story.append(tbl)
                serials = contagem.get("seriais_200") or []
                if serials:
                    story.append(Paragraph(
                        "Seriais R$ 200: " + ", ".join(serials), styles["Normal"]
                    ))
                story.append(Spacer(1, 0.2 * cm))

    finally:
        pass

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.drawString(1.5 * cm, 1 * cm, "CaixaPos")
        canvas.drawRightString(19.5 * cm, 1 * cm, f"Pagina {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)

    pdf_bytes = Path(tmp_path).read_bytes()
    try:
        Path(tmp_path).unlink()
    except OSError:
        pass
    return pdf_bytes


def _styled_table(table_data: list[list]) -> Table:
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle

    tbl = Table(table_data, repeatRows=1, hAlign="LEFT")
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9ecef")),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#adb5bd")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("ALIGN", (-1, 1), (-1, -1), "CENTER"),
    ]))
    return tbl
