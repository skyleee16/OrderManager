import asyncio
import logging
import json
import os
import re
import urllib.parse
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ================= ВАШИ ДАННЫЕ =================
BOT_TOKEN = "8955658887:AAF5KliOKHIGQrGT67ss0X4SzkGcI20iYkY"
DATA_FILE = "leads_data.json"  # файл для сохранения статусов и контактов

# --- ИНИЦИАЛИЗАЦИЯ ---
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- МАССИВ ЗАВЕДЕНИЙ (из твоих ссылок) ---
# Названия извлечены из URL или уточнены вручную
leads_template = [
    {"id": 1, "name": "Zell", "url": "https://yandex.ru/maps/org/zell/1684155978/"},
    {"id": 2, "name": "X Квест", "url": "https://yandex.ru/maps/org/x_kvest/149909784428/"},
    {"id": 3, "name": "Escape Rooms", "url": "https://yandex.ru/maps/org/escape_rooms/52636490008/"},
    {"id": 4, "name": "Tsunami Боулинг", "url": "https://yandex.ru/maps/org/tsunami/1107910502/"},
    {"id": 5, "name": "Kot i Klever", "url": "https://yandex.ru/maps/org/kot_i_klever/1367001542/"},
    {"id": 6, "name": "Дом молодежи", "url": "https://yandex.ru/maps/org/dom_molodezhi/1226955093/"},
    {"id": 7, "name": "Праздники на 5+", "url": "https://yandex.ru/maps/org/prazdniki_na_5_igrovaya_gostinnaya/219506316085/"},
    {"id": 8, "name": "Рампа", "url": "https://yandex.ru/maps/org/rampa/9558991091/"},
    {"id": 9, "name": "Тихоокеанский ТРЦ", "url": "https://yandex.ru/maps/org/tikhookeanskiy/1051730565/"},
    {"id": 10, "name": "Prostranstvo", "url": "https://yandex.ru/maps/org/prostranstvo/169879589973/"},
    {"id": 11, "name": "Музейно-выставочный центр", "url": "https://yandex.ru/maps/org/muzeyno_vystavochny_tsentr/1126886161/"},
    {"id": 12, "name": "Jack's Karaoke", "url": "https://yandex.ru/maps/org/jack_s_karaoke/180087139561/"},
    {"id": 13, "name": "Armada", "url": "https://yandex.ru/maps/org/armada/1941791318/"},
    {"id": 14, "name": "Штаб", "url": "https://yandex.ru/maps/org/shtab/79939761729/"},
    {"id": 15, "name": "Sinichka", "url": "https://yandex.ru/maps/org/sinichka/35330055595/"},
    {"id": 16, "name": "Без понтов", "url": "https://yandex.ru/maps/org/bez_pontov/192944061703/"},
    {"id": 17, "name": "Театр кукол", "url": "https://yandex.ru/maps/org/teatr_kukol_goroda_nakhodka/1053006526/"},
    {"id": 18, "name": "Sinichka (дубль)", "url": "https://yandex.ru/maps/org/sinichka/35330055595/"}  # дубль, можно удалить
]

# Удалим дубль Sinichka, оставим один
leads_template = [item for item in leads_template if item["name"] != "Sinichka (дубль)"]

# Загружаем сохранённые данные (статусы и контакты)
def load_leads_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
        # Обновляем шаблон сохранёнными статусами и контактами
        for lead in leads_template:
            saved_lead = saved.get(str(lead["id"]))
            if saved_lead:
                lead["status"] = saved_lead.get("status", "new")
                lead["vk"] = saved_lead.get("vk", "")
                lead["telegram"] = saved_lead.get("telegram", "")
                lead["whatsapp"] = saved_lead.get("whatsapp", "")
                lead["site"] = saved_lead.get("site", "")
            else:
                lead["status"] = "new"
                lead["vk"] = ""
                lead["telegram"] = ""
                lead["whatsapp"] = ""
                lead["site"] = ""
    else:
        for lead in leads_template:
            lead["status"] = "new"
            lead["vk"] = ""
            lead["telegram"] = ""
            lead["whatsapp"] = ""
            lead["site"] = ""
    return leads_template

def save_leads_data(leads):
    to_save = {}
    for lead in leads:
        to_save[lead["id"]] = {
            "status": lead["status"],
            "vk": lead["vk"],
            "telegram": lead["telegram"],
            "whatsapp": lead["whatsapp"],
            "site": lead["site"]
        }
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(to_save, f, ensure_ascii=False, indent=2)

leads = load_leads_data()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def get_status_emoji(status):
    return {"new": "🟡", "in_progress": "🟠", "contacted": "📞", "success": "✅", "rejected": "❌"}.get(status, "⚪")

def get_status_text(status):
    return {"new": "🟡 Не обработан", "in_progress": "🟠 В работе", "contacted": "📞 Связались", "success": "✅ Успех", "rejected": "❌ Отказ"}.get(status, "⚪ Неизвестно")

# --- КОМАНДЫ ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎯 Мои клиенты (Находка)", callback_data="show_leads")]
    ])
    await message.answer(
        "Привет! Я твой помощник по клиентам. Здесь список заведений Находки.\n"
        "Ты можешь отслеживать статусы и добавлять контакты.",
        reply_markup=keyboard
    )

@dp.callback_query(lambda c: c.data == "show_leads")
async def show_leads_list(callback: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for lead in leads:
        emoji = get_status_emoji(lead["status"])
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text=f"{emoji} {lead['name']}", callback_data=f"lead_{lead['id']}")
        ])
    await callback.message.edit_text("📋 *Список заведений Находки:*", reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(lambda c: c.data and c.data.startswith("lead_") and not c.data.startswith("lead_set_status_"))
async def show_lead_card(callback: types.CallbackQuery):
    lead_id = int(callback.data.split("_")[1])
    lead = next((l for l in leads if l["id"] == lead_id), None)
    if not lead:
        await callback.answer("Ошибка", show_alert=True)
        return
    status_text = get_status_text(lead["status"])
    text = f"🏢 *{lead['name']}*\n🔗 [Ссылка на Яндекс.Карты]({lead['url']})\n📊 *Статус:* {status_text}"
    if lead.get("vk"): text += f"\n📘 VK: {lead['vk']}"
    if lead.get("telegram"): text += f"\n📱 Telegram: {lead['telegram']}"
    if lead.get("whatsapp"): text += f"\n💬 WhatsApp: {lead['whatsapp']}"
    if lead.get("site"): text += f"\n🌐 Сайт: {lead['site']}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Изменить статус", callback_data=f"lead_status_menu_{lead_id}")],
        [InlineKeyboardButton(text="✏️ Редактировать контакты", callback_data=f"edit_contacts_{lead_id}")],
        [InlineKeyboardButton(text="◀️ Назад к списку", callback_data="show_leads")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown", disable_web_page_preview=True)
    await callback.answer()

# --- МЕНЮ ИЗМЕНЕНИЯ СТАТУСА ---
@dp.callback_query(lambda c: c.data and c.data.startswith("lead_status_menu_"))
async def lead_status_menu(callback: types.CallbackQuery):
    lead_id = int(callback.data.split("_")[3])
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟡 В работу", callback_data=f"lead_set_status_{lead_id}_in_progress"),
         InlineKeyboardButton(text="📞 Связались", callback_data=f"lead_set_status_{lead_id}_contacted")],
        [InlineKeyboardButton(text="✅ Успех", callback_data=f"lead_set_status_{lead_id}_success"),
         InlineKeyboardButton(text="❌ Отказ", callback_data=f"lead_set_status_{lead_id}_rejected")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"lead_{lead_id}")]
    ])
    await callback.message.edit_text("Выбери новый статус:", reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(lambda c: c.data and c.data.startswith("lead_set_status_"))
async def set_lead_status(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    lead_id = int(parts[3])
    new_status = parts[4]
    for lead in leads:
        if lead["id"] == lead_id:
            lead["status"] = new_status
            break
    save_leads_data(leads)
    await callback.answer(f"Статус изменён!", show_alert=True)
    await show_lead_card(callback)

# --- РЕДАКТИРОВАНИЕ КОНТАКТОВ (упрощённо) ---
# Пользователь вводит команду /set_contacts id VK Telegram WhatsApp Сайт
@dp.message(Command("set_contacts"))
async def set_contacts(message: types.Message):
    args = message.text.split(maxsplit=5)
    if len(args) < 6:
        await message.answer("Использование: /set_contacts <id> <VK> <Telegram> <WhatsApp> <Сайт>\nЕсли контакта нет, поставьте '-'")
        return
    try:
        lead_id = int(args[1])
        lead = next((l for l in leads if l["id"] == lead_id), None)
        if not lead:
            await message.answer("ID не найден")
            return
        vk = args[2] if args[2] != "-" else ""
        tg = args[3] if args[3] != "-" else ""
        wa = args[4] if args[4] != "-" else ""
        site = args[5] if args[5] != "-" else ""
        lead["vk"] = vk
        lead["telegram"] = tg
        lead["whatsapp"] = wa
        lead["site"] = site
        save_leads_data(leads)
        await message.answer(f"✅ Контакты для {lead['name']} обновлены!")
    except Exception as e:
        await message.answer(f"Ошибка: {e}")

# --- ЗАПУСК ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())