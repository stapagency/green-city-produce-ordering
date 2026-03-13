from __future__ import annotations

import json
import os
import secrets
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from mimetypes import guess_type
from pathlib import Path
from urllib.parse import parse_qs, urlparse


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"
ORDERS_DIR = DATA_DIR / "orders"
PRINTED_DIR = DATA_DIR / "printed"
DRAFTS_DIR = DATA_DIR / "drafts"
CATALOG_PATH = DATA_DIR / "catalog.json"
USERS_PATH = DATA_DIR / "users.json"
SETTINGS_PATH = DATA_DIR / "settings.json"
SESSIONS: dict[str, dict] = {}


def ensure_storage() -> None:
    ORDERS_DIR.mkdir(parents=True, exist_ok=True)
    PRINTED_DIR.mkdir(parents=True, exist_ok=True)
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    if not SETTINGS_PATH.exists():
        save_settings(
            {
                "contact_phone": "(xxx) xxx-xxxx",
                "contact_message": "Questions about availability, delivery timing, or weekly pricing can be confirmed with the office after your order is placed.",
            }
        )


def load_settings() -> dict:
    with SETTINGS_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_settings(settings: dict) -> None:
    with SETTINGS_PATH.open("w", encoding="utf-8") as file:
        json.dump(settings, file, indent=2)


def load_catalog() -> list[dict]:
    with CATALOG_PATH.open("r", encoding="utf-8") as file:
        catalog = json.load(file)
    catalog.sort(key=lambda section: section["category"].lower())
    for section in catalog:
        section["items"].sort(key=lambda item: item["name"].lower())
        for item in section["items"]:
            if item.get("children"):
                item["children"].sort(key=lambda child: child["name"].lower())
    return catalog


def load_users() -> list[dict]:
    with USERS_PATH.open("r", encoding="utf-8") as file:
        users = json.load(file)
    changed = False
    for user in users:
        if "role" not in user:
            user["role"] = "customer"
            changed = True
        if "status" not in user:
            user["status"] = "approved"
            changed = True
    if changed:
        save_users(users)
    return users


def save_users(users: list[dict]) -> None:
    with USERS_PATH.open("w", encoding="utf-8") as file:
        json.dump(users, file, indent=2)


def get_user(username: str) -> dict | None:
    for user in load_users():
        if user["username"].lower() == username.lower():
            return user
    return None


def create_user(payload: dict) -> tuple[dict | None, str | None]:
    required = [
        "username",
        "password",
        "customer_name",
        "company_name",
        "phone",
        "email",
    ]
    for key in required:
        if not str(payload.get(key, "")).strip():
            return None, "All fields are required."

    username = payload["username"].strip()
    if get_user(username):
        return None, "That username is already in use."

    users = load_users()
    user = {
        "username": username,
        "password": payload["password"].strip(),
        "customer_name": payload["customer_name"].strip(),
        "company_name": payload["company_name"].strip(),
        "phone": payload["phone"].strip(),
        "email": payload["email"].strip(),
        "role": "customer",
        "status": "pending",
    }
    users.append(user)
    users.sort(key=lambda item: item["username"].lower())
    save_users(users)
    return user, None


def update_user(username: str, payload: dict) -> tuple[dict | None, str | None]:
    users = load_users()
    target = None
    for user in users:
        if user["username"].lower() == username.lower():
            target = user
            break
    if not target:
        return None, "Account not found."

    required = ["customer_name", "company_name", "phone", "email"]
    for key in required:
        if not str(payload.get(key, "")).strip():
            return None, "All profile fields are required."

    target["customer_name"] = payload["customer_name"].strip()
    target["company_name"] = payload["company_name"].strip()
    target["phone"] = payload["phone"].strip()
    target["email"] = payload["email"].strip()
    save_users(users)
    return target, None


def set_user_status(username: str, status: str) -> tuple[dict | None, str | None]:
    users = load_users()
    for user in users:
        if user["username"].lower() == username.lower():
            user["status"] = status
            save_users(users)
            return user, None
    return None, "Account not found."


def load_order(order_id: str) -> dict | None:
    path = ORDERS_DIR / f"{order_id}.json"
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def draft_path_for_user(user: dict) -> Path:
    return DRAFTS_DIR / f"{user['username'].lower()}.json"


def load_draft(user: dict) -> dict | None:
    path = draft_path_for_user(user)
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_draft(user: dict, draft: dict) -> None:
    path = draft_path_for_user(user)
    with path.open("w", encoding="utf-8") as file:
        json.dump(draft, file, indent=2)


def delete_draft(user: dict) -> None:
    path = draft_path_for_user(user)
    if path.exists():
        path.unlink()


def save_order(order: dict) -> None:
    path = ORDERS_DIR / f"{order['id']}.json"
    with path.open("w", encoding="utf-8") as file:
        json.dump(order, file, indent=2)


def list_pending_orders() -> list[dict]:
    pending = []
    for path in sorted(ORDERS_DIR.glob("*.json")):
        with path.open("r", encoding="utf-8") as file:
            order = json.load(file)
        if order["status"] == "pending_print":
            pending.append(order)
    pending.sort(key=lambda item: item["created_at"])
    return pending


def list_orders_for_user(user: dict) -> list[dict]:
    orders = []
    username = user["username"].strip().lower()
    email = user["email"].strip().lower()
    company_name = user["company_name"].strip().lower()
    customer_name = user["customer_name"].strip().lower()
    for path in sorted(ORDERS_DIR.glob("*.json")):
        with path.open("r", encoding="utf-8") as file:
            order = json.load(file)
        order_username = str(order.get("username", "")).strip().lower()
        order_email = str(order.get("email", "")).strip().lower()
        order_company = str(order.get("company_name", "")).strip().lower()
        order_customer = str(order.get("customer_name", "")).strip().lower()
        if order_username == username or (
            order_email == email
            and order_company == company_name
            and order_customer == customer_name
        ):
            orders.append(order)
    orders.sort(key=lambda item: item["created_at"], reverse=True)
    return orders


def mark_printed(order_id: str) -> dict | None:
    order = load_order(order_id)
    if not order:
        return None
    order["status"] = "printed"
    order["printed_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    save_order(order)
    printed_path = PRINTED_DIR / f"{order_id}.txt"
    printed_path.write_text(render_ticket(order), encoding="utf-8")
    return order


def render_index() -> str:
    catalog = load_catalog()
    catalog_json = json.dumps(catalog)
    settings = load_settings()
    template = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    return (
        template.replace("__CATALOG__", catalog_json)
        .replace("__CATEGORY_TABS__", render_category_tabs(catalog))
        .replace("__CATALOG_CARDS__", render_catalog_cards(catalog))
        .replace("__CONTACT_PHONE__", settings["contact_phone"])
        .replace("__CONTACT_MESSAGE__", settings["contact_message"])
    )


def render_login() -> str:
    return (STATIC_DIR / "login.html").read_text(encoding="utf-8")


def render_signup() -> str:
    return (STATIC_DIR / "signup.html").read_text(encoding="utf-8")


def render_account_nav(active: str) -> str:
    links = [
        ("Order", "/portal", "order"),
        ("Dashboard", "/dashboard", "dashboard"),
    ]
    parts = ['<nav class="account-nav">']
    for label, href, key in links:
        class_name = "account-link active" if key == active else "account-link"
        parts.append(f'<a class="{class_name}" href="{href}">{label}</a>')
    parts.append('<button id="logoutButton" class="ghost-button" type="button">Logout</button>')
    parts.append("</nav>")
    return "".join(parts)


def render_admin_nav() -> str:
    return (
        '<nav class="account-nav">'
        '<a class="account-link active" href="/admin">Admin</a>'
        '<button id="logoutButton" class="ghost-button" type="button">Logout</button>'
        "</nav>"
    )


def render_portal(user: dict) -> str:
    catalog = load_catalog()
    catalog_json = json.dumps(catalog)
    settings = load_settings()
    template = (STATIC_DIR / "portal.html").read_text(encoding="utf-8")
    account_summary = f'{user["company_name"]} | {user["customer_name"]}'
    return (
        template.replace("__CATALOG__", catalog_json)
        .replace("__CATEGORY_TABS__", render_category_tabs(catalog))
        .replace("__CATALOG_CARDS__", render_catalog_cards(catalog))
        .replace("__ACCOUNT_SUMMARY__", account_summary)
        .replace("__ACCOUNT_NAV__", render_account_nav("order"))
        .replace("__CONTACT_PHONE__", settings["contact_phone"])
        .replace("__CONTACT_MESSAGE__", settings["contact_message"])
    )


def render_dashboard(user: dict) -> str:
    settings = load_settings()
    template = (STATIC_DIR / "dashboard.html").read_text(encoding="utf-8")
    account_summary = f'{user["company_name"]} | {user["customer_name"]}'
    orders = list_orders_for_user(user)
    return (
        template.replace("__ACCOUNT_SUMMARY__", account_summary)
        .replace("__ACCOUNT_NAV__", render_account_nav("dashboard"))
        .replace("__ACCOUNT_CARD__", render_account_profile(user))
        .replace("__ORDER_HISTORY__", render_order_history(orders))
        .replace("__INVOICES__", render_invoices(orders))
        .replace("__REPORTS__", render_customer_reports(orders))
        .replace("__CONTACT_PHONE__", settings["contact_phone"])
        .replace("__CONTACT_MESSAGE__", settings["contact_message"])
    )


def render_admin() -> str:
    settings = load_settings()
    catalog = load_catalog()
    users = load_users()
    template = (STATIC_DIR / "admin.html").read_text(encoding="utf-8")
    return (
        template.replace("__ADMIN_NAV__", render_admin_nav())
        .replace("__CONTACT_PHONE__", settings["contact_phone"])
        .replace("__CONTACT_MESSAGE__", settings["contact_message"])
        .replace("__PENDING_ACCOUNTS__", render_pending_accounts(users))
        .replace("__CUSTOMER_ACCOUNTS__", render_customer_accounts(users))
        .replace("__PRODUCT_ROWS__", render_admin_catalog(catalog))
    )


def render_admin_customer_detail(user: dict) -> str:
    settings = load_settings()
    template = (STATIC_DIR / "admin-customer.html").read_text(encoding="utf-8")
    orders = list_orders_for_user(user)
    return (
        template.replace("__ADMIN_NAV__", render_admin_nav())
        .replace("__CUSTOMER_NAME__", user["customer_name"])
        .replace("__COMPANY_NAME__", user["company_name"])
        .replace("__CUSTOMER_EMAIL__", user["email"])
        .replace("__CUSTOMER_PHONE__", user["phone"])
        .replace("__ORDER_COUNT__", str(len(orders)))
        .replace("__ORDER_DETAILS__", render_detailed_order_history(orders))
        .replace("__CONTACT_PHONE__", settings["contact_phone"])
        .replace("__CONTACT_MESSAGE__", settings["contact_message"])
    )


def render_admin_order_detail(order: dict) -> str:
    settings = load_settings()
    template = (STATIC_DIR / "admin-order.html").read_text(encoding="utf-8")
    item_lines = []
    for item in order.get("items", []):
        item_lines.append(
            "".join(
                [
                    '<div class="detail-item-row">',
                    f"<strong>{item['quantity']} {item['unit']}</strong>",
                    f"<span>{item['name']}</span>",
                    f"<span>{item.get('notes') or ''}</span>",
                    "</div>",
                ]
            )
        )
    return (
        template.replace("__ADMIN_NAV__", render_admin_nav())
        .replace("__ORDER_ID__", order["id"])
        .replace("__CUSTOMER_NAME__", order.get("customer_name", ""))
        .replace("__COMPANY_NAME__", order.get("company_name", ""))
        .replace("__CUSTOMER_EMAIL__", order.get("email", ""))
        .replace("__CUSTOMER_PHONE__", order.get("phone", ""))
        .replace("__DELIVERY_DATE__", order.get("delivery_date") or "No delivery date")
        .replace("__CREATED_AT__", order.get("created_at", ""))
        .replace("__ORDER_STATUS__", order.get("status") or "saved")
        .replace("__ORDER_NOTES__", order.get("notes") or "-")
        .replace("__ORDER_ITEMS__", "".join(item_lines))
        .replace("__CONTACT_PHONE__", settings["contact_phone"])
        .replace("__CONTACT_MESSAGE__", settings["contact_message"])
    )


def render_category_tabs(catalog: list[dict]) -> str:
    buttons = ['<button class="tab-button active" type="button" data-category="">All items</button>']
    for index, section in enumerate(catalog):
        buttons.append(
            f'<button class="tab-button" type="button" data-category="{section["category"]}">{section["category"]}</button>'
        )
    return "".join(buttons)


def render_catalog_cards(catalog: list[dict]) -> str:
    cards = []
    for section in catalog:
        for item in section["items"]:
            if item.get("children"):
                cards.append(
                    f'<div class="item-group-header" data-category="{section["category"]}">{item["name"]}</div>'
                )
                for child in item["children"]:
                    cards.append(render_item_card(section["category"], child, is_child=True))
            else:
                cards.append(render_item_card(section["category"], item))
    return "".join(cards)


def render_item_card(category: str, item: dict, is_child: bool = False) -> str:
    options = "".join(f'<option value="{unit}">{unit}</option>' for unit in item["units"])
    details = item.get("details") or "&nbsp;"
    child_class = " child-card" if is_child else ""
    return "".join(
        [
            f'<article class="item-card{child_class}" '
            f'data-category="{category}" '
            f'data-name="{item["name"].lower()}" '
            f'data-details="{item.get("details", "").lower()}">',
            "<div>",
            f"<h3>{item['name']}</h3>",
            f'<p class="item-details">{details}</p>',
            "</div>",
            '<div class="item-controls">',
            f'<input type="number" min="1" value="1" aria-label="Quantity for {item["name"]}">',
            f'<select aria-label="Unit for {item["name"]}">{options}</select>',
            "</div>",
            f'<button class="add-button" type="button" data-item-name="{item["name"]}" data-item-details="{item.get("details", "")}">Add</button>',
            "</article>",
        ]
    )


def render_ticket(order: dict) -> str:
    lines = [
        "WAREHOUSE ORDER TICKET",
        "=" * 72,
        f"Order ID: {order['id']}",
        f"Placed: {order['created_at']}",
        f"Customer: {order['customer_name']}",
        f"Company: {order['company_name'] or '-'}",
        f"Delivery Date: {order['delivery_date'] or '-'}",
        f"Phone: {order['phone'] or '-'}",
        f"Email: {order['email'] or '-'}",
        "-" * 72,
        "ITEMS",
        "-" * 72,
    ]
    for item in order["items"]:
        lines.append(
            f"{str(item['quantity']).rjust(4)}  {item['unit'].ljust(3)}  {item['name']}"
        )
        if item.get("notes"):
            lines.append(f"      note: {item['notes']}")
    lines.extend(
        [
            "-" * 72,
            "ORDER NOTES",
            order["notes"] or "-",
            "",
            "Pricing is assigned later and invoiced on delivery.",
        ]
    )
    return "\n".join(lines) + "\n"


def render_order_history(orders: list[dict]) -> str:
    if not orders:
        return "<p>No past orders yet.</p>"

    rows = []
    for order in orders:
        item_summary = []
        for item in order.get("items", [])[:3]:
            item_summary.append(
                f"{item['quantity']} {item['unit']} {item['name']}"
            )
        if len(order.get("items", [])) > 3:
            item_summary.append(f"+{len(order['items']) - 3} more")
        rows.append(
            "".join(
                [
                    '<article class="history-row">',
                    '<div class="history-meta">',
                    f"<strong>Order {order['id']}</strong>",
                    f"<span>{order.get('delivery_date') or 'No delivery date'}</span>",
                    f"<span>{order['created_at']}</span>",
                    "</div>",
                    '<div class="history-summary">',
                    f"<span>{len(order.get('items', []))} items</span>",
                    f"<span>{order.get('status') or 'saved'}</span>",
                    "</div>",
                    f'<p class="history-items">{" | ".join(item_summary)}</p>',
                    "</article>",
                ]
            )
        )
    return "".join(rows)


def render_detailed_order_history(orders: list[dict]) -> str:
    if not orders:
        return "<p>No orders yet for this customer.</p>"

    rows = []
    for order in orders:
        item_lines = []
        for item in order.get("items", []):
            item_lines.append(
                "".join(
                    [
                        '<div class="detail-item-row">',
                        f"<strong>{item['quantity']} {item['unit']}</strong>",
                        f"<span>{item['name']}</span>",
                        f"<span>{item.get('notes') or ''}</span>",
                        "</div>",
                    ]
                )
            )
        rows.append(
            "".join(
                [
                    '<article class="history-row detail-order-row">',
                    '<div class="history-meta">',
                    f"<strong>Order {order['id']}</strong>",
                    f"<span>{order.get('delivery_date') or 'No delivery date'}</span>",
                    f"<span>{order['created_at']}</span>",
                    "</div>",
                    '<div class="history-summary">',
                    f"<span>{order.get('status') or 'saved'}</span>",
                    f"<span>{len(order.get('items', []))} items</span>",
                    "</div>",
                    f'<p class="history-items">{order.get("notes") or "No order notes."}</p>',
                    f'<div class="admin-actions"><a class="account-link detail-link" href="/admin/order?id={order["id"]}">View order</a></div>',
                    "</article>",
                ]
            )
        )
    return "".join(rows)


def render_pending_accounts(users: list[dict]) -> str:
    pending = [user for user in users if user.get("role") == "customer" and user.get("status") != "approved"]
    if not pending:
        return "<p>No accounts waiting for approval.</p>"
    rows = []
    for user in pending:
        rows.append(
            "".join(
                [
                    '<article class="history-row admin-row">',
                    '<div class="history-meta">',
                    f"<strong>{user['customer_name']}</strong>",
                    f"<span>{user['company_name']}</span>",
                    f"<span>{user['username']}</span>",
                    "</div>",
                    '<div class="history-summary">',
                    f"<span>{user['email']}</span>",
                    f"<span>{user['phone']}</span>",
                    "</div>",
                    f'<div class="admin-actions"><button class="submit-button small-button approve-account" data-username="{user["username"]}" type="button">Approve</button></div>',
                    "</article>",
                ]
            )
        )
    return "".join(rows)


def render_admin_catalog(catalog: list[dict]) -> str:
    rows = []
    for section in catalog:
        rows.append(f'<div class="item-group-header admin-group">{section["category"]}</div>')
        for item in section["items"]:
            if item.get("children"):
                rows.append(
                    "".join(
                        [
                            '<article class="history-row admin-row">',
                            f"<strong>{item['name']}</strong>",
                            f'<div class="admin-actions"><button class="ghost-button remove-product" data-category="{section["category"]}" data-item="{item["name"]}" data-parent="" type="button">Remove group</button></div>',
                            "</article>",
                        ]
                    )
                )
                for child in item["children"]:
                    rows.append(
                        "".join(
                            [
                                '<article class="history-row admin-row child-admin-row">',
                                f"<span>{child['name']}</span>",
                                f"<span>{', '.join(child['units'])}</span>",
                                f'<div class="admin-actions"><button class="ghost-button remove-product" data-category="{section["category"]}" data-item="{child["name"]}" data-parent="{item["name"]}" type="button">Remove</button></div>',
                                "</article>",
                            ]
                        )
                    )
            else:
                rows.append(
                    "".join(
                        [
                            '<article class="history-row admin-row">',
                            f"<strong>{item['name']}</strong>",
                            f"<span>{', '.join(item['units'])}</span>",
                            f'<div class="admin-actions"><button class="ghost-button remove-product" data-category="{section["category"]}" data-item="{item["name"]}" data-parent="" type="button">Remove</button></div>',
                            "</article>",
                        ]
                    )
                )
    return "".join(rows)


def render_customer_accounts(users: list[dict]) -> str:
    customers = [
        user for user in users
        if user.get("role") == "customer"
    ]
    if not customers:
        return "<p>No customer accounts found.</p>"

    rows = []
    for user in customers:
        orders = list_orders_for_user(user)
        order_preview = []
        for order in orders[:3]:
            order_preview.append(
                f"Order {order['id']} | {order.get('delivery_date') or 'No delivery date'} | {len(order.get('items', []))} items"
            )
        if len(orders) > 3:
            order_preview.append(f"+{len(orders) - 3} more orders")
        if not order_preview:
            order_preview.append("No orders yet.")
        rows.append(
            "".join(
                [
                    '<article class="history-row admin-row">',
                    '<div class="history-meta">',
                    f"<strong>{user['customer_name']}</strong>",
                    f"<span>{user['company_name']}</span>",
                    f"<span>{user['status']}</span>",
                    "</div>",
                    '<div class="history-summary">',
                    f"<span>{user['email']}</span>",
                    f"<span>{user['phone']}</span>",
                    f"<span>{len(orders)} orders</span>",
                    "</div>",
                    f'<p class="history-items">{" | ".join(order_preview)}</p>',
                    f'<div class="admin-actions"><a class="account-link detail-link" href="/admin/customer?username={user["username"]}">View details</a></div>',
                    "</article>",
                ]
            )
        )
    return "".join(rows)


def render_account_profile(user: dict) -> str:
    return "".join(
        [
            '<div class="profile-grid">',
            f'<label>Customer name<input name="customer_name" value="{user["customer_name"]}"></label>',
            f'<label>Company<input name="company_name" value="{user["company_name"]}"></label>',
            f'<label>Phone<input name="phone" value="{user["phone"]}"></label>',
            f'<label>Email<input name="email" type="email" value="{user["email"]}"></label>',
            "</div>",
        ]
    )


def render_invoices(orders: list[dict]) -> str:
    if not orders:
        return "<p>No invoices yet.</p>"
    rows = []
    for order in orders:
        invoice_status = "Pending delivery invoice"
        if order.get("status") == "printed":
            invoice_status = "Prepared for invoice"
        rows.append(
            "".join(
                [
                    '<article class="history-row invoice-row">',
                    '<div class="history-meta">',
                    f"<strong>Invoice for Order {order['id']}</strong>",
                    f"<span>{order.get('delivery_date') or 'No delivery date'}</span>",
                    "</div>",
                    '<div class="history-summary">',
                    f"<span>{invoice_status}</span>",
                    f"<span>{len(order.get('items', []))} items</span>",
                    "</div>",
                    '<p class="history-items">Invoice is issued on delivery. This dashboard keeps the order record tied to that invoice.</p>',
                    "</article>",
                ]
            )
        )
    return "".join(rows)


def render_customer_reports(orders: list[dict]) -> str:
    if not orders:
        return "<p>No report data yet.</p>"

    total_orders = len(orders)
    total_items = sum(len(order.get("items", [])) for order in orders)
    average_items = total_items / total_orders if total_orders else 0
    last_order = orders[0].get("created_at", "")

    item_names: dict[str, int] = {}
    units: dict[str, int] = {}
    for order in orders:
        for item in order.get("items", []):
            item_names[item["name"]] = item_names.get(item["name"], 0) + 1
            units[item["unit"]] = units.get(item["unit"], 0) + int(item.get("quantity", 0))

    top_item = max(item_names.items(), key=lambda pair: pair[1])[0] if item_names else "-"
    top_unit = max(units.items(), key=lambda pair: pair[1])[0] if units else "-"

    cards = [
        ("Total orders", str(total_orders)),
        ("Average items / order", f"{average_items:.1f}"),
        ("Most ordered item", top_item),
        ("Most used unit", top_unit),
        ("Last order placed", last_order or "-"),
    ]
    return "".join(
        [
            "".join(
                [
                    '<article class="report-card">',
                    f'<p class="section-kicker">{label}</p>',
                    f'<p class="report-value">{value}</p>',
                    "</article>",
                ]
            )
            for label, value in cards
        ]
    )


def add_catalog_item(payload: dict) -> str | None:
    category_name = str(payload.get("category", "")).strip()
    item_name = str(payload.get("item_name", "")).strip()
    parent_name = str(payload.get("parent_name", "")).strip()
    details = str(payload.get("details", "")).strip()
    units = [unit.strip().upper() for unit in str(payload.get("units", "")).split(",") if unit.strip()]
    if not category_name or not item_name or not units:
        return "Category, item name, and units are required."

    catalog = load_catalog()
    target_section = None
    for section in catalog:
        if section["category"].lower() == category_name.lower():
            target_section = section
            break
    if not target_section:
        target_section = {"category": category_name, "items": []}
        catalog.append(target_section)

    if parent_name:
        parent = None
        for item in target_section["items"]:
            if item["name"].lower() == parent_name.lower():
                parent = item
                break
        if not parent:
            parent = {"name": parent_name, "children": []}
            target_section["items"].append(parent)
        if not parent.get("children"):
            parent["children"] = []
        parent["children"].append({"name": item_name, "details": details, "units": units})
    else:
        target_section["items"].append({"name": item_name, "details": details, "units": units})

    save_catalog(catalog)
    return None


def remove_catalog_item(payload: dict) -> str | None:
    category_name = str(payload.get("category", "")).strip().lower()
    item_name = str(payload.get("item_name", "")).strip().lower()
    parent_name = str(payload.get("parent_name", "")).strip().lower()
    catalog = load_catalog()

    for section in catalog:
        if section["category"].lower() != category_name:
            continue
        if parent_name:
            for item in section["items"]:
                if item["name"].lower() == parent_name and item.get("children"):
                    item["children"] = [child for child in item["children"] if child["name"].lower() != item_name]
                    if not item["children"]:
                        section["items"] = [entry for entry in section["items"] if entry["name"].lower() != parent_name]
                    save_catalog(catalog)
                    return None
        else:
            section["items"] = [item for item in section["items"] if item["name"].lower() != item_name]
            save_catalog(catalog)
            return None
    return "Product not found."


def save_catalog(catalog: list[dict]) -> None:
    with CATALOG_PATH.open("w", encoding="utf-8") as file:
        json.dump(catalog, file, indent=2)


class AppHandler(BaseHTTPRequestHandler):
    server_version = "ProduceOrderServer/1.0"

    def _send_json(
        self,
        payload: dict | list,
        status: int = 200,
        extra_headers: list[tuple[str, str]] | None = None,
    ) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if extra_headers:
            for key, value in extra_headers:
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, text: str, content_type: str = "text/plain; charset=utf-8") -> None:
        body = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, content_type: str) -> None:
        if not path.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _cookie_value(self, key: str) -> str | None:
        cookie_header = self.headers.get("Cookie", "")
        for chunk in cookie_header.split(";"):
            if "=" not in chunk:
                continue
            name, value = chunk.strip().split("=", 1)
            if name == key:
                return value
        return None

    def _current_user(self) -> dict | None:
        session_id = self._cookie_value("session_id")
        if not session_id:
            return None
        session = SESSIONS.get(session_id)
        if not session:
            return None
        return get_user(session["username"])

    def _current_admin(self) -> dict | None:
        user = self._current_user()
        if not user or user.get("role") != "admin":
            return None
        return user

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        route = parsed.path

        if route == "/":
            self._send_text(render_index(), "text/html; charset=utf-8")
            return
        if route == "/login":
            self._send_text(render_login(), "text/html; charset=utf-8")
            return
        if route == "/signup":
            self._send_text(render_signup(), "text/html; charset=utf-8")
            return
        if route == "/portal":
            user = self._current_user()
            if not user or user.get("role") != "customer" or user.get("status") != "approved":
                self.send_response(302)
                self.send_header("Location", "/login")
                self.end_headers()
                return
            self._send_text(render_portal(user), "text/html; charset=utf-8")
            return
        if route == "/dashboard":
            user = self._current_user()
            if not user or user.get("role") != "customer" or user.get("status") != "approved":
                self.send_response(302)
                self.send_header("Location", "/login")
                self.end_headers()
                return
            self._send_text(render_dashboard(user), "text/html; charset=utf-8")
            return
        if route == "/admin":
            if not self._current_admin():
                self.send_response(302)
                self.send_header("Location", "/login")
                self.end_headers()
                return
            self._send_text(render_admin(), "text/html; charset=utf-8")
            return
        if route == "/admin/customer":
            if not self._current_admin():
                self.send_response(302)
                self.send_header("Location", "/login")
                self.end_headers()
                return
            username = parse_qs(parsed.query).get("username", [""])[0]
            user = get_user(username)
            if not user or user.get("role") != "customer":
                self.send_error(HTTPStatus.NOT_FOUND, "Customer not found")
                return
            self._send_text(render_admin_customer_detail(user), "text/html; charset=utf-8")
            return
        if route == "/admin/order":
            if not self._current_admin():
                self.send_response(302)
                self.send_header("Location", "/login")
                self.end_headers()
                return
            order_id = parse_qs(parsed.query).get("id", [""])[0]
            order = load_order(order_id)
            if not order:
                self.send_error(HTTPStatus.NOT_FOUND, "Order not found")
                return
            self._send_text(render_admin_order_detail(order), "text/html; charset=utf-8")
            return
        if route == "/static/style.css":
            self._send_file(STATIC_DIR / "style.css", "text/css; charset=utf-8")
            return
        if route == "/static/app.js":
            self._send_file(STATIC_DIR / "app.js", "application/javascript; charset=utf-8")
            return
        if route == "/static/login.js":
            self._send_file(STATIC_DIR / "login.js", "application/javascript; charset=utf-8")
            return
        if route == "/static/signup.js":
            self._send_file(STATIC_DIR / "signup.js", "application/javascript; charset=utf-8")
            return
        if route == "/static/portal.js":
            self._send_file(STATIC_DIR / "portal.js", "application/javascript; charset=utf-8")
            return
        if route == "/static/dashboard.js":
            self._send_file(STATIC_DIR / "dashboard.js", "application/javascript; charset=utf-8")
            return
        if route == "/static/admin.js":
            self._send_file(STATIC_DIR / "admin.js", "application/javascript; charset=utf-8")
            return
        if route == "/static/admin-customer.js":
            self._send_file(STATIC_DIR / "admin-customer.js", "application/javascript; charset=utf-8")
            return
        if route == "/static/admin-order.js":
            self._send_file(STATIC_DIR / "admin-order.js", "application/javascript; charset=utf-8")
            return
        if route.startswith("/static/"):
            relative_path = route.removeprefix("/static/")
            file_path = (STATIC_DIR / relative_path).resolve()
            if STATIC_DIR.resolve() not in file_path.parents and file_path != STATIC_DIR.resolve():
                self.send_error(HTTPStatus.NOT_FOUND, "Not found")
                return
            content_type = guess_type(str(file_path))[0] or "application/octet-stream"
            self._send_file(file_path, content_type)
            return
        if route == "/api/catalog":
            self._send_json(load_catalog())
            return
        if route == "/api/me":
            user = self._current_user()
            if not user:
                self._send_json({"user": None}, status=401)
                return
            self._send_json(
                {
                    "user": {
                        "customer_name": user["customer_name"],
                        "company_name": user["company_name"],
                        "phone": user["phone"],
                        "email": user["email"],
                        "username": user["username"],
                        "role": user.get("role", "customer"),
                        "status": user.get("status", "approved"),
                    }
                }
            )
            return
        if route == "/api/admin/pending-users":
            if not self._current_admin():
                self._send_json({"users": []}, status=401)
                return
            pending = [
                user for user in load_users()
                if user.get("role") == "customer" and user.get("status") != "approved"
            ]
            self._send_json({"users": pending})
            return
        if route == "/api/admin/catalog":
            if not self._current_admin():
                self._send_json({"catalog": []}, status=401)
                return
            self._send_json({"catalog": load_catalog()})
            return
        if route == "/api/admin/customers":
            if not self._current_admin():
                self._send_json({"customers": []}, status=401)
                return
            customers = []
            for user in load_users():
                if user.get("role") != "customer":
                    continue
                customers.append(
                    {
                        "username": user["username"],
                        "customer_name": user["customer_name"],
                        "company_name": user["company_name"],
                        "phone": user["phone"],
                        "email": user["email"],
                        "status": user.get("status", "approved"),
                        "orders": [
                            {
                                "id": order["id"],
                                "delivery_date": order.get("delivery_date", ""),
                                "status": order.get("status", ""),
                                "item_count": len(order.get("items", [])),
                            }
                            for order in list_orders_for_user(user)
                        ],
                    }
                )
            self._send_json({"customers": customers})
            return
        if route == "/api/admin/settings":
            if not self._current_admin():
                self._send_json({"settings": {}}, status=401)
                return
            self._send_json({"settings": load_settings()})
            return
        if route == "/api/account/orders":
            user = self._current_user()
            if not user:
                self._send_json({"orders": []}, status=401)
                return
            orders = [
                {
                    "id": order["id"],
                    "created_at": order["created_at"],
                    "delivery_date": order.get("delivery_date", ""),
                    "status": order.get("status", ""),
                    "item_count": len(order.get("items", [])),
                    "items": order.get("items", []),
                }
                for order in list_orders_for_user(user)
            ]
            self._send_json({"orders": orders})
            return
        if route == "/api/account/draft":
            user = self._current_user()
            if not user:
                self._send_json({"draft": None}, status=401)
                return
            self._send_json({"draft": load_draft(user)})
            return
        if route == "/api/account/invoices":
            user = self._current_user()
            if not user:
                self._send_json({"invoices": []}, status=401)
                return
            invoices = [
                {
                    "order_id": order["id"],
                    "delivery_date": order.get("delivery_date", ""),
                    "status": "Prepared for invoice" if order.get("status") == "printed" else "Pending delivery invoice",
                    "item_count": len(order.get("items", [])),
                }
                for order in list_orders_for_user(user)
            ]
            self._send_json({"invoices": invoices})
            return
        if route == "/api/account/reports":
            user = self._current_user()
            if not user:
                self._send_json({"html": ""}, status=401)
                return
            self._send_json({"html": render_customer_reports(list_orders_for_user(user))})
            return
        if route == "/api/orders":
            pending = [
                {
                    "id": order["id"],
                    "customer_name": order["customer_name"],
                    "company_name": order["company_name"],
                    "delivery_date": order["delivery_date"],
                    "created_at": order["created_at"],
                    "status": order["status"],
                    "item_count": len(order["items"]),
                }
                for order in list_pending_orders()
            ]
            self._send_json(pending)
            return
        if route == "/api/print/next":
            pending = list_pending_orders()
            if not pending:
                self._send_json({"order": None})
                return
            order = pending[0]
            self._send_json(
                {
                    "order": {
                        "id": order["id"],
                        "ticket": render_ticket(order),
                        "created_at": order["created_at"],
                    }
                }
            )
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        route = parsed.path
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length)
        body = json.loads(raw_body.decode("utf-8") or "{}")

        if route == "/api/login":
            user = get_user(body.get("username", ""))
            if not user or user["password"] != body.get("password", ""):
                self._send_json({"error": "Invalid username or password."}, status=401)
                return
            if user.get("role") == "customer" and user.get("status") != "approved":
                self._send_json({"error": "Your account is waiting for approval."}, status=403)
                return
            session_id = secrets.token_urlsafe(24)
            SESSIONS[session_id] = {"username": user["username"]}
            self._send_json(
                {"ok": True},
                extra_headers=[("Set-Cookie", f"session_id={session_id}; Path=/; HttpOnly; SameSite=Lax")],
            )
            return

        if route == "/api/signup":
            user, error = create_user(body)
            if error:
                self._send_json({"error": error}, status=400)
                return
            self._send_json({"ok": True, "message": "Account created. It must be approved before login."}, status=201)
            return

        if route == "/api/logout":
            session_id = self._cookie_value("session_id")
            if session_id:
                SESSIONS.pop(session_id, None)
            self._send_json(
                {"ok": True},
                extra_headers=[("Set-Cookie", "session_id=deleted; Path=/; Max-Age=0; HttpOnly; SameSite=Lax")],
            )
            return

        if route == "/api/account/profile":
            user = self._current_user()
            if not user or user.get("role") != "customer":
                self._send_json({"error": "Unauthorized."}, status=401)
                return
            updated_user, error = update_user(user["username"], body)
            if error:
                self._send_json({"error": error}, status=400)
                return
            self._send_json({"ok": True, "user": updated_user})
            return

        if route == "/api/admin/approve-user":
            if not self._current_admin():
                self._send_json({"error": "Unauthorized."}, status=401)
                return
            user, error = set_user_status(body.get("username", ""), "approved")
            if error:
                self._send_json({"error": error}, status=404)
                return
            self._send_json({"ok": True, "user": user})
            return

        if route == "/api/admin/settings":
            if not self._current_admin():
                self._send_json({"error": "Unauthorized."}, status=401)
                return
            phone = str(body.get("contact_phone", "")).strip()
            message = str(body.get("contact_message", "")).strip()
            if not phone or not message:
                self._send_json({"error": "Phone and message are required."}, status=400)
                return
            settings = {"contact_phone": phone, "contact_message": message}
            save_settings(settings)
            self._send_json({"ok": True, "settings": settings})
            return

        if route == "/api/admin/catalog/add":
            if not self._current_admin():
                self._send_json({"error": "Unauthorized."}, status=401)
                return
            error = add_catalog_item(body)
            if error:
                self._send_json({"error": error}, status=400)
                return
            self._send_json({"ok": True})
            return

        if route == "/api/admin/catalog/remove":
            if not self._current_admin():
                self._send_json({"error": "Unauthorized."}, status=401)
                return
            error = remove_catalog_item(body)
            if error:
                self._send_json({"error": error}, status=404)
                return
            self._send_json({"ok": True})
            return

        if route == "/api/orders":
            items = body.get("items", [])
            if not body.get("customer_name") or not items:
                self._send_json(
                    {"error": "Customer name and at least one item are required."},
                    status=400,
                )
                return

            order_id = datetime.utcnow().strftime("%Y%m%d%H%M%S")
            order = {
                "id": order_id,
                "customer_name": body["customer_name"].strip(),
                "company_name": body.get("company_name", "").strip(),
                "delivery_date": body.get("delivery_date", "").strip(),
                "phone": body.get("phone", "").strip(),
                "email": body.get("email", "").strip(),
                "notes": body.get("notes", "").strip(),
                "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                "status": "pending_print",
                "items": items,
            }
            save_order(order)
            self._send_json({"ok": True, "order_id": order_id}, status=201)
            return

        if route == "/api/account/orders":
            user = self._current_user()
            items = body.get("items", [])
            if not user:
                self._send_json({"error": "Unauthorized."}, status=401)
                return
            if not items:
                self._send_json({"error": "At least one item is required."}, status=400)
                return

            order_id = datetime.utcnow().strftime("%Y%m%d%H%M%S")
            order = {
                "id": order_id,
                "username": user["username"],
                "customer_name": user["customer_name"],
                "company_name": user["company_name"],
                "delivery_date": body.get("delivery_date", "").strip(),
                "phone": user["phone"],
                "email": user["email"],
                "notes": body.get("notes", "").strip(),
                "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                "status": "pending_print",
                "items": items,
            }
            save_order(order)
            delete_draft(user)
            self._send_json({"ok": True, "order_id": order_id}, status=201)
            return

        if route == "/api/account/draft":
            user = self._current_user()
            if not user:
                self._send_json({"error": "Unauthorized."}, status=401)
                return
            items = body.get("items", [])
            if not items:
                self._send_json({"error": "Add at least one item before saving for later."}, status=400)
                return
            draft = {
                "delivery_date": body.get("delivery_date", "").strip(),
                "notes": body.get("notes", "").strip(),
                "items": items,
                "saved_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            }
            save_draft(user, draft)
            self._send_json({"ok": True})
            return

        if route == "/api/account/draft/delete":
            user = self._current_user()
            if not user:
                self._send_json({"error": "Unauthorized."}, status=401)
                return
            delete_draft(user)
            self._send_json({"ok": True})
            return

        if route == "/api/print/ack":
            order_id = body.get("order_id", "")
            order = mark_printed(order_id)
            if not order:
                self._send_json({"error": "Order not found."}, status=404)
                return
            self._send_json({"ok": True, "order_id": order_id})
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not found")


def main() -> None:
    ensure_storage()
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), AppHandler)
    print(f"Serving on http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
