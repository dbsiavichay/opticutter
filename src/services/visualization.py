import base64
import io
from typing import List, Tuple

from PIL import Image, ImageDraw, ImageFont

from src.schemas import BoardLayout, PlacedCut, WastePiece


class VisualizationService:
    """Service for generating visual representations of optimization results."""

    def __init__(self):
        # Colors for different elements
        self.colors = {
            "background": "#FFFFFF",
            "board_outline": "#000000",
            "cut_fill": "#E3F2FD",
            "cut_outline": "#1976D2",
            "waste_fill": "#FFEBEE",
            "waste_outline": "#D32F2F",
            "text": "#212121",
        }

        # Scale factor for visualization (pixels per mm)
        self.scale = 0.2  # 1mm = 0.2 pixels

        # Minimum dimensions for readability
        self.min_board_width = 400
        self.min_board_height = 300

        # Margins
        self.margin = 40
        self.board_spacing = 60

    def create_optimization_image(
        self, boards_layout: List[BoardLayout], materials: dict
    ) -> str:
        """
        Generate a visual representation of the optimization result.

        Args:
            boards_layout: List of board layouts from optimization
            materials: Dictionary mapping material codes to Material objects

        Returns:
            Base64 encoded PNG image
        """
        if not boards_layout:
            return self._create_empty_image("No hay tableros para mostrar")

        # Filter out boards without cuts for better visualization
        boards_with_cuts = [board for board in boards_layout if board.cuts_placed]

        if not boards_with_cuts:
            return self._create_empty_image("No hay cortes colocados para mostrar")

        # Calculate total image dimensions
        total_width, total_height, board_positions = self._calculate_layout_dimensions(
            boards_with_cuts, materials
        )

        # Create image
        img = Image.new("RGB", (total_width, total_height), self.colors["background"])
        draw = ImageDraw.Draw(img)

        # Try to load a font, fallback to default
        try:
            font = ImageFont.truetype("arial.ttf", 12)
            title_font = ImageFont.truetype("arial.ttf", 16)
        except:
            try:
                # Try common font paths
                font = ImageFont.truetype(
                    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                    12,
                )
                title_font = ImageFont.truetype(
                    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                    16,
                )
            except:
                font = ImageFont.load_default()
                title_font = ImageFont.load_default()

        # Draw title
        title = f"Optimización de Cortes - {len(boards_with_cuts)} tableros"
        title_bbox = draw.textbbox((0, 0), title, font=title_font)
        title_x = (total_width - (title_bbox[2] - title_bbox[0])) // 2
        draw.text((title_x, 10), title, fill=self.colors["text"], font=title_font)

        # Draw each board
        for i, (board, position) in enumerate(zip(boards_with_cuts, board_positions)):
            self._draw_board(draw, board, position, materials, font)

        # Convert to base64
        return self._image_to_base64(img)

    def _calculate_layout_dimensions(
        self, boards_layout: List[BoardLayout], materials: dict
    ) -> Tuple[int, int, List[Tuple[int, int, int, int]]]:
        """Calculate the total dimensions needed and position of each board."""

        board_positions = []
        current_x = self.margin
        current_y = self.margin + 40  # Space for title
        max_row_height = 0
        total_width = 0

        for board in boards_layout:
            material = materials.get(board.material)
            if not material:
                continue

            # Calculate board dimensions in pixels
            board_width = max(int(material.width * self.scale), self.min_board_width)
            board_height = max(int(material.height * self.scale), self.min_board_height)

            # Check if we need to start a new row
            if current_x + board_width + self.margin > 1400:  # Max width per row
                current_y += max_row_height + self.board_spacing
                current_x = self.margin
                max_row_height = 0

            # Store position
            board_positions.append((current_x, current_y, board_width, board_height))

            # Update positions
            current_x += board_width + self.board_spacing
            max_row_height = max(max_row_height, board_height)
            total_width = max(total_width, current_x)

        total_height = current_y + max_row_height + self.margin

        return total_width, total_height, board_positions

    def _draw_board(
        self,
        draw: ImageDraw.ImageDraw,
        board: BoardLayout,
        position: Tuple[int, int, int, int],
        materials: dict,
        font,
    ):
        """Draw a single board with its cuts and waste pieces."""
        x, y, width, height = position
        material = materials.get(board.material)

        if not material:
            return

        # Draw board outline
        draw.rectangle(
            [x, y, x + width, y + height], outline=self.colors["board_outline"], width=2
        )

        # Draw board info
        info_text = f"{board.material} - Tablero #{board.index + 1}"
        utilization_text = f"Aprovechamiento: {board.utilization_percentage:.1f}%"

        draw.text((x + 5, y - 35), info_text, fill=self.colors["text"], font=font)
        draw.text(
            (x + 5, y - 20), utilization_text, fill=self.colors["text"], font=font
        )

        # Calculate scale factors for this board
        scale_x = width / material.width
        scale_y = height / material.height

        # Draw placed cuts
        for cut in board.cuts_placed:
            self._draw_cut(draw, cut, x, y, scale_x, scale_y, font)

        # Draw waste pieces
        for waste in board.waste_pieces:
            self._draw_waste(draw, waste, x, y, scale_x, scale_y)

    def _draw_cut(
        self,
        draw: ImageDraw.ImageDraw,
        cut: PlacedCut,
        board_x: int,
        board_y: int,
        scale_x: float,
        scale_y: float,
        font,
    ):
        """Draw a single cut piece."""
        # Convert coordinates
        x1 = board_x + int(cut.x * scale_x)
        y1 = board_y + int(cut.y * scale_y)
        x2 = x1 + int(cut.width * scale_x)
        y2 = y1 + int(cut.height * scale_y)

        # Draw cut rectangle
        draw.rectangle(
            [x1, y1, x2, y2],
            fill=self.colors["cut_fill"],
            outline=self.colors["cut_outline"],
        )

        # Draw cut label if it exists and the piece is large enough
        if cut.label and (x2 - x1) > 40 and (y2 - y1) > 20:
            text_bbox = draw.textbbox((0, 0), cut.label, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]

            text_x = x1 + (x2 - x1 - text_width) // 2
            text_y = y1 + (y2 - y1 - text_height) // 2

            draw.text((text_x, text_y), cut.label, fill=self.colors["text"], font=font)

        # Draw dimensions if the piece is large enough
        if (x2 - x1) > 60 and (y2 - y1) > 30:
            dim_text = f"{cut.width}×{cut.height}"
            text_bbox = draw.textbbox((0, 0), dim_text, font=font)
            text_width = text_bbox[2] - text_bbox[0]

            dim_x = x1 + (x2 - x1 - text_width) // 2
            dim_y = y2 - 15

            draw.text((dim_x, dim_y), dim_text, fill=self.colors["text"], font=font)

    def _draw_waste(
        self,
        draw: ImageDraw.ImageDraw,
        waste: WastePiece,
        board_x: int,
        board_y: int,
        scale_x: float,
        scale_y: float,
    ):
        """Draw a waste piece."""
        # Convert coordinates
        x1 = board_x + int(waste.x * scale_x)
        y1 = board_y + int(waste.y * scale_y)
        x2 = x1 + int(waste.width * scale_x)
        y2 = y1 + int(waste.height * scale_y)

        # Only draw if the waste piece is visible (at least 3x3 pixels)
        if x2 - x1 >= 3 and y2 - y1 >= 3:
            128 if waste.reusable else 64

            # Draw waste rectangle
            draw.rectangle(
                [x1, y1, x2, y2],
                fill=self.colors["waste_fill"],
                outline=self.colors["waste_outline"],
            )

    def _create_empty_image(self, message: str) -> str:
        """Create an empty image with a message."""
        img = Image.new("RGB", (400, 200), self.colors["background"])
        draw = ImageDraw.Draw(img)

        try:
            font = ImageFont.truetype("arial.ttf", 16)
        except:
            font = ImageFont.load_default()

        text_bbox = draw.textbbox((0, 0), message, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]

        x = (400 - text_width) // 2
        y = (200 - text_height) // 2

        draw.text((x, y), message, fill=self.colors["text"], font=font)

        return self._image_to_base64(img)

    def _image_to_base64(self, img: Image.Image) -> str:
        """Convert PIL Image to base64 string."""
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return img_base64


# Global instance
visualization_service = VisualizationService()
