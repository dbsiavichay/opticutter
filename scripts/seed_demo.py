"""Seed de demostración: sucursales, usuarios, clientes, pre-órdenes y órdenes.

Genera un conjunto de datos completo y realista para poblar el dashboard / hacer QA:

- **Sucursales**: tomadas de ``COMPANY_BRANCHES`` del entorno (.env): Sucúa y Macas.
- **Usuarios**: 1 administrador global + 1 vendedor y 1 operador por sucursal
  (``admin@empresa.com``, ``vendedor<slug>@empresa.com``, ``operador<slug>@empresa.com``).
- **Clientes**: 5, todos con celular (requisito para emitir proforma/pedido).
- **Tableros**: reusa el catálogo si existe; si no, crea unos tableros demo (insumo
  del optimizador).
- **Pre-órdenes**: una en CADA estado por sucursal (draft, sent, changes_requested,
  confirmed, rejected, expired, cancelled), recorriendo el flujo real (enlace de
  revisión + acciones del cliente) donde aplica.
- **Órdenes**: una en CADA estado por sucursal (confirmed, in_production, cutting,
  cut, completed, cancelled), avanzando la máquina de estados con los actores y
  roles correctos (el operador se autoasigna en ``cutting``, se marcan todas las
  piezas cortadas antes de cerrar el corte, etc.).

Idempotente para los cimientos (sucursales/usuarios/clientes/tableros: get-or-create).
Las pre-órdenes/órdenes solo se generan si aún no existen datos de demo (marcados con
``source="seed"``); usa ``--reset`` para borrarlos y regenerarlos.

Requiere que el esquema ya exista (migraciones aplicadas). Ejemplos:

    make seed-demo
    DATABASE_URL=postgresql://cutter:cutter@localhost:5433/cutter_db \\
        .venv/bin/python scripts/seed_demo.py [--reset]
"""

import argparse
import itertools
import os
import sys
import unicodedata

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Carga el .env ANTES de importar la config (environs no lo lee solo). Así las
# sucursales (COMPANY_BRANCHES) y demás ajustes salen del .env. ``override=False``:
# una variable ya presente en el entorno (p. ej. DATABASE_URL pasado por el make
# target apuntando al Postgres local) gana sobre la del archivo.
from environs import Env  # noqa: E402

Env().read_env(os.path.join(os.path.dirname(__file__), "..", ".env"), recurse=False)

from datetime import datetime, timedelta  # noqa: E402

from src.modules.branches.model import BranchModel  # noqa: E402
from src.modules.clients.model import ClientModel  # noqa: E402
from src.modules.orders.model import OrderModel, OrderStatus  # noqa: E402
from src.modules.orders.schemas import OrderCreate  # noqa: E402
from src.modules.orders.service import OrderService  # noqa: E402
from src.modules.preorders.model import (  # noqa: E402
    PreOrderModel,
    PreOrderStatus,
)
from src.modules.preorders.review_service import PreOrderReviewService  # noqa: E402
from src.modules.preorders.schemas import PreOrderCreate  # noqa: E402
from src.modules.preorders.service import PreOrderService  # noqa: E402
from src.modules.products.model import ProductModel, ProductType  # noqa: E402
from src.modules.users.enums import UserRole  # noqa: E402
from src.modules.users.model import UserModel  # noqa: E402
from src.shared.audit import staff_actor  # noqa: E402
from src.shared.config import config  # noqa: E402
from src.shared.database import SessionLocal  # noqa: E402
from src.shared.security import hash_password  # noqa: E402

# Contraseña única para todos los usuarios sembrados (override con SEED_PASSWORD).
SEED_PASSWORD = os.getenv("SEED_PASSWORD") or config.ADMIN_PASSWORD or "Cutter2026!"

# Marca de origen para identificar (y poder resetear) los datos transaccionales demo.
SEED_SOURCE = "seed"

# 5 clientes: (identifier, nombre, apellido, celular, email).
CLIENTS = [
    ("0102030405", "María", "González", "0991111111", "maria.gonzalez@example.com"),
    ("0203040506", "Carlos", "Pérez", "0992222222", "carlos.perez@example.com"),
    ("0304050607", "Lucía", "Vásquez", "0993333333", "lucia.vasquez@example.com"),
    ("0405060708", "Jorge", "Mendoza", "0994444444", None),
    ("0506070809", "Ana", "Torres", "0995555555", "ana.torres@example.com"),
]

# Tableros demo (solo se crean si el catálogo está vacío): (code, name, alto, ancho,
# grosor, precio). Dimensiones grandes para que las listas de corte demo entren holgadas.
DEMO_BOARDS = [
    ("DEMO-MDP-BLN-15", "Tablero Demo Blanco 15mm", 2440, 1830, 15, 48.00),
    ("DEMO-MDP-NGR-15", "Tablero Demo Negro 15mm", 2440, 1830, 15, 52.00),
    ("DEMO-MDP-ROB-18", "Tablero Demo Roble 18mm", 2440, 1830, 18, 64.00),
]

# Estados a sembrar por sucursal.
PREORDER_STATUSES = [
    PreOrderStatus.draft,
    PreOrderStatus.sent,
    PreOrderStatus.changes_requested,
    PreOrderStatus.confirmed,
    PreOrderStatus.rejected,
    PreOrderStatus.expired,
    PreOrderStatus.cancelled,
]
ORDER_STATUSES = [
    OrderStatus.confirmed,
    OrderStatus.in_production,
    OrderStatus.cutting,
    OrderStatus.cut,
    OrderStatus.completed,
    OrderStatus.cancelled,
]

# Contador global: garantiza un hash de optimización único por entidad (vía el
# ``label`` de las piezas), de modo que la dedupe de órdenes nunca las colapse.
_seq = itertools.count(1)


def slugify(name: str) -> str:
    """Slug ascii en minúsculas y sin acentos: 'Sucúa' -> 'sucua', 'Macas' -> 'macas'."""
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_str = nfkd.encode("ascii", "ignore").decode("ascii")
    return "".join(ch for ch in ascii_str.lower() if ch.isalnum())


def make_cutlist(material_key: str) -> list[dict]:
    """Lista de corte demo con etiquetas únicas (hash de optimización distinto)."""
    i = next(_seq)
    return [
        {
            "priority": 1,
            "height": 600,
            "width": 400,
            "quantity": 2,
            "material_key": material_key,
            "label": f"Puerta {i}",
        },
        {
            "priority": 0,
            "height": 350,
            "width": 300,
            "quantity": 3,
            "material_key": material_key,
            "label": f"Estante {i}",
        },
        {
            "priority": 0,
            "height": 700,
            "width": 250,
            "quantity": 2,
            "material_key": material_key,
            "label": f"Lateral {i}",
        },
    ]


def build_inputs(board: ProductModel) -> tuple[list[dict], list[dict]]:
    """Materiales (1 tablero de catálogo) + lista de corte única para una entidad."""
    key = "b1"
    materials = [{"key": key, "source": "catalog", "product_id": board.id}]
    return materials, make_cutlist(key)


# --------------------------------------------------------------------------- #
# Cimientos (idempotentes)                                                     #
# --------------------------------------------------------------------------- #


def ensure_branches(db) -> list[BranchModel]:
    """Crea/obtiene las sucursales desde ``COMPANY_BRANCHES`` del entorno."""
    branches = []
    for entry in config.COMPANY_BRANCHES:
        name = entry["name"]
        code = slugify(name).upper()[:32]
        branch = db.query(BranchModel).filter(BranchModel.code == code).first()
        if branch is None:
            branch = BranchModel(
                code=code,
                name=name,
                address=entry.get("address"),
                is_active=True,
            )
            db.add(branch)
            db.flush()
            print(f"  + Sucursal {code} ({name})")
        else:
            print(f"  = Sucursal {code} ({name}) ya existía")
        branches.append(branch)
    return branches


def ensure_user(db, email, full_name, role, branch_id) -> UserModel:
    """Crea/obtiene un usuario por email."""
    user = db.query(UserModel).filter(UserModel.email == email).first()
    if user is None:
        user = UserModel(
            email=email,
            full_name=full_name,
            hashed_password=hash_password(SEED_PASSWORD),
            role=role,
            is_active=True,
            branch_id=branch_id,
        )
        db.add(user)
        db.flush()
        print(f"  + Usuario {email} ({role})")
    else:
        print(f"  = Usuario {email} ya existía")
    return user


def ensure_users(db, branches) -> dict[int, dict[str, UserModel]]:
    """Admin global + vendedor y operador por sucursal. Devuelve staff por sucursal."""
    ensure_user(
        db, "admin@empresa.com", "Administrador General", UserRole.ADMIN.value, None
    )
    staff: dict[int, dict[str, UserModel]] = {}
    for branch in branches:
        slug = slugify(branch.name)
        seller = ensure_user(
            db,
            f"vendedor{slug}@empresa.com",
            f"Vendedor {branch.name}",
            UserRole.SELLER.value,
            branch.id,
        )
        operator = ensure_user(
            db,
            f"operador{slug}@empresa.com",
            f"Operador {branch.name}",
            UserRole.OPERATOR.value,
            branch.id,
        )
        staff[branch.id] = {"seller": seller, "operator": operator}
    return staff


def ensure_clients(db) -> list[ClientModel]:
    """Crea/obtiene los 5 clientes demo (todos con celular)."""
    clients = []
    for identifier, first, last, phone, email in CLIENTS:
        client = (
            db.query(ClientModel).filter(ClientModel.identifier == identifier).first()
        )
        if client is None:
            client = ClientModel(
                identifier=identifier,
                first_name=first,
                last_name=last,
                phone=phone,
                email=email,
                source=SEED_SOURCE,
            )
            db.add(client)
            db.flush()
            print(f"  + Cliente {identifier} ({first} {last})")
        else:
            print(f"  = Cliente {identifier} ya existía")
        clients.append(client)
    return clients


def ensure_boards(db) -> list[ProductModel]:
    """Reusa hasta 3 tableros del catálogo; si no hay, crea los tableros demo."""
    existing = (
        db.query(ProductModel)
        .filter(ProductModel.type == ProductType.BOARD.value)
        .order_by(ProductModel.id)
        .limit(3)
        .all()
    )
    if existing:
        print(f"  = Usando {len(existing)} tablero(s) existentes del catálogo")
        return existing

    boards = []
    for code, name, height, width, thickness, price in DEMO_BOARDS:
        board = ProductModel(
            type=ProductType.BOARD.value,
            code=code,
            name=name,
            description=name,
            price=price,
            is_active=True,
            attributes={
                "height": height,
                "width": width,
                "thickness": thickness,
                "grainDirection": None,
            },
        )
        db.add(board)
        boards.append(board)
        print(f"  + Tablero {code} ({name})")
    db.flush()
    return boards


# --------------------------------------------------------------------------- #
# Datos transaccionales (pre-órdenes y órdenes)                                #
# --------------------------------------------------------------------------- #


def seed_preorder(db, status, branch, client, seller, board):
    """Crea una pre-orden y la lleva al ``status`` objetivo por el flujo real."""
    pre_svc = PreOrderService(db)
    review_svc = PreOrderReviewService(db)
    actor = staff_actor(seller)

    materials, requirements = build_inputs(board)
    preorder = pre_svc.create(
        PreOrderCreate(
            materials=materials,
            requirements=requirements,
            client_id=client.id,
            branch_id=branch.id,
            source=SEED_SOURCE,
            notes=f"Pre-orden demo en estado {status.value}",
        ),
        actor=actor,
        branch_scope=None,  # ruta admin: usa branch_id del body
    )

    if status == PreOrderStatus.draft:
        pass

    elif status == PreOrderStatus.sent:
        review_svc.generate(preorder.id, actor=actor)

    elif status == PreOrderStatus.changes_requested:
        _, token = review_svc.generate(preorder.id, actor=actor)
        review_svc.request_changes(
            token, note="¿Pueden ajustar la medida de las puertas?"
        )

    elif status == PreOrderStatus.confirmed:
        _, token = review_svc.generate(preorder.id, actor=actor)
        review_svc.confirm(token, note="Aprobado por el cliente")

    elif status == PreOrderStatus.rejected:
        _, token = review_svc.generate(preorder.id, actor=actor)
        review_svc.reject(token, note="El cliente prefirió otra cotización")

    elif status == PreOrderStatus.expired:
        # Vence la vigencia y deja que el barrido perezoso la marque 'expired'.
        preorder.expires_at = datetime.utcnow() - timedelta(days=1)
        db.commit()
        pre_svc.get_or_404(preorder.id)

    elif status == PreOrderStatus.cancelled:
        # No hay endpoint de cancelación hoy; se registra la transición a mano para
        # tener el estado representado en la demo.
        pre_svc._record_transition(
            preorder,
            preorder.status,
            PreOrderStatus.cancelled,
            actor,
            note="Cancelada por el vendedor",
        )
        preorder.status = PreOrderStatus.cancelled.value
        db.commit()

    db.refresh(preorder)
    return preorder


def _mark_all_pieces_cut(svc: OrderService, order_id: int, actor):
    """Marca como cortadas todas las piezas colocadas (requiere estado 'cutting')."""
    order = svc.get_or_404(order_id)
    for board in order.boards:
        for piece in board.pieces:
            svc.mark_piece_cut(order_id, piece.id, cut=True, actor=actor)


def drive_order_to(svc, order, target, seller_actor, operator_actor):
    """Avanza la orden por la máquina de estados hasta ``target``."""
    if target == OrderStatus.confirmed:
        return
    if target == OrderStatus.cancelled:
        svc.transition(
            order.id, OrderStatus.cancelled, actor=seller_actor, note="Cancelada"
        )
        return

    svc.transition(
        order.id,
        OrderStatus.in_production,
        actor=seller_actor,
        note="Enviada a producción",
    )
    if target == OrderStatus.in_production:
        return

    # El operador se autoasigna al tomar el corte.
    svc.transition(
        order.id,
        OrderStatus.cutting,
        actor=operator_actor,
        note="Operador toma el corte",
    )
    if target == OrderStatus.cutting:
        return

    _mark_all_pieces_cut(svc, order.id, operator_actor)
    svc.transition(
        order.id, OrderStatus.cut, actor=operator_actor, note="Corte finalizado"
    )
    if target == OrderStatus.cut:
        return

    svc.transition(
        order.id, OrderStatus.completed, actor=seller_actor, note="Pedido entregado"
    )


def seed_order(db, status, branch, client, seller, operator, board):
    """Crea una orden y la lleva al ``status`` objetivo por la máquina de estados."""
    svc = OrderService(db)
    seller_actor = staff_actor(seller)
    operator_actor = staff_actor(operator)

    materials, requirements = build_inputs(board)
    order = svc.create(
        OrderCreate(
            materials=materials,
            requirements=requirements,
            client_id=client.id,
            branch_id=branch.id,
            source=SEED_SOURCE,
            notes=f"Orden demo en estado {status.value}",
        ),
        actor=seller_actor,
    )
    drive_order_to(svc, order, status, seller_actor, operator_actor)
    db.refresh(order)
    return order


def seed_transactional(db, branches, clients, staff, boards):
    """Una pre-orden y una orden en cada estado, por sucursal."""
    for branch in branches:
        seller = staff[branch.id]["seller"]
        operator = staff[branch.id]["operator"]
        print(f"\n  Sucursal {branch.name}:")

        for i, status in enumerate(PREORDER_STATUSES):
            client = clients[i % len(clients)]
            board = boards[i % len(boards)]
            preorder = seed_preorder(db, status, branch, client, seller, board)
            print(f"    + Pre-orden {preorder.code} [{preorder.status}]")

        for i, status in enumerate(ORDER_STATUSES):
            client = clients[(i + 2) % len(clients)]
            board = boards[i % len(boards)]
            order = seed_order(db, status, branch, client, seller, operator, board)
            print(f"    + Orden {order.code} [{order.status}]")


def reset_demo(db):
    """Borra las pre-órdenes/órdenes demo (``source='seed'``). Pre-órdenes primero
    (referencian a la orden vía ``order_id``)."""
    pres = db.query(PreOrderModel).filter(PreOrderModel.source == SEED_SOURCE).all()
    for p in pres:
        db.delete(p)
    db.flush()
    orders = db.query(OrderModel).filter(OrderModel.source == SEED_SOURCE).all()
    for o in orders:
        db.delete(o)
    db.commit()
    print(f"Reset: borradas {len(pres)} pre-órdenes y {len(orders)} órdenes demo.\n")


def main():
    parser = argparse.ArgumentParser(description="Seed de demostración de Cutter.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Borra las pre-órdenes/órdenes demo previas antes de regenerarlas.",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.reset:
            reset_demo(db)

        print("Sucursales:")
        branches = ensure_branches(db)
        print("Usuarios:")
        staff = ensure_users(db, branches)
        print("Clientes:")
        clients = ensure_clients(db)
        print("Tableros:")
        boards = ensure_boards(db)
        db.commit()

        existing_demo = (
            db.query(PreOrderModel).filter(PreOrderModel.source == SEED_SOURCE).count()
        )
        if existing_demo and not args.reset:
            print(
                f"\nYa existen {existing_demo} pre-órdenes demo; omito la generación "
                "transaccional. Usa --reset para regenerarlas."
            )
        else:
            print("\nPre-órdenes y órdenes (una por estado, por sucursal):")
            seed_transactional(db, branches, clients, staff, boards)
            db.commit()

        print("\n✅ Seed completado.")
        print("   Usuarios: admin@empresa.com + vendedor/operador por sucursal")
        print(f"   Contraseña de todos los usuarios: {SEED_PASSWORD}")
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
