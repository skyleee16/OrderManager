import asyncio
import logging
import json
import os
import re
import aiohttp
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from openai import OpenAI

# ================= ВАШИ КЛЮЧИ (ВСТАВЬТЕ СЮДА) =================
BOT_TOKEN = "8955658887:AAF5KliOKHIGQrGT67ss0X4SzkGcI20iYkY""          # например, "8955658887:AAF5KliOKHIGQrGT67ss0X4SzkGcI20iYkY"
DEEPSEEK_API_KEY = "sk-d480f4c756cf442db439f23452be062f"  # например, "sk-d480f4c756cf442db439f23452be062f"
# ===============================================================

DATA_FILE = "leads_data.json"
LEADS_SOURCE = "leads.json"
EARNINGS_FILE = "earnings.json"
GOAL_FILE = "goal.json"      # хранит цель

# --- ИНИЦИАЛИЗАЦИЯ ---
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
openai_client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com/v1")

# --- ФИНАНСОВЫЕ ФУНКЦИИ ---
def load_goal():
    if os.path.exists(GOAL_FILE):
        with open(GOAL_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("goal", 100000)
    return 100000  # цель по умолчанию

def save_goal(goal):
    with open(GOAL_FILE, "w", encoding="utf-8") as f:
        json.dump({"goal": goal}, f, ensure_ascii=False)

def load_earnings():
    if os.path.exists(EARNINGS_FILE):
        with open(EARNINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []  # список транзакций: [{"amount": 15000, "description": "сайт для кафе", "date": "2026-06-06 14:30"}]

def save_earnings(earnings):
    with open(EARNINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(earnings, f, ensure_ascii=False, indent=2)

def add_earning(amount, description=""):
    from datetime import datetime
    earnings = load_earnings()
    earnings.append({
        "amount": amount,
        "description": description,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M")
    })
    save_earnings(earnings)

def get_total_earned():
    return sum(item["amount"] for item in load_earnings())

# --- ЗАГРУЗКА ДАННЫХ ПО ЗАВЕДЕНИЯМ ---
def load_leads_from_json():
    if not os.path.exists(LEADS_SOURCE):
        with open(LEADS_SOURCE, "w", encoding="utf-8") as f:
            json.dump([], f)
        return []
    with open(LEADS_SOURCE, "r", encoding="utf-8") as f:
        return json.load(f)

def load_saved_data(leads_template):
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
        for lead in leads_template:
            s = saved.get(str(lead["id"]), {})
            lead["status"] = s.get("status", "new")
            lead["vk"] = s.get("vk", "")
            lead["telegram"] = s.get("telegram", "")
            lead["whatsapp"] = s.get("whatsapp", "")
            lead["site"] = s.get("site", "")
            lead["phone"] = s.get("phone", "")
    else:
        for lead in leads_template:
            lead["status"] = "new"
            lead["vk"] = lead["telegram"] = lead["whatsapp"] = lead["site"] = lead["phone"] = ""
    return leads_template

def save_leads_data(leads):
    to_save = {}
    for lead in leads:
        to_save[lead["id"]] = {
            "status": lead["status"],
            "vk": lead["vk"],
            "telegram": lead["telegram"],
            "whatsapp": lead["whatsapp"],
            "site": lead["site"],
            "phone": lead.get("phone", "")
        }
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(to_save, f, ensure_ascii=False, indent=2)

def save_leads_source(leads):
    source = [{"id": lead["id"], "name": lead["name"], "url": lead["url"]} for lead in leads]
    with open(LEADS_SOURCE, "w", encoding="utf-8") as f:
        json.dump(source, f, ensure_ascii=False, indent=2)

leads_template = load_leads_from_json()
leads = load_saved_data(leads_template)

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ КАРТОЧЕК ЗАВЕДЕНИЙ ---
def get_status_emoji(status):
    return {"new": "🟡", "in_progress": "🟠", "contacted": "📞", "success": "✅", "rejected": "❌"}.get(status, "⚪")

def get_status_text(status):
    return {"new": "🟡 Не обработан", "in_progress": "🟠 В работе", "contacted": "📞 Связались", "success": "✅ Успех", "rejected": "❌ Отказ"}.get(status, "⚪ Неизвестно")

# --- ПАРСИНГ СТРАНИЦЫ ЯНДЕКС.КАРТ ЧЕРЕЗ AI ---
async def fetch_page_html(url: str) -> str:
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers={"User-Agent": "Mozilla/5.0"}) as resp:
            if resp.status == 200:
                return await resp.text()
            return ""

async def parse_yandex_card_with_ai(url: str):
    html = await fetch_page_html(url)
    if not html:
        return None
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text(separator=' ', strip=True)[:4000]
    prompt = f"""
Ты — парсер контактов организаций. Проанализируй содержимое страницы Яндекс.Карт по URL: {url}
Текст страницы: {text}
Извлеки следующую информацию:
- Название организации
- Телефон (если есть)
- Сайт (если есть)
- VK (если есть)
- Telegram (если есть)
- WhatsApp (если есть)
Ответь строго в формате JSON:
{{
    "name": "название",
    "phone": "телефон или пустая строка",
    "site": "сайт или пустая строка",
    "vk": "ссылка VK или пустая строка",
    "telegram": "ссылка Telegram или пустая строка",
    "whatsapp": "ссылка WhatsApp или пустая строка"
}}
"""
    try:
        response = openai_client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        logging.error(f"DeepSeek error: {e}")
        return None

# --- ОБРАБОТЧИК ССЫЛОК НА ЯНДЕКС.КАРТЫ ---
@dp.message(lambda message: message.text and "yandex.ru/maps/org/" in message.text)
async def handle_yandex_link(message: types.Message):
    url = message.text.strip()
    await message.answer("🔍 Анализирую ссылку через нейросеть, подожди немного...")
    data = await parse_yandex_card_with_ai(url)
    if not data or not data.get("name"):
        await message.answer("❌ Не удалось обработать ссылку. Попробуй другую или добавь вручную.")
        return
    name = data["name"].strip()
    existing = next((l for l in leads if l["url"] == url), None)
    if existing:
        await message.answer(f"❓ Заведение «{existing['name']}» уже есть в списке (ID {existing['id']}).")
        return
    new_id = max([l["id"] for l in leads]) + 1 if leads else 1
    new_lead = {
        "id": new_id,
        "name": name,
        "url": url,
        "status": "new",
        "vk": data.get("vk", ""),
        "telegram": data.get("telegram", ""),
        "whatsapp": data.get("whatsapp", ""),
        "site": data.get("site", ""),
        "phone": data.get("phone", "")
    }
    leads.append(new_lead)
    save_leads_data(leads)
    save_leads_source(leads)
    contacts = []
    if new_lead["phone"]: contacts.append(f"📞 Телефон: {new_lead['phone']}")
    if new_lead["site"]: contacts.append(f"🌐 Сайт: {new_lead['site']}")
    if new_lead["vk"]: contacts.append(f"📘 VK: {new_lead['vk']}")
    if new_lead["telegram"]: contacts.append(f"📱 Telegram: {new_lead['telegram']}")
    if new_lead["whatsapp"]: contacts.append(f"💬 WhatsApp: {new_lead['whatsapp']}")
    contact_text = "\n".join(contacts) if contacts else "Контакты не найдены"
    await message.answer(f"✅ Добавлено новое заведение:\n🏢 *{name}*\n{contact_text}\n\nОно появится в списке «Мои клиенты».", parse_mode="Markdown")

# --- КОМАНДА /start (ГЛАВНОЕ МЕНЮ) ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎯 Мои клиенты", callback_data="show_leads")],
        [InlineKeyboardButton(text="💰 Финансы", callback_data="show_finance")]
    ])
    await message.answer(
        "Привет! Я твой помощник.\n"
        "📌 Отправь мне ссылку на Яндекс.Карты, и я добавлю заведение с контактами.\n"
        "💰 Команды финансов:\n"
        "/add_earn 15000 - добавить доход\n"
        "/stats - статистика к цели\n"
        "/goal 100000 - установить новую цель\n"
        "Меню управления - по кнопкам ниже.",
        reply_markup=keyboard
    )

# --- КЛИЕНТЫ (список заведений) ---
@dp.callback_query(lambda c: c.data == "show_leads")
async def show_leads_list(callback: types.CallbackQuery):
    if not leads:
        await callback.message.edit_text("Список заведений пуст. Добавь через отправку ссылок с Яндекс.Карт.")
        await callback.answer()
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for lead in leads:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text=f"{get_status_emoji(lead['status'])} {lead['name']}", callback_data=f"lead_{lead['id']}")
        ])
    await callback.message.edit_text("📋 *Список заведений:*", reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(lambda c: c.data and c.data.startswith("lead_") and not c.data.startswith("lead_status_") and not c.data.startswith("lead_edit_"))
async def show_lead_card(callback: types.CallbackQuery):
    lead_id = int(callback.data.split("_")[1])
    lead = next((l for l in leads if l["id"] == lead_id), None)
    if not lead:
        await callback.answer("Ошибка", show_alert=True)
        return
    text = f"🏢 *{lead['name']}*\n🔗 [Яндекс.Карты]({lead['url']})\n📊 Статус: {get_status_text(lead['status'])}"
    if lead.get("phone"): text += f"\n📞 Телефон: {lead['phone']}"
    if lead.get("site"): text += f"\n🌐 Сайт: {lead['site']}"
    if lead.get("vk"): text += f"\n📘 VK: {lead['vk']}"
    if lead.get("telegram"): text += f"\n📱 Telegram: {lead['telegram']}"
    if lead.get("whatsapp"): text += f"\n💬 WhatsApp: {lead['whatsapp']}"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Статус", callback_data=f"lead_status_{lead_id}"),
         InlineKeyboardButton(text="✏️ Контакты", callback_data=f"lead_edit_{lead_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="show_leads")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown", disable_web_page_preview=True)
    await callback.answer()

@dp.callback_query(lambda c: c.data and c.data.startswith("lead_status_"))
async def lead_status_menu(callback: types.CallbackQuery):
    lead_id = int(callback.data.split("_")[2])
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

@dp.callback_query(lambda c: c.data and c.data.startswith("lead_edit_"))
async def edit_contacts_menu(callback: types.CallbackQuery):
    lead_id = int(callback.data.split("_")[2])
    lead = next((l for l in leads if l["id"] == lead_id), None)
    if not lead:
        await callback.answer("Ошибка", show_alert=True)
        return
    text = (f"✏️ *Редактирование контактов для {lead['name']}*\n\n"
            f"Текущие значения:\n"
            f"Телефон: {lead.get('phone','—')}\n"
            f"Сайт: {lead.get('site','—')}\n"
            f"VK: {lead.get('vk','—')}\n"
            f"Telegram: {lead.get('telegram','—')}\n"
            f"WhatsApp: {lead.get('whatsapp','—')}\n\n"
            "Используй команду:\n"
            "`/set_contacts id телефон сайт vk telegram whatsapp`\n\n"
            "Пример:\n"
            "`/set_contacts 12 +71234567890 https://site.ru https://vk.com/... https://t.me/... https://wa.me/...`\n"
            "Если контакта нет, поставь `-`.")
    await callback.message.edit_text(text, parse_mode="Markdown")
    await callback.answer()

@dp.message(Command("set_contacts"))
async def set_contacts(message: types.Message):
    args = message.text.split(maxsplit=6)
    if len(args) < 7:
        await message.answer("Использование: `/set_contacts <id> <телефон> <сайт> <VK> <Telegram> <WhatsApp>`\nЕсли контакта нет, поставьте `-`", parse_mode="Markdown")
        return
    try:
        lead_id = int(args[1])
        lead = next((l for l in leads if l["id"] == lead_id), None)
        if not lead:
            await message.answer("ID не найден")
            return
        lead["phone"] = args[2] if args[2] != "-" else ""
        lead["site"] = args[3] if args[3] != "-" else ""
        lead["vk"] = args[4] if args[4] != "-" else ""
        lead["telegram"] = args[5] if args[5] != "-" else ""
        lead["whatsapp"] = args[6] if args[6] != "-" else ""
        save_leads_data(leads)
        await message.answer(f"✅ Контакты для {lead['name']} обновлены!")
    except Exception as e:
        await message.answer(f"Ошибка: {e}")

# --- ФИНАНСЫ ---
@dp.callback_query(lambda c: c.data == "show_finance")
async def show_finance(callback: types.CallbackQuery):
    goal = load_goal()
    total = get_total_earned()
    left = goal - total
    earnings = load_earnings()[-5:]  # последние 5 записей
    lines = [f"💰 *Доход: {total} ₽*", f"🎯 *Цель: {goal} ₽*", f"📉 *Осталось: {left} ₽*"]
    if earnings:
        lines.append("\n📋 *Последние поступления:*")
        for e in reversed(earnings):
            desc = f" ({e['description']})" if e['description'] else ""
            lines.append(f"• +{e['amount']} ₽{desc} – {e['date']}")
    else:
        lines.append("\nПока нет записей. Добавь через /add_earn")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить доход", callback_data="add_earn_btn")],
        [InlineKeyboardButton(text="🎯 Мои клиенты", callback_data="show_leads")]
    ])
    await callback.message.edit_text("\n".join(lines), reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "add_earn_btn")
async def ask_earn_amount(callback: types.CallbackQuery):
    await callback.message.edit_text("Введи сумму и описание в формате:\n`/add_earn 15000 описание`\n\nНапример:\n`/add_earn 20000 сайт для ресторана`", parse_mode="Markdown")
    await callback.answer()

@dp.message(Command("add_earn"))
async def add_earn_command(message: types.Message):
    parts = message.text.split(maxsplit=2)
    if len(parts) < 2:
        await message.answer("Использование: `/add_earn <сумма> [описание]`", parse_mode="Markdown")
        return
    try:
        amount = int(parts[1])
        description = parts[2] if len(parts) > 2 else ""
        add_earning(amount, description)
        total = get_total_earned()
        goal = load_goal()
        left = goal - total
        await message.answer(f"✅ Записано: +{amount} ₽\n💰 Всего заработано: {total} ₽\n🎯 До цели: {left} ₽")
        # Обновим клавиатуру финансов, если открыта
        # но это не обязательно
    except ValueError:
        await message.answer("Сумма должна быть числом.")

@dp.message(Command("stats"))
async def show_stats(message: types.Message):
    goal = load_goal()
    total = get_total_earned()
    left = goal - total
    earnings = load_earnings()[-10:]  # последние 10
    lines = [f"💰 *Заработано: {total} ₽*", f"🎯 *Цель: {goal} ₽*", f"📉 *Осталось: {left} ₽*"]
    if earnings:
        lines.append("\n📋 *История:*")
        for e in reversed(earnings):
            desc = f" ({e['description']})" if e['description'] else ""
            lines.append(f"• +{e['amount']} ₽{desc} – {e['date']}")
    else:
        lines.append("\nНет записей. Добавьте /add_earn")
    await message.answer("\n".join(lines), parse_mode="Markdown")

@dp.message(Command("goal"))
async def set_goal_command(message: types.Message):
    parts = message.text.split()
    if len(parts) == 2 and parts[1].isdigit():
        new_goal = int(parts[1])
        save_goal(new_goal)
        await message.answer(f"🎯 Новая цель: {new_goal} ₽")
    else:
        current = load_goal()
        await message.answer(f"🎯 Текущая цель: {current} ₽\nИзменить: `/goal 150000`", parse_mode="Markdown")

# --- ЗАПУСК ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
