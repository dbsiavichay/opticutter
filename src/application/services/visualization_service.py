import io
from typing import List

from PIL import Image, ImageDraw, ImageFont


class VisualizationService:
    @staticmethod
    def generate_cutting_layout_image(
        solutions: List[dict], width: int = 2400, height: int = 1600
    ) -> io.BytesIO:
        boards_per_row = 2
        board_margin = 60
        info_height = 100

        num_boards = len(solutions)
        num_rows = (num_boards + boards_per_row - 1) // boards_per_row

        total_height = (
            info_height + num_rows * (height // num_rows + board_margin) + board_margin
        )

        img = Image.new("RGB", (width, total_height), color="white")
        draw = ImageDraw.Draw(img)

        try:
            title_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 36)
            label_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
            small_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14)
        except:
            title_font = ImageFont.load_default()
            label_font = ImageFont.load_default()
            small_font = ImageFont.load_default()

        draw.text(
            (width // 2 - 200, 30),
            "Optimización de Cortes",
            fill="black",
            font=title_font,
        )

        y_offset = info_height

        for idx, solution in enumerate(solutions):
            row = idx // boards_per_row
            col = idx % boards_per_row

            material = solution.get("material", {})
            board_width = material.get("width", 1220)
            board_height = material.get("height", 2440)

            available_width = (
                width - (boards_per_row + 1) * board_margin
            ) // boards_per_row
            available_height = (
                total_height - info_height - (num_rows + 1) * board_margin
            ) // num_rows

            scale_x = available_width / board_width
            scale_y = available_height / board_height
            scale = min(scale_x, scale_y) * 0.9

            scaled_board_width = int(board_width * scale)
            scaled_board_height = int(board_height * scale)

            board_x = board_margin + col * (available_width + board_margin)
            board_y = y_offset + row * (available_height + board_margin)

            draw.rectangle(
                [
                    board_x,
                    board_y,
                    board_x + scaled_board_width,
                    board_y + scaled_board_height,
                ],
                outline="black",
                width=2,
            )

            board_label = f"Tablero {idx + 1}"
            draw.text(
                (board_x + 10, board_y - 25), board_label, fill="black", font=label_font
            )

            efficiency = solution.get("statistics", {}).get("efficiency", 0)
            efficiency_text = f"Eficiencia: {efficiency:.1f}%"
            draw.text(
                (board_x + 200, board_y - 25),
                efficiency_text,
                fill="green",
                font=small_font,
            )

            placed_pieces = solution.get("placed_pieces", [])
            for piece in placed_pieces:
                px = board_x + int(piece["x"] * scale)
                py = board_y + int(piece["y"] * scale)
                pw = int(piece["width"] * scale)
                ph = int(piece["height"] * scale)

                draw.rectangle(
                    [px, py, px + pw, py + ph],
                    fill="#E3F2FD",
                    outline="#1976D2",
                    width=2,
                )

                piece_label = f"{int(piece['width'])}x{int(piece['height'])}"
                text_bbox = draw.textbbox((0, 0), piece_label, font=small_font)
                text_width = text_bbox[2] - text_bbox[0]
                text_height = text_bbox[3] - text_bbox[1]

                if pw > text_width + 10 and ph > text_height + 10:
                    text_x = px + (pw - text_width) // 2
                    text_y = py + (ph - text_height) // 2
                    draw.text(
                        (text_x, text_y), piece_label, fill="black", font=small_font
                    )

            remainders = solution.get("remainders", [])
            for remainder in remainders:
                rx = board_x + int(remainder["x"] * scale)
                ry = board_y + int(remainder["y"] * scale)
                rw = int(remainder["width"] * scale)
                rh = int(remainder["height"] * scale)

                if rw > 5 and rh > 5:
                    draw.rectangle(
                        [rx, ry, rx + rw, ry + rh],
                        fill="#FFEBEE",
                        outline="#D32F2F",
                        width=1,
                    )

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer
