"""Seed script: borra los tableros existentes e inserta 20 nuevos."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.modules.boards.model import BoardModel
from src.shared.database import SessionLocal

BOARDS = [
    # Colores puros
    {
        "code": "MEL-18-BL",
        "name": "Melamina 18mm Blanco Polar",
        "description": "Melamina blanco polar liso, uso general en muebles",
        "length": 2440,
        "width": 1220,
        "thickness": 18,
        "grain_direction": None,
        "price": 52.00,
    },
    {
        "code": "MEL-18-NG",
        "name": "Melamina 18mm Negro Azabache",
        "description": "Melamina negro azabache, acabado mate",
        "length": 2440,
        "width": 1220,
        "thickness": 18,
        "grain_direction": None,
        "price": 54.00,
    },
    {
        "code": "MEL-18-GR",
        "name": "Melamina 18mm Gris Perla",
        "description": "Melamina gris perla liso para mobiliario moderno",
        "length": 2440,
        "width": 1220,
        "thickness": 18,
        "grain_direction": None,
        "price": 54.00,
    },
    {
        "code": "MEL-18-AN",
        "name": "Melamina 18mm Antracita",
        "description": "Melamina antracita oscuro acabado suave",
        "length": 2440,
        "width": 1220,
        "thickness": 18,
        "grain_direction": None,
        "price": 55.00,
    },
    {
        "code": "MEL-18-BG",
        "name": "Melamina 18mm Beige Arena",
        "description": "Melamina beige arena, tono cálido neutro",
        "length": 2440,
        "width": 1220,
        "thickness": 18,
        "grain_direction": None,
        "price": 52.00,
    },
    {
        "code": "MEL-18-AZ",
        "name": "Melamina 18mm Azul Océano",
        "description": "Melamina azul océano para acentos y frentes",
        "length": 2440,
        "width": 1220,
        "thickness": 18,
        "grain_direction": None,
        "price": 56.00,
    },
    {
        "code": "MEL-18-VD",
        "name": "Melamina 18mm Verde Salvia",
        "description": "Melamina verde salvia tendencia nórdica",
        "length": 2440,
        "width": 1220,
        "thickness": 18,
        "grain_direction": None,
        "price": 56.00,
    },
    {
        "code": "MEL-15-BL",
        "name": "Melamina 15mm Blanco Polar",
        "description": "Melamina blanco polar 15mm para laterales y fondos",
        "length": 2440,
        "width": 1220,
        "thickness": 15,
        "grain_direction": None,
        "price": 44.00,
    },
    {
        "code": "MEL-25-BL",
        "name": "Melamina 25mm Blanco Polar",
        "description": "Melamina blanco polar 25mm para mesones y repisas",
        "length": 2440,
        "width": 1220,
        "thickness": 25,
        "grain_direction": None,
        "price": 68.00,
    },
    {
        "code": "MEL-25-NG",
        "name": "Melamina 25mm Negro Azabache",
        "description": "Melamina negro azabache 25mm para tops y mesones",
        "length": 2440,
        "width": 1220,
        "thickness": 25,
        "grain_direction": None,
        "price": 70.00,
    },
    # Maderados
    {
        "code": "MEL-18-RB",
        "name": "Melamina 18mm Roble Natural",
        "description": "Melamina maderada roble natural veta horizontal",
        "length": 2440,
        "width": 1220,
        "thickness": 18,
        "grain_direction": "H",
        "price": 58.00,
    },
    {
        "code": "MEL-18-WN",
        "name": "Melamina 18mm Nogal Oscuro",
        "description": "Melamina maderada nogal oscuro veta fina",
        "length": 2440,
        "width": 1220,
        "thickness": 18,
        "grain_direction": "H",
        "price": 60.00,
    },
    {
        "code": "MEL-18-TC",
        "name": "Melamina 18mm Teca Dorada",
        "description": "Melamina maderada teca dorada acabado cálido",
        "length": 2440,
        "width": 1220,
        "thickness": 18,
        "grain_direction": "H",
        "price": 62.00,
    },
    {
        "code": "MEL-18-WG",
        "name": "Melamina 18mm Wengué",
        "description": "Melamina maderada wengué veta pronunciada oscura",
        "length": 2440,
        "width": 1220,
        "thickness": 18,
        "grain_direction": "H",
        "price": 62.00,
    },
    {
        "code": "MEL-18-HP",
        "name": "Melamina 18mm Haya Perla",
        "description": "Melamina maderada haya perla tono claro suave",
        "length": 2440,
        "width": 1220,
        "thickness": 18,
        "grain_direction": "H",
        "price": 58.00,
    },
    {
        "code": "MEL-18-PN",
        "name": "Melamina 18mm Pino Nórdico",
        "description": "Melamina maderada pino nórdico veta clara natural",
        "length": 2440,
        "width": 1220,
        "thickness": 18,
        "grain_direction": "V",
        "price": 56.00,
    },
    {
        "code": "MEL-18-CE",
        "name": "Melamina 18mm Cerezo",
        "description": "Melamina maderada cerezo tono rojizo cálido",
        "length": 2440,
        "width": 1220,
        "thickness": 18,
        "grain_direction": "H",
        "price": 60.00,
    },
    {
        "code": "MEL-18-AC",
        "name": "Melamina 18mm Acacia",
        "description": "Melamina maderada acacia veta irregular moderna",
        "length": 2440,
        "width": 1220,
        "thickness": 18,
        "grain_direction": "H",
        "price": 61.00,
    },
    {
        "code": "MEL-25-RB",
        "name": "Melamina 25mm Roble Natural",
        "description": "Melamina maderada roble natural 25mm para mesones",
        "length": 2440,
        "width": 1220,
        "thickness": 25,
        "grain_direction": "H",
        "price": 74.00,
    },
    {
        "code": "MEL-25-WN",
        "name": "Melamina 25mm Nogal Oscuro",
        "description": "Melamina maderada nogal oscuro 25mm para tops",
        "length": 2440,
        "width": 1220,
        "thickness": 25,
        "grain_direction": "H",
        "price": 76.00,
    },
]


def main():
    db = SessionLocal()
    try:
        deleted = db.query(BoardModel).delete()
        print(f"Eliminados {deleted} tableros existentes.")

        boards = [BoardModel(**data) for data in BOARDS]
        db.add_all(boards)
        db.commit()
        print(f"Insertados {len(boards)} tableros nuevos.")
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
