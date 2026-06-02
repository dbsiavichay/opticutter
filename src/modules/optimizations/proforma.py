import io
from datetime import datetime
from typing import List

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from src.modules.optimizations.model import OptimizationModel
from src.modules.optimizations.visualization import VisualizationService
from src.shared.config import config

# Paleta de marca de la proforma.
BRAND_BLUE = colors.HexColor("#1976D2")
DARK_BLUE = colors.HexColor("#0D47A1")
LIGHT_BLUE = colors.HexColor("#E3F2FD")
ZEBRA_GREY = colors.HexColor("#F5F5F5")
TEXT_GREY = colors.HexColor("#424242")

PAGE_WIDTH, _ = A4
LEFT_MARGIN = RIGHT_MARGIN = 0.5 * inch
CONTENT_WIDTH = PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN


def _draw_page_footer(canvas, doc) -> None:
    """Dibuja el pie con la marca de generación y el número de página."""
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.grey)
    canvas.drawString(
        LEFT_MARGIN,
        0.35 * inch,
        f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')}",
    )
    canvas.drawRightString(
        PAGE_WIDTH - RIGHT_MARGIN,
        0.35 * inch,
        f"Página {canvas.getPageNumber()}",
    )
    canvas.restoreState()


class ProformaService:
    @staticmethod
    def generate_proforma_pdf(optimization: OptimizationModel) -> io.BytesIO:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            topMargin=0.5 * inch,
            bottomMargin=0.6 * inch,
            leftMargin=LEFT_MARGIN,
            rightMargin=RIGHT_MARGIN,
        )

        styles = getSampleStyleSheet()
        heading_style = ParagraphStyle(
            "SectionHeading",
            parent=styles["Heading2"],
            fontSize=13,
            textColor=DARK_BLUE,
            spaceAfter=2,
            spaceBefore=4,
            fontName="Helvetica-Bold",
        )
        cell_style = ParagraphStyle(
            "Cell",
            parent=styles["Normal"],
            fontSize=9,
            leading=11,
            textColor=TEXT_GREY,
            alignment=TA_LEFT,
        )

        story = []
        story.extend(ProformaService._build_header(optimization, styles))
        story.append(Spacer(1, 0.25 * inch))

        story.extend(_section("INFORMACIÓN DEL CLIENTE", heading_style))
        story.append(ProformaService._build_client_table(optimization))
        story.append(Spacer(1, 0.25 * inch))

        story.extend(_section("DETALLE DE REQUERIMIENTOS", heading_style))
        story.append(
            ProformaService._build_requirements_table(optimization, cell_style)
        )
        story.append(Spacer(1, 0.25 * inch))

        story.extend(_section("RESUMEN DE MATERIALES", heading_style))
        story.append(ProformaService._build_materials_table(optimization, cell_style))
        story.append(Spacer(1, 0.2 * inch))
        story.append(ProformaService._build_totals_table(optimization))

        story.append(Spacer(1, 0.3 * inch))
        story.extend(_section("DISPOSICIÓN DE CORTES", heading_style))
        story.append(Spacer(1, 0.08 * inch))
        layout_image = ProformaService._build_layout_image(optimization)
        if layout_image is not None:
            story.append(layout_image)

        story.append(Spacer(1, 0.3 * inch))
        story.append(
            Paragraph(
                "Esta proforma es válida por 15 días. Los precios no incluyen IVA.",
                ParagraphStyle(
                    "Note",
                    parent=styles["Normal"],
                    fontSize=8,
                    textColor=colors.grey,
                    alignment=TA_LEFT,
                ),
            )
        )

        doc.build(story, onFirstPage=_draw_page_footer, onLaterPages=_draw_page_footer)
        buffer.seek(0)
        return buffer

    @staticmethod
    def _build_header(optimization: OptimizationModel, styles) -> List:
        """Encabezado tipo factura: datos de empresa + bloque PROFORMA."""
        name_style = ParagraphStyle(
            "CompanyName",
            parent=styles["Normal"],
            fontSize=18,
            leading=22,
            textColor=colors.white,
            fontName="Helvetica-Bold",
        )
        detail_style = ParagraphStyle(
            "CompanyDetail",
            parent=styles["Normal"],
            fontSize=9,
            leading=13,
            textColor=colors.white,
        )
        proforma_title_style = ParagraphStyle(
            "ProformaTitle",
            parent=styles["Normal"],
            fontSize=16,
            leading=20,
            textColor=colors.white,
            fontName="Helvetica-Bold",
            alignment=TA_RIGHT,
        )
        proforma_detail_style = ParagraphStyle(
            "ProformaDetail",
            parent=styles["Normal"],
            fontSize=10,
            leading=15,
            textColor=colors.white,
            alignment=TA_RIGHT,
        )

        left_cell = [
            Paragraph(config.COMPANY_NAME, name_style),
            Spacer(1, 4),
            Paragraph(
                f"RUC: {config.COMPANY_RUC}<br/>"
                f"{config.COMPANY_ADDRESS}<br/>"
                f"Tel: {config.COMPANY_PHONE}<br/>"
                f"{config.COMPANY_EMAIL}",
                detail_style,
            ),
        ]
        right_cell = [
            Paragraph("PROFORMA", proforma_title_style),
            Paragraph(
                f"N° {optimization.id:06d}<br/>"
                f"Fecha: {datetime.now().strftime('%d/%m/%Y')}",
                proforma_detail_style,
            ),
        ]

        header_table = Table(
            [[left_cell, right_cell]],
            colWidths=[CONTENT_WIDTH * 0.6, CONTENT_WIDTH * 0.4],
        )
        header_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), BRAND_BLUE),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 16),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 16),
                    ("TOPPADDING", (0, 0), (-1, -1), 14),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
                ]
            )
        )
        return [header_table]

    @staticmethod
    def _build_client_table(optimization: OptimizationModel) -> Table:
        client = optimization.client
        client_name = (
            f"{client.first_name or ''} {client.last_name or ''}".strip() or "N/A"
        )
        client_data = [
            ["Nombre:", client_name],
            ["Identificador:", client.identifier or "N/A"],
            ["ID Cliente:", str(client.id)],
        ]
        client_table = Table(
            client_data, colWidths=[1.5 * inch, CONTENT_WIDTH - 1.5 * inch]
        )
        client_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("TEXTCOLOR", (0, 0), (-1, -1), TEXT_GREY),
                    ("BACKGROUND", (0, 0), (0, -1), ZEBRA_GREY),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        return client_table

    @staticmethod
    def _build_requirements_table(optimization: OptimizationModel, cell_style) -> Table:
        requirements = optimization.requirements
        req_data = [["#", "Alto", "Ancho", "Cantidad", "Tablero", "Etiqueta"]]
        if isinstance(requirements, list):
            for idx, req in enumerate(requirements, 1):
                req_data.append(
                    [
                        str(idx),
                        f"{req.get('height', 0)} mm",
                        f"{req.get('width', 0)} mm",
                        str(req.get("quantity", 1)),
                        req.get("board_code", "N/A"),
                        Paragraph(req.get("label") or "-", cell_style),
                    ]
                )

        req_table = Table(
            req_data,
            colWidths=[
                0.4 * inch,
                0.9 * inch,
                0.9 * inch,
                0.95 * inch,
                1.0 * inch,
                CONTENT_WIDTH - 4.15 * inch,
            ],
            repeatRows=1,
        )
        req_table.setStyle(_data_table_style(header_size=10, body_size=9))
        return req_table

    @staticmethod
    def _build_materials_table(optimization: OptimizationModel, cell_style) -> Table:
        materials_summary = optimization.materials_summary
        mat_data = [
            [
                "Código",
                "Nombre",
                "Dimensiones",
                "Cant.",
                "Área Total",
                "Efic. Prom.",
                "P. Unit.",
                "Subtotal",
            ]
        ]
        if isinstance(materials_summary, list) and materials_summary:
            for entry in materials_summary:
                mat_data.append(
                    [
                        entry.get("board_code", "N/A"),
                        Paragraph(entry.get("board_name", "N/A"), cell_style),
                        f"{entry.get('height', 0):.0f}×{entry.get('width', 0):.0f} mm",
                        str(entry.get("count", 0)),
                        f"{entry.get('total_area_m2', 0):.2f} m²",
                        f"{entry.get('avg_efficiency', 0):.1f}%",
                        f"${entry.get('cost_per_unit', 0):.2f}",
                        f"${entry.get('total_cost', 0):.2f}",
                    ]
                )
        else:
            mat_data.append(["Sin datos de materiales", "", "", "", "", "", "", ""])

        mat_table = Table(
            mat_data,
            colWidths=[
                0.75 * inch,
                CONTENT_WIDTH - 5.65 * inch,
                1.1 * inch,
                0.5 * inch,
                0.8 * inch,
                0.7 * inch,
                0.7 * inch,
                0.8 * inch,
            ],
            repeatRows=1,
        )
        mat_table.setStyle(_data_table_style(header_size=9, body_size=8))
        return mat_table

    @staticmethod
    def _build_totals_table(optimization: OptimizationModel) -> Table:
        summary_data = [
            ["Total de tableros utilizados:", str(optimization.total_boards_used)],
            ["Costo total estimado:", f"${optimization.total_boards_cost:.2f}"],
        ]
        summary_table = Table(
            summary_data, colWidths=[CONTENT_WIDTH - 2.0 * inch, 2.0 * inch]
        )
        summary_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BLUE),
                    ("BOX", (0, 0), (-1, -1), 1, BRAND_BLUE),
                    ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#BBDEFB")),
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 11),
                    ("TEXTCOLOR", (0, 0), (-1, -1), DARK_BLUE),
                    ("ALIGN", (0, 0), (0, -1), "LEFT"),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("LEFTPADDING", (0, 0), (-1, -1), 12),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ]
            )
        )
        return summary_table

    @staticmethod
    def _build_layout_image(optimization: OptimizationModel):
        layouts = optimization.layouts
        if not (isinstance(layouts, list) and layouts):
            return None

        img_buffer, (img_w, img_h) = VisualizationService.generate_cutting_layout_image(
            layouts, width=2400, height=1600
        )
        draw_width = CONTENT_WIDTH
        draw_height = draw_width * (img_h / img_w)
        max_height = 8.5 * inch
        if draw_height > max_height:
            draw_height = max_height
            draw_width = draw_height * (img_w / img_h)

        image = Image(img_buffer, width=draw_width, height=draw_height)
        image.hAlign = "CENTER"
        return image


def _section(title: str, heading_style) -> List:
    """Título de sección con regla de color debajo."""
    return [
        Paragraph(title, heading_style),
        HRFlowable(
            width="100%", thickness=1.2, color=BRAND_BLUE, spaceBefore=2, spaceAfter=8
        ),
    ]


def _data_table_style(header_size: int, body_size: int) -> TableStyle:
    """Estilo común para tablas de datos con cabecera azul y filas zebra."""
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), BRAND_BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), header_size),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), body_size),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ZEBRA_GREY]),
        ]
    )
