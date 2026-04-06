#!/usr/bin/env python3
"""
بوت تيليجرام لتحميل الفيديوهات
يدعم اختيار الصيغة والجودة قبل التحميل
وصول مقيّد لمستخدم واحد فقط
"""

import os
import asyncio
import tempfile
import subprocess
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# ==================== الإعدادات ====================
BOT_TOKEN = "8430195653:AAFboRTMriG9Eh5zFYvRHDe0697JfuUNAjk"
ALLOWED_USER_ID = 1599638825  # معرّفك الشخصي فقط

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== التحقق من الصلاحية ====================
def is_authorized(user_id: int) -> bool:
    return user_id == ALLOWED_USER_ID

# ==================== جلب معلومات الفيديو ====================
async def get_video_info(url: str) -> dict | None:
    try:
        result = subprocess.run(
            ["yt-dlp", "--dump-json", "--no-playlist", url],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        return None
    except Exception as e:
        logger.error(f"خطأ في جلب معلومات الفيديو: {e}")
        return None

# ==================== الأوامر ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("⛔ غير مصرح لك باستخدام هذا البوت.")
        return
    await update.message.reply_text(
        "👋 أهلاً!\n\n"
        "📥 أرسل لي رابط أي فيديو وسأعطيك خيارات الجودة والصيغة قبل التحميل.\n\n"
        "✅ يدعم: YouTube, TikTok, Instagram, Twitter وأكثر من 1000 موقع."
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return
    await update.message.reply_text(
        "📖 *كيفية الاستخدام:*\n\n"
        "1. أرسل رابط الفيديو مباشرة\n"
        "2. اختر الصيغة: MP4 أو MP3\n"
        "3. اختر الجودة المطلوبة\n"
        "4. انتظر التحميل ✅\n\n"
        "*/start* - بدء البوت\n"
        "*/help* - هذه المساعدة",
        parse_mode="Markdown"
    )

# ==================== معالجة الروابط ====================
async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("⛔ غير مصرح لك.")
        return

    url = update.message.text.strip()

    # التحقق من أن الرسالة رابط
    if not (url.startswith("http://") or url.startswith("https://")):
        await update.message.reply_text("⚠️ أرسل رابط صحيح يبدأ بـ http أو https")
        return

    msg = await update.message.reply_text("🔍 جاري جلب معلومات الفيديو...")

    info = await get_video_info(url)
    if not info:
        await msg.edit_text("❌ تعذّر جلب معلومات الفيديو. تحقق من الرابط.")
        return

    title = info.get("title", "فيديو")[:50]
    duration = info.get("duration", 0)
    mins = int(duration) // 60
    secs = int(duration) % 60

    # حفظ الرابط للاستخدام لاحقاً
    context.user_data["url"] = url
    context.user_data["title"] = title

    # أزرار اختيار الصيغة
    keyboard = [
        [
            InlineKeyboardButton("🎬 MP4 (فيديو)", callback_data="format_mp4"),
            InlineKeyboardButton("🎵 MP3 (صوت فقط)", callback_data="format_mp3"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await msg.edit_text(
        f"✅ *{title}*\n"
        f"⏱ المدة: {mins}:{secs:02d}\n\n"
        f"اختر الصيغة:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# ==================== اختيار الصيغة ====================
async def format_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_authorized(query.from_user.id):
        return

    fmt = query.data.split("_")[1]  # mp4 أو mp3
    context.user_data["format"] = fmt

    if fmt == "mp3":
        # MP3 لا يحتاج اختيار جودة — تحميل مباشر
        await query.edit_message_text("⬇️ جاري تحميل الصوت بأعلى جودة...")
        await download_and_send(query, context, "mp3", "best")
        return

    # خيارات جودة MP4
    keyboard = [
        [InlineKeyboardButton("🔵 1080p (Full HD)", callback_data="quality_1080")],
        [InlineKeyboardButton("🟢 720p (HD)", callback_data="quality_720")],
        [InlineKeyboardButton("🟡 480p", callback_data="quality_480")],
        [InlineKeyboardButton("🔴 360p (خفيف)", callback_data="quality_360")],
        [InlineKeyboardButton("⚡ أفضل جودة متاحة", callback_data="quality_best")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "🎬 اختر جودة الفيديو:",
        reply_markup=reply_markup
    )

# ==================== اختيار الجودة والتحميل ====================
async def quality_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_authorized(query.from_user.id):
        return

    quality = query.data.split("_")[1]
    await query.edit_message_text(f"⬇️ جاري التحميل بجودة {quality}p...")
    await download_and_send(query, context, "mp4", quality)

# ==================== التحميل والإرسال ====================
async def download_and_send(query, context: ContextTypes.DEFAULT_TYPE, fmt: str, quality: str):
    url = context.user_data.get("url")
    if not url:
        await query.edit_message_text("❌ انتهت الجلسة، أرسل الرابط مجدداً.")
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        output_template = os.path.join(tmpdir, "%(title)s.%(ext)s")

        # بناء أمر yt-dlp
        if fmt == "mp3":
            cmd = [
                "yt-dlp",
                "-x", "--audio-format", "mp3",
                "--audio-quality", "0",
                "-o", output_template,
                "--no-playlist",
                url
            ]
        else:
            if quality == "best":
                fmt_selector = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
            else:
                fmt_selector = (
                    f"bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]"
                    f"/best[height<={quality}][ext=mp4]"
                    f"/best[height<={quality}]"
                )
            cmd = [
                "yt-dlp",
                "-f", fmt_selector,
                "--merge-output-format", "mp4",
                "-o", output_template,
                "--no-playlist",
                url
            ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode != 0:
                logger.error(f"yt-dlp error: {result.stderr}")
                await query.edit_message_text(
                    "❌ فشل التحميل.\n"
                    f"السبب: {result.stderr[-200:] if result.stderr else 'غير معروف'}"
                )
                return

            # البحث عن الملف المحمّل
            files = os.listdir(tmpdir)
            if not files:
                await query.edit_message_text("❌ لم يُعثر على الملف بعد التحميل.")
                return

            file_path = os.path.join(tmpdir, files[0])
            file_size = os.path.getsize(file_path)

            # تيليجرام يقبل حتى 50MB
            if file_size > 50 * 1024 * 1024:
                await query.edit_message_text(
                    f"⚠️ حجم الملف كبير جداً ({file_size // (1024*1024)} MB).\n"
                    "جرّب جودة أقل أو صيغة MP3."
                )
                return

            await query.edit_message_text("📤 جاري الإرسال...")

            with open(file_path, "rb") as f:
                title = context.user_data.get("title", "فيديو")
                if fmt == "mp3":
                    await query.message.reply_audio(
                        audio=f,
                        title=title,
                        caption=f"🎵 {title}"
                    )
                else:
                    await query.message.reply_video(
                        video=f,
                        caption=f"🎬 {title}",
                        supports_streaming=True
                    )

            await query.edit_message_text("✅ تم الإرسال بنجاح!")

        except subprocess.TimeoutExpired:
            await query.edit_message_text("⏰ انتهت مهلة التحميل (5 دقائق). جرّب رابطاً أقصر.")
        except Exception as e:
            logger.error(f"خطأ غير متوقع: {e}")
            await query.edit_message_text(f"❌ خطأ: {str(e)[:200]}")

# ==================== التشغيل الرئيسي ====================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(format_choice, pattern="^format_"))
    app.add_handler(CallbackQueryHandler(quality_choice, pattern="^quality_"))

    logger.info("✅ البوت يعمل...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
