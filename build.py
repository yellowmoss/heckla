from pathlib import Path
import shutil
from dataclasses import dataclass
import os
import markdown
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape


# --------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------

SITE_ROOT = Path(os.environ.get("GITHUB_WORKSPACE", Path.cwd()))

CONTENT_DIR = SITE_ROOT / "content"
TEMPLATES_DIR = SITE_ROOT / "templates"
DIST_DIR = SITE_ROOT / "dist"

# --------------------------------------------------------------------
# Models
# --------------------------------------------------------------------

@dataclass
class Page:
    source: Path
    output_dir: Path
    url: str
    title: str
    description: str
    content_html: str
    section: Path


# --------------------------------------------------------------------
# Setup
# --------------------------------------------------------------------

# Clean output directory
if DIST_DIR.exists():
    shutil.rmtree(DIST_DIR)
DIST_DIR.mkdir()

# Jinja environment
env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html"])
)
template = env.get_template("default.html")

# Markdown renderer
md = markdown.Markdown(
    extensions=["extra", "tables", "fenced_code"]
)

# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------

def parse_markdown(path: Path):
    raw = path.read_text(encoding="utf-8")

    frontmatter = {}
    body = raw

    if raw.lstrip().startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) == 3:
            _, fm, body = parts
            frontmatter = yaml.safe_load(fm) or {}

    html = md.convert(body)
    md.reset()

    return frontmatter, html


def title_from_path(path: Path) -> str:
    return path.stem.replace("-", " ").title()


# --------------------------------------------------------------------
# Parse phase (no writing)
# --------------------------------------------------------------------

pages: list[Page] = []
sections: dict[Path, list[Page]] = {}

for md_path in CONTENT_DIR.rglob("*.md"):
    rel = md_path.relative_to(CONTENT_DIR)
    section = rel.parent

    frontmatter, content_html = parse_markdown(md_path)

    # Routing rules
    if rel == Path("_index.md"):
        output_dir = DIST_DIR
        url = "/"
    elif rel.name == "_index.md":
        output_dir = DIST_DIR / section
        url = f"/{section}/"
    else:
        output_dir = DIST_DIR / rel.with_suffix("")
        url = f"/{rel.with_suffix('')}/"

    page = Page(
        source=md_path,
        output_dir=output_dir,
        url=url,
        title=frontmatter.get("title", title_from_path(md_path)),
        description=frontmatter.get("description", ""),
        content_html=content_html,
        section=section,
    )

    pages.append(page)
    sections.setdefault(section, []).append(page)

# --------------------------------------------------------------------
# Emit real pages
# --------------------------------------------------------------------

for page in pages:
    page.output_dir.mkdir(parents=True, exist_ok=True)

    html = template.render(
        title=page.title,
        description=page.description,
        content=page.content_html,
    )

    (page.output_dir / "index.html").write_text(html, encoding="utf-8")
    print(f"Built {page.url}")

# --------------------------------------------------------------------
# Emit synthetic section indexes
# --------------------------------------------------------------------

for section, section_pages in sections.items():
    # Root handled explicitly via content/_index.md
    if section == Path("."):
        continue

    index_md = CONTENT_DIR / section / "_index.md"
    output_dir = DIST_DIR / section
    output_file = output_dir / "index.html"

    # If a real section index exists, do nothing
    if index_md.exists():
        continue

    # Only include real content pages
    children = [
        p for p in section_pages
        if p.source.name != "_index.md"
    ]

    if not children:
        continue

    heading = section.name.replace("-", " ").title()

    list_items = "\n".join(
        f'<li><a href="{p.url}">{p.title}</a></li>'
        for p in sorted(children, key=lambda p: p.title)
    )

    synthetic_content = f"""
<h1>{heading}</h1>
<ul>
{list_items}
</ul>
"""

    html = template.render(
        title=heading,
        description=f"Index of {heading}",
        content=synthetic_content,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    output_file.write_text(html, encoding="utf-8")

    print(f"Generated synthetic index for /{section}/")

# --------------------------------------------------------------------
# Done
# --------------------------------------------------------------------

print("Build complete.")
