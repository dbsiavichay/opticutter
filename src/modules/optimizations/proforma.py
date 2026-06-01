import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from src.modules.optimizations.model import OptimizationModel
from src.modules.optimizations.visualization import VisualizationService


class ProformaService:
    @staticmethod
    def generate_proforma_pdf(optimization: OptimizationModel) -> io.BytesIO:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4, topMargin=0.5 * inch, bottomMargin=0.5 * inch
        )

        story = []
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=24,
            textColor=colors.HexColor("#1976D2"),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
        )

        heading_style = ParagraphStyle(
            "CustomHeading",
            parent=styles["Heading2"],
            fontSize=14,
            textColor=colors.HexColor("#424242"),
            spaceAfter=12,
            spaceBefore=12,
            fontName="Helvetica-Bold",
        )

        normal_style = styles["Normal"]
        normal_style.fontSize = 10

        story.append(Paragraph("PROFORMA DE OPTIMIZACIÓN DE CORTES", title_style))
        story.append(Spacer(1, 0.3 * inch))

        company_data = [
            ["EMPRESA MADERABLE S.A.", ""],
            ["RUC: 1234567890001", f'Fecha: {datetime.now().strftime("%d/%m/%Y")}'],
            ["Dirección: Av. Principal 123", f"Proforma N°: {optimization.id:06d}"],
            ["Teléfono: (02) 234-5678", ""],
            ["Email: info@maderable.com", ""],
        ]

        company_table = Table(company_data, colWidths=[3.5 * inch, 2.5 * inch])
        company_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#424242")),
                    ("ALIGN", (0, 0), (0, -1), "LEFT"),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(company_table)
        story.append(Spacer(1, 0.3 * inch))

        story.append(Paragraph("INFORMACIÓN DEL CLIENTE", heading_style))
        client = optimization.client
        client_name = (
            f"{client.first_name or ''} {client.last_name or ''}".strip() or "N/A"
        )

        client_data = [
            ["Nombre:", client_name],
            ["Identificador:", client.identifier or "N/A"],
            ["ID Cliente:", str(client.id)],
        ]

        client_table = Table(client_data, colWidths=[1.5 * inch, 4.5 * inch])
        client_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#424242")),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F5F5F5")),
                ]
            )
        )
        story.append(client_table)
        story.append(Spacer(1, 0.3 * inch))

        story.append(Paragraph("DETALLE DE REQUERIMIENTOS", heading_style))

        requirements = optimization.requirements
        if isinstance(requirements, list):
            req_data = [["#", "Alto", "Ancho", "Cantidad", "Tablero", "Etiqueta"]]

            for idx, req in enumerate(requirements, 1):
                req_data.append(
                    [
                        str(idx),
                        f"{req.get('height', 0)} mm",
                        f"{req.get('width', 0)} mm",
                        str(req.get("quantity", 1)),
                        req.get("board_code", "N/A"),
                        (req.get("label") or "-")[:20],
                    ]
                )

            req_table = Table(
                req_data,
                colWidths=[
                    0.4 * inch,
                    0.9 * inch,
                    0.9 * inch,
                    0.9 * inch,
                    1 * inch,
                    1.9 * inch,
                ],
            )
            req_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1976D2")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 10),
                        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                        ("FONTSIZE", (0, 1), (-1, -1), 9),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 8),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                        (
                            "ROWBACKGROUNDS",
                            (0, 1),
                            (-1, -1),
                            [colors.white, colors.HexColor("#F5F5F5")],
                        ),
                    ]
                )
            )
            story.append(req_table)

        story.append(Spacer(1, 0.3 * inch))

        story.append(Paragraph("RESUMEN DE MATERIALES", heading_style))

        layouts = optimization.layouts
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
                        entry.get("board_name", "N/A")[:22],
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
                0.8 * inch,
                1.4 * inch,
                1.2 * inch,
                0.5 * inch,
                0.8 * inch,
                0.7 * inch,
                0.7 * inch,
                0.8 * inch,
            ],
        )
        mat_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1976D2")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 9),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 1), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#F5F5F5")],
                    ),
                ]
            )
        )
        story.append(mat_table)

        story.append(Spacer(1, 0.2 * inch))

        summary_data = [
            ["Total de tableros utilizados:", str(optimization.total_boards_used)],
            ["Costo total estimado:", f"${optimization.total_boards_cost:.2f}"],
        ]

        summary_table = Table(summary_data, colWidths=[3.5 * inch, 2.5 * inch])
        summary_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 11),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#1976D2")),
                    ("ALIGN", (0, 0), (0, -1), "LEFT"),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(summary_table)

        story.append(Spacer(1, 0.3 * inch))
        story.append(Paragraph("DISPOSICIÓN DE CORTES", heading_style))
        story.append(Spacer(1, 0.1 * inch))

        if isinstance(layouts, list) and len(layouts) > 0:
            img_buffer = VisualizationService.generate_cutting_layout_image(
                layouts, width=2400, height=1600
            )
            img = Image(img_buffer, width=6.5 * inch, height=4.3 * inch)
            story.append(img)

        story.append(Spacer(1, 0.5 * inch))

        footer_text = (
            "Esta proforma es válida por 15 días. Los precios no incluyen IVA."
        )
        footer_para = Paragraph(
            footer_text,
            ParagraphStyle(
                "Footer",
                parent=styles["Normal"],
                fontSize=8,
                textColor=colors.grey,
                alignment=TA_CENTER,
            ),
        )
        story.append(footer_para)

        doc.build(story)
        buffer.seek(0)
        return buffer
