import io
from dataclasses import dataclass
from typing import Optional, Set, Tuple

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

# Grosor del borde de la pieza. Los lados canteados se resaltan con una franja más
# gruesa pegada al borde, por dentro de la pieza.
PIECE_OUTLINE_WIDTH = 2
EDGE_BANDING_WIDTH = PIECE_OUTLINE_WIDTH + 5
# Paso (px) del rayado diagonal que distingue el canto duro en modo monocromo.
HATCH_STEP = 6


@dataclass(frozen=True)
class _DiagramTheme:
    """Colores del diagrama. ``brand`` (proforma, con marca) o ``mono`` (hoja de
    producción, blanco y negro para el taller)."""

    board_outline: str
    piece_fill: str
    piece_outline: str
    dim: str
    label: str
    efficiency: str
    waste_fill: str
    waste_outline: str
    edge: str  # color de la franja del canto


_BRAND_THEME = _DiagramTheme(
    board_outline=COLOR_BOARD_OUTLINE,
    piece_fill=COLOR_PIECE_FILL,
    piece_outline=COLOR_PIECE_OUTLINE,
    dim=COLOR_DIM,
    label=COLOR_LABEL,
    efficiency=COLOR_EFFICIENCY,
    waste_fill=COLOR_WASTE_FILL,
    waste_outline=COLOR_WASTE_OUTLINE,
    edge=COLOR_PIECE_OUTLINE,
)
# Monocromo: contornos/cotas/etiquetas en negro, pieza en blanco; el retazo gris ya
# es neutro y sirve igual. El canto se diferencia por relleno (sólido vs. rayado).
_MONO_THEME = _DiagramTheme(
    board_outline="black",
    piece_fill="white",
    piece_outline="black",
    dim="black",
    label="black",
    efficiency="black",
    waste_fill=COLOR_WASTE_FILL,
    waste_outline=COLOR_WASTE_OUTLINE,
    edge="black",
)


def _draw_edge_strip(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    rect: Tuple[int, int, int, int],
    color: str,
    hatched: bool,
) -> None:
    """Pinta la franja de un canto dentro de ``rect``. Sólida (canto suave) o con
    rayado diagonal (canto duro). El rayado se dibuja en una imagen temporal del
    tamaño de la franja y se pega, de modo que queda recortado a la franja."""
    x0, y0, x1, y1 = rect
    if not hatched:
        draw.rectangle(rect, fill=color)
        return
    w, h = x1 - x0, y1 - y0
    if w <= 0 or h <= 0:
        return
    draw.rectangle(rect, outline=color, width=1)
    strip = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(strip)
    offset = -h
    while offset < w:
        sdraw.line([(offset, h), (offset + h, 0)], fill=color, width=1)
        offset += HATCH_STEP
    img.paste(strip, (x0, y0), strip)


def _rotated_rect(
    board_x: int,
    board_y: int,
    board_height: float,
    scale: float,
    x: float,
    y: float,
    w: float,
    h: float,
) -> Tuple[int, int, int, int]:
    """Mapea un rect del tablero (mm) a su rect en píxeles tras girar el tablero 90°
    en sentido horario. El punto de tablero ``(bx, by)`` va a ``(H - by, bx)``, así que
    el ancho/alto en mm se intercambian: el alto pasa a la extensión horizontal y el
    ancho a la vertical. Devuelve ``(px, py, pw, ph)``."""
    px = board_x + int((board_height - y - h) * scale)
    py = board_y + int(x * scale)
    pw = int(h * scale)
    ph = int(w * scale)
    return px, py, pw, ph


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
        group: dict, target_long: int = 2000, mono: bool = False
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

        # El tablero se dibuja girado 90° en sentido horario (landscape): el alto del
        # tablero pasa a ser la extensión horizontal del lienzo y el ancho la vertical.
        scale = target_long / max(board_width, board_height)
        scaled_board_width = int(board_height * scale)
        scaled_board_height = int(board_width * scale)

        canvas_width = scaled_board_width + 2 * margin
        canvas_height = info_height + scaled_board_height + 2 * margin

        img = Image.new("RGB", (canvas_width, canvas_height), color="white")
        draw = ImageDraw.Draw(img)

        header_font = _load_font(36)
        dim_font = _load_font(26)
        label_font = _load_font(30)
        legend_font = _load_font(32)

        theme = _MONO_THEME if mono else _BRAND_THEME

        # Tipos de canto presentes en el patrón (para la leyenda). Un canteado sin
        # tipo conocido (snapshots viejos) se trata como sólido → "Soft".
        band_types: Set[str] = set()
        for piece in layout.get("placed_pieces", []):
            edges = piece.get("edges") or {}
            if edges.get("sides"):
                bt = edges.get("band_type")
                band_types.add(bt if bt in ("Soft", "Hard") else "Soft")

        VisualizationService._draw_legend(
            img,
            draw,
            margin,
            24,
            legend_font,
            theme,
            mono=mono,
            band_types=band_types,
            max_x=canvas_width - margin,
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
            fill=theme.efficiency,
            font=header_font,
        )

        draw.rectangle(
            [
                board_x,
                board_y,
                board_x + scaled_board_width,
                board_y + scaled_board_height,
            ],
            outline=theme.board_outline,
            width=3,
        )

        for piece in layout.get("placed_pieces", []):
            VisualizationService._draw_piece(
                img,
                draw,
                board_x,
                board_y,
                board_height,
                scale,
                piece,
                dim_font,
                label_font,
                theme,
                mono=mono,
            )

        for remainder in layout.get("remainders", []):
            rx, ry, rw, rh = _rotated_rect(
                board_x,
                board_y,
                board_height,
                scale,
                remainder["x"],
                remainder["y"],
                remainder["width"],
                remainder["height"],
            )
            if rw > 5 and rh > 5:
                draw.rectangle(
                    [rx, ry, rx + rw, ry + rh],
                    fill=theme.waste_fill,
                    outline=theme.waste_outline,
                    width=1,
                )

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer, (canvas_width, canvas_height)

    @staticmethod
    def _draw_legend(
        img: Image.Image,
        draw: ImageDraw.ImageDraw,
        x: int,
        y: int,
        legend_font: ImageFont.ImageFont,
        theme: _DiagramTheme,
        mono: bool = False,
        band_types: Optional[Set[str]] = None,
        max_x: Optional[int] = None,
    ) -> None:
        """Dibuja la leyenda (pieza, retazo y, según el patrón, los cantos).

        En monocromo desglosa el canto suave (muestra sólida) y el duro (muestra
        rayada) según los tipos presentes; con marca usa una sola "Lado canteado".
        Envuelve en una nueva fila cuando una entrada se saldría de ``max_x``.
        """
        band_types = band_types or set()
        # entradas: (fill, outline, width, text, hatched)
        legend = [
            (
                theme.piece_fill,
                theme.piece_outline,
                PIECE_OUTLINE_WIDTH,
                "Pieza",
                False,
            ),
            (
                theme.waste_fill,
                theme.waste_outline,
                PIECE_OUTLINE_WIDTH,
                "Retazo / Desperdicio",
                False,
            ),
        ]
        if mono:
            if "Soft" in band_types:
                legend.append((theme.edge, theme.edge, 1, "Canto suave", False))
            if "Hard" in band_types:
                legend.append(("white", theme.edge, 1, "Canto duro", True))
        elif band_types:
            legend.append(
                ("white", theme.edge, EDGE_BANDING_WIDTH, "Lado canteado", False)
            )

        text_color = theme.label if mono else "black"
        box = 32
        start_x = x
        for fill, outline, width, text, hatched in legend:
            tw, th = _text_size(text, legend_font)
            item_w = box + 12 + tw + 50
            if max_x is not None and x > start_x and x + box + 12 + tw > max_x:
                x = start_x
                y += box + 16
            if hatched:
                _draw_edge_strip(img, draw, (x, y, x + box, y + box), outline, True)
            else:
                draw.rectangle(
                    [x, y, x + box, y + box], fill=fill, outline=outline, width=width
                )
            draw.text(
                (x + box + 12, y + (box - th) // 2),
                text,
                fill=text_color,
                font=legend_font,
            )
            x += item_w

    @staticmethod
    def _draw_piece(
        img: Image.Image,
        draw: ImageDraw.ImageDraw,
        board_x: int,
        board_y: int,
        board_height: float,
        scale: float,
        piece: dict,
        dim_font: ImageFont.ImageFont,
        label_font: ImageFont.ImageFont,
        theme: _DiagramTheme,
        mono: bool = False,
    ) -> None:
        """Dibuja una pieza (tablero girado 90° horario) con una cota acotada a la
        izquierda, otra abajo y la etiqueta al centro. Tras el giro el alto en mm es la
        extensión horizontal del rect y el ancho la vertical."""
        px, py, pw, ph = _rotated_rect(
            board_x,
            board_y,
            board_height,
            scale,
            piece["x"],
            piece["y"],
            piece["width"],
            piece["height"],
        )

        draw.rectangle(
            [px, py, px + pw, py + ph],
            fill=theme.piece_fill,
            outline=theme.piece_outline,
            width=PIECE_OUTLINE_WIDTH,
        )

        # Lados canteados: franja gruesa pegada al borde, por dentro de la pieza. En
        # monocromo el canto duro va rayado en diagonal y el suave (o desconocido)
        # sólido. Se dibujan antes de las cotas para que los números queden encima. Al
        # girar el tablero 90° horario los lados rotan: left→top, top→right,
        # right→bottom, bottom→left.
        edges = piece.get("edges") or {}
        sides = set(edges.get("sides") or [])
        if sides:
            hatched = mono and edges.get("band_type") == "Hard"
            w = EDGE_BANDING_WIDTH
            color = theme.edge
            if "left" in sides:
                _draw_edge_strip(img, draw, (px, py, px + pw, py + w), color, hatched)
            if "right" in sides:
                _draw_edge_strip(
                    img, draw, (px, py + ph - w, px + pw, py + ph), color, hatched
                )
            if "bottom" in sides:
                _draw_edge_strip(img, draw, (px, py, px + w, py + ph), color, hatched)
            if "top" in sides:
                _draw_edge_strip(
                    img, draw, (px + pw - w, py, px + pw, py + ph), color, hatched
                )

        pad = 4

        # Tras el giro, el alto (primera medida) es la extensión horizontal: va sobre el
        # borde inferior con texto horizontal.
        alto = _text_image(str(int(piece["height"])), dim_font, theme.dim)
        if alto.width <= pw - 2 * pad and alto.height <= ph - 2 * pad:
            img.paste(
                alto,
                (px + (pw - alto.width) // 2, py + ph - alto.height - pad),
                alto,
            )

        # El ancho (segunda medida) es la extensión vertical: va sobre el borde izquierdo
        # con texto vertical.
        ancho = _text_image(str(int(piece["width"])), dim_font, theme.dim).rotate(
            90, expand=True
        )
        if ancho.height <= ph - 2 * pad and ancho.width <= pw - 2 * pad:
            img.paste(ancho, (px + pad, py + (ph - ancho.height) // 2), ancho)

        # Texto centrado: la etiqueta de la pieza (etiqueta base, sin sufijo de
        # instancia y omitiendo las auto-generadas piece_N) y, debajo, la notación de
        # cantos (p. ej. "2L1C CS"). Se apilan y se centran como bloque; cada línea se
        # omite si no cabe, cubriendo etiqueta+notación, solo etiqueta o solo notación.
        stack = []
        piece_id = base_label(str(piece.get("piece_id", "")))
        if piece_id and not piece_id.startswith("piece_"):
            label = _fit_label(piece_id, label_font, pw - 2 * pad, ph - 2 * pad)
            if label:
                stack.append(_text_image(label, label_font, theme.label))

        notation = edges.get("notation")
        if notation:
            fitted = _fit_label(notation, dim_font, pw - 2 * pad, ph - 2 * pad)
            if fitted:
                stack.append(_text_image(fitted, dim_font, theme.label))

        if stack:
            gap = 2
            total_h = sum(im.height for im in stack) + gap * (len(stack) - 1)
            if total_h <= ph - 2 * pad:
                y = py + (ph - total_h) // 2
                for im in stack:
                    img.paste(im, (px + (pw - im.width) // 2, y), im)
                    y += im.height + gap
