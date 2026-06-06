import io
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from src.modules.optimizations.patterns import base_label

# Rutas de fuentes a probar en orden (macOS primero, luego Linux/Docker).
_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/Library/Fonts/Arial.ttf",
]

# Paleta del diagrama (alineada con la marca MADERABLE de la proforma).
COLOR_BOARD_OUTLINE = "#1D1D1B"
COLOR_PIECE_FILL = "#FCE9E6"
COLOR_PIECE_OUTLINE = "#E8564B"
COLOR_DIM = "#1D1D1B"
COLOR_LABEL = "#212121"
COLOR_EFFICIENCY = "#2E7D32"
COLOR_WASTE_FILL = "#ECECEC"  # gris neutro: contrasta con el coral de las piezas
COLOR_WASTE_OUTLINE = "#9E9E9E"

# Grosor del borde de la pieza. Los lados canteados se resaltan con el mismo color
# del borde, solo que con una línea más gruesa (sin franja de color por tipo).
PIECE_OUTLINE_WIDTH = 2
EDGE_BANDING_WIDTH = PIECE_OUTLINE_WIDTH + 5


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    """Carga una fuente TrueType escalable; cae al bitmap por defecto si no hay."""
    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _text_size(text: str, font: ImageFont.ImageFont) -> Tuple[int, int]:
    """Mide el ancho y alto de un texto con la fuente dada."""
    bbox = ImageDraw.Draw(Image.new("RGBA", (1, 1))).textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _text_image(
    text: str, font: ImageFont.ImageFont, fill: str, pad: int = 2
) -> Image.Image:
    """Renderiza el texto en una imagen RGBA transparente (para pegar/rotar)."""
    bbox = ImageDraw.Draw(Image.new("RGBA", (1, 1))).textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    img = Image.new("RGBA", (tw + 2 * pad, th + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((pad - bbox[0], pad - bbox[1]), text, font=font, fill=fill)
    return img


def _fit_label(
    text: str, font: ImageFont.ImageFont, max_width: int, max_height: int
) -> Optional[str]:
    """Devuelve la etiqueta (truncada con … si hace falta) o None si no entra."""
    tw, th = _text_size(text, font)
    if th > max_height or max_width < 24:
        return None
    if tw <= max_width:
        return text
    truncated = text
    while truncated and _text_size(truncated + "…", font)[0] > max_width:
        truncated = truncated[:-1]
    return (truncated + "…") if truncated else None


class VisualizationService:
    @staticmethod
    def generate_layout_image(
        group: dict, target_long: int = 2000
    ) -> Tuple[io.BytesIO, Tuple[int, int]]:
        """Dibuja un único patrón de corte ocupando todo el lienzo.

        El lienzo adopta el aspecto del tablero para que, incrustado a página
        completa, lo llene al máximo. El alto de cada pieza se acota sobre el borde
        izquierdo (texto vertical) y el ancho sobre el borde inferior; la etiqueta va
        centrada. Devuelve el buffer PNG y sus dimensiones en px para incrustarlo
        respetando la proporción.
        """
        layout = group.get("layout", group)
        count = group.get("count", 1)
        material = layout.get("material", {})
        board_width = material.get("width", 1220)
        board_height = material.get("height", 2440)

        margin = 60
        info_height = 150

        scale = target_long / max(board_width, board_height)
        scaled_board_width = int(board_width * scale)
        scaled_board_height = int(board_height * scale)

        canvas_width = scaled_board_width + 2 * margin
        canvas_height = info_height + scaled_board_height + 2 * margin

        img = Image.new("RGB", (canvas_width, canvas_height), color="white")
        draw = ImageDraw.Draw(img)

        header_font = _load_font(36)
        dim_font = _load_font(26)
        label_font = _load_font(30)
        legend_font = _load_font(32)

        # ¿Hay alguna pieza canteada en este patrón? (para la entrada de leyenda).
        has_edge_banding = any(
            (piece.get("edges") or {}).get("sides")
            for piece in layout.get("placed_pieces", [])
        )

        VisualizationService._draw_legend(
            draw, margin, 24, legend_font, has_edge_banding, max_x=canvas_width - margin
        )

        board_x = margin
        board_y = info_height

        badge = f"  ·  ×{count}" if count > 1 else ""
        board_label = (
            f"Tablero {group.get('pattern_id', 1)}{badge}  ·  "
            f"{int(board_height)}×{int(board_width)} mm"
        )
        draw.text((board_x, board_y - 48), board_label, fill="black", font=header_font)
        label_w, _ = _text_size(board_label, header_font)
        efficiency = layout.get("statistics", {}).get("efficiency", 0)
        draw.text(
            (board_x + label_w + 30, board_y - 48),
            f"Eficiencia: {efficiency:.1f}%",
            fill=COLOR_EFFICIENCY,
            font=header_font,
        )

        draw.rectangle(
            [
                board_x,
                board_y,
                board_x + scaled_board_width,
                board_y + scaled_board_height,
            ],
            outline=COLOR_BOARD_OUTLINE,
            width=3,
        )

        for piece in layout.get("placed_pieces", []):
            VisualizationService._draw_piece(
                img, draw, board_x, board_y, scale, piece, dim_font, label_font
            )

        for remainder in layout.get("remainders", []):
            rx = board_x + int(remainder["x"] * scale)
            ry = board_y + int(remainder["y"] * scale)
            rw = int(remainder["width"] * scale)
            rh = int(remainder["height"] * scale)
            if rw > 5 and rh > 5:
                draw.rectangle(
                    [rx, ry, rx + rw, ry + rh],
                    fill=COLOR_WASTE_FILL,
                    outline=COLOR_WASTE_OUTLINE,
                    width=1,
                )

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer, (canvas_width, canvas_height)

    @staticmethod
    def _draw_legend(
        draw: ImageDraw.ImageDraw,
        x: int,
        y: int,
        legend_font: ImageFont.ImageFont,
        has_edge_banding: bool = False,
        max_x: Optional[int] = None,
    ) -> None:
        """Dibuja la leyenda de colores (pieza, retazo y, si aplica, lado canteado).

        Envuelve en una nueva fila cuando una entrada se saldría de ``max_x``.
        """
        legend = [
            (COLOR_PIECE_FILL, COLOR_PIECE_OUTLINE, PIECE_OUTLINE_WIDTH, "Pieza"),
            (
                COLOR_WASTE_FILL,
                COLOR_WASTE_OUTLINE,
                PIECE_OUTLINE_WIDTH,
                "Retazo / Desperdicio",
            ),
        ]
        if has_edge_banding:
            legend.append(
                ("white", COLOR_PIECE_OUTLINE, EDGE_BANDING_WIDTH, "Lado canteado")
            )
        box = 32
        start_x = x
        for fill, outline, width, text in legend:
            tw, th = _text_size(text, legend_font)
            item_w = box + 12 + tw + 50
            if max_x is not None and x > start_x and x + box + 12 + tw > max_x:
                x = start_x
                y += box + 16
            draw.rectangle(
                [x, y, x + box, y + box], fill=fill, outline=outline, width=width
            )
            draw.text(
                (x + box + 12, y + (box - th) // 2),
                text,
                fill="black",
                font=legend_font,
            )
            x += item_w

    @staticmethod
    def _draw_piece(
        img: Image.Image,
        draw: ImageDraw.ImageDraw,
        board_x: int,
        board_y: int,
        scale: float,
        piece: dict,
        dim_font: ImageFont.ImageFont,
        label_font: ImageFont.ImageFont,
    ) -> None:
        """Dibuja una pieza con el alto acotado a la izquierda, el ancho abajo y la
        etiqueta al centro."""
        px = board_x + int(piece["x"] * scale)
        py = board_y + int(piece["y"] * scale)
        pw = int(piece["width"] * scale)
        ph = int(piece["height"] * scale)

        draw.rectangle(
            [px, py, px + pw, py + ph],
            fill=COLOR_PIECE_FILL,
            outline=COLOR_PIECE_OUTLINE,
            width=PIECE_OUTLINE_WIDTH,
        )

        # Lados canteados: se resaltan con el mismo color del borde de la pieza, solo
        # que con una banda más gruesa pintada DESDE el borde HACIA ADENTRO (se dibujan
        # antes de las cotas para que los números queden legibles encima).
        edges = piece.get("edges") or {}
        sides = set(edges.get("sides") or [])
        if sides:
            w = EDGE_BANDING_WIDTH
            if "top" in sides:
                draw.rectangle([px, py, px + pw, py + w], fill=COLOR_PIECE_OUTLINE)
            if "bottom" in sides:
                draw.rectangle(
                    [px, py + ph - w, px + pw, py + ph], fill=COLOR_PIECE_OUTLINE
                )
            if "left" in sides:
                draw.rectangle([px, py, px + w, py + ph], fill=COLOR_PIECE_OUTLINE)
            if "right" in sides:
                draw.rectangle(
                    [px + pw - w, py, px + pw, py + ph], fill=COLOR_PIECE_OUTLINE
                )

        pad = 4

        # Ancho (segunda medida) sobre el borde inferior, texto horizontal.
        ancho = _text_image(str(int(piece["width"])), dim_font, COLOR_DIM)
        if ancho.width <= pw - 2 * pad and ancho.height <= ph - 2 * pad:
            img.paste(
                ancho,
                (px + (pw - ancho.width) // 2, py + ph - ancho.height - pad),
                ancho,
            )

        # Alto (primera medida) sobre el borde izquierdo, texto vertical.
        alto = _text_image(str(int(piece["height"])), dim_font, COLOR_DIM).rotate(
            90, expand=True
        )
        if alto.height <= ph - 2 * pad and alto.width <= pw - 2 * pad:
            img.paste(alto, (px + pad, py + (ph - alto.height) // 2), alto)

        # Texto centrado: la etiqueta de la pieza (etiqueta base, sin sufijo de
        # instancia y omitiendo las auto-generadas piece_N) y, debajo, la notación de
        # cantos (p. ej. "2L1C CS"). Se apilan y se centran como bloque; cada línea se
        # omite si no cabe, cubriendo etiqueta+notación, solo etiqueta o solo notación.
        stack = []
        piece_id = base_label(str(piece.get("piece_id", "")))
        if piece_id and not piece_id.startswith("piece_"):
            label = _fit_label(piece_id, label_font, pw - 2 * pad, ph - 2 * pad)
            if label:
                stack.append(_text_image(label, label_font, COLOR_LABEL))

        notation = edges.get("notation")
        if notation:
            fitted = _fit_label(notation, dim_font, pw - 2 * pad, ph - 2 * pad)
            if fitted:
                stack.append(_text_image(fitted, dim_font, COLOR_LABEL))

        if stack:
            gap = 2
            total_h = sum(im.height for im in stack) + gap * (len(stack) - 1)
            if total_h <= ph - 2 * pad:
                y = py + (ph - total_h) // 2
                for im in stack:
                    img.paste(im, (px + (pw - im.width) // 2, y), im)
                    y += im.height + gap
