from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
import structlog
from bs4 import BeautifulSoup

logger = structlog.get_logger(__name__)

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
BLOCKED_DOMAINS = {"example.com", "domain.com", "yoursite.com", "yourdomain.com"}
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

SENDGRID_FROM = "noreply@owlbell.xyz"


async def find_email_on_page(url: str, client: httpx.AsyncClient) -> Optional[str]:
    try:
        resp = await client.get(url, timeout=10, follow_redirects=True, headers={"User-Agent": USER_AGENT})
        if resp.status_code != 200:
            return None
        content_type = resp.headers.get("content-type", "")
        if "text/html" not in content_type and "text/plain" not in content_type:
            return None
        return _extract_email(resp.text)
    except Exception:
        return None


def _extract_email(html: str) -> Optional[str]:
    soup = BeautifulSoup(html, "lxml")

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("mailto:"):
            email = href[7:].split("?")[0].strip()
            if _is_valid_email(email):
                return email

    for tag in soup.find_all(["a", "span", "p", "div", "li"]):
        text = tag.get_text(strip=True)
        if "@" in text:
            found = EMAIL_RE.findall(text)
            for email in found:
                if _is_valid_email(email):
                    return email

    text = soup.get_text()
    found = EMAIL_RE.findall(text)
    for email in found:
        if _is_valid_email(email):
            return email

    return None


def _is_valid_email(email: str) -> bool:
    email = email.strip().lower()
    if not EMAIL_RE.match(email):
        return False
    domain = email.split("@")[1] if "@" in email else ""
    if domain in BLOCKED_DOMAINS:
        return False
    if domain.endswith((".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")):
        return False
    return True


def _normalize_url(raw_url: str) -> Optional[str]:
    raw_url = raw_url.strip()
    if not raw_url:
        return None
    if not raw_url.startswith(("http://", "https://")):
        raw_url = "https://" + raw_url
    parsed = urlparse(raw_url)
    if not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}/"


COMMON_EMAIL_PREFIXES = ["info", "contact", "hello", "office", "admin", "support", "inquiries", "sales"]


async def find_contractor_email(website: str) -> Optional[str]:
    normalized = _normalize_url(website)
    if not normalized:
        return None

    domain = urlparse(normalized).netloc

    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        email = await find_email_on_page(normalized, client)
        if email:
            return email

        contact_urls = [
            urljoin(normalized, "contact"),
            urljoin(normalized, "contact-us"),
            urljoin(normalized, "about"),
            urljoin(normalized, "about-us"),
        ]
        for cu in contact_urls:
            email = await find_email_on_page(cu, client)
            if email:
                return email

    for prefix in COMMON_EMAIL_PREFIXES:
        guessed = f"{prefix}@{domain}"
        if _is_valid_email(guessed):
            return guessed

    return None


async def find_emails_for_leads(leads: list[dict]) -> list[dict]:
    enriched = []
    for lead in leads:
        website = lead.get("website", "")
        if website:
            email = await find_contractor_email(website)
            if email:
                lead["email"] = email
                logger.info("email_finder.found", business=lead.get("name"), email=email)
            else:
                lead["email"] = None
                logger.info("email_finder.not_found", business=lead.get("name"), website=website)
        else:
            lead["email"] = None
        enriched.append(lead)
    return enriched
