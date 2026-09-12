"""Capability menu (the "+" button's sheet) — stored under app_settings'
`capability_menu` key (ADR 0012: structured, admin-editable, not simple
enough for a raw settings PATCH to be safe, so it gets its own small
CRUD-shaped service on top of the same underlying key).

Route/enabled state lives here in the DB (config, not code) — but which
routes actually exist is still a frontend fact; an admin editing this has to
know that. Icon is a small fixed vocabulary the frontend maps to real SVGs
(the one deliberate exception to "no frontend config" — see CLAUDE.md).
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services import app_settings

_KEY = "capability_menu"

_DEFAULT_ITEMS: list[dict[str, Any]] = [
    {
        "id": "tts",
        "icon": "mic",
        "route": "/app/create/tts",
        "enabled": True,
        "order": 1,
        "badge": None,
        "labels": {
            "en": "Text to Voice",
            "th": "แปลงข้อความเป็นเสียง",
            "id": "Teks ke Suara",
            "es": "Texto a Voz",
        },
        "descriptions": {
            "en": "Convert text to natural speech",
            "th": "แปลงข้อความเป็นเสียงพูดที่เป็นธรรมชาติ",
            "id": "Ubah teks menjadi ucapan alami",
            "es": "Convierte texto en habla natural",
        },
    },
    {
        "id": "voice-clone",
        "icon": "clone",
        "route": "/app/create/clone",
        "enabled": True,
        "order": 2,
        "badge": None,
        "labels": {
            "en": "Clone Your Voice",
            "th": "โคลนเสียงของคุณ",
            "id": "Klon Suara Anda",
            "es": "Clona Tu Voz",
        },
        "descriptions": {
            "en": "Train a voice from a sample, then speak in it",
            "th": "ฝึกเสียงจากตัวอย่าง แล้วพูดด้วยเสียงนั้น",
            "id": "Latih suara dari sampel, lalu bicara dengannya",
            "es": "Entrena una voz a partir de una muestra y habla con ella",
        },
    },
    {
        "id": "dialogue",
        "icon": "message",
        "route": "/app/create/dialogue",
        "enabled": False,
        "order": 3,
        "badge": None,
        "labels": {
            "en": "Text to Dialogue",
            "th": "แปลงข้อความเป็นบทสนทนา",
            "id": "Teks ke Dialog",
            "es": "Texto a Diálogo",
        },
        "descriptions": {
            "en": "Create multi-character dialogues",
            "th": "สร้างบทสนทนาหลายตัวละคร",
            "id": "Buat dialog multi-karakter",
            "es": "Crea diálogos con varios personajes",
        },
    },
    {
        "id": "image",
        "icon": "image",
        "route": "/app/create/image",
        "enabled": False,
        "order": 4,
        "badge": None,
        "labels": {
            "en": "AI Image",
            "th": "สร้างภาพ AI",
            "id": "Gambar AI",
            "es": "Imagen IA",
        },
        "descriptions": {
            "en": "Generate images from text prompts",
            "th": "สร้างภาพจากข้อความที่กำหนด",
            "id": "Hasilkan gambar dari perintah teks",
            "es": "Genera imágenes a partir de descripciones de texto",
        },
    },
    {
        "id": "bg-remove",
        "icon": "wand",
        "route": "/app/create/bg-remove",
        "enabled": False,
        "order": 5,
        "badge": None,
        "labels": {
            "en": "BG Remover & HD Upscaler",
            "th": "ลบพื้นหลัง & เพิ่มความคมชัด",
            "id": "Penghapus BG & Peningkat HD",
            "es": "Eliminar fondo y mejorar a HD",
        },
        "descriptions": {
            "en": "Remove background or upscale images",
            "th": "ลบพื้นหลังหรือเพิ่มความละเอียดภาพ",
            "id": "Hapus latar belakang atau tingkatkan resolusi gambar",
            "es": "Elimina el fondo o mejora la resolución de las imágenes",
        },
    },
    {
        "id": "video-download",
        "icon": "download",
        "route": "/app/create/video-download",
        "enabled": False,
        "order": 6,
        "badge": "popular",
        "labels": {
            "en": "Video Downloader",
            "th": "ดาวน์โหลดวิดีโอ",
            "id": "Pengunduh Video",
            "es": "Descargador de Video",
        },
        "descriptions": {
            "en": "Download YouTube videos",
            "th": "ดาวน์โหลดวิดีโอจาก YouTube",
            "id": "Unduh video YouTube",
            "es": "Descarga videos de YouTube",
        },
    },
]


async def _load(db: AsyncSession) -> list[dict[str, Any]]:
    try:
        return await app_settings.get_setting(db, _KEY)
    except KeyError:
        return _DEFAULT_ITEMS


async def _save(db: AsyncSession, items: list[dict[str, Any]], *, updated_by: str) -> None:
    await app_settings.set_setting(db, _KEY, items, updated_by=updated_by)


async def list_for_client(db: AsyncSession, *, locale: str) -> list[dict[str, Any]]:
    """GET /config/menu — enabled items only, sorted, text resolved to one
    locale (falls back to English). This is the whole point: the frontend
    gets back something it can render with zero lookup of its own."""
    items = await _load(db)
    enabled = sorted((i for i in items if i["enabled"]), key=lambda i: i["order"])
    return [
        {
            "id": i["id"],
            "icon": i["icon"],
            "route": i["route"],
            "badge": i.get("badge"),
            "label": i["labels"].get(locale, i["labels"]["en"]),
            "description": i["descriptions"].get(locale, i["descriptions"]["en"]),
        }
        for i in enabled
    ]


async def list_for_admin(db: AsyncSession) -> list[dict[str, Any]]:
    """GET /admin/menu — every item, every locale, disabled ones included."""
    return await _load(db)


async def create_item(db: AsyncSession, item: dict[str, Any], *, updated_by: str) -> dict[str, Any]:
    items = await _load(db)
    if any(i["id"] == item["id"] for i in items):
        raise ValueError(f"menu item {item['id']!r} already exists")
    items.append(item)
    await _save(db, items, updated_by=updated_by)
    return item


async def update_item(
    db: AsyncSession, item_id: str, patch: dict[str, Any], *, updated_by: str
) -> dict[str, Any]:
    items = await _load(db)
    for i in items:
        if i["id"] == item_id:
            i.update(patch)
            await _save(db, items, updated_by=updated_by)
            return i
    raise KeyError(f"no menu item {item_id!r}")


async def delete_item(db: AsyncSession, item_id: str, *, updated_by: str) -> None:
    items = await _load(db)
    remaining = [i for i in items if i["id"] != item_id]
    if len(remaining) == len(items):
        raise KeyError(f"no menu item {item_id!r}")
    await _save(db, remaining, updated_by=updated_by)
