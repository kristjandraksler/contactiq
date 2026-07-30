from pathlib import Path

main_path = Path("apps/api/app/main.py")

if not main_path.exists():
    raise SystemExit("apps/api/app/main.py ne obstaja.")

text = main_path.read_text(encoding="utf-8")

import_line = (
    "from app.routes.public_providers import "
    "router as public_providers_router\n"
)
include_line = "app.include_router(public_providers_router)\n"

if import_line not in text:
    marker = "from fastapi"
    lines = text.splitlines(keepends=True)
    insert_at = 0

    for index, line in enumerate(lines):
        if line.startswith("from app.routes.") or line.startswith("from app."):
            insert_at = index + 1

    lines.insert(insert_at, import_line)
    text = "".join(lines)

if include_line not in text:
    first_include = text.find("app.include_router(")

    if first_include >= 0:
        line_end = text.find("\n", first_include)
        text = text[: line_end + 1] + include_line + text[line_end + 1 :]
    else:
        app_marker = "app = FastAPI("
        app_index = text.find(app_marker)

        if app_index < 0:
            raise SystemExit("FastAPI app ni bil najden v main.py.")

        close_index = text.find("\n)", app_index)

        if close_index < 0:
            raise SystemExit("Zaključek FastAPI konstruktorja ni bil najden.")

        insert_at = close_index + 3
        text = text[:insert_at] + "\n" + include_line + text[insert_at:]

main_path.write_text(text, encoding="utf-8")
print("main.py je posodobljen.")
