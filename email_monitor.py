"""Gmail Email Monitor — Desktop app showing inbox + sent emails in real time."""

from __future__ import annotations

import base64
import os
import threading
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from tkinter import ttk
from typing import Any, Optional
import tkinter as tk

import httpx

ENV_FILE = Path(__file__).parent / ".env"
GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REFRESH_INTERVAL = 20  # seconds


def _load_env() -> dict[str, str]:
    """Read Gmail OAuth vars from .env file."""
    if not ENV_FILE.exists():
        return {}
    out = {}
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, val = line.partition("=")
        out[key.strip()] = val.strip()
    return out


class GmailMonitor:
    """Gmail REST client for fetching inbox + sent mail."""

    def __init__(self):
        env = _load_env()
        self.client_id = env.get("INTEGRATION_GMAIL_CLIENT_ID", "")
        self.client_secret = env.get("INTEGRATION_GMAIL_CLIENT_SECRET", "")
        self.refresh_token = env.get("INTEGRATION_GMAIL_REFRESH_TOKEN", "")
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0

    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret and self.refresh_token)

    def _refresh_access_token(self) -> Optional[str]:
        try:
            resp = httpx.post(
                TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": self.refresh_token,
                    "grant_type": "refresh_token",
                },
                timeout=10,
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            self._access_token = data["access_token"]
            self._token_expires_at = time.time() + (data.get("expires_in", 3600) - 60)
            return self._access_token
        except Exception:
            return None

    def _get_token(self) -> Optional[str]:
        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token
        return self._refresh_access_token()

    def fetch_messages(self, label: str = "INBOX", max_results: int = 30) -> list[dict]:
        token = self._get_token()
        if not token:
            return []
        try:
            resp = httpx.get(
                f"{GMAIL_API_BASE}/users/me/messages",
                params={"labelIds": label, "maxResults": max_results},
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            if resp.status_code != 200:
                return []
            return resp.json().get("messages", [])
        except Exception:
            return []

    def get_message_detail(self, msg_id: str) -> Optional[dict]:
        token = self._get_token()
        if not token:
            return None
        try:
            resp = httpx.get(
                f"{GMAIL_API_BASE}/users/me/messages/{msg_id}",
                params={"format": "metadata"},
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            if resp.status_code != 200:
                return None
            return resp.json()
        except Exception:
            return None

    def get_message_full(self, msg_id: str) -> Optional[dict]:
        token = self._get_token()
        if not token:
            return None
        try:
            resp = httpx.get(
                f"{GMAIL_API_BASE}/users/me/messages/{msg_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            if resp.status_code != 200:
                return None
            return resp.json()
        except Exception:
            return None


def decode_body(payload: dict) -> str:
    if "parts" in payload:
        for part in payload["parts"]:
            if part.get("mimeType") == "text/plain" and "data" in part.get("body", {}):
                return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
            if "parts" in part:
                result = decode_body(part)
                if result:
                    return result
    if "body" in payload and "data" in payload["body"]:
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
    return ""


def get_header(headers: list[dict], name: str) -> str:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def _fmt_date(ts_str: str) -> str:
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return dt.strftime("%b %d %I:%M %p")
    except Exception:
        return ts_str[:16] if ts_str else ""


class EmailMonitorApp:
    def __init__(self):
        self.gmail = GmailMonitor()
        self.root = tk.Tk()
        self.root.title("Owlbell Email Monitor")
        self.root.geometry("1000x650")
        self.root.minsize(700, 400)

        if os.name == "nt":
            self.root.iconbitmap(default=None)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=6, pady=6)

        self.inbox_frame = ttk.Frame(self.notebook)
        self.sent_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.inbox_frame, text="📥 Inbox")
        self.notebook.add(self.sent_frame, text="📤 Sent")

        self._build_list(self.inbox_frame, "inbox")
        self._build_list(self.sent_frame, "sent")

        self.status_var = tk.StringVar(value="Starting up...")
        status_bar = tk.Label(self.root, textvariable=self.status_var, bd=1, relief="sunken", anchor="w")
        status_bar.pack(side="bottom", fill="x")

        self.after_id: Optional[str] = None
        self._schedule_refresh()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_list(self, parent: ttk.Frame, kind: str):
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill="x", pady=(0, 4))

        ttk.Button(toolbar, text="⟳ Refresh", command=lambda: self._refresh(kind)).pack(side="left", padx=(0, 4))

        search_var = tk.StringVar()
        search_entry = ttk.Entry(toolbar, textvariable=search_var, width=30)
        search_entry.pack(side="left", padx=(0, 4))
        search_entry.bind("<KeyRelease>", lambda e: self._filter(kind, search_var.get()))

        container = ttk.Frame(parent)
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollable = ttk.Frame(canvas)

        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel, add="+")

        setattr(self, f"_{kind}_canvas", canvas)
        setattr(self, f"_{kind}_scrollable", scrollable)
        setattr(self, f"_{kind}_search_var", search_var)

    def _get_list(self, kind: str):
        return getattr(self, f"_{kind}_scrollable")

    def _clear_list(self, kind: str):
        frame = self._get_list(kind)
        for w in frame.winfo_children():
            w.destroy()

    def _filter(self, kind: str, query: str):
        frame = self._get_list(kind)
        q = query.lower().strip()
        for child in frame.winfo_children():
            if hasattr(child, "full_text"):
                text = getattr(child, "full_text", "").lower()
                child.pack_forget() if q and q not in text else child.pack(fill="x", pady=1)

    def _add_email_card(self, parent: ttk.Frame, msg_data: dict, kind: str):
        payload = msg_data.get("payload", {})
        headers = payload.get("headers", [])
        msg_id = msg_data.get("id", "")

        subject = get_header(headers, "subject") or "(no subject)"
        sender = get_header(headers, "from") or "(unknown)"
        date_str = _fmt_date(get_header(headers, "date"))
        snippet = msg_data.get("snippet", "")
        body_text = decode_body(payload) or snippet

        card = tk.Frame(parent, bd=1, relief="solid", padx=8, pady=4, cursor="hand2")
        card.full_text = f"{sender} {subject} {snippet}".lower()

        header_frame = tk.Frame(card)
        header_frame.pack(fill="x")

        sender_label = tk.Label(header_frame, text=sender[:55], font=("Segoe UI", 10, "bold"), anchor="w")
        sender_label.pack(side="left", fill="x", expand=True)

        date_label = tk.Label(header_frame, text=date_str, font=("Segoe UI", 9), fg="gray")
        date_label.pack(side="right", padx=(8, 0))

        subject_label = tk.Label(card, text=subject[:80], font=("Segoe UI", 9), anchor="w", fg="#2a2a2a")
        subject_label.pack(fill="x")

        snippet_label = tk.Label(card, text=snippet[:120], font=("Segoe UI", 8), anchor="w", fg="#666")
        snippet_label.pack(fill="x")

        detail_frame = tk.Frame(card)
        detail_frame.pack(fill="x")
        detail_frame.pack_forget()

        body_text_widget = None

        def toggle_detail():
            nonlocal body_text_widget
            if detail_frame.winfo_ismapped():
                detail_frame.pack_forget()
                card.configure(bg="SystemButtonFace" if os.name == "nt" else "#f0f0f0")
            else:
                card.configure(bg="#e8f0fe")
                if not detail_frame.winfo_children():
                    body_preview = (body_text[:2000] + "..." if len(body_text) > 2000 else body_text) if body_text else "(no content)"
                    body_text_widget = tk.Text(detail_frame, height=12, wrap="word", font=("Segoe UI", 9), bd=0)
                    body_text_widget.pack(fill="both", expand=True)
                    body_text_widget.insert("1.0", body_preview)
                    body_text_widget.configure(state="disabled")

                    btn_frame = tk.Frame(detail_frame)
                    btn_frame.pack(fill="x", pady=(4, 0))
                    tk.Button(btn_frame, text="View in Gmail", command=lambda: self._open_in_gmail(msg_id)).pack(side="left")
                    tk.Button(btn_frame, text="Copy body", command=lambda: self._copy_text(body_text)).pack(side="left", padx=(8, 0))
                detail_frame.pack(fill="x", pady=(4, 0))

        for w in (card, sender_label, subject_label, snippet_label):
            w.bind("<Button-1>", lambda e, t=toggle_detail: t())

        card.pack(fill="x", pady=1)

    def _open_in_gmail(self, msg_id: str):
        import webbrowser
        webbrowser.open(f"https://mail.google.com/mail/u/0/#inbox/{msg_id}")

    def _copy_text(self, text: str):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)

    def _refresh(self, kind: str):
        label = "INBOX" if kind == "inbox" else "SENT"
        label_display = "Inbox" if kind == "inbox" else "Sent"

        self.status_var.set(f"Fetching {label_display}...")

        def _fetch():
            msgs = self.gmail.fetch_messages(label=label, max_results=30)
            details = []
            for m in msgs[:30]:
                detail = self.gmail.get_message_detail(m["id"])
                if detail:
                    details.append(detail)
            self.root.after(0, self._render_messages, kind, details)

        threading.Thread(target=_fetch, daemon=True).start()

    def _render_messages(self, kind: str, details: list[dict]):
        self._clear_list(kind)
        parent = self._get_list(kind)
        for d in details:
            self._add_email_card(parent, d, kind)

        label_display = "Inbox" if kind == "inbox" else "Sent"
        count = len(details)
        self.status_var.set(f"{label_display}: {count} messages  |  Auto-refresh every {REFRESH_INTERVAL}s")

    def refresh_all(self):
        self._refresh("inbox")
        self._refresh("sent")

    def _schedule_refresh(self):
        self.refresh_all()
        self.after_id = self.root.after(REFRESH_INTERVAL * 1000, self._schedule_refresh)

    def _on_close(self):
        if self.after_id:
            self.root.after_cancel(self.after_id)
        self.root.destroy()

    def run(self):
        if not self.gmail.is_configured():
            tk.messagebox.showerror(
                "Configuration Error",
                "Gmail OAuth not configured.\n\n"
                "Make sure .env has:\n"
                "  INTEGRATION_GMAIL_CLIENT_ID\n"
                "  INTEGRATION_GMAIL_CLIENT_SECRET\n"
                "  INTEGRATION_GMAIL_REFRESH_TOKEN\n\n"
                "Run: python backend/integrations/gmail/setup_oauth.py",
            )
            self.root.destroy()
            return
        self.root.mainloop()


if __name__ == "__main__":
    app = EmailMonitorApp()
    app.run()
