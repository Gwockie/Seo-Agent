"""Conservative static source readiness; challenges are never page content."""
import re
from bs4 import BeautifulSoup


def usable_html(html):
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True).casefold() if soup.title else ""
    if not soup.html or not soup.body or not title:
        return False
    if soup.find(id=re.compile(r"^(cf-chl|challenge|captcha|sg-captcha)", re.I)):
        return False
    if any(value in title for value in ("just a moment", "attention required", "verify you are human", "access denied", "security check", "captcha", "robot check")):
        return False
    if soup.find("script", src=re.compile(r"challenge-platform|captcha-delivery|sgcaptcha", re.I)):
        return False
    text = soup.body.get_text(" ", strip=True).casefold()
    return bool(text) and text not in {"loading...", "loading…"} and not any(value in text for value in ("checking your browser before accessing", "enable javascript and cookies to continue", "verify that you are human"))
