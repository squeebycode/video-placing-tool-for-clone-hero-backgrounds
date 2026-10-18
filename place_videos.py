#!/usr/bin/env python3
"""
place_videos.py - move Clone Hero video dumps into the matching song folders.

For every folder under VIDEO DUMPS that contains a video file, the script looks
for the best-matching song folder under your Clone Hero Songs folder, shows you
what it wants to do, and waits for a keypress:

    y = do it      n = skip      q = quit      1-9 = pick one of several matches

The screen is cleared before each question so only the current one is shown, with
a one-line "Last:" reminder of the previous action. Every action is also appended
to place_videos.log (next to this script), one line each, in the same style as the
--dry-run output, so you can scroll back through the history there.

With --auto, a dump whose single exact match is found is placed without asking.
You are still asked whenever a real decision is needed: several possible songs to
pick from, a match that is only a close guess, or a song that already has a video.

After a video has been moved, its origin folder in the dump is renamed with a
"(moved) " prefix, e.g. "Aggro" -> "(moved) Aggro", so you can see at a glance what
is done. (Not done in --copy mode, since the video is still in that folder.)

Matching works in three stages (the first stage that finds anything wins):
  1. Exact match after "normalizing" both names. Normalizing lowercases the text
     and throws away every character that isn't a letter or digit, so
     "L_Via L_Viaquez" and "L'Via L'Viaquez" both become "lvialviaquez".
  2. One name contained inside the other (handles extra tags like "(Live)").
  3. Fuzzy matching with difflib (handles typos / small differences).

Song titles and artists are read from each song's song.ini when it exists, so a
dump folder named only "Cochise" still matches "Audioslave - Cochise".
When several songs match, the game folder name in the dump path
("Guitar Hero World Unzipped Video Dump") is used to rank them.

Usage:
    python place_videos.py                 # uses the paths configured below
    python place_videos.py --dry-run       # show what would happen, move nothing
    python place_videos.py --copy          # copy instead of move
    python place_videos.py --no-clear      # keep all output on screen instead
    python place_videos.py --auto          # say yes to exact matches automatically
    python place_videos.py --auto --auto-min 0.9   # ...and to close guesses (90%+)
    python place_videos.py --log "D:\\my.log"   # write the log somewhere else
    python place_videos.py --songs "D:\\Songs" --dumps "D:\\Video Dumps"

Needs only the Python standard library (Python 3.8+).
"""

import argparse
import datetime
import difflib
import os
import re
import shutil
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

# ----------------------------------------------------------------------------
# CONFIG - change these if your folders live somewhere else
# ----------------------------------------------------------------------------
SONGS_ROOT = Path(r"C:\Users\timmy\Documents\Clone Hero\Songs")
DUMPS_ROOT = Path(r"C:\Users\timmy\Documents\Video Dumps")

VIDEO_EXTS = {".mp4", ".webm", ".avi", ".mkv", ".mov", ".m4v",
              ".mpg", ".mpeg", ".ogv", ".vp8"}
SONG_MARKERS = {"song.ini", "notes.chart", "notes.mid"}

FUZZY_CUTOFF = 0.78       # 0-1, lower = more (and sloppier) suggestions
MAX_CANDIDATES = 5        # how many matches to show at most
MIN_SUBSTRING_LEN = 5     # ignore "contains" matches on very short names
LOG_FILE = Path(__file__).with_name("place_videos.log")   # history of every action
MOVED_PREFIX = "(moved) "   # added to a dump folder's name once its video is moved


# ----------------------------------------------------------------------------
# Data
# ----------------------------------------------------------------------------
@dataclass
class Song:
    path: Path
    rel: str                  # path relative to SONGS_ROOT, for display
    artist: str
    title: str
    title_key: str
    full_key: str             # artist + title
    folder_key: str           # the song folder's own name
    hint_tokens: set = field(default_factory=set)


@dataclass
class Dump:
    folder: Path
    rel: str
    video: Path
    key: str
    hint_tokens: set


@dataclass
class Candidate:
    song: Song
    score: float
    reason: str


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def norm(text: str) -> str:
    """Lowercase, strip accents, drop everything except letters and digits."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower().replace("&", "and")
    return re.sub(r"[\W_]+", "", text)


def tokens(parts) -> set:
    """Words from path parts, used only to break ties between matches."""
    words = set()
    for part in parts:
        words.update(re.findall(r"[a-z0-9]+", part.lower()))
    return words


def read_song_ini(folder: Path):
    """Return (artist, title) from song.ini, or ("", "") if unavailable."""
    ini = folder / "song.ini"
    if not ini.is_file():
        return "", ""
    raw = ini.read_bytes()
    for enc in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeError:
            continue
    else:
        return "", ""
    artist = title = ""
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().lower()
        value = value.strip()
        if key == "artist" and not artist:
            artist = value
        elif key == "name" and not title:
            title = value
    return artist, title


def find_video(folder: Path):
    """Pick the video file in a folder (prefers one already named 'video')."""
    vids = [p for p in folder.iterdir()
            if p.is_file() and p.suffix.lower() in VIDEO_EXTS]
    if not vids:
        return None
    vids.sort(key=lambda p: (p.stem.lower() != "video", p.name.lower()))
    return vids[0]


def existing_videos(song_dir: Path):
    return [p for p in song_dir.iterdir()
            if p.is_file() and p.stem.lower() == "video"
            and p.suffix.lower() in VIDEO_EXTS]


# ----------------------------------------------------------------------------
# Scanning
# ----------------------------------------------------------------------------
def scan_songs(root: Path):
    songs = []
    for dirpath, dirnames, filenames in os.walk(root):
        if SONG_MARKERS & {f.lower() for f in filenames}:
            folder = Path(dirpath)
            dirnames[:] = []                      # a song folder has no sub-songs
            artist, title = read_song_ini(folder)
            name = folder.name
            # Fall back to the "Artist - Title" folder name
            if not title:
                if " - " in name:
                    artist, _, title = name.partition(" - ")
                else:
                    title = name
            rel = str(folder.relative_to(root))
            songs.append(Song(
                path=folder,
                rel=rel,
                artist=artist,
                title=title,
                title_key=norm(title),
                full_key=norm(artist + title),
                folder_key=norm(name),
                hint_tokens=tokens(folder.relative_to(root).parts[:-1]),
            ))
    return songs


def scan_dumps(root: Path):
    dumps = []
    for dirpath, _dirs, _files in os.walk(root):
        folder = Path(dirpath)
        if folder.name.startswith(MOVED_PREFIX):
            continue                              # already handled in an earlier run
        try:
            video = find_video(folder)
        except OSError:
            continue
        if video is None:
            continue
        rel_parts = folder.relative_to(root).parts
        dumps.append(Dump(
            folder=folder,
            rel=str(folder.relative_to(root)),
            video=video,
            key=norm(folder.name),
            hint_tokens=tokens(rel_parts[:-1]),
        ))
    dumps.sort(key=lambda d: d.rel.lower())
    return dumps


class Index:
    """Lookup tables so exact matches are instant."""

    def __init__(self, songs):
        self.songs = songs
        self.by_key = {}
        for s in songs:
            for k in {s.title_key, s.full_key, s.folder_key}:
                if k:
                    self.by_key.setdefault(k, []).append(s)
        self.all_keys = list(self.by_key)

    def candidates(self, dump: Dump):
        key = dump.key
        if not key:
            return []
        found = {}   # song path -> Candidate (keep best)

        def add(song, score, reason):
            old = found.get(song.path)
            if old is None or score > old.score:
                found[song.path] = Candidate(song, score, reason)

        # 1) exact
        for s in self.by_key.get(key, []):
            add(s, 1.0, "exact name match")

        # 2) contains
        if not found:
            for s in self.songs:
                for k in (s.title_key, s.full_key):
                    if not k:
                        continue
                    shorter, longer = sorted((key, k), key=len)
                    if len(shorter) >= MIN_SUBSTRING_LEN and shorter in longer:
                        add(s, 0.9, "one name contains the other")
                        break

        # 3) fuzzy
        if not found:
            for k in difflib.get_close_matches(key, self.all_keys,
                                               n=MAX_CANDIDATES * 2,
                                               cutoff=FUZZY_CUTOFF):
                ratio = difflib.SequenceMatcher(None, key, k).ratio()
                for s in self.by_key[k]:
                    add(s, ratio, f"fuzzy match ({ratio:.0%})")

        ranked = sorted(
            found.values(),
            key=lambda c: (-c.score,
                           -len(dump.hint_tokens & c.song.hint_tokens),
                           c.song.rel.lower()),
        )
        return ranked[:MAX_CANDIDATES]


# ----------------------------------------------------------------------------
# Input
# ----------------------------------------------------------------------------
def get_key(valid: str) -> str:
    """Wait for one of the characters in `valid`; no Enter needed on Windows."""
    valid = valid.lower()
    while True:
        try:
            if os.name == "nt":
                import msvcrt
                ch = msvcrt.getwch()
                if ch == "\x03":
                    return "q"
                if ch in ("\x00", "\xe0"):      # arrow / function key prefix
                    msvcrt.getwch()
                    continue
            elif sys.stdin.isatty():
                import termios
                import tty
                fd = sys.stdin.fileno()
                old = termios.tcgetattr(fd)
                try:
                    tty.setraw(fd, termios.TCSADRAIN)   # don't drop typed-ahead keys
                    ch = sys.stdin.read(1)
                finally:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old)
                if ch == "\x03":
                    return "q"
            else:
                line = sys.stdin.readline()
                if line == "":
                    return "q"                  # input ended
                ch = line.strip()[:1]
        except (KeyboardInterrupt, EOFError):
            return "q"
        if ch.lower() in valid:
            return ch.lower()


# ----------------------------------------------------------------------------
# Main loop
# ----------------------------------------------------------------------------
class RunLog:
    """Append-only history. One line per action, same style as --dry-run."""

    def __init__(self, path: Path):
        self.path = path

    def _write(self, text: str):
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(text + "\n")
        except OSError:
            pass                                 # never crash over the log

    def header(self, dry_run: bool):
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        suffix = " (dry run)" if dry_run else ""
        self._write(f"\n=== Run started {stamp}{suffix} ===")

    def add(self, line: str):
        self._write(f"{datetime.datetime.now():%H:%M:%S}  {line}")


def clear_screen():
    if sys.stdout.isatty():
        os.system("cls" if os.name == "nt" else "clear")


def src_name(dump: Dump) -> str:
    return f"{dump.rel}{os.sep}{dump.video.name}"


def moved_name(folder: Path) -> Path:
    """New path for a handled dump folder: '(moved) Aggro' (or '... (2)' if taken)."""
    target = folder.with_name(MOVED_PREFIX + folder.name)
    n = 2
    while target.exists():
        target = folder.with_name(f"{MOVED_PREFIX}{folder.name} ({n})")
        n += 1
    return target


def place(dump: Dump, song: Song, copy: bool, dry_run: bool):
    """Do (or simulate) one move/copy. Returns (done, one-line description)."""
    dest = song.path / ("video" + dump.video.suffix.lower())
    src = src_name(dump)
    verb = "COPY" if copy else "MOVE"

    old = existing_videos(song.path)
    note = ""
    if old:
        names = ", ".join(p.name for p in old)
        print(f"   !! That song already has: {names}")
        print("   Replace it? [y]es / [n]o  ", end="", flush=True)
        ans = get_key("yn")
        print(ans)
        if ans != "y":
            return False, f"SKIP {src} (kept existing {names})"
        note = f"   [replaced {names}]"

    new_folder = None if copy else moved_name(dump.folder)

    if dry_run:
        if new_folder:
            note += f'   [would rename folder to "{new_folder.name}"]'
        return True, f"(dry run) would {verb} {src} -> {dest}{note}"

    try:
        for p in old:
            p.unlink()
        if copy:
            shutil.copy2(dump.video, dest)
        else:
            shutil.move(str(dump.video), str(dest))
    except OSError as e:
        return False, f"ERROR {src}: {e}"

    if new_folder:                    # the video is safely moved; now tag its old folder
        try:
            dump.folder.rename(new_folder)
            note += f'   [folder renamed to "{new_folder.name}"]'
        except OSError as e:          # e.g. the folder is open in Explorer
            note += f"   [folder NOT renamed: {e}]"
    return True, f"{verb} {src} -> {dest}{note}"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--songs", type=Path, default=SONGS_ROOT,
                    help="Clone Hero Songs folder")
    ap.add_argument("--dumps", type=Path, default=DUMPS_ROOT,
                    help="folder containing the unzipped video dumps")
    ap.add_argument("--copy", action="store_true",
                    help="copy videos instead of moving them")
    ap.add_argument("--dry-run", action="store_true",
                    help="show what would happen without changing anything")
    ap.add_argument("--log", type=Path, default=LOG_FILE,
                    help="where to write the action history (default: next to the script)")
    ap.add_argument("--no-clear", action="store_true",
                    help="don't clear the screen between questions")
    ap.add_argument("--auto", action="store_true",
                    help="place clear-cut matches without asking; still asks when you "
                         "must pick from a list, the match is only a guess, or a "
                         "video would be replaced")
    ap.add_argument("--auto-min", type=float, default=1.0, metavar="SCORE",
                    help="with --auto, the lowest match score (0-1) accepted without "
                         "asking. 1.0 = exact name matches only (default); e.g. 0.9 "
                         "also accepts close matches")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass

    for label, p in (("Songs", args.songs), ("Video dumps", args.dumps)):
        if not p.is_dir():
            sys.exit(f"{label} folder not found: {p}")

    print("Scanning songs...", flush=True)
    songs = scan_songs(args.songs)
    print(f"  found {len(songs)} songs")
    print("Scanning video dumps...", flush=True)
    dumps = scan_dumps(args.dumps)
    print(f"  found {len(dumps)} dump folders containing a video\n")
    if not songs or not dumps:
        sys.exit("Nothing to do.")

    index = Index(songs)
    log = RunLog(args.log)
    log.header(args.dry_run)
    moved = skipped = nomatch = auto_n = errors = 0
    last = ""

    for n, dump in enumerate(dumps, 1):
        src = src_name(dump)
        cands = index.candidates(dump)

        if not cands:                     # nothing to ask, so nothing to show
            nomatch += 1
            last = f"NO MATCH {src}"
            log.add(last)
            continue

        # --auto: take clear-cut single matches without asking. Anything that
        # needs a real decision (a list, a guess, replacing a video) still asks.
        if (args.auto and len(cands) == 1 and cands[0].score >= args.auto_min
                and not existing_videos(cands[0].song.path)):
            done, last = place(dump, cands[0].song, args.copy, args.dry_run)
            last += "   [auto]"
            log.add(last)
            if args.no_clear:
                print(f"[{n}/{len(dumps)}]  {last}")
            if done:
                moved += 1
                auto_n += 1
            else:
                skipped += 1
                errors += last.startswith("ERROR")
            continue

        # Fresh screen for every question; the log file keeps the history.
        if args.no_clear:
            print("=" * 78)
        else:
            clear_screen()
        print(f"[{n}/{len(dumps)}]  done {moved}   skipped {skipped}   "
              f"no match {nomatch}")
        if last and not args.no_clear:
            print(f"Last: {last}")
        print("-" * 78)
        print(f"Dump: {src}")

        if len(cands) == 1:
            c = cands[0]
            print(f"   Match [{c.reason}]: -> {c.song.rel}")
            print("   Place it here? [y]es / [n]o / [q]uit  ", end="", flush=True)
            ans = get_key("ynq")
            print(ans)
            choice = c if ans == "y" else None
        else:
            print("   Several possible matches:")
            for i, c in enumerate(cands, 1):
                print(f"     {i}) {c.song.rel}   [{c.reason}]")
            print(f"   Press 1-{len(cands)} to pick, [n] to skip, [q] to quit  ",
                  end="", flush=True)
            ans = get_key("".join(str(i) for i in range(1, len(cands) + 1)) + "nq")
            print(ans)
            choice = cands[int(ans) - 1] if ans.isdigit() else None

        if ans == "q":
            log.add("QUIT (you pressed q)")
            break
        if choice is None:
            skipped += 1
            last = f"SKIP {src} (you pressed n)"
            log.add(last)
            if args.no_clear:
                print(f"   {last}")
            continue

        done, last = place(dump, choice.song, args.copy, args.dry_run)
        log.add(last)
        if args.no_clear:
            print(f"   {last}")
        if done:
            moved += 1
        else:
            skipped += 1
            errors += last.startswith("ERROR")

    # Final screen: the last action plus totals (the log has everything else).
    print("\n" + "=" * 78)
    if last and not args.no_clear:
        print(f"Last: {last}")
    action = "would be placed" if args.dry_run else "placed"
    summary = (f"{moved} video(s) {action}"
               + (f" ({auto_n} automatically)" if args.auto else "")
               + f", {skipped} skipped, {nomatch} with no match"
               + (f", {errors} ERROR(S) - see the log" if errors else "")
               + ".")
    print(summary)
    log.add(summary)
    print(f"Every action is listed in: {args.log}")


if __name__ == "__main__":
    main()
