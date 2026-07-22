from dataclasses import dataclass
from urllib.parse import urlparse
import re
import tldextract

PHONE_PATTERN = re.compile(
    r"(?:(?:\+|00)386|0)[\s./-]?(?:1|2|3|4|5|7|8)[\s./-]?\d{2,3}[\s./-]?\d{2,3}[\s./-]?\d{2,3}"
)

@dataclass
class EmailTarget:
    email: str

    @property
    def domain(self) -> str:
        raw_domain = self.email.rsplit("@", 1)[-1].lower().strip()
        extracted = tldextract.extract(raw_domain)
        return ".".join(part for part in [extracted.domain, extracted.suffix] if part)

def main() -> None:
    print("ContactIQ worker je pripravljen.")
    example = EmailTarget("info@primer.si")
    print(f"Primer domene: {example.domain}")
    print("Naslednji korak: povezava s Supabase čakalno vrsto.")

if __name__ == "__main__":
    main()
