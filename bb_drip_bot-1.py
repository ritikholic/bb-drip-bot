import os
import random
import math
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is not set!")


def rand_int(a, b):
    return random.randint(a, b)


def uneven_size(base, variance=55):
    v = variance / 100
    lo = max(101, math.floor(base * (1 - v)))
    hi = math.ceil(base * (1 + v))
    n = rand_int(lo, hi)
    tail = n % 10
    if tail == 0 or tail == 5:
        n += random.choice([-1, 1, 2, -2, 3])
    return max(101, n)


def batch_count(total):
    if total <= 600:
        return rand_int(3, 6)
    elif total <= 1500:
        return rand_int(7, 14)
    elif total <= 3000:
        return rand_int(15, 25)
    elif total <= 6000:
        return rand_int(22, 42)
    elif total <= 15000:
        return rand_int(40, 70)
    else:
        return rand_int(60, 100)


def fmt_time(sec):
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def generate_drip(total_views, window_min, variance=55):
    num_batches = batch_count(total_views)
    base = total_views / num_batches
    batches = [uneven_size(base, variance) for _ in range(num_batches)]
    raw_sum = sum(batches)
    scale = total_views / raw_sum
    batches = [max(101, round(b * scale)) for b in batches]
    diff = total_views - sum(batches)
    batches[-1] += diff
    if batches[-1] < 101:
        batches[-1] = 101
    window_sec = window_min * 60
    times = [0]
    for i in range(1, num_batches):
        base_t = round((i / num_batches) * window_sec)
        jitter = round((random.random() - 0.5) * window_sec * 0.06)
        t = max(1, min(window_sec - 1, base_t + jitter))
        times.append(t)
    times.sort()
    for i in range(1, len(times)):
        if times[i] <= times[i - 1]:
            times[i] = times[i - 1] + rand_int(5, 30)
    if times[-1] > window_sec:
        times[-1] = window_sec
    return [(fmt_time(times[i]), batches[i]) for i in range(num_batches)]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "⚡ *BruceBroke Drip Engine Bot*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Simulate organic, human-like view delivery.\n\n"
        "*Commands:*\n"
        "`/drip <views> <minutes>` — Generate drip plan\n"
        "`/last` — Regenerate last schedule\n"
        "`/help` — Show usage guide\n\n"
        "*Example:*\n"
        "`/drip 5000 60`\n\n"
        "_Powered by BruceBroke SMM Automation_"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📖 *How to use:*\n\n"
        "`/drip [total views] [minutes]`\n\n"
        "*Examples:*\n"
        "`/drip 1000 30`\n"
        "`/drip 5000 60`\n"
        "`/drip 10000 240`\n\n"
        "Use `/last` to re-roll same params 🎲"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def drip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "⚠️ Usage: `/drip <views> <minutes>`\nExample: `/drip 5000 60`",
            parse_mode="Markdown"
        )
        return
    try:
        total = int(args[0])
        window = int(args[1])
    except ValueError:
        await update.message.reply_text("⚠️ Both values must be numbers.")
        return
    if total < 300:
        await update.message.reply_text("⚠️ Minimum 300 views required.")
        return
    if window not in [30, 60, 90, 120, 180, 240, 360, 480, 720, 1440]:
        await update.message.reply_text(
            "⚠️ Valid windows (minutes):\n30, 60, 90, 120, 180, 240, 360, 480, 720, 1440"
        )
        return
    context.user_data['last_total'] = total
    context.user_data['last_window'] = window
    await send_drip(update, context, total, window)


async def last(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total = context.user_data.get('last_total')
    window = context.user_data.get('last_window')
    if not total:
        await update.message.reply_text("No previous schedule. Use `/drip` first.", parse_mode="Markdown")
        return
    await update.message.reply_text("🔄 Re-randomizing...")
    await send_drip(update, context, total, window)


async def send_drip(update, context, total, window):
    await update.message.reply_text("⚙️ Generating drip schedule...")
    schedule = generate_drip(total, window)
    num_batches = len(schedule)
    total_actual = sum(b for _, b in schedule)
    avg_batch = round(total_actual / num_batches)
    window_label = f"{window}m" if window < 60 else f"{window // 60}h"
    header = (
        f"⚡ *BRUCEBROKE DRIP PLAN*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 Total: `{total_actual:,}` views\n"
        f"⏱ Window: `{window_label}`\n"
        f"📦 Batches: `{num_batches}`\n"
        f"∅ Avg: `{avg_batch:,}` per batch\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
    )
    rows = []
    running = 0
    for i, (t, views) in enumerate(schedule):
        running += views
        rows.append(f"`#{i+1:03d}` `{t}` → `{views:,}`  _{running:,}_")
    chunk_size = 30
    chunks = [rows[i:i+chunk_size] for i in range(0, len(rows), chunk_size)]
    await update.message.reply_text(header + "\n".join(chunks[0]), parse_mode="Markdown")
    for chunk in chunks[1:]:
        await update.message.reply_text("\n".join(chunk), parse_mode="Markdown")
    await update.message.reply_text(
        f"✅ *Done! Last drop at {schedule[-1][0]}*\nUse `/last` to re-roll 🎲",
        parse_mode="Markdown"
    )


if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("drip", drip))
    app.add_handler(CommandHandler("last", last))
    print("✅ BruceBroke Drip Bot running...")
    app.run_polling()
