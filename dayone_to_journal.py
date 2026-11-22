#!/usr/bin/env python3
"""
Day One  ->  Apple Journal converter
====================================

Turns a Day One JSON export into one small .txt file per entry, in the format
the "Import into Journal" Apple Shortcut expects:

    YYYY-MM-DD HH:MM:SS|||Title|||Entry text (Markdown)|||photo1.jpeg,photo2.heic

(the last field is "-" when the entry has no photos)

It also:
  * converts each entry's time from UTC to the time zone it was written in,
  * strips Day One's photo placeholders and backslash escapes from the text,
  * splits the files into batch folders (100 per batch by default),
  * copies every photo/video into one folder, renamed with the entry number
    and date, plus a checklist telling you which entry each one belongs to.

Nothing is uploaded anywhere: it only reads your export and writes files
into a new output folder next to it.

Builds on Felix Wong's method (date|||title|||text files + a Shortcut):
https://felixwong.com/2026/08/how-i-imported-day-one-into-apple-journal/

Usage (Terminal on your Mac):
    python3 dayone_to_journal.py ~/Downloads/DayOneExport.zip

    # options
    python3 dayone_to_journal.py EXPORT [--out FOLDER] [--batch-size 100]
                                        [--first-line-as-title]
                                        [--add-location] [--add-tags]
                                        [--tz Asia/Colombo]

EXPORT can be the .zip Day One gives you, the unzipped folder, or a single
Journal.json file.
"""

import argparse
import json
import re
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:  # Python < 3.9
    ZoneInfo = None
    ZoneInfoNotFoundError = Exception

DELIM = "|||"
MEDIA_KEYS = ("photos", "videos", "audios", "pdfAttachments")
MEDIA_REF = re.compile(r"!\[[^\]]*\]\(dayone-moment:[^)]*\)")
MD_ESCAPE = re.compile(r"\\([\\`*_{}\[\]()#+\-.!|>~<=:])")
HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$")


# --------------------------------------------------------------------------- #
# Reading the export (zip, folder or single json)
# --------------------------------------------------------------------------- #
class Export:
    def __init__(self, src: Path):
        self.src = src
        self.zip = None
        self.journals = []      # list of (journal_name, entries)
        self.media = {}         # md5/identifier stem -> source path (str)

        if src.is_file() and src.suffix.lower() == ".zip":
            self.zip = zipfile.ZipFile(src)
            names = [n for n in self.zip.namelist()
                     if not n.startswith("__MACOSX") and not n.endswith("/")]
            for n in names:
                p = PurePosixPath(n)
                if p.suffix.lower() == ".json":
                    self._add_journal(p.stem, json.loads(self.zip.read(n)))
                elif p.parent.name in ("photos", "videos", "audios", "pdfs"):
                    self.media[p.stem.lower()] = n
        elif src.is_dir():
            for f in src.rglob("*"):
                if not f.is_file() or "__MACOSX" in f.parts:
                    continue
                if f.suffix.lower() == ".json":
                    self._add_journal(f.stem, json.loads(f.read_text("utf-8")))
                elif f.parent.name in ("photos", "videos", "audios", "pdfs"):
                    self.media[f.stem.lower()] = str(f)
        elif src.is_file() and src.suffix.lower() == ".json":
            self._add_journal(src.stem, json.loads(src.read_text("utf-8")))
            for sub in ("photos", "videos", "audios", "pdfs"):
                d = src.parent / sub
                if d.is_dir():
                    for f in d.iterdir():
                        if f.is_file():
                            self.media[f.stem.lower()] = str(f)
        else:
            sys.exit(f"Can't read {src}. Give me the Day One .zip, its folder, or a .json file.")

        if not self.journals:
            sys.exit("No Day One journal (.json) found in that export.")

    def _add_journal(self, name, data):
        if isinstance(data, dict) and isinstance(data.get("entries"), list):
            self.journals.append((name, data["entries"]))

    def copy_media(self, key: str, dest: Path) -> bool:
        src = self.media.get(key.lower())
        if not src:
            return False
        if self.zip:
            with self.zip.open(src) as fin, open(dest, "wb") as fout:
                shutil.copyfileobj(fin, fout)
        else:
            shutil.copy2(src, dest)
        return True

    def media_ext(self, key: str, fallback: str) -> str:
        src = self.media.get(key.lower())
        return PurePosixPath(src).suffix if src else f".{fallback}"


# --------------------------------------------------------------------------- #
# Converting one entry
# --------------------------------------------------------------------------- #
def local_time(entry, default_tz):
    raw = entry.get("creationDate")
    if not raw:
        return None
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    tz = None
    if ZoneInfo:
        for name in (entry.get("timeZone"), default_tz):
            if not name:
                continue
            try:
                tz = ZoneInfo(name)
                break
            except (ZoneInfoNotFoundError, ValueError):
                continue
    return dt.astimezone(tz) if tz else dt.astimezone()  # fall back to this Mac's zone


def clean_text(text):
    text = MEDIA_REF.sub("", text or "")
    text = MD_ESCAPE.sub(r"\1", text)
    text = text.replace("\r\n", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_title(text, first_line_as_title):
    lines = text.split("\n")
    if not lines or not lines[0].strip():
        return "", text
    first = lines[0]
    m = HEADING.match(first)
    if m:
        title = m.group(1)
    elif first_line_as_title and len(first) <= 120:
        title = first
    else:
        return "", text
    title = re.sub(r"(\*\*|__|\*|_)(.+?)\1", r"\2", title).strip()
    return title, "\n".join(lines[1:]).strip()


def location_line(entry):
    loc = entry.get("location") or {}
    parts = [loc.get("placeName"), loc.get("localityName"), loc.get("country")]
    seen, out = set(), []
    for p in parts:
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return ("📍 " + ", ".join(out)) if out else ""


def safe(s):
    return s.replace(DELIM, "| | |")


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="Convert a Day One JSON export for Apple Journal.")
    ap.add_argument("export", type=Path, help="Day One export: .zip, unzipped folder, or .json")
    ap.add_argument("--out", type=Path, help="Output folder (default: 'Journal Import' next to the export)")
    ap.add_argument("--batch-size", type=int, default=100, help="Entries per batch folder (default 100)")
    ap.add_argument("--first-line-as-title", action="store_true",
                    help="Use the first line of every entry as the title (default: only '# Heading' lines)")
    ap.add_argument("--add-location", action="store_true", help="Append '📍 Place' to the entry text")
    ap.add_argument("--add-tags", action="store_true", help="Append Day One tags as #tags")
    ap.add_argument("--tz", default=None,
                    help="Time zone for entries with none recorded, e.g. Asia/Colombo (default: this computer's)")
    args = ap.parse_args()

    src = args.export.expanduser().resolve()
    exp = Export(src)
    out = (args.out.expanduser() if args.out else src.parent / "Journal Import").resolve()
    if out.exists() and any(out.iterdir()):
        sys.exit(f"Output folder already has files in it: {out}\nDelete it or pass --out somewhere else.")
    media_dir = out / "photos_by_entry"
    out.mkdir(parents=True, exist_ok=True)

    rows = []
    for jname, entries in exp.journals:
        for e in entries:
            rows.append((jname, e, local_time(e, args.tz)))
    rows.sort(key=lambda r: (r[2] is None, r[2] or datetime.min.replace(tzinfo=timezone.utc)))

    checklist, missing, skipped, skipped_empty, written = [], 0, 0, 0, 0
    total = len(rows)
    width = max(4, len(str(total)))
    for jname, e, dt in rows:
        if dt is None:
            skipped += 1
            continue
        title, body = split_title(clean_text(e.get("text")), args.first_line_as_title)

        extras = []
        if args.add_location:
            loc = location_line(e)
            if loc:
                extras.append(loc)
        if args.add_tags and e.get("tags"):
            extras.append(" ".join("#" + re.sub(r"\s+", "", t) for t in e["tags"]))
        if extras:
            body = (body + "\n\n" + "\n".join(extras)).strip()

        has_media = any(e.get(k) for k in MEDIA_KEYS)
        if not title and not body:
            if not has_media:
                skipped_empty += 1      # completely empty Day One entry: nothing to import
                continue
            body = "📷"                 # photo-only entry: give it visible text so Journal shows it

        # A single space keeps the |||-split from collapsing an empty title.
        title = safe(title) or " "
        body = safe(body)

        written += 1
        batch = (written - 1) // args.batch_size + 1
        num = str(written).zfill(width)
        bdir = out / f"batch_{batch:02d}"
        bdir.mkdir(exist_ok=True)
        stamp = dt.strftime("%Y-%m-%d %H:%M:%S")

        # Media: copy into photos_by_entry and remember the file names
        media_items = []
        for key in MEDIA_KEYS:
            for m in e.get(key) or []:
                media_items.append(m)
        media_items.sort(key=lambda m: m.get("orderInEntry", 0))
        copied, attached = [], []
        for k, m in enumerate(media_items, start=1):
            mkey = m.get("md5") or m.get("identifier") or ""
            ext = exp.media_ext(mkey, m.get("type") or m.get("format") or "bin")
            name = f"{num}_{dt:%Y-%m-%d}_{k}{ext}"
            media_dir.mkdir(exist_ok=True)
            if exp.copy_media(mkey, media_dir / name):
                copied.append(name)
                attached.append(name)
            else:
                missing += 1
                copied.append(f"(missing from export: {mkey}{ext})")

        # 4th field: comma-separated photo file names, or "-" if none
        photos_field = ",".join(attached) if attached else "-"
        (bdir / f"{num}.txt").write_text(
            f"{stamp}{DELIM}{title}{DELIM}{body}{DELIM}{photos_field}", encoding="utf-8")

        if copied:
            label = "📷 photo-only entry" if body == "📷" else (
                title.strip() or body.strip().split("\n")[0][:50])
            checklist.append(f"[ ] {num}  {stamp[:16]}  batch_{batch:02d}  {label}\n      " +
                             "\n      ".join(copied))

    if checklist:
        (out / "PHOTO_CHECKLIST.txt").write_text(
            "Entries that had photos/media in Day One.\n"
            "The Shortcut attaches these automatically. Use this list to spot-check a few\n"
            "in Apple Journal, and to add by hand any marked 'missing from export'.\n\n"
            + "\n\n".join(checklist) + "\n", encoding="utf-8")

    batches = (written - 1) // args.batch_size + 1 if written else 0
    print(f"\n✅ Converted {written} entries from {len(exp.journals)} journal(s) into {batches} batch folder(s).")
    print(f"   After importing, Apple Journal should show {written} entries.")
    if skipped_empty:
        print(f"   ({skipped_empty} completely empty Day One entr(y/ies) left out.)")
    print(f"   Output: {out}")
    if checklist:
        print(f"   {len(checklist)} entries had photos/media → see PHOTO_CHECKLIST.txt")
    if missing:
        print(f"   ⚠️  {missing} media file(s) referenced but not found in the export.")
    if skipped:
        print(f"   ⚠️  {skipped} entr(y/ies) skipped because they had no date.")
    print()


if __name__ == "__main__":
    main()
