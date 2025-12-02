import os
import json
from datetime import datetime
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, Message, CallbackQuery
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import asyncio

# Konfiguratsiya yuklash
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# Malumotlarni saqlash
students_data = {}
requests_data = {}
Tyutors_data = {}

CONFIG_FILE = "config.json"

def load_faculties():
    """Load faculties from config.json"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                FACULTIES = json.load(f)
        else:
            FACULTIES = {}
        
        total_Tyutors = sum(len(Tyutors) for Tyutors in FACULTIES.values())
        print(f" ✅ Fakultetlar yuklandi: {list(FACULTIES.keys())}")
        print(f" ✅ Jami Tyutorlar: {total_Tyutors}")
        
        for faculty, Tyutors in FACULTIES.items():
            for Tyutor in Tyutors:
                print(f"   - {Tyutor['name']} (ID: {Tyutor['chat_id']}) - {faculty}")
        
        return FACULTIES if FACULTIES else {}
    except json.JSONDecodeError as e:
        print(f" ❌ ERROR: JSON parsing xatosi: {e}")
        return {}
    except Exception as e:
        print(f" ❌ ERROR: {e}")
        return {}

def save_faculties(faculties):
    """Save faculties to config.json"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(faculties, f, ensure_ascii=False, indent=2)
        print(f" ✅ Config saqlandi: {CONFIG_FILE}")
        return True
    except Exception as e:
        print(f" ❌ ERROR: Config saqlanmadi: {e}")
        return False

FACULTIES = load_faculties()

# Rad etish sabablarini yuklash
try:
    reasons_str = os.getenv("REJECTION_REASONS", "Vaqt ichida javob bera olmayapman,Boshqa sabablar")
    REJECTION_REASONS = [r.strip() for r in reasons_str.split(",") if r.strip()]
except:
    REJECTION_REASONS = ["Vaqt ichida javob bera olmayapman", "Boshqa sabablar"]

print(f" Bot ishga tushmoqda... Admin ID: {ADMIN_ID}")

# Talaba states
class StudentStates(StatesGroup):
    selecting_faculty = State()
    selecting_Tyutor = State()
    entering_name = State()
    entering_phone = State()
    entering_request = State()
    waiting_for_response = State()

# Tyutor states
class TyutorStates(StatesGroup):
    responding = State()

# Admin states
class AdminStates(StatesGroup):
    adding_Tyutor_name = State()
    adding_Tyutor_chat_id = State()
    adding_Tyutor_faculty = State()
    editing_Tyutor_faculty = State()
    selecting_Tyutor_to_edit = State()
    editing_Tyutor_name = State()
    editing_Tyutor_chat_id = State()

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ===== TALABA HANDLERLARI =====

@dp.message(Command("start"))
async def start(message: Message, state: FSMContext):
    """Bot boshlanishi"""
    user_id = message.from_user.id
    print(f" DEBUG: /start - user_id = {user_id}, first_name = {message.from_user.first_name}")
    
    if user_id == ADMIN_ID:
        print(f" Admin kiritildi!")
        await admin_menu(message, state)
        return
    
    is_Tyutor = False
    Tyutor_faculty = None
    Tyutor_obj = None
    
    for faculty, Tyutors in FACULTIES.items():
        for Tyutor in Tyutors:
            Tyutor_chat_id = Tyutor.get('chat_id')
            print(f" Tekshirilmoqda: user_id={user_id} vs Tyutor_chat_id={Tyutor_chat_id}")
            
            if Tyutor_chat_id == user_id:
                is_Tyutor = True
                Tyutor_faculty = faculty
                Tyutor_obj = Tyutor
                Tyutors_data[user_id] = Tyutor['name']
                print(f" ✅ Tyutor TOPILDI: {Tyutor['name']} ({user_id}) - {faculty}")
                break
        
        if is_Tyutor:
            break
    
    if is_Tyutor:
        await show_Tyutor_panel(message, state)
        return
    
    if not is_Tyutor:
        print(f" ⚠️ Tyutor topilmadi user_id={user_id} uchun")
        print(f" Mavjud Tyutorlar ID lari: {[t['chat_id'] for faculty, Tyutors in FACULTIES.items() for t in Tyutors]}")
    
    # Oddiy talaba
    if user_id not in students_data:
        students_data[user_id] = {
            "name": None,
            "phone": None,
            "requests": []
        }
    
    keyboards = []
    for faculty in FACULTIES.keys():
        keyboards.append([InlineKeyboardButton(text=faculty, callback_data=f"faculty_{faculty}")])
    
    keyboards.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboards)
    await message.answer(
        f"👋 Salom, {message.from_user.first_name}!\n\n"
        "Murojaat qilmoqchi bo'lgan fakultetingizni tanlang:",
        reply_markup=keyboard
    )
    await state.set_state(StudentStates.selecting_faculty)

async def show_Tyutor_panel(message: Message, state: FSMContext):
    """Tyutor uchun panel"""
    Tyutor_id = message.from_user.id
    
    Tyutor_requests = [
        (req_id, req) for req_id, req in requests_data.items() 
        if req.get('Tyutor_id') == Tyutor_id
    ]
    
    if not Tyutor_requests:
        await message.answer("📭 Sizga murojat kelmagan.")
        return
    
    text = "📋 SIZNING MUROJATLARINGIZ\n\n"
    keyboards = []
    
    for req_id, req in Tyutor_requests:
        status_emoji = "⏳" if req['status'] == "pending" else \
                      "✅" if req['status'] == "accepted" else \
                      "❌" if req['status'] == "rejected" else "✔️"
        
        text += f"{status_emoji} {req['student_name']} - {req['status']}\n"
        keyboards.append([
            InlineKeyboardButton(
                text=f"👀 {req['student_name']}", 
                callback_data=f"Tyutor_view_{req_id}"
            )
        ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboards)
    await message.answer(text, reply_markup=keyboard)

@dp.callback_query(F.data == "cancel")
async def cancel_student_request(query: CallbackQuery, state: FSMContext):
    """Bekor qilish"""
    await query.message.delete()
    await query.message.answer("❌ Bekor qilindi. /start buyrug'ini yuboring.")
    await state.clear()

@dp.callback_query(StateFilter(StudentStates.selecting_faculty))
async def faculty_selected(query: CallbackQuery, state: FSMContext):
    """Fakultet tanlandi"""
    faculty_name = query.data.split("_", 1)[1]
    
    await state.update_data(selected_faculty=faculty_name)
    
    Tyutors = FACULTIES.get(faculty_name, [])
    
    keyboards = []
    for Tyutor in Tyutors:
        keyboards.append([
            InlineKeyboardButton(
                text=f"👨‍🏫 {Tyutor['name']}", 
                callback_data=f"Tyutor_{Tyutor['chat_id']}"
            )
        ])
    
    keyboards.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="go_back")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboards)
    await query.message.edit_text(
        f"📚 {faculty_name} - Tyutorlarni tanlang:",
        reply_markup=keyboard
    )
    await state.set_state(StudentStates.selecting_Tyutor)

@dp.callback_query(F.data == "go_back")
async def go_back(query: CallbackQuery, state: FSMContext):
    """Orqaga qaytish"""
    await state.clear()
    await start(query.message, state)

@dp.callback_query(StateFilter(StudentStates.selecting_Tyutor))
async def Tyutor_selected(query: CallbackQuery, state: FSMContext):
    """Tyutor tanlandi"""
    Tyutor_id = int(query.data.split("_")[1])
    
    await state.update_data(selected_Tyutor=Tyutor_id)
    
    await query.message.edit_text(
        "📝 Iltimosda, o'z ismingizni kiriting:"
    )
    await state.set_state(StudentStates.entering_name)

@dp.message(StateFilter(StudentStates.entering_name))
async def get_name(message: Message, state: FSMContext):
    """Ismi olinadi"""
    students_data[message.from_user.id]["name"] = message.text
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[
            KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)
        ]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(
        "📱 Telefon raqamingizni tugmasi orqali yuboruq:",
        reply_markup=keyboard
    )
    await state.set_state(StudentStates.entering_phone)

@dp.message(StateFilter(StudentStates.entering_phone), F.contact)
async def get_contact(message: Message, state: FSMContext):
    """Kontakt qabul qilish"""
    students_data[message.from_user.id]["phone"] = message.contact.phone_number
    
    await message.answer(
        "✍️ Endi murojatingizni yozing.\nAniq va to'liq ma'lumot bering:",
        reply_markup=ReplyKeyboardMarkup(keyboard=[[]], resize_keyboard=True)
    )
    await state.set_state(StudentStates.entering_request)

@dp.message(StateFilter(StudentStates.entering_phone))
async def get_phone_text(message: Message, state: FSMContext):
    """Qo'lda telefon kiritish"""
    students_data[message.from_user.id]["phone"] = message.text
    
    await message.answer(
        "✍️ Endi murojatingizni yozing:\nAniq va to'liq ma'lumot bering:",
        reply_markup=ReplyKeyboardMarkup(keyboard=[[]], resize_keyboard=True)
    )
    await state.set_state(StudentStates.entering_request)

@dp.message(StateFilter(StudentStates.entering_request))
async def save_request(message: Message, state: FSMContext):
    """Murojaat saqlash"""
    user_id = message.from_user.id
    data = await state.get_data()
    
    request_id = f"req_{user_id}_{int(datetime.now().timestamp() * 1000)}"
    
    Tyutor_id = data.get("selected_Tyutor")
    faculty = data.get("selected_faculty")
    
    requests_data[request_id] = {
        "student_id": user_id,
        "student_name": students_data[user_id]["name"],
        "student_phone": students_data[user_id]["phone"],
        "Tyutor_id": Tyutor_id,
        "faculty": faculty,
        "text": message.text,
        "status": "pending",
        "messages": [],
        "created_at": datetime.now().isoformat()
    }
    
    print(f" Murojaat yaratildi: {request_id} -> Tyutor_id: {Tyutor_id}")
    
    cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"cancel_request_{request_id}")
    ]])
    
    await message.answer(
        "✅ Murojatingiz qabul qilindi!\n"
        "Tyutor javob berilgach sizga habar yuboriladi.",
        reply_markup=cancel_keyboard
    )
    
    Tyutor_chat_id = Tyutor_id
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Qabul qilish", callback_data=f"accept_{request_id}"),
        InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_{request_id}")
    ]])
    
    try:
        await bot.send_message(
            Tyutor_chat_id,
            f"📬 YANGI MUROJAAT\n\n"
            f"👤 Talaba: {students_data[user_id]['name']}\n"
            f"📚 Fakultet: {faculty}\n"
            f"📱 Telefon: {students_data[user_id]['phone']}\n\n"
            f"💬 Murojaat:\n{message.text}\n\n"
            f"ID: {request_id}",
            reply_markup=keyboard
        )
        print(f" Murojaat Tyutorga yuborildi: {Tyutor_chat_id}")
    except Exception as e:
        print(f" ERROR: Tyutor {Tyutor_chat_id} ga yuborilmadi: {e}")
        await message.answer(f"⚠️ Xato: Tyutor {Tyutor_chat_id} ga habar yuborilmadi!")
    
    await state.clear()

@dp.callback_query(F.data.startswith("cancel_request_"))
async def cancel_request_callback(query: CallbackQuery):
    """Murojatni bekor qilish"""
    request_id = query.data.split("_", 2)[2]
    
    if request_id in requests_data:
        req = requests_data[request_id]
        if req['status'] == 'pending':
            requests_data[request_id]['status'] = 'cancelled'
            try:
                await bot.send_message(
                    req['Tyutor_id'],
                    f"⛔ Murojat bekor qilindi!\nTalaba: {req['student_name']}"
                )
            except:
                pass
            await query.answer("✅ Murojat bekor qilindi!")
        else:
            await query.answer("⚠️ Bu murojatni bekor qila olmaysiz!", show_alert=True)

# ===== Tyutor HANDLERLARI =====

@dp.callback_query(F.data.startswith("Tyutor_view_"))
async def Tyutor_view_request(query: CallbackQuery, state: FSMContext):
    """Tyutor murojatni ko'radi"""
    request_id = query.data.split("_", 2)[2]
    
    if request_id not in requests_data:
        await query.answer("❌ Murojaat topilmadi!", show_alert=True)
        return
    
    req = requests_data[request_id]
    
    text = (
        f"📬 MUROJAAT\n\n"
        f"👤 Talaba: {req['student_name']}\n"
        f"📱 Telefon: {req['student_phone']}\n"
        f"📚 Fakultet: {req['faculty']}\n"
        f"Status: {req['status']}\n\n"
        f"💬 Murojaat:\n{req['text']}"
    )
    
    if req['status'] == 'rejected':
        await query.message.edit_text(text + "\n\n❌ Bu murojat rad etildi!")
        return
    
    if req['status'] == 'cancelled':
        await query.message.edit_text(text + "\n\n⛔ Bu murojat bekor qilindi!")
        return
    
    keyboards = []
    if req['status'] == 'pending':
        keyboards.append([[
            InlineKeyboardButton(text="✅ Qabul qilish", callback_data=f"accept_{request_id}"),
            InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_{request_id}")
        ]])
    elif req['status'] == 'accepted':
        keyboards.append([[
            InlineKeyboardButton(text="💬 Javob berish", callback_data=f"respond_{request_id}"),
            InlineKeyboardButton(text="✔️ Yakunlash", callback_data=f"finish_{request_id}")
        ]])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboards)
    await query.message.edit_text(text, reply_markup=keyboard)

@dp.callback_query(F.data.startswith("accept_"))
async def accept_request(query: CallbackQuery, state: FSMContext):
    """Murojaat qabul qilish"""
    request_id = query.data.split("_", 1)[1]
    
    if request_id not in requests_data:
        await query.answer("❌ Murojaat topilmadi!", show_alert=True)
        return
    
    requests_data[request_id]["status"] = "accepted"
    
    req = requests_data[request_id]
    try:
        await bot.send_message(
            req["student_id"],
            f"✅ Tyutor murojatingizni qabul qildi!\n\n"
            f"👨‍🏫 Tyutor: {Tyutors_data.get(req['Tyutor_id'], 'Noma\'lum')}\n"
            "Javob kutilmoqda..."
        )
    except:
        pass
    
    await query.answer("✅ Murojat qabul qilindi!")
    await state.update_data(current_request=request_id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💬 Javob berish", callback_data=f"respond_{request_id}")
    ]])
    await query.message.edit_reply_markup(reply_markup=keyboard)

@dp.callback_query(F.data.startswith("respond_"))
async def respond_request(query: CallbackQuery, state: FSMContext):
    """Javob berishni boshlash"""
    request_id = query.data.split("_", 1)[1]
    
    await state.update_data(current_request=request_id)
    await query.message.answer("📝 Javobingizni yozing:")
    await state.set_state(TyutorStates.responding)

@dp.message(StateFilter(TyutorStates.responding))
async def send_response(message: Message, state: FSMContext):
    """Tyutor javob beradi"""
    data = await state.get_data()
    request_id = data.get("current_request")
    
    if request_id not in requests_data:
        await message.answer("❌ Murojaat topilmadi!")
        return
    
    req = requests_data[request_id]
    
    if req['status'] == 'rejected':
        await message.answer("❌ Rad etilgan murojatga javob bera olmaysiz!")
        await state.clear()
        return
    
    if req['status'] == 'cancelled':
        await message.answer("⛔ Bekor qilingan murojatga javob bera olmaysiz!")
        await state.clear()
        return
    
    req["messages"].append({
        "sender": "Tyutor",
        "text": message.text,
        "time": datetime.now().isoformat(),
        "request_id": request_id
    })
    
    talaba_keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💬 Javob berish", callback_data=f"student_reply_{request_id}")
    ]])
    
    try:
        await bot.send_message(
            req["student_id"],
            f"📩 Tyutordan javob:\n\n{message.text}",
            reply_markup=talaba_keyboard
        )
    except:
        pass
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔄 Davom etish", callback_data=f"continue_{request_id}"),
        InlineKeyboardButton(text="✔️ Yakunlash", callback_data=f"finish_{request_id}")
    ]])
    
    await message.answer("✅ Javobingiz talabaga yuborildi!", reply_markup=keyboard)
    await state.clear()

@dp.callback_query(F.data.startswith("student_reply_"))
async def student_reply(query: CallbackQuery, state: FSMContext):
    """Talaba javob beradi"""
    request_id = query.data.split("_", 2)[2]
    
    if request_id in requests_data and requests_data[request_id]['status'] == 'rejected':
        await query.answer("❌ Rad etilgan murojatga javob bera olmaysiz!", show_alert=True)
        return
    
    await state.update_data(current_request=request_id)
    await query.message.answer("✍️ Javobingizni yozing:")
    await state.set_state(StudentStates.waiting_for_response)

@dp.message(StateFilter(StudentStates.waiting_for_response))
async def student_send_reply(message: Message, state: FSMContext):
    """Talabani javobi"""
    data = await state.get_data()
    request_id = data.get("current_request")
    
    if request_id not in requests_data:
        await message.answer("❌ Xato!")
        return
    
    req = requests_data[request_id]
    
    if req['status'] == 'rejected':
        await message.answer("❌ Rad etilgan murojatga javob bera olmaysiz!")
        await state.clear()
        return
    
    req["messages"].append({
        "sender": "student",
        "text": message.text,
        "time": datetime.now().isoformat(),
        "request_id": request_id
    })
    
    Tyutor_keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔄 Davom etish", callback_data=f"continue_{request_id}"),
        InlineKeyboardButton(text="✔️ Yakunlash", callback_data=f"finish_{request_id}")
    ]])
    
    try:
        await bot.send_message(
            req["Tyutor_id"],
            f"📨 {req['student_name']} dan javob:\n\n{message.text}",
            reply_markup=Tyutor_keyboard
        )
    except:
        pass
    
    await message.answer("✅ Javobingiz Tyutorga yuborildi.")
    await state.clear()

@dp.callback_query(F.data.startswith("reject_"))
async def reject_request(query: CallbackQuery, state: FSMContext):
    """Murojaat rad etish"""
    request_id = query.data.split("_", 1)[1]
    
    keyboards = [[InlineKeyboardButton(text=reason, callback_data=f"reason_{request_id}_{i}")] 
                 for i, reason in enumerate(REJECTION_REASONS)]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboards)
    
    await query.message.edit_text(
        "❌ Rad etish sababini tanlang:",
        reply_markup=keyboard
    )

@dp.callback_query(F.data.startswith("reason_"))
async def send_rejection(query: CallbackQuery):
    """Rad etish sababini yuborish"""
    parts = query.data.split("_")
    request_id = "_".join(parts[1:-1])
    reason_idx = int(parts[-1])
    
    if request_id not in requests_data:
        await query.answer("❌ Murojaat topilmadi!", show_alert=True)
        return
    
    reason = REJECTION_REASONS[reason_idx]
    req = requests_data[request_id]
    req["status"] = "rejected"
    
    try:
        await bot.send_message(
            req["student_id"],
            f"❌ Kechirasiz, murojatingiz rad etildi.\n"
            f"Sabab: {reason}"
        )
    except:
        pass
    
    await query.message.edit_text(
        query.message.text + f"\n\n✅ Murojat rad etildi.\nSabab: {reason}",
        parse_mode="Markdown"
    )
    
    await query.answer("Murojaat rad etildi!")

@dp.callback_query(F.data.startswith("continue_"))
async def continue_conversation(query: CallbackQuery, state: FSMContext):
    """Suxbatni davom etish"""
    request_id = query.data.split("_", 1)[1]
    
    await state.update_data(current_request=request_id)
    await state.set_state(TyutorStates.responding)
    
    await query.message.answer("💬 Qo'shimcha javobingizni yozing:")

@dp.callback_query(F.data.startswith("finish_"))
async def finish_conversation(query: CallbackQuery):
    """Suxbatni yakunlash"""
    request_id = query.data.split("_", 1)[1]
    
    if request_id not in requests_data:
        await query.answer("❌ Murojaat topilmadi!", show_alert=True)
        return
    
    req = requests_data[request_id]
    req["status"] = "finished"
    
    try:
        await bot.send_message(
            req["student_id"],
            "✔️ Suxbat yakunlandi. Agar yana savol bo'lsa, qayta murojaat qiling."
        )
    except:
        pass
    
    await query.answer("✅ Suxbat yakunlandi!")
    await query.message.edit_reply_markup(reply_markup=None)

# ===== ADMIN HANDLERLARI =====

async def admin_menu(message: Message, state: FSMContext):
    """Admin menyusi"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[
            KeyboardButton(text="📊 Statistika"),
            KeyboardButton(text="👥 Tyutorlarni ko'rish"),
            KeyboardButton(text="➕ Tyutor qo'shish"),
            KeyboardButton(text="✏️ Tyutor tahrirlash"),
        ]],
        resize_keyboard=True
    )
    
    await message.answer(
        "⚙️ ADMIN PANEL\n\n"
        "Kerakli amalni tanlang:",
        reply_markup=keyboard
    )

@dp.message(F.text == "➕ Tyutor qo'shish")
async def add_Tyutor_start(message: Message, state: FSMContext):
    """Tyutor qo'shish jarayonini boshlash"""
    if not FACULTIES:
        await message.answer("❌ Hech qanday fakultet topilmadi!")
        return
    
    keyboard_buttons = []
    for faculty in FACULTIES.keys():
        keyboard_buttons.append([KeyboardButton(text=faculty)])
    
    keyboard_buttons.append([KeyboardButton(text="🔙 Orqaga qaytish")])
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=keyboard_buttons,
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(
        "Tyutor qaysi fakultetda ishlaydi?",
        reply_markup=keyboard
    )
    await state.set_state(AdminStates.adding_Tyutor_faculty)

@dp.message(AdminStates.adding_Tyutor_faculty)
async def add_Tyutor_faculty_selected(message: Message, state: FSMContext):
    """Fakultetni tanlangan"""
    if message.text == "🔙 Orqaga qaytish":
        await state.clear()
        await admin_menu(message, state)
        return
    
    faculty = message.text.strip()
    
    if faculty not in FACULTIES:
        await message.answer(f"❌ Noto'g'ri fakultet!")
        return
    
    await state.update_data(faculty=faculty)
    await message.answer("Tyutor nomini kiriting:")
    await state.set_state(AdminStates.adding_Tyutor_name)

@dp.message(AdminStates.adding_Tyutor_name)
async def add_Tyutor_name(message: Message, state: FSMContext):
    """Tyutor nomini qabul qilish"""
    Tyutor_name = message.text.strip()
    
    if not Tyutor_name or len(Tyutor_name) < 2:
        await message.answer("Iltimos, to'g'ri ism kiriting:")
        return
    
    await state.update_data(Tyutor_name=Tyutor_name)
    await message.answer("Tyutor Telegram ID raqamini kiriting (masalan: 123456789):")
    await state.set_state(AdminStates.adding_Tyutor_chat_id)

@dp.message(AdminStates.adding_Tyutor_chat_id)
async def add_Tyutor_chat_id(message: Message, state: FSMContext):
    """Tyutor Telegram ID sini qabul qilish"""
    try:
        chat_id = int(message.text.strip())
    except ValueError:
        await message.answer("Iltimos, raqam kiriting:")
        return
    
    data = await state.get_data()
    faculty = data.get("faculty")
    Tyutor_name = data.get("Tyutor_name")
    
    new_Tyutor = {"name": Tyutor_name, "chat_id": chat_id}
    FACULTIES[faculty].append(new_Tyutor)
    
    save_faculties(FACULTIES)
    
    print(f" ✅ Tyutor qo'shildi: {Tyutor_name} ({chat_id}) - {faculty}")
    
    await message.answer(
        f"✅ Tyutor qo'shildi!\n\n"
        f"📚 Fakultet: {faculty}\n"
        f"👤 Ism: {Tyutor_name}\n"
        f"🆔 Telegram ID: {chat_id}\n\n"
        f"✨ Tyutor avtomatik saqlandi va ishlaydi!"
    )
    
    await state.clear()
    await admin_menu(message, state)

@dp.message(F.text == "📊 Statistika")
async def show_statistics(message: Message):
    """Statistika ko'rsatish"""
    stat_text = "📊 STATISTIKA\n\n"
    
    stat_by_faculty = {}
    for req_id, req in requests_data.items():
        faculty = req["faculty"]
        if faculty not in stat_by_faculty:
            stat_by_faculty[faculty] = {"total": 0, "accepted": 0, "rejected": 0, "finished": 0, "pending": 0, "cancelled": 0}
        
        stat_by_faculty[faculty]["total"] += 1
        stat_by_faculty[faculty][req["status"]] += 1
    
    if not stat_by_faculty:
        stat_text += "Murojat yo'q"
    else:
        for faculty, stats in stat_by_faculty.items():
            stat_text += (
                f"📚 {faculty}\n"
                f"  Jami: {stats['total']} | ⏳ Kutilmoqda: {stats['pending']} | "
                f"✅ Qabul: {stats['accepted']} | ❌ Rad: {stats['rejected']} | "
                f"✔️ Tugallagan: {stats['finished']}\n\n"
            )
    
    await message.answer(stat_text)

@dp.message(F.text == "👥 Tyutorlarni ko'rish")
async def view_Tyutors_admin(message: Message):
    """Tyutorlarni ko'rish"""
    text = "👥 TyutorLAR RO'YXATI\n\n"
    
    for faculty, Tyutors in FACULTIES.items():
        text += f"📚 {faculty}:\n"
        for Tyutor in Tyutors:
            text += f"  • {Tyutor['name']} (ID: {Tyutor['chat_id']})\n"
        text += "\n"
    
    await message.answer(text)

@dp.message(F.text == "✏️ Tyutor tahrirlash")
async def edit_Tyutor_start(message: Message, state: FSMContext):
    """Tyutor tahrirlash jarayonini boshlash"""
    if not FACULTIES:
        await message.answer("❌ Hech qanday fakultet topilmadi!")
        return
    
    keyboard_buttons = []
    for faculty in FACULTIES.keys():
        keyboard_buttons.append([KeyboardButton(text=faculty)])
    
    keyboard_buttons.append([KeyboardButton(text="🔙 Orqaga qaytish")])
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=keyboard_buttons,
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(
        "Tyutori qaysi fakultetda?",
        reply_markup=keyboard
    )
    await state.set_state(AdminStates.editing_Tyutor_faculty)

@dp.message(AdminStates.editing_Tyutor_faculty)
async def edit_Tyutor_faculty_selected(message: Message, state: FSMContext):
    """Tahrirlash uchun fakultetni tanlash"""
    if message.text == "🔙 Orqaga qaytish":
        await state.clear()
        await admin_menu(message, state)
        return
    
    faculty = message.text.strip()
    
    if faculty not in FACULTIES:
        await message.answer(f"❌ Noto'g'ri fakultet!")
        return
    
    await state.update_data(edit_faculty=faculty)
    
    Tyutors = FACULTIES[faculty]
    if not Tyutors:
        await message.answer(f"❌ {faculty} da Tyutor yo'q!")
        await state.clear()
        await admin_menu(message, state)
        return
    
    keyboard_buttons = []
    for Tyutor in Tyutors:
        keyboard_buttons.append([KeyboardButton(text=f"{Tyutor['name']} ({Tyutor['chat_id']})")])
    
    keyboard_buttons.append([KeyboardButton(text="🔙 Orqaga qaytish")])
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=keyboard_buttons,
        resize_keyboard=True
    )
    
    await message.answer(
        "Tahrirlash uchun Tyutorini tanlang:",
        reply_markup=keyboard
    )
    await state.set_state(AdminStates.selecting_Tyutor_to_edit)

@dp.message(StateFilter(AdminStates.selecting_Tyutor_to_edit))
async def edit_Tyutor_selected(message: Message, state: FSMContext):
    """Tahrirlash uchun Tyutor tanlash"""
    data = await state.get_data()
    faculty = data.get("edit_faculty")
    
    if not faculty or faculty not in FACULTIES:
        await message.answer("❌ Fakultet topilmadi!")
        return
    
    Tyutors = FACULTIES[faculty]
    Tyutor_name = message.text.strip()
    
    if " (" in Tyutor_name:
        Tyutor_name = Tyutor_name.split(" (")[0].strip()
    
    Tyutor_to_edit = None
    Tyutor_index = None
    
    # Find the Tyutor by name
    for idx, Tyutor in enumerate(Tyutors):
        if Tyutor['name'].strip() == Tyutor_name:
            Tyutor_to_edit = Tyutor.copy()
            Tyutor_index = idx
            break
    
    if not Tyutor_to_edit:
        await message.answer(f"❌ '{Tyutor_name}' nomli Tyutor topilmadi!")
        return
    
    await state.update_data(
        Tyutor_to_edit=Tyutor_to_edit, 
        Tyutor_index=Tyutor_index,
        Tyutor_name_original=Tyutor_to_edit['name'],
        Tyutor_id_original=Tyutor_to_edit['chat_id']
    )
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[
            KeyboardButton(text="👤 Ismni o'zgaritirish"),
            KeyboardButton(text="🆔 ID sini o'zgaritirish"),
            KeyboardButton(text="❌ Bekor qilish")
        ]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(
        f"👨‍🏫 {Tyutor_to_edit['name']} (ID: {Tyutor_to_edit['chat_id']})\n\n"
        "Nima o'zgaritira olsiz?",
        reply_markup=keyboard
    )
    await state.set_state(AdminStates.editing_Tyutor_name)

@dp.message(StateFilter(AdminStates.editing_Tyutor_name), F.text == "👤 Ismni o'zgaritirish")
async def edit_Tyutor_name_prompt(message: Message, state: FSMContext):
    """Ismni o'zgaritirish uchun so'rash"""
    await message.answer(
        "📝 Yangi ismni kiriting:",
        reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Bekor qilish")]], resize_keyboard=True)
    )
    await state.set_state(AdminStates.editing_Tyutor_name)

@dp.message(StateFilter(AdminStates.editing_Tyutor_name), F.text != "🆔 ID sini o'zgaritirish")
async def edit_Tyutor_name_save(message: Message, state: FSMContext):
    """Ismni o'zgaritirish"""
    if message.text == "❌ Bekor qilish":
        await message.answer("Bekor qilindi!")
        await state.clear()
        return
    
    if message.text == "👤 Ismni o'zgaritirish":
        await edit_Tyutor_name_prompt(message, state)
        return
    
    data = await state.get_data()
    faculty = data.get("edit_faculty")
    Tyutor_index = data.get("Tyutor_index")
    old_name = data.get("Tyutor_name_original")
    new_name = message.text.strip()
    
    if not faculty or Tyutor_index is None:
        await message.answer("❌ Xato: Ma'lumot topilmadi!")
        await state.clear()
        return
    
    try:
        FACULTIES[faculty][Tyutor_index]['name'] = new_name
        
        save_faculties(FACULTIES)
        
        await message.answer(
            f"✅ Ismni o'zgaritirish: '{old_name}' → '{new_name}'\n\n"
            f"✨ O'zgarish avtomatik saqlandi!"
        )
        
        print(f" ✅ Ismni o'zgaritirish: '{old_name}' -> '{new_name}'")
    except Exception as e:
        await message.answer(f"❌ Xato: {str(e)}")
    
    await state.clear()

@dp.message(StateFilter(AdminStates.editing_Tyutor_name), F.text == "🆔 ID sini o'zgaritirish")
async def edit_Tyutor_id_prompt(message: Message, state: FSMContext):
    """ID sini o'zgaritirish uchun so'rash"""
    await message.answer(
        "🆔 Yangi Telegram ID ni kiriting:",
        reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Bekor qilish")]], resize_keyboard=True)
    )
    await state.set_state(AdminStates.editing_Tyutor_chat_id)

@dp.message(StateFilter(AdminStates.editing_Tyutor_chat_id))
async def edit_Tyutor_id_save(message: Message, state: FSMContext):
    """ID sini o'zgaritirish"""
    if message.text == "❌ Bekor qilish":
        await message.answer("Bekor qilindi!")
        await state.clear()
        return
    
    data = await state.get_data()
    faculty = data.get("edit_faculty")
    Tyutor_index = data.get("Tyutor_index")
    old_id = data.get("Tyutor_id_original")
    
    if not faculty or Tyutor_index is None:
        await message.answer("❌ Xato: Ma'lumot topilmadi!")
        await state.clear()
        return
    
    try:
        new_id = int(message.text.strip())
        FACULTIES[faculty][Tyutor_index]['chat_id'] = new_id
        
        save_faculties(FACULTIES)
        
        await message.answer(
            f"✅ ID o'zgaritildi: {old_id} → {new_id}\n\n"
            f"✨ O'zgarish avtomatik saqlandi!"
        )
        
        print(f" ✅ ID o'zgaritirish: {old_id} -> {new_id}")
    except ValueError:
        await message.answer("❌ Xato: ID raqam bo'lishi kerak!")
    except Exception as e:
        await message.answer(f"❌ Xato: {str(e)}")
    
    await state.clear()

@dp.message(F.text == "❌ Bekor qilish")
async def cancel_operation(message: Message, state: FSMContext):
    """Birorta operatsiyani bekor qilish"""
    await message.answer("Bekor qilindi!")
    await state.clear()
    await admin_menu(message, state)

# ===== MAIN =====

async def main():
    print(f"\n{'='*60}")
    print(f" 🤖 BOT ISHGA TUSHMOQDA...")
    print(f" Admin ID: {ADMIN_ID}")
    print(f" Jami fakultetlar: {len(FACULTIES)}")
    print(f"{'='*60}\n")
    
    try:
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        print(" Bot to'xtatildi (Ctrl+C)")
    except Exception as e:
        print(f" ❌ Xato: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n Bot xususiy to'xtatildi.")
