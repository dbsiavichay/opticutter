import base64
import io
from datetime import datetime
from pathlib import Path
from typing import List, Union

from fastapi.responses import StreamingResponse
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    HRFlowable,
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from src.modules.optimizations.carrier import ProformaCarrier
from src.modules.optimizations.patterns import group_layouts
from src.modules.optimizations.visualization import VisualizationService
from src.shared.config import config

# Paleta de marca MADERABLE (muestreada del membrete oficial).
BRAND_CORAL = colors.HexColor("#E8564B")  # acento principal / cabeceras de tabla
BRAND_ORANGE = colors.HexColor("#EC7829")  # banda del pie de página
BRAND_BLACK = colors.HexColor("#1D1D1B")  # logo / texto / reglas
LIGHT_CORAL = colors.HexColor("#FCE9E6")  # fondo de la caja de totales
ZEBRA_GREY = colors.HexColor("#F5F5F5")
TEXT_GREY = colors.HexColor("#424242")

PAGE_WIDTH, PAGE_HEIGHT = A4
LEFT_MARGIN = RIGHT_MARGIN = 0.5 * inch
CONTENT_WIDTH = PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN

ASSETS_DIR = Path(__file__).parent / "assets"
LOGO_PATH = ASSETS_DIR / "header.jpg"
WATERMARK_PATH = ASSETS_DIR / "watermark.jpg"
ICON_WHATSAPP = ASSETS_DIR / "whatsapp.jpg"
ICON_EMAIL = ASSETS_DIR / "email.jpg"
ICON_ADDRESS = ASSETS_DIR / "address.jpg"


def _scaled_image(path: Path, width: float) -> Image:
    """Imagen escalada a ``width`` conservando su relación de aspecto."""
    img_width, img_height = ImageReader(str(path)).getSize()
    height = width * img_height / img_width
    return Image(str(path), width=width, height=height)


def _draw_watermark(canvas) -> None:
    """Marca de agua tenue centrada (se dibuja debajo del contenido)."""
    reader = ImageReader(str(WATERMARK_PATH))
    img_width, img_height = reader.getSize()
    wm_width = 3.8 * inch
    wm_height = wm_width * img_height / img_width
    canvas.drawImage(
        reader,
        (PAGE_WIDTH - wm_width) / 2,
        (PAGE_HEIGHT - wm_height) / 2,
        width=wm_width,
        height=wm_height,
        mask="auto",
    )


def _draw_footer_accent(canvas) -> None:
    """Banda angular naranja con muesca negra en el borde inferior (estilo membrete)."""
    band_h = 12
    slant = 20
    x0 = PAGE_WIDTH * 0.52

    canvas.setFillColor(BRAND_BLACK)
    notch = canvas.beginPath()
    notch.moveTo(x0 - 44, 0)
    notch.lineTo(x0 + 6, 0)
    notch.lineTo(x0 + 6 + slant, band_h)
    notch.lineTo(x0 - 44 + slant, band_h)
    notch.close()
    canvas.drawPath(notch, fill=1, stroke=0)

    canvas.setFillColor(BRAND_ORANGE)
    band = canvas.beginPath()
    band.moveTo(x0, 0)
    band.lineTo(PAGE_WIDTH, 0)
    band.lineTo(PAGE_WIDTH, band_h)
    band.lineTo(x0 + slant, band_h)
    band.close()
    canvas.drawPath(band, fill=1, stroke=0)


def _draw_page_decoration(canvas, doc) -> None:
    """Marca de agua, acento de pie y línea de generación/página en cada hoja."""
    canvas.saveState()
    _draw_watermark(canvas)
    _draw_footer_accent(canvas)
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


def _new_doc(buffer: io.BytesIO) -> SimpleDocTemplate:
    """Documento A4 con los márgenes estándar de los PDFs de Cutter."""
    return SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=0.5 * inch,
        bottomMargin=0.6 * inch,
        leftMargin=LEFT_MARGIN,
        rightMargin=RIGHT_MARGIN,
    )


class ProformaService:
    @staticmethod
    def generate_proforma_pdf(carrier: ProformaCarrier) -> io.BytesIO:
        """Proforma comercial: requerimientos, materiales con precios y disposición."""
        buffer = io.BytesIO()
        doc = _new_doc(buffer)

        styles = getSampleStyleSheet()
        heading_style = _heading_style(styles)
        cell_style = _cell_style(styles)

        story = []
        story.extend(ProformaService._build_header(carrier, styles, "PROFORMA"))
        story.append(Spacer(1, 0.25 * inch))

        story.extend(_section("INFORMACIÓN DEL CLIENTE", heading_style))
        story.append(ProformaService._build_client_table(carrier))
        story.append(Spacer(1, 0.25 * inch))

        story.extend(_section("DETALLE DE REQUERIMIENTOS", heading_style))
        story.append(ProformaService._build_requirements_table(carrier, cell_style))
        story.append(Spacer(1, 0.25 * inch))

        story.extend(_section("RESUMEN DE MATERIALES", heading_style))
        story.append(ProformaService._build_materials_table(carrier, cell_style))
        story.append(Spacer(1, 0.2 * inch))
        story.append(ProformaService._build_totals_table(carrier))

        story.append(PageBreak())
        story.extend(_section("DISPOSICIÓN DE CORTES", heading_style))
        story.append(Spacer(1, 0.08 * inch))
        story.extend(ProformaService._build_layout_pages(carrier))

        story.append(Spacer(1, 0.3 * inch))
        story.append(
            Paragraph(
                f"Esta proforma es válida por {config.ORDER_VALIDITY_DAYS} días. "
                "Los precios no incluyen IVA.",
                ParagraphStyle(
                    "Note",
                    parent=styles["Normal"],
                    fontSize=8,
                    textColor=colors.grey,
                    alignment=TA_LEFT,
                ),
            )
        )

        doc.build(
            story,
            onFirstPage=_draw_page_decoration,
            onLaterPages=_draw_page_decoration,
        )
        buffer.seek(0)
        return buffer

    @staticmethod
    def generate_production_sheet_pdf(carrier: ProformaCarrier) -> io.BytesIO:
        """Hoja de producción para el taller: lista de corte y disposición, SIN precios."""
        buffer = io.BytesIO()
        doc = _new_doc(buffer)

        styles = getSampleStyleSheet()
        heading_style = _heading_style(styles)
        cell_style = _cell_style(styles)

        story = []
        story.extend(
            ProformaService._build_header(carrier, styles, "HOJA DE PRODUCCIÓN")
        )
        story.append(Spacer(1, 0.25 * inch))

        story.extend(_section("CLIENTE", heading_style))
        story.append(ProformaService._build_client_table(carrier))
        story.append(Spacer(1, 0.25 * inch))

        story.extend(_section("LISTA DE CORTE", heading_style))
        story.append(ProformaService._build_requirements_table(carrier, cell_style))
        story.append(Spacer(1, 0.25 * inch))

        story.extend(_section("TABLEROS A UTILIZAR", heading_style))
        story.append(ProformaService._build_materials_plain_table(carrier, cell_style))
        story.append(Spacer(1, 0.2 * inch))
        story.append(ProformaService._build_boards_total_table(carrier))

        story.append(PageBreak())
        story.extend(_section("DISPOSICIÓN DE CORTES", heading_style))
        story.append(Spacer(1, 0.08 * inch))
        story.extend(ProformaService._build_layout_pages(carrier))

        doc.build(
            story,
            onFirstPage=_draw_page_decoration,
            onLaterPages=_draw_page_decoration,
        )
        buffer.seek(0)
        return buffer

    @staticmethod
    def _build_header(carrier: ProformaCarrier, styles, title: str) -> List:
        """Membrete MADERABLE: logo + contacto, regla negra y franja de título."""
        logo = _scaled_image(LOGO_PATH, 1.9 * inch)
        logo.hAlign = "LEFT"

        header_table = Table(
            [[logo, ProformaService._build_contact_block(styles)]],
            colWidths=[CONTENT_WIDTH * 0.38, CONTENT_WIDTH * 0.62],
        )
        header_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (0, 0), (0, 0), "LEFT"),
                    ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )

        rule = HRFlowable(
            width="100%",
            thickness=1.5,
            color=BRAND_BLACK,
            spaceBefore=10,
            spaceAfter=10,
        )

        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Normal"],
            fontSize=16,
            leading=20,
            textColor=BRAND_CORAL,
            fontName="Helvetica-Bold",
            alignment=TA_LEFT,
        )
        meta_style = ParagraphStyle(
            "DocMeta",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            textColor=BRAND_BLACK,
            alignment=TA_RIGHT,
        )
        title_bar = Table(
            [
                [
                    Paragraph(title, title_style),
                    Paragraph(
                        f"N° {carrier.reference}<br/>"
                        f"Fecha: {datetime.now().strftime('%d/%m/%Y')}",
                        meta_style,
                    ),
                ]
            ],
            colWidths=[CONTENT_WIDTH * 0.5, CONTENT_WIDTH * 0.5],
        )
        title_bar.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )

        return [header_table, rule, title_bar]

    @staticmethod
    def _build_contact_block(styles) -> Table:
        """Bloque de contacto con iconos: WhatsApp, correo y sucursales."""
        text_style = ParagraphStyle(
            "Contact",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
            textColor=BRAND_BLACK,
            alignment=TA_LEFT,
        )
        icon_w = 0.18 * inch

        rows = [
            [
                _scaled_image(ICON_WHATSAPP, icon_w),
                Paragraph(config.COMPANY_PHONE, text_style),
            ],
            [
                _scaled_image(ICON_EMAIL, icon_w),
                Paragraph(config.COMPANY_EMAIL, text_style),
            ],
        ]
        for branch in config.COMPANY_BRANCHES:
            rows.append(
                [
                    _scaled_image(ICON_ADDRESS, icon_w),
                    Paragraph(
                        f"<b>{branch['name']}</b> {branch['address']}", text_style
                    ),
                ]
            )

        table = Table(rows, colWidths=[icon_w + 8, 4.0 * inch])
        table.hAlign = "RIGHT"
        table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (0, 0), (0, -1), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (0, -1), 6),
                    ("RIGHTPADDING", (1, 0), (1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        return table

    @staticmethod
    def _build_client_table(carrier: ProformaCarrier) -> Table:
        client = carrier.client
        client_name = (
            f"{client.first_name or ''} {client.last_name or ''}".strip() or "N/A"
        )
        client_data = [
            ["Nombre:", client_name],
            ["Celular:", getattr(client, "phone", None) or "N/A"],
        ]
        if getattr(client, "email", None):
            client_data.append(["Email:", client.email])
        client_data.append(["ID Cliente:", str(client.id)])
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
    def _build_requirements_table(carrier: ProformaCarrier, cell_style) -> Table:
        requirements = carrier.requirements
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
    def _build_materials_table(carrier: ProformaCarrier, cell_style) -> Table:
        materials_summary = carrier.materials_summary
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
    def _build_materials_plain_table(carrier: ProformaCarrier, cell_style) -> Table:
        """Tableros a usar SIN precios (hoja de producción): código, dimensiones, cant."""
        materials_summary = carrier.materials_summary
        mat_data = [
            ["Código", "Nombre", "Dimensiones", "Espesor", "Cantidad", "Efic. Prom."]
        ]
        if isinstance(materials_summary, list) and materials_summary:
            for entry in materials_summary:
                mat_data.append(
                    [
                        entry.get("board_code", "N/A"),
                        Paragraph(entry.get("board_name", "N/A"), cell_style),
                        f"{entry.get('height', 0):.0f}×{entry.get('width', 0):.0f} mm",
                        f"{entry.get('thickness', 0):.0f} mm",
                        str(entry.get("count", 0)),
                        f"{entry.get('avg_efficiency', 0):.1f}%",
                    ]
                )
        else:
            mat_data.append(["Sin datos de materiales", "", "", "", "", ""])

        mat_table = Table(
            mat_data,
            colWidths=[
                0.9 * inch,
                CONTENT_WIDTH - 4.5 * inch,
                1.3 * inch,
                0.9 * inch,
                0.9 * inch,
                0.9 * inch,
            ],
            repeatRows=1,
        )
        mat_table.setStyle(_data_table_style(header_size=10, body_size=9))
        return mat_table

    @staticmethod
    def _build_totals_table(carrier: ProformaCarrier) -> Table:
        summary_data = [
            ["Total de tableros utilizados:", str(carrier.total_boards_used)],
            ["Costo total estimado:", f"${carrier.total_boards_cost:.2f}"],
        ]
        return _totals_table(summary_data)

    @staticmethod
    def _build_boards_total_table(carrier: ProformaCarrier) -> Table:
        """Total de tableros a cortar, sin costos (hoja de producción)."""
        return _totals_table(
            [["Total de tableros a cortar:", str(carrier.total_boards_used)]]
        )

    @staticmethod
    def _build_layout_pages(carrier: ProformaCarrier) -> List:
        """Una imagen por patrón, cada una a página completa ocupando el máximo."""
        layouts = carrier.layouts
        if not (isinstance(layouts, list) and layouts):
            return []

        # Usa los grupos persistidos; recompútalos para optimizaciones antiguas que
        # se guardaron antes de existir el campo ``layout_groups``.
        groups = carrier.layout_groups
        if not (isinstance(groups, list) and groups):
            groups = group_layouts(layouts)

        flowables: List = []
        # Cada imagen ocupa casi toda la página; el tope deja sitio al encabezado de
        # sección en la primera (las demás van solas tras un salto de página).
        max_height = 9.3 * inch
        for idx, group in enumerate(groups):
            if idx > 0:
                flowables.append(PageBreak())

            img_buffer, (img_w, img_h) = VisualizationService.generate_layout_image(
                group
            )
            draw_width = CONTENT_WIDTH
            draw_height = draw_width * (img_h / img_w)
            if draw_height > max_height:
                draw_height = max_height
                draw_width = draw_height * (img_w / img_h)

            image = Image(img_buffer, width=draw_width, height=draw_height)
            image.hAlign = "CENTER"
            flowables.append(image)

        return flowables


def pdf_response(
    buffer: io.BytesIO, filename: str, fmt: str = "pdf"
) -> Union[StreamingResponse, dict]:
    """Devuelve el PDF como descarga (``pdf``) o envuelto en JSON base64 (``base64``)."""
    if fmt.lower() == "base64":
        content = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return {
            "format": "base64",
            "content": content,
            "filename": filename,
            "mimeType": "application/pdf",
        }
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def _heading_style(styles) -> ParagraphStyle:
    return ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=13,
        textColor=BRAND_BLACK,
        spaceAfter=2,
        spaceBefore=4,
        fontName="Helvetica-Bold",
    )


def _cell_style(styles) -> ParagraphStyle:
    return ParagraphStyle(
        "Cell",
        parent=styles["Normal"],
        fontSize=9,
        leading=11,
        textColor=TEXT_GREY,
        alignment=TA_LEFT,
    )


def _section(title: str, heading_style) -> List:
    """Título de sección con regla de color debajo."""
    return [
        Paragraph(title, heading_style),
        HRFlowable(
            width="100%", thickness=1.2, color=BRAND_CORAL, spaceBefore=2, spaceAfter=8
        ),
    ]


def _totals_table(rows: List[List[str]]) -> Table:
    """Caja resaltada de totales (clave a la izquierda, valor a la derecha)."""
    table = Table(rows, colWidths=[CONTENT_WIDTH - 2.0 * inch, 2.0 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT_CORAL),
                ("BOX", (0, 0), (-1, -1), 1, BRAND_CORAL),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#F5C9C3")),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 11),
                ("TEXTCOLOR", (0, 0), (-1, -1), BRAND_BLACK),
                ("ALIGN", (0, 0), (0, -1), "LEFT"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    return table


def _data_table_style(header_size: int, body_size: int) -> TableStyle:
    """Estilo común para tablas de datos con cabecera azul y filas zebra."""
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), BRAND_CORAL),
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
