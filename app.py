import os
from io import BytesIO
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    CallbackContext,
    CallbackQueryHandler,
)
from PIL import Image, ImageDraw, ImageFont
from bidi.algorithm import get_display
from arabic_reshaper import reshape

# Constants
TOKEN = "8542825604:AAF9Tmk9niAux0smE4n1Q4-ON4EKAGBtdWk"
CHANNEL_ID = -1003861013503
TEMPLATE_IMAGE = "real.jpg"
COUNTER_FILE = "counter.txt"

# Conversation states
NAME, COURSE, SEARCH_TYPE, SEARCH_QUERY = range(4)

def load_counter():
    if not os.path.exists(COUNTER_FILE):
        with open(COUNTER_FILE, "w") as f:
            f.write("8888888888888")
    with open(COUNTER_FILE, "r") as f:
        return int(f.read().strip())

def save_counter(counter):
    with open(COUNTER_FILE, "w") as f:
        f.write(str(counter))

def persian_text(text):
    reshaped_text = reshape(text)
    return get_display(reshaped_text)

async def get_channel_id(update: Update, context: CallbackContext):
    if update.message.forward_from_chat:
        chat_id = update.message.forward_from_chat.id
        chat_title = update.message.forward_from_chat.title or "Unknown"
        await update.message.reply_text(
            f"آیدی کانال/چت:\n`{chat_id}`\n\nنام: {chat_title}"
        )
        print(f"Got channel ID: {chat_id}")
    else:
        await update.message.reply_text(
            "لطفاً یک پیام از کانال خود به این ربات فوروارد کنید!"
        )

async def show_main_menu(update: Update, context: CallbackContext, is_callback=False):
    keyboard = [
        [InlineKeyboardButton("📜 ساخت مدرک جدید", callback_data="new_cert")],
        [InlineKeyboardButton("🔍 جستجوی مدارک", callback_data="search_cert")],
        [InlineKeyboardButton("ℹ️ راهنما", callback_data="help")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "سلام! به ربات ساخت مدرک خوش آمدید!\nیکی از گزینه‌های زیر را انتخاب کنید:"
    if is_callback:
        query = update.callback_query
        try:
            await query.edit_message_text(text=text, reply_markup=reply_markup)
        except Exception:
            await query.message.reply_text(text=text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text=text, reply_markup=reply_markup)

async def start(update: Update, context: CallbackContext):
    await show_main_menu(update, context)

async def button_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    if query.data == "new_cert":
        try:
            await query.edit_message_text(text="لطفاً نام متقاضی را وارد کنید:")
        except Exception:
            await query.message.reply_text(text="لطفاً نام متقاضی را وارد کنید:")
        return NAME
    elif query.data == "search_cert":
        keyboard = [
            [InlineKeyboardButton("🔢 جستجو بر اساس شماره ثبت", callback_data="search_num")],
            [InlineKeyboardButton("👤 جستجو بر اساس نام متقاضی", callback_data="search_name")],
            [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="main_menu")]
        ]
        try:
            await query.edit_message_text("نحوه جستجو را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception:
            await query.message.reply_text("نحوه جستجو را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))
        return ConversationHandler.END
    elif query.data == "search_num":
        context.user_data["search_type"] = "number"
        try:
            await query.edit_message_text("شماره ثبت را وارد کنید:")
        except Exception:
            await query.message.reply_text("شماره ثبت را وارد کنید:")
        return SEARCH_QUERY
    elif query.data == "search_name":
        context.user_data["search_type"] = "name"
        try:
            await query.edit_message_text("نام متقاضی را وارد کنید:")
        except Exception:
            await query.message.reply_text("نام متقاضی را وارد کنید:")
        return SEARCH_QUERY
    elif query.data == "help":
        help_text = """راهنما:
1. ساخت مدرک جدید: نام و دوره را وارد کنید تا مدرک ساخته شود
2. جستجوی مدارک: بر اساس شماره ثبت یا نام متقاضی جستجو کنید
3. برای دریافت آیدی کانال، یک پیام از کانال به ربات فوروارد کنید!"""
        back_keyboard = [[InlineKeyboardButton("🔙 بازگشت به منو", callback_data="main_menu")]]
        try:
            await query.edit_message_text(text=help_text, reply_markup=InlineKeyboardMarkup(back_keyboard))
        except Exception:
            await query.message.reply_text(text=help_text, reply_markup=InlineKeyboardMarkup(back_keyboard))
        return ConversationHandler.END
    elif query.data == "main_menu":
        await show_main_menu(update, context, is_callback=True)
        return ConversationHandler.END
    elif query.data == "send_cert":
        reg_number = context.user_data.get("reg_number")
        cert_data = context.user_data.get("cert_data")
        name = context.user_data.get("name")
        course = context.user_data.get("course")
        
        if reg_number and cert_data:
            # Rewind the BytesIO object before using it
            cert_data.seek(0)
            await query.message.reply_photo(
                photo=cert_data,
                caption=f"مدرک شما - شماره ثبت: {reg_number}"
            )
            # Archive to channel
            await archive_to_channel_with_photo(
                context.bot,
                name,
                course,
                reg_number,
                cert_data
            )
        return ConversationHandler.END

async def handle_search_query(update: Update, context: CallbackContext):
    search_type = context.user_data.get("search_type")
    search_query = update.message.text.strip()
    
    status_msg = await update.message.reply_text("در حال جستجو...")
    
    try:
        found = False
        messages = []
        
        chat = await context.bot.get_chat(CHANNEL_ID)
        
        # Try to get some updates
        updates = await context.bot.get_updates(limit=100, allowed_updates=["message"])
        for u in updates:
            if u.message and u.message.chat_id == CHANNEL_ID:
                messages.append(u.message)
        
        if not found and messages:
            for msg in reversed(messages):
                text_to_search = msg.caption or msg.text or ""
                if search_type == "number" and search_query in text_to_search:
                    await status_msg.delete()
                    await update.message.reply_text("مدرک پیدا شد!")
                    if msg.photo:
                        await update.message.reply_photo(
                            photo=msg.photo[-1].file_id,
                            caption=text_to_search
                        )
                    else:
                        await update.message.reply_text(text_to_search)
                    found = True
                    break
                elif search_type == "name" and search_query in text_to_search:
                    await status_msg.delete()
                    await update.message.reply_text("مدرک پیدا شد!")
                    if msg.photo:
                        await update.message.reply_photo(
                            photo=msg.photo[-1].file_id,
                            caption=text_to_search
                        )
                    else:
                        await update.message.reply_text(text_to_search)
                    found = True
                    break
        
        if not found:
            await status_msg.delete()
            await update.message.reply_text("مدرکی یافت نشد!")
            
    except Exception as e:
        await status_msg.delete()
        await update.message.reply_text(f"خطا در جستجو: {e}")
        print(f"Search error: {e}")
        import traceback
        traceback.print_exc()
    
    await show_main_menu(update, context)
    return ConversationHandler.END

async def get_name(update: Update, context: CallbackContext):
    context.user_data["name"] = update.message.text
    await update.message.reply_text("لطفاً نام دوره را وارد کنید:")
    return COURSE

async def get_course(update: Update, context: CallbackContext):
    context.user_data["course"] = update.message.text
    counter = load_counter()
    reg_number = counter
    context.user_data["reg_number"] = reg_number
    
    # Generate certificate in memory
    cert_data = generate_certificate(
        context.user_data["name"],
        context.user_data["course"],
        reg_number
    )
    context.user_data["cert_data"] = cert_data
    
    save_counter(counter + 1)
    
    keyboard = [
        [InlineKeyboardButton("ارسال مدرک", callback_data="send_cert")],
        [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Rewind before sending
    cert_data.seek(0)
    await update.message.reply_photo(
        photo=cert_data,
        caption=f"مدرک شما با موفقیت ایجاد شد!\nشماره ثبت: {reg_number}",
        reply_markup=reply_markup
    )
    
    await archive_to_channel(
        context.bot,
        context.user_data["name"],
        context.user_data["course"],
        reg_number
    )
    
    return ConversationHandler.END

def generate_certificate(name, course, reg_number):
    img = Image.open(TEMPLATE_IMAGE)
    draw = ImageDraw.Draw(img)
    
    # Load bundled font first, then fallback to system fonts
    font = None
    bundled_font_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Vazirmatn-Regular.ttf")
    
    if os.path.exists(bundled_font_path):
        try:
            font = ImageFont.truetype(bundled_font_path, 36)
        except Exception as e:
            print(f"Couldn't load bundled font: {e}")
    
    if font is None:
        font_paths = [
            "C:/Windows/Fonts/tahoma.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
        ]
        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    font = ImageFont.truetype(font_path, 36)
                    break
                except:
                    continue
    
    if font is None:
        font = ImageFont.load_default()
    
    persian_name = persian_text(name)
    persian_course = persian_text(course)
    
    course_x, course_y = 1845, 730
    name_x, name_y = 1845, 500
    reg_x, reg_y = 1845, 620
    
    draw.text((course_x, course_y), persian_course, font=font, fill=(0, 0, 0), anchor="rs")
    draw.text((name_x, name_y), persian_name, font=font, fill=(0, 0, 0), anchor="rs")
    draw.text((reg_x, reg_y), str(reg_number), font=font, fill=(0, 0, 0), anchor="rs")
    
    # Save to in-memory BytesIO instead of file
    img_byte_arr = BytesIO()
    img.save(img_byte_arr, format='JPEG')
    img_byte_arr.name = f"certificate_{reg_number}.jpg"
    return img_byte_arr

async def archive_to_channel(bot, name, course, reg_number):
    message = f"آرشیو مدرک:\nنام متقاضی: {name}\nنام دوره: {course}\nشماره ثبت: {reg_number}"
    try:
        await bot.send_message(chat_id=CHANNEL_ID, text=message)
        print("Successfully archived to channel!")
    except Exception as e:
        print(f"Error archiving to channel: {e}")
        import traceback
        traceback.print_exc()

async def archive_to_channel_with_photo(bot, name, course, reg_number, cert_data):
    message = f"آرشیو مدرک کامل:\nنام متقاضی: {name}\nنام دوره: {course}\nشماره ثبت: {reg_number}"
    try:
        cert_data.seek(0)
        await bot.send_photo(chat_id=CHANNEL_ID, photo=cert_data, caption=message)
        print("Successfully archived photo to channel!")
    except Exception as e:
        print(f"Error archiving photo to channel: {e}")
        import traceback
        traceback.print_exc()

async def cancel(update: Update, context: CallbackContext):
    await show_main_menu(update, context)
    return ConversationHandler.END

def main():
    application = Application.builder().token(TOKEN).build()
    
    search_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_callback, pattern="^search_num$|^search_name$")],
        states={SEARCH_QUERY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search_query)]},
        fallbacks=[CommandHandler("cancel", cancel), CallbackQueryHandler(button_callback)],
        allow_reentry=True
    )
    
    cert_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_callback, pattern="^new_cert$")],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            COURSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_course)]
        },
        fallbacks=[CommandHandler("cancel", cancel), CallbackQueryHandler(button_callback)],
        allow_reentry=True
    )
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("getid", get_channel_id))
    application.add_handler(MessageHandler(filters.FORWARDED, get_channel_id))
    application.add_handler(search_conv)
    application.add_handler(cert_conv)
    application.add_handler(CallbackQueryHandler(button_callback))
    
    print("Bot started!")
    print(f"Using CHANNEL_ID: {CHANNEL_ID}")
    application.run_polling()

if __name__ == "__main__":
    main()