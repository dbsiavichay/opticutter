"""Demo seed: branches, users, clients, pre-orders and orders.

Generates a complete, realistic dataset to populate the dashboard / do QA:

- **Branches**: taken from ``COMPANY_BRANCHES`` in the environment (.env): Sucúa and Macas.
- **Users**: 1 global admin + 1 seller, 1 operator and 1 bander per branch
  (``admin@empresa.com``, ``vendedor<slug>@empresa.com``, ``operador<slug>@empresa.com``,
  ``canteador<slug>@empresa.com``).
- **Clients**: 5, all with a phone number (required to issue a proforma/order).
- **Boards and edge bandings**: reuses the catalog if present; otherwise creates
  coordinated demo boards + edge bandings (optimizer input + banding track).
- **Pre-orders**: one in EVERY status per branch (draft, sent, changes_requested,
  confirmed, rejected, expired, cancelled), walking the real flow (review link
  + client actions) where applicable.
- **Orders**: one in EVERY status per branch (confirmed, queued, cutting,
  cut, completed, cancelled), advancing the state machine with the correct
  actors and roles (the operator self-assigns on ``cutting``, all pieces are
  marked cut before closing the cut, etc.). Workshop orders
  (cutting/cut/completed) include edge banding and demonstrate the banding
  track with each branch's bander.

Idempotent for the foundations (branches/users/clients/boards: get-or-create).
Pre-orders/orders are only generated if no demo data exists yet (flagged with
``source="seed"``); use ``--reset`` to delete and regenerate them.

Requires the schema to already exist (migrations applied). Examples:

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

# Load .env BEFORE importing config (environs doesn't read it on its own). This way
# branches (COMPANY_BRANCHES) and other settings come from .env. ``override=False``:
# a variable already present in the environment (e.g. DATABASE_URL passed by the
# make target pointing at the local Postgres) wins over the one in the file.
from environs import Env  # noqa: E402

Env().read_env(os.path.join(os.path.dirname(__file__), "..", ".env"), recurse=False)

from datetime import datetime, timedelta  # noqa: E402

from src.modules.branches.model import BranchModel  # noqa: E402
from src.modules.clients.model import ClientModel  # noqa: E402
from src.modules.orders.model import (  # noqa: E402
    BandingStatus,
    OrderModel,
    OrderStatus,
)
from src.modules.orders.schemas import OrderCreate, OrderPaymentInput  # noqa: E402
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

# Single password for all seeded users (override with SEED_PASSWORD).
SEED_PASSWORD = os.getenv("SEED_PASSWORD") or config.ADMIN_PASSWORD or "Cutter2026!"

# Origin marker to identify (and be able to reset) the demo transactional data.
SEED_SOURCE = "seed"

# 5 clients: (identifier, first name, last name, phone, email).
CLIENTS = [
    ("0102030405", "María", "González", "0991111111", "maria.gonzalez@example.com"),
    ("0203040506", "Carlos", "Pérez", "0992222222", "carlos.perez@example.com"),
    ("0304050607", "Lucía", "Vásquez", "0993333333", "lucia.vasquez@example.com"),
    ("0405060708", "Jorge", "Mendoza", "0994444444", None),
    ("0506070809", "Ana", "Torres", "0995555555", "ana.torres@example.com"),
]

# Demo boards (only created if the catalog is empty): (code, name, height, width,
# thickness, price). Large dimensions so the demo cutlists fit comfortably.
DEMO_BOARDS = [
    ("DEMO-MDP-BLN-15", "Tablero Demo Blanco 15mm", 2440, 1830, 15, 48.00),
    ("DEMO-MDP-NGR-15", "Tablero Demo Negro 15mm", 2440, 1830, 15, 52.00),
    ("DEMO-MDP-ROB-18", "Tablero Demo Roble 18mm", 2440, 1830, 18, 64.00),
]

# Demo edge bandings coordinated with the first two boards (TAP-* code + design):
# (code, name, thickness_mm, width_mm, band_type, price_per_m).
DEMO_EDGE_BANDINGS = [
    ("TAP-MDP-BLN-19", "Tapacanto Demo Blanco 19mm", 0.45, 19, "Soft", 0.35),
    ("TAP-MDP-NGR-19", "Tapacanto Demo Negro 19mm", 0.45, 19, "Soft", 0.35),
]

# Statuses to seed per branch.
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
    OrderStatus.queued,
    OrderStatus.cutting,
    OrderStatus.cut,
    OrderStatus.completed,
    OrderStatus.dispatched,
    OrderStatus.cancelled,
]

# Global counter: guarantees a unique optimization hash per entity (via the
# pieces' ``label``), so order dedupe never collapses them.
_seq = itertools.count(1)


def slugify(name: str) -> str:
    """Lowercase ascii slug without accents: 'Sucúa' -> 'sucua', 'Macas' -> 'macas'."""
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_str = nfkd.encode("ascii", "ignore").decode("ascii")
    return "".join(ch for ch in ascii_str.lower() if ch.isalnum())


def make_cutlist(material_key: str) -> list[dict]:
    """Demo cutlist with unique labels (distinct optimization hash)."""
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
    """Materials (1 catalog board) + unique cutlist for an entity."""
    key = "b1"
    materials = [{"key": key, "source": "catalog", "product_id": board.id}]
    return materials, make_cutlist(key)


def make_cutlist_with_banding(material_key: str, edge_band_id: int) -> list[dict]:
    """Cutlist with edge banding on the main pieces."""
    i = next(_seq)
    banding = {"product_id": edge_band_id, "sides": ["top", "bottom", "left", "right"]}
    return [
        {
            "priority": 1,
            "height": 600,
            "width": 400,
            "quantity": 2,
            "material_key": material_key,
            "label": f"Puerta {i}",
            "edge_banding": banding,
        },
        {
            "priority": 0,
            "height": 350,
            "width": 300,
            "quantity": 3,
            "material_key": material_key,
            "label": f"Estante {i}",
            "edge_banding": {"product_id": edge_band_id, "sides": ["top", "bottom"]},
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


def build_inputs_with_banding(
    board: ProductModel, edge_band: ProductModel
) -> tuple[list[dict], list[dict]]:
    """Materials + cutlist with edge banding on some pieces."""
    key = "b1"
    materials = [{"key": key, "source": "catalog", "product_id": board.id}]
    return materials, make_cutlist_with_banding(key, edge_band.id)


# --------------------------------------------------------------------------- #
# Foundations (idempotent)                                                     #
# --------------------------------------------------------------------------- #


def ensure_branches(db) -> list[BranchModel]:
    """Creates/gets the branches from ``COMPANY_BRANCHES`` in the environment."""
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
            print(f"  + Branch {code} ({name})")
        else:
            print(f"  = Branch {code} ({name}) already existed")
        branches.append(branch)
    return branches


def ensure_user(db, email, full_name, role, branch_id) -> UserModel:
    """Creates/gets a user by email."""
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
        print(f"  + User {email} ({role})")
    else:
        print(f"  = User {email} already existed")
    return user


def ensure_users(db, branches) -> dict[int, dict[str, UserModel]]:
    """Global admin + seller, operator and bander per branch. Returns staff per branch."""
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
        bander = ensure_user(
            db,
            f"canteador{slug}@empresa.com",
            f"Canteador {branch.name}",
            UserRole.BANDER.value,
            branch.id,
        )
        staff[branch.id] = {
            "seller": seller,
            "operator": operator,
            "bander": bander,
        }
    return staff


def ensure_clients(db) -> list[ClientModel]:
    """Creates/gets the 5 demo clients (all with a phone number)."""
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
            print(f"  + Client {identifier} ({first} {last})")
        else:
            print(f"  = Client {identifier} already existed")
        clients.append(client)
    return clients


def ensure_boards(db) -> list[ProductModel]:
    """Reuses up to 3 boards from the catalog; if none, creates the demo boards."""
    existing = (
        db.query(ProductModel)
        .filter(ProductModel.type == ProductType.BOARD.value)
        .order_by(ProductModel.id)
        .limit(3)
        .all()
    )
    if existing:
        print(f"  = Using {len(existing)} existing board(s) from the catalog")
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
        print(f"  + Board {code} ({name})")
    db.flush()
    return boards


def ensure_edge_bandings(db) -> list[ProductModel]:
    """Reuses existing demo edge bandings; if none, creates the demo catalog ones."""
    existing = (
        db.query(ProductModel)
        .filter(
            ProductModel.type == ProductType.EDGE_BANDING.value,
            ProductModel.code.in_([c for c, *_ in DEMO_EDGE_BANDINGS]),
        )
        .order_by(ProductModel.id)
        .all()
    )
    if len(existing) == len(DEMO_EDGE_BANDINGS):
        print(f"  = Using {len(existing)} existing demo edge banding(s)")
        return existing

    edge_bands = []
    for code, name, thickness, width, band_type, price in DEMO_EDGE_BANDINGS:
        band = db.query(ProductModel).filter(ProductModel.code == code).first()
        if band is None:
            band = ProductModel(
                type=ProductType.EDGE_BANDING.value,
                code=code,
                name=name,
                description=name,
                price=price,
                is_active=True,
                attributes={
                    "thickness": thickness,
                    "width": width,
                    "bandType": band_type,
                    "color": None,
                    "length": None,
                },
            )
            db.add(band)
            print(f"  + Edge banding {code} ({name})")
        else:
            print(f"  = Edge banding {code} already existed")
        edge_bands.append(band)
    db.flush()
    return edge_bands


# --------------------------------------------------------------------------- #
# Transactional data (pre-orders and orders)                                   #
# --------------------------------------------------------------------------- #


def seed_preorder(db, status, branch, client, seller, board):
    """Creates a pre-order and drives it to the target ``status`` via the real flow."""
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
        branch_scope=None,  # admin route: uses branch_id from the body
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
        # Expire its validity and let the lazy sweep mark it 'expired'.
        preorder.expires_at = datetime.utcnow() - timedelta(days=1)
        db.commit()
        pre_svc.get_or_404(preorder.id)

    elif status == PreOrderStatus.cancelled:
        # There's no cancellation endpoint today; the transition is recorded by hand
        # to have the status represented in the demo.
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
    """Marks all placed pieces as cut (requires 'cutting' status)."""
    order = svc.get_or_404(order_id)
    for board in order.boards:
        for piece in board.pieces:
            svc.mark_piece_cut(order_id, piece.id, cut=True, actor=actor)


def drive_order_to(svc, order, target, seller_actor, operator_actor, bander_actor=None):
    """Advances the order through the state machine up to ``target``.

    If ``bander_actor`` is given, also advances the banding track according to
    the target status: ``cutting`` → in_progress; ``cut``/``completed`` → done.
    """
    has_banding = bander_actor is not None

    if target == OrderStatus.confirmed:
        return
    if target == OrderStatus.cancelled:
        svc.transition(
            order.id, OrderStatus.cancelled, actor=seller_actor, note="Cancelada"
        )
        return

    # confirmed → queued requires a payment method (at least one amount > 0).
    svc.transition(
        order.id,
        OrderStatus.queued,
        actor=seller_actor,
        note="Enviada a la cola de producción",
        payment=OrderPaymentInput(cash_amount=500.00),
    )
    if target == OrderStatus.queued:
        return

    # The operator self-assigns when taking the cut.
    svc.transition(
        order.id,
        OrderStatus.cutting,
        actor=operator_actor,
        note="Operador toma el corte",
    )
    if target == OrderStatus.cutting:
        if has_banding:
            svc.transition_banding(
                order.id, BandingStatus.in_progress, actor=bander_actor
            )
        return

    # To close the cut: mark all pieces and finish banding first.
    _mark_all_pieces_cut(svc, order.id, operator_actor)
    if has_banding:
        svc.transition_banding(order.id, BandingStatus.in_progress, actor=bander_actor)
        svc.transition_banding(order.id, BandingStatus.done, actor=bander_actor)
    svc.transition(
        order.id, OrderStatus.cut, actor=operator_actor, note="Corte finalizado"
    )
    if target == OrderStatus.cut:
        return

    svc.transition(
        order.id, OrderStatus.completed, actor=seller_actor, note="Pedido entregado"
    )
    if target == OrderStatus.completed:
        return

    # completed → despachado: any role can dispatch.
    svc.transition(
        order.id,
        OrderStatus.dispatched,
        actor=seller_actor,
        note="Mercadería entregada",
    )


def seed_order(
    db, status, branch, client, seller, operator, board, bander=None, edge_band=None
):
    """Creates an order and drives it to the target ``status`` via the state machine.

    If ``bander`` and ``edge_band`` are provided, the order includes edge banding
    and the banding track is advanced according to the target status.
    """
    svc = OrderService(db)
    seller_actor = staff_actor(seller)
    operator_actor = staff_actor(operator)
    bander_actor = staff_actor(bander) if bander and edge_band else None

    if bander_actor:
        materials, requirements = build_inputs_with_banding(board, edge_band)
        notes = f"Orden demo con tapacantos en estado {status.value}"
    else:
        materials, requirements = build_inputs(board)
        notes = f"Orden demo en estado {status.value}"

    order = svc.create(
        OrderCreate(
            materials=materials,
            requirements=requirements,
            client_id=client.id,
            branch_id=branch.id,
            source=SEED_SOURCE,
            notes=notes,
        ),
        actor=seller_actor,
    )
    drive_order_to(svc, order, status, seller_actor, operator_actor, bander_actor)
    db.refresh(order)
    return order


def seed_transactional(db, branches, clients, staff, boards, edge_bands):
    """One pre-order and one order in each status, per branch.

    Orders in workshop statuses (cutting/cut/completed) are created with edge
    banding to demonstrate the banding track with the branch's bander.
    """
    # Statuses that must include edge banding to demonstrate the banding flow.
    BANDING_STATUSES = {
        OrderStatus.cutting,
        OrderStatus.cut,
        OrderStatus.completed,
        OrderStatus.dispatched,
    }

    for branch in branches:
        seller = staff[branch.id]["seller"]
        operator = staff[branch.id]["operator"]
        bander = staff[branch.id]["bander"]
        print(f"\n  Branch {branch.name}:")

        for i, status in enumerate(PREORDER_STATUSES):
            client = clients[i % len(clients)]
            board = boards[i % len(boards)]
            preorder = seed_preorder(db, status, branch, client, seller, board)
            print(f"    + Pre-order {preorder.code} [{preorder.status}]")

        for i, status in enumerate(ORDER_STATUSES):
            client = clients[(i + 2) % len(clients)]
            board = boards[i % len(boards)]
            use_banding = status in BANDING_STATUSES and edge_bands
            edge_band = edge_bands[i % len(edge_bands)] if use_banding else None
            order = seed_order(
                db,
                status,
                branch,
                client,
                seller,
                operator,
                board,
                bander=bander if use_banding else None,
                edge_band=edge_band,
            )
            banding_note = f" (canteado: {order.banding_status})" if use_banding else ""
            print(f"    + Order {order.code} [{order.status}]{banding_note}")


def reset_demo(db):
    """Deletes the demo pre-orders/orders (``source='seed'``). Pre-orders first
    (they reference the order via ``order_id``)."""
    pres = db.query(PreOrderModel).filter(PreOrderModel.source == SEED_SOURCE).all()
    for p in pres:
        db.delete(p)
    db.flush()
    orders = db.query(OrderModel).filter(OrderModel.source == SEED_SOURCE).all()
    for o in orders:
        db.delete(o)
    db.commit()
    print(
        f"Reset: deleted {len(pres)} demo pre-orders and {len(orders)} demo orders.\n"
    )


def main():
    parser = argparse.ArgumentParser(description="Cutter demo seed.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete previous demo pre-orders/orders before regenerating them.",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.reset:
            reset_demo(db)

        print("Branches:")
        branches = ensure_branches(db)
        print("Users:")
        staff = ensure_users(db, branches)
        print("Clients:")
        clients = ensure_clients(db)
        print("Boards and edge bandings:")
        boards = ensure_boards(db)
        edge_bands = ensure_edge_bandings(db)
        db.commit()

        existing_demo = (
            db.query(PreOrderModel).filter(PreOrderModel.source == SEED_SOURCE).count()
        )
        if existing_demo and not args.reset:
            print(
                f"\n{existing_demo} demo pre-orders already exist; skipping transactional "
                "generation. Use --reset to regenerate them."
            )
        else:
            print("\nPre-orders and orders (one per status, per branch):")
            seed_transactional(db, branches, clients, staff, boards, edge_bands)
            db.commit()

        print("\n✅ Seed complete.")
        print("   Users: admin@empresa.com + seller/operator/bander per branch")
        print(f"   Password for all users: {SEED_PASSWORD}")
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
