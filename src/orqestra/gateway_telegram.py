#!/usr/bin/env python3
"""Telegram gateway for Orqestra — Long Polling (no inbound port).

Uses the same config, wiki, and skills as the CLI (`build_engine` from orqestra.core.bootstrap).

Environment / config:
  - telegram.token or TELEGRAM_BOT_TOKEN (via ${TELEGRAM_BOT_TOKEN} in config.yaml)
  - telegram.require_whitelist (default: true) — only merged allowed_* IDs may use the bot
  - Open access (any user) requires allow_insecure_open_access: true or TELEGRAM_INSECURE_OPEN_ACCESS=1
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import queue
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from orqestra._paths import REPO_ROOT as ROOT

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from orqestra.capabilities.files import format_upload_user_message, process_upload
from orqestra.core.bootstrap import build_engine, load_config, resolve_env
from orqestra.core.department_builder import DepartmentBuilderSession
from orqestra.core.departments import DepartmentRegistry
from orqestra.core.engine import StrategyEngine

TELEGRAM_MAX_MESSAGE = 4096
SESSION_IDLE_SECONDS = 24 * 3600

log = logging.getLogger(__name__)


@dataclass
class ChatSession:
    history: list[dict] = field(default_factory=list)
    last_seen: float = field(default_factory=time.time)


def split_for_telegram(text: str, limit: int = TELEGRAM_MAX_MESSAGE) -> list[str]:
    """Split long assistant output into Telegram-sized chunks (UTF-8 safe)."""
    if not text:
        return [""]
    chunks: list[str] = []
    rest = text
    while rest:
        if len(rest) <= limit:
            chunks.append(rest)
            break
        cut = rest.rfind("\n", 1, limit + 1)
        if cut <= 0 or cut < limit // 2:
            cut = limit
        chunks.append(rest[:cut].rstrip())
        rest = rest[cut:].lstrip()
    return chunks


def format_jobs_status(registry: DepartmentRegistry) -> str:
    """Plain-text job list for Telegram (no ANSI)."""
    jobs = registry.jobs_for_display()
    if not jobs:
        return "Keine Background-Jobs."
    lines = ["Background-Jobs:"]
    for j in jobs:
        preview = j.task.replace("\n", " ")[:80]
        if len(j.task) > 80:
            preview += "…"
        lines.append(
            f"• {j.id} — {j.status()} — {j.elapsed_seconds():.0f}s — {preview}"
        )
    return "\n".join(lines)


def format_job_result_text(job) -> str:
    """Plain-text result for one job."""
    st = job.status()
    result, err = job.result_or_error()
    if err:
        return f"{job.id} ({st}): Fehler — {err}"
    if result is None:
        return f"{job.id} ({st}): (noch kein Ergebnis)"
    body = result if isinstance(result, str) else str(result)
    if len(body) > 12000:
        body = body[:11900] + "\n\n[… gekürzt …]"
    return f"{job.id} ({st}):\n\n{body}"


_TYPING_INTERVAL = 4.0
_EDIT_COOLDOWN = 1.5


def _html_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _format_progress_html(
    steps: list[tuple[str, str]],
    current_label: str = "",
) -> str:
    """Build an HTML-formatted progress message for Telegram."""
    parts = ["<b>Verarbeite…</b>\n"]
    for name, preview in steps:
        esc = _html_escape(preview)
        if len(esc) > 55:
            esc = esc[:52] + "…"
        line = f"  • <code>{name}</code>"
        if esc:
            line += f"  {esc}"
        parts.append(line)
    if current_label:
        parts.append(f"\n<i>{_html_escape(current_label)}…</i>")
    return "\n".join(parts)


def _merge_allowed_ids(tg: dict) -> set[int]:
    """Merge allowed_chat_ids and allowed_user_ids (same numeric space for private DMs)."""
    ids: set[int] = set()
    for key in ("allowed_chat_ids", "allowed_user_ids"):
        for x in tg.get(key) or []:
            ids.add(int(x))
    return ids


def validate_telegram_access(cfg: dict) -> None:
    """Enforce whitelist by default; open access only with explicit insecure opt-in."""
    tg = cfg.get("telegram") or {}
    require = tg.get("require_whitelist", True)
    ids = _merge_allowed_ids(tg)

    if require:
        if not ids:
            log.error(
                "telegram.require_whitelist is true (default) but allowed_user_ids / "
                "allowed_chat_ids is empty — refusing to start. Add at least one numeric "
                "Telegram user or chat ID so only those clients can use the bot."
            )
            sys.exit(1)
        log.info("Telegram access: whitelist only (%d id(s) configured).", len(ids))
        return

    insecure_env = os.environ.get("TELEGRAM_INSECURE_OPEN_ACCESS", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    insecure_cfg = tg.get("allow_insecure_open_access", False) is True
    if not (insecure_env or insecure_cfg):
        log.error(
            "telegram.require_whitelist is false but open access is not permitted without "
            "an explicit opt-in. To allow only specific users, set require_whitelist: true "
            "and list allowed_user_ids / allowed_chat_ids. "
            "For local testing only, set allow_insecure_open_access: true in config.yaml "
            "or TELEGRAM_INSECURE_OPEN_ACCESS=1 in the environment."
        )
        sys.exit(1)

    log.warning(
        "SECURITY: Telegram bot is in OPEN ACCESS mode (any user can chat). "
        "Use only for development. Production: require_whitelist: true and a non-empty whitelist."
    )


class TelegramGateway:
    """Holds engine, registry, and per-chat sessions."""

    def __init__(
        self,
        cfg: dict,
        *,
        engine: StrategyEngine | None = None,
        registry: DepartmentRegistry | None = None,
        pipeline_runner: object | None = None,
    ) -> None:
        self.cfg = cfg
        self.engine: StrategyEngine
        self.registry: DepartmentRegistry
        if engine and registry and pipeline_runner:
            self.engine = engine
            self.registry = registry
            self.pipeline_runner = pipeline_runner
            self._owns_registry = False
        else:
            self.engine, self.registry, self.pipeline_runner = build_engine(cfg, headless=True)
            self._owns_registry = True
        self.sessions: dict[int, ChatSession] = {}
        tg = cfg.get("telegram") or {}
        require_whitelist = tg.get("require_whitelist", True)
        ids = _merge_allowed_ids(tg)
        if require_whitelist:
            self.allowed_chat_ids: set[int] | None = ids
        else:
            self.allowed_chat_ids = ids if ids else None
        self.builder_sessions: dict[int, DepartmentBuilderSession] = {}

    def is_allowed(self, chat_id: int, user_id: int | None = None) -> bool:
        """Allow if chat is whitelisted (e.g. group) or user is whitelisted (private DM or group)."""
        if self.allowed_chat_ids is None:
            return True
        if chat_id in self.allowed_chat_ids:
            return True
        if user_id is not None and user_id in self.allowed_chat_ids:
            return True
        log.warning(
            "Blocked unauthorized access chat_id=%s user_id=%s",
            chat_id,
            user_id,
        )
        return False

    def prune_stale_sessions(self) -> None:
        now = time.time()
        stale = [
            cid
            for cid, s in self.sessions.items()
            if now - s.last_seen > SESSION_IDLE_SECONDS
        ]
        for cid in stale:
            del self.sessions[cid]
            log.debug("Pruned idle session chat_id=%s", cid)

    def session_for(self, chat_id: int) -> ChatSession:
        if chat_id not in self.sessions:
            self.sessions[chat_id] = ChatSession()
        s = self.sessions[chat_id]
        s.last_seen = time.time()
        return s


async def reply_text_chunks(update: Update, text: str) -> None:
    """Send multi-chunk replies; render Markdown via telegramify-markdown when installed."""
    if update.message is None:
        return
    if not text:
        await update.message.reply_text("")
        return

    try:
        from telegramify_markdown import convert, split_entities
    except ImportError:
        for part in split_for_telegram(text):
            await update.message.reply_text(part)
        return

    try:
        plain, entities = convert(text)
        chunks = list(split_entities(plain, entities, max_utf16_len=4096))
    except Exception as exc:
        log.warning("Markdown→Telegram-Konvertierung fehlgeschlagen (%s), sende Klartext.", exc)
        for part in split_for_telegram(text):
            await update.message.reply_text(part)
        return

    for chunk_text, chunk_ents in chunks:
        ent_list = [e.to_dict() for e in chunk_ents] if chunk_ents else None
        try:
            await update.message.reply_text(chunk_text, entities=ent_list)
        except Exception as exc:
            log.warning("Telegram reply_text mit entities fehlgeschlagen (%s), nur Text.", exc)
            await update.message.reply_text(chunk_text)


def build_application(gw: TelegramGateway, token: str) -> Application:
    def _user_id(update: Update) -> int | None:
        return update.effective_user.id if update.effective_user else None

    async def cmd_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_chat is None or update.message is None:
            return
        cid = update.effective_chat.id
        if not gw.is_allowed(cid, _user_id(update)):
            await update.message.reply_text("Zugriff verweigert.")
            return
        gw.sessions[cid] = ChatSession()
        gw.builder_sessions.pop(cid, None)
        await update.message.reply_text("Neue Konversation — Verlauf zurückgesetzt.")

    async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_chat is None or update.message is None:
            return
        cid = update.effective_chat.id
        if not gw.is_allowed(cid, _user_id(update)):
            await update.message.reply_text("Zugriff verweigert.")
            return
        if len(gw.registry) == 0:
            await update.message.reply_text("Keine Departments geladen.")
            return
        text = format_jobs_status(gw.registry)
        await reply_text_chunks(update, text)

    async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_chat is None or update.message is None:
            return
        cid = update.effective_chat.id
        if not gw.is_allowed(cid, _user_id(update)):
            await update.message.reply_text("Zugriff verweigert.")
            return
        if len(gw.registry) == 0:
            await update.message.reply_text("Keine Departments.")
            return
        args = context.args or []
        if not args:
            await update.message.reply_text("Nutze: /stop <job_id>  (z. B. /stop seo-1)")
            return
        job_id = args[0].strip()
        out = gw.registry.cancel_job(job_id)
        if "error" in out:
            await update.message.reply_text(f"Fehler: {out['error']}")
        else:
            await update.message.reply_text(f"Stopp angefordert für {out.get('job_id', job_id)}.")

    async def cmd_results(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_chat is None or update.message is None:
            return
        cid = update.effective_chat.id
        if not gw.is_allowed(cid, _user_id(update)):
            await update.message.reply_text("Zugriff verweigert.")
            return
        if len(gw.registry) == 0:
            await update.message.reply_text("Keine Departments.")
            return
        args = context.args or []
        if not args:
            text = format_jobs_status(gw.registry)
            await reply_text_chunks(update, text)
            return
        job_id = args[0].strip()
        job = gw.registry.get_job(job_id)
        if not job:
            await update.message.reply_text(f"Unbekannte Job-ID: {job_id}")
            return
        await reply_text_chunks(update, format_job_result_text(job))

    async def cmd_department(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_chat is None or update.message is None:
            return
        cid = update.effective_chat.id
        if not gw.is_allowed(cid, _user_id(update)):
            await update.message.reply_text("Zugriff verweigert.")
            return
        session = DepartmentBuilderSession(
            engine=gw.engine,
            registry=gw.registry,
            cfg=gw.cfg,
            root=ROOT,
        )
        gw.builder_sessions[cid] = session
        resp = session.start()
        await reply_text_chunks(update, resp.text)

    async def cmd_cancel_builder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_chat is None or update.message is None:
            return
        cid = update.effective_chat.id
        if not gw.is_allowed(cid, _user_id(update)):
            await update.message.reply_text("Zugriff verweigert.")
            return
        if cid in gw.builder_sessions:
            del gw.builder_sessions[cid]
            await update.message.reply_text("Department-Generator abgebrochen.")
        else:
            await update.message.reply_text("Kein aktiver Department-Generator.")

    async def run_engine_for_message(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        user_text: str,
    ) -> None:
        if update.effective_chat is None or update.message is None:
            return
        cid = update.effective_chat.id
        if not gw.is_allowed(cid, _user_id(update)):
            await update.message.reply_text("Zugriff verweigert.")
            return

        gw.prune_stale_sessions()
        session = gw.session_for(cid)

        active_jobs = gw.registry.active_jobs_info() if len(gw.registry) > 0 else None
        session.history = gw.engine.summarize_if_needed(session.history, active_jobs=active_jobs)

        progress_q: queue.Queue[tuple[str, str, str]] = queue.Queue()

        def _on_tool_call(name: str, preview: str, fn_args: dict | None = None) -> None:
            progress_q.put(("tool", name, preview))

        def _on_thinking(label: str, preview: str = "") -> None:
            progress_q.put(("thinking", label, preview))

        status_msg = await context.bot.send_message(
            chat_id=cid,
            text="<b>Verarbeite…</b>\n\n<i>Denke nach…</i>",
            parse_mode="HTML",
        )

        engine_task = asyncio.ensure_future(
            asyncio.to_thread(
                gw.engine.run,
                user_text,
                session.history,
                on_tool_call=_on_tool_call,
                on_thinking=_on_thinking,
            )
        )

        tool_steps: list[tuple[str, str]] = []
        current_label = "Denke nach"
        last_edit = 0.0
        last_typing = time.time()

        while not engine_task.done():
            changed = False
            try:
                while True:
                    kind, name, preview = progress_q.get_nowait()
                    if kind == "tool":
                        tool_steps.append((name, preview))
                        changed = True
                    elif kind == "thinking":
                        current_label = name
                        changed = True
            except queue.Empty:
                pass

            now = time.time()

            if changed and now - last_edit >= _EDIT_COOLDOWN:
                try:
                    await status_msg.edit_text(
                        _format_progress_html(tool_steps, current_label),
                        parse_mode="HTML",
                    )
                    last_edit = now
                except Exception:
                    pass

            if now - last_typing >= _TYPING_INTERVAL:
                try:
                    await context.bot.send_chat_action(
                        chat_id=cid, action=ChatAction.TYPING
                    )
                    last_typing = now
                except Exception:
                    pass

            await asyncio.sleep(0.8)

        try:
            answer = engine_task.result()
        except Exception:
            log.exception("engine.run failed")
            try:
                await status_msg.delete()
            except Exception:
                pass
            await update.message.reply_text(
                "Interner Fehler bei der Verarbeitung. Bitte sp\u00e4ter erneut versuchen."
            )
            return

        # Final drain — capture any remaining events
        try:
            while True:
                kind, name, preview = progress_q.get_nowait()
                if kind == "tool":
                    tool_steps.append((name, preview))
        except queue.Empty:
            pass

        if tool_steps:
            try:
                await status_msg.edit_text(
                    _format_progress_html(tool_steps, ""),
                    parse_mode="HTML",
                )
                await asyncio.sleep(0.6)
            except Exception:
                pass

        try:
            await status_msg.delete()
        except Exception:
            pass

        session.history.append({"role": "user", "content": user_text})
        session.history.append({"role": "assistant", "content": answer})

        await reply_text_chunks(update, answer)

    async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_chat is None or update.message is None:
            return
        cid = update.effective_chat.id
        if not gw.is_allowed(cid, _user_id(update)):
            await update.message.reply_text("Zugriff verweigert.")
            return
        text = (update.message.text or "").strip()
        if not text:
            return
        if cid in gw.builder_sessions:
            sess = gw.builder_sessions[cid]
            resp = await asyncio.to_thread(sess.advance, text)
            await reply_text_chunks(update, resp.text)
            if resp.done:
                gw.builder_sessions.pop(cid, None)
            return
        await run_engine_for_message(update, context, text)

    async def on_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_chat is None or update.message is None or update.message.document is None:
            return
        cid = update.effective_chat.id
        if not gw.is_allowed(cid, _user_id(update)):
            await update.message.reply_text("Zugriff verweigert.")
            return
        doc = update.message.document
        caption = (update.message.caption or "").strip()
        tg_file = await context.bot.get_file(doc.file_id)
        orig_name = doc.file_name or "upload"
        suffix = Path(orig_name).suffix or ".bin"
        fd, raw = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        tmp_path = Path(raw)
        try:
            await tg_file.download_to_drive(tmp_path)
            try:
                result = process_upload(
                    tmp_path,
                    doc.mime_type,
                    orig_name,
                    gw.engine.llm,
                    gw.engine.model,
                )
            except ValueError as exc:
                await update.message.reply_text(f"Datei: {exc}")
                return
            combined = format_upload_user_message(
                result.filename,
                result.context_text,
                result.is_image,
                caption,
            )
            await run_engine_for_message(update, context, combined)
        finally:
            tmp_path.unlink(missing_ok=True)

    async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_chat is None or update.message is None or not update.message.photo:
            return
        cid = update.effective_chat.id
        if not gw.is_allowed(cid, _user_id(update)):
            await update.message.reply_text("Zugriff verweigert.")
            return
        photo = update.message.photo[-1]
        caption = (update.message.caption or "").strip()
        tg_file = await context.bot.get_file(photo.file_id)
        fd, raw = tempfile.mkstemp(suffix=".jpg")
        os.close(fd)
        tmp_path = Path(raw)
        try:
            await tg_file.download_to_drive(tmp_path)
            try:
                result = process_upload(
                    tmp_path,
                    "image/jpeg",
                    "photo.jpg",
                    gw.engine.llm,
                    gw.engine.model,
                )
            except ValueError as exc:
                await update.message.reply_text(f"Bild: {exc}")
                return
            combined = format_upload_user_message(
                result.filename,
                result.context_text,
                result.is_image,
                caption,
            )
            await run_engine_for_message(update, context, combined)
        finally:
            tmp_path.unlink(missing_ok=True)

    async def cmd_proactive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_chat is None or update.message is None:
            return
        cid = update.effective_chat.id
        if not gw.is_allowed(cid, _user_id(update)):
            await update.message.reply_text("Zugriff verweigert.")
            return
        args_text = (update.message.text or "").split(None, 2)
        if len(args_text) >= 2 and args_text[1].lower() == "trigger":
            from orqestra.core.scheduler import trigger_now
            count = trigger_now(gw.registry)
            await update.message.reply_text(f"Proaktive Jobs für {count} Departments gestartet.")
        else:
            await update.message.reply_text("Usage: /proactive trigger")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("new", cmd_new))
    app.add_handler(CommandHandler("start", cmd_new))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("results", cmd_results))
    app.add_handler(CommandHandler("proactive", cmd_proactive))
    app.add_handler(CommandHandler("department", cmd_department))
    app.add_handler(CommandHandler("cancel", cmd_cancel_builder))
    app.add_handler(MessageHandler(filters.Document.ALL & ~filters.COMMAND, on_document))
    app.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, on_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    return app


async def _run_polling_no_signals(app: Application) -> None:
    """Like Application.run_polling() but without signal handlers.

    Safe to call from a non-main thread (daemon thread started by main.py).
    """
    async with app:
        await app.start()
        await app.updater.start_polling()
        # Block indefinitely — daemon thread dies with the process.
        await asyncio.Event().wait()


def run_gateway(
    cfg: dict,
    *,
    engine: StrategyEngine | None = None,
    registry: DepartmentRegistry | None = None,
    pipeline_runner: object | None = None,
) -> None:
    """Start the Telegram gateway (blocking — call from a thread or as main).

    Validates access, builds engine + bot, and enters the polling loop.
    When *engine*, *registry*, and *pipeline_runner* are provided (embedded
    mode from ``main.py``), the gateway shares the same runtime objects
    instead of building a separate stack.
    """
    tg = cfg.get("telegram") or {}

    token = resolve_env(tg.get("token", "${TELEGRAM_BOT_TOKEN}"))
    if not token:
        log.error("Missing bot token: set telegram.token or TELEGRAM_BOT_TOKEN in the environment.")
        return

    validate_telegram_access(cfg)

    gw = TelegramGateway(
        cfg,
        engine=engine,
        registry=registry,
        pipeline_runner=pipeline_runner,
    )
    app = build_application(gw, token)

    log.info("Starting Telegram gateway (long polling)\u2026")
    try:
        if threading.current_thread() is threading.main_thread():
            app.run_polling()
        else:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(_run_polling_no_signals(app))
            finally:
                loop.close()
    finally:
        if gw._owns_registry:
            active = gw.registry.active_jobs()
            if active:
                log.info("Stopping %d background job(s)\u2026", len(active))
            gw.registry.shutdown()
        log.info("Telegram gateway shutdown complete.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Orqestra \u2014 Telegram Gateway (Long Polling)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    cfg = load_config()
    tg = cfg.get("telegram") or {}
    if tg.get("enabled") is False:
        log.error("telegram.enabled is false \u2014 exiting.")
        sys.exit(1)

    run_gateway(cfg)


if __name__ == "__main__":
    main()
