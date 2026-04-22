import os
import random
import math
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ── Get token from environment variable ──
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_TOKEN_HERE")


# ══════════════════════════════════════
#  CORE DRIP ENGINE LOGIC
# ══════════════════════════════════════

def rand_int(a, b):
    return random.randint(a, b)


def uneven_size(base, variance=55):
    """Generate organic, non-round batch size"""
    v = variance / 100
    lo = max(101, math.floor(base * (1 - v)))
    hi = math.ceil(base * (1 + v))
    n = rand_int(lo, hi)
    # force last digit to not be 0 or 5 (looks human)
    tail = n % 10
    if tail == 0 or tail == 5:
        n += random.choice([-1, 1, 2, -2, 3])
    return max(101, n)


def batch_count(total):
    """Scale batch count based on total views"""
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
    """Format seconds into mm:ss or hh:mm:ss"""
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def generate_drip(total_views, window_min, variance=55):
    """Main drip generation — returns list of (timestamp_str, batch_size)"""

    num_batches = batch_count(total_views)
    base = total_views / num_batches

    # Generate raw uneven sizes
    batches = [uneven_size(base, variance) for _ in range(num_batches)]

    # Scale to exact total
    raw_sum = sum(batches)
    scale = total_views / raw_sum
    batches = [max(101, round(b * scale)) for b in batches]

    # Fix rounding drift
    diff = total_views - sum(batches)
    batches[-1] += diff
    if batches[-1] < 101:
        batches[-1] = 101

    # Generate random timestamps across window
    window_sec = window_min * 60
    times = [0]
    for i in range(1, num_batches):
        base_t = round((i / num_batches) * window_sec)
        jitter = round((random.random() - 0.5) * window_sec * 0.06)
        t = max(1, min(window_sec - 1, base_t + jitter))
        times.append(t)

    times.sort()

    # Deduplicate
    for i in range(1, len(times)):
        if times[i] <= times[i - 1]:
            times[i] = times[i - 1] + rand_int(5, 30)
    if times[-1] > window_sec:
        times[-1] = window_sec

    return [(fmt_time(times[i]), batches[i]) for i in range(num_batches)]


# ══════════════════════════════════════
#  TELEGRAM COMMAND HANDLERS
# ══════════════════════════════════════

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
        "`/drip 5000 60`\n"
        "→ 5000 views over 60 minutes\n\n"
        "_Powered by BruceBroke SMM Automation_"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📖 *How to use:*\n\n"
        "`/drip [total views] [minutes]`\n\n"
        "*Window options (minutes):*\n"
        "30 · 60 · 90 · 120 · 180\n"
        "240 · 360 · 480 · 720 · 1440\n\n"
        "*Examples:*\n"
        "`/drip 1000 30` — 1k views in 30 min\n"
        "`/drip 5000 60` — 5k views in 1 hour\n"
        "`/drip 10000 240` — 10k views in 4 hours\n\n"
        "Each run is *fully randomized* 🎲\n"
        "Use `/last` to re-roll same params."
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def drip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args

    # Validate input
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
        await update.message.reply_text("⚠️ Both values must be numbers.\nExample: `/drip 5000 60`", parse_mode="Markdown")
        return

    if total < 300:
        await update.message.reply_text("⚠️ Minimum 300 views required.")
        return

    if window not in [30, 60, 90, 120, 180, 240, 360, 480, 720, 1440]:
        await update.message.reply_text(
            "⚠️ Choose a valid window (minutes):\n30, 60, 90, 120, 180, 240, 360, 480, 720, 1440"
        )
        return

    # Save for /last command
    context.user_data['last_total'] = total
    context.user_data['last_window'] = window

    await send_drip(update, context, total, window)


async def last(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total = context.user_data.get('last_total')
    window = context.user_data.get('last_window')

    if not total:
        await update.message.reply_text("No previous schedule found. Use `/drip` first.", parse_mode="Markdown")
        return

    await update.message.reply_text("🔄 Re-randomizing same params...", parse_mode="Markdown")
    await send_drip(update, context, total, window)


async def send_drip(update, context, total, window):
    """Generate and send drip schedule"""
    await update.message.reply_text("⚙️ Generating drip schedule...", parse_mode="Markdown")

    schedule = generate_drip(total, window)
    num_batches = len(schedule)
    total_actual = sum(b for _, b in schedule)
    avg_batch = round(total_actual / num_batches)
    window_label = f"{window}m" if window < 60 else f"{window // 60}h"

    # ── Summary header ──
    header = (
        f"⚡ *BRUCEBROKE DRIP PLAN*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 Total Views: `{total_actual:,}`\n"
        f"⏱ Window: `{window_label}`\n"
        f"📦 Batches: `{num_batches}`\n"
        f"∅ Avg/Batch: `{avg_batch:,}`\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    # ── Build table in chunks (Telegram 4096 char limit) ──
    rows = []
    running = 0
    for i, (t, views) in enumerate(schedule):
        running += views
        rows.append(f"`#{i+1:03d}` `{t}` → `{views:,}` views  _{running:,}_")

    # Split into chunks of 30 rows each
    chunk_size = 30
    chunks = [rows[i:i+chunk_size] for i in range(0, len(rows), chunk_size)]

    # Send header + first chunk
    first_msg = header + "\n".join(chunks[0])
    if len(chunks) > 1:
        first_msg += f"\n\n_...{len(rows) - chunk_size} more batches below_"

    await update.message.reply_text(first_msg, parse_mode="Markdown")

    # Send remaining chunks
    for chunk in chunks[1:]:
        msg = "📋 *continued...*\n\n" + "\n".join(chunk)
        await update.message.reply_text(msg, parse_mode="Markdown")

    # Footer
    footer = (
        f"\n✅ *Delivery complete at {schedule[-1][0]}*\n"
        f"Use `/last` to re-roll this schedule 🎲"
    )
    await update.message.reply_text(footer, parse_mode="Markdown")


# ══════════════════════════════════════
#  MAIN — Start the bot
# ══════════════════════════════════════

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("drip", drip))
    app.add_handler(CommandHandler("last", last))

    print("✅ BruceBroke Drip Bot is running...")
    app.run_polling()
