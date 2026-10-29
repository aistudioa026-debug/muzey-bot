import asyncio, io, json, os, re, uuid

import qrcode
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, Message
from aiohttp import web

TOKEN = os.getenv("BOT_TOKEN", "")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8080")  # ochiq HTTPS manzil
DATA = "data"
MAX_ITEMS = 24
os.makedirs(DATA, exist_ok=True)

bot = Bot(TOKEN)
dp = Dispatcher()
rooms = {}  # user_id -> room_id


def room_dir(rid):
    return os.path.join(DATA, rid)


def meta_path(rid):
    return os.path.join(room_dir(rid), "items.json")


def load(rid):
    try:
        with open(meta_path(rid)) as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def save(rid, items):
    with open(meta_path(rid), "w") as f:
        json.dump(items, f)


def new_room(uid):
    rid = uuid.uuid4().hex[:8]
    os.makedirs(room_dir(rid))
    save(rid, [])
    rooms[uid] = rid
    return rid


@dp.message(Command("start"))
async def start(m: Message):
    new_room(m.from_user.id)
    await m.answer(
        "🏛 Muzey yaratamiz!\n"
        f"Rasm yoki video yuboring (maksimum {MAX_ITEMS} ta, video 20 MB gacha).\n"
        "Tugagach /tayyor deb yozing."
    )


@dp.message(F.photo | F.video)
async def media(m: Message):
    uid = m.from_user.id
    rid = rooms.get(uid) or new_room(uid)
    items = load(rid)
    if len(items) >= MAX_ITEMS:
        await m.answer("Limit tugadi. /tayyor deb yozing.")
        return
    if m.photo:
        fid, kind, ext = m.photo[-1].file_id, "image", "jpg"
    else:
        fid, kind, ext = m.video.file_id, "video", "mp4"
    name = f"{uuid.uuid4().hex[:8]}.{ext}"
    try:
        await bot.download(fid, destination=os.path.join(room_dir(rid), name))
    except Exception:
        await m.answer("❌ Yuklab bo'lmadi (video 20 MB dan oshmasin).")
        return
    items.append({"type": kind, "src": f"/files/{rid}/{name}"})
    save(rid, items)
    await m.answer(f"✅ {len(items)} ta qo'shildi. Yana yuboring yoki /tayyor")


@dp.message(Command("tayyor"))
async def ready(m: Message):
    rid = rooms.pop(m.from_user.id, None)
    if not rid or not load(rid):
        await m.answer("Avval rasm yoki video yuboring.")
        return
    url = f"{BASE_URL}/m/{rid}"
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    await m.answer_photo(
        BufferedInputFile(buf.getvalue(), "muzey.png"),
        caption=f"🏛 Muzeyingiz tayyor!\n{url}\nQR ni skaner qiling.",
    )


# ---------- veb-server ----------
async def page(request):
    return web.FileResponse("museum.html")


async def ping(request):
    return web.Response(text="ok")


async def api(request):
    rid = request.match_info["rid"]
    if not re.fullmatch(r"[0-9a-f]{8}", rid):
        raise web.HTTPNotFound()
    return web.json_response(load(rid))


async def main():
    app = web.Application()
    app.add_routes([web.get("/", ping), web.get("/m/{rid}", page), web.get("/api/{rid}", api)])
    app.router.add_static("/files", DATA)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", "8080"))).start()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
