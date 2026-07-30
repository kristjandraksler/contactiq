from __future__ import annotations

PUBLIC_EMAIL_DOMAINS = {
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.uk", "yahoo.de",
    "yahoo.fr", "yahoo.it", "yahoo.es", "outlook.com", "outlook.de",
    "outlook.fr", "hotmail.com", "hotmail.co.uk", "hotmail.de", "hotmail.fr",
    "live.com", "live.co.uk", "live.de", "msn.com", "icloud.com", "me.com",
    "mac.com", "proton.me", "protonmail.com", "aol.com", "gmx.com",
    "gmx.de", "gmx.at", "gmx.ch", "mail.com", "zoho.com", "yandex.com",
    "yandex.ru", "tutanota.com", "tuta.com", "fastmail.com",
    # Slovenian and regional ISP / public mailbox domains. These are mailbox
    # providers, not the user's company website, and must never be crawled.
    # Additional European public mailbox providers.
    "wp.pl",
    "onet.pl",
    "interia.pl",
    "poczta.fm",
    "mail.ru",
    "inbox.ru",
    "bk.ru",
    "list.ru",
    "zoznam.sk",
    "centrum.sk",
    "centrum.cz",
    "seznam.cz",
    "mail.ee",
    "inbox.lv",
    "abv.bg",
    "web.de",
    "orange.fr",
    "laposte.net",
    "freemail.hu",
    "private.relay.appleid.com",
    "telemach.net", "siol.net", "t-2.net", "amis.net", "volja.net",
    "email.si", "guest.arnes.si", "arnes.si", "net.hr", "vip.hr",
    "iskon.hr", "t-com.hr", "mts.rs", "eunet.rs", "sbb.rs",
}


def clean_domain(value: str) -> str:
    domain = value.strip().lower()
    if "@" in domain:
        domain = domain.rsplit("@", 1)[1]
    domain = domain.replace("http://", "").replace("https://", "")
    domain = domain.split("/", 1)[0].split(":", 1)[0].strip(".")
    return domain.removeprefix("www.")


def is_public_email_domain(value: str) -> bool:
    return clean_domain(value) in PUBLIC_EMAIL_DOMAINS
