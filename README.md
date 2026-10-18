# video-placing-tool-for-clone-hero-backgrounds
Manually placing every video from one folder to the next was taking way too much time, so I had Claude write a python script that would automate the entire process. 
# Clone Hero Video Placer

EVERYTHING BELOW THIS IS WRITTEN WITH AI. 

Match a pile of downloaded video backgrounds to the right songs in your
[Clone Hero](https://clonehero.net/) library and drop each one in as `video.*`, with a
yes/no check on every move.

```
Dump: Guitar Hero World Unzipped Video Dump\Assassin\video.webm
   Match [exact name match]: -> Guitar Hero World Tour\Muse - Assassin
   Place it here? [y]es / [n]o / [q]uit
```

## Why this exists

Clone Hero plays a background video if a song folder contains a file named `video`
(`video.mp4`, `video.webm`, ...). Community video dumps come as one folder per song, but
the folder names rarely match your song folders exactly:

| In the video dump | In your Clone Hero library |
| --- | --- |
| `L_Via L_Viaquez\video.webm` | `The Mars Volta - L'Via L'Viaquez\` |
| `Cochise\video.mp4` | `Audioslave - Cochise\` |

The artist is missing, and characters like `'` have been swapped for `_`. Doing hundreds
of these by hand is miserable, so this script does the matching for you and asks before it
touches anything.

## Features

- **Forgiving name matching**: ignores case, punctuation, `_` vs `'`, accents and a
  missing artist. Falls back to fuzzy matching for typos.
- **Reads `song.ini`** for the real artist and title, so it still works when folder names
  are odd.
- **You approve every move** with a single keypress (no Enter needed on Windows).
- **Picks from a list** when several songs match, using the game name in the dump's path
  (e.g. "Guitar Hero World...") to rank them.
- **`--auto` mode** accepts the clear-cut matches and only stops for real decisions.
- **`--dry-run`** shows exactly what would happen and changes nothing.
- **Action log** with one line per action, so you can review everything afterwards.
- **Tags finished folders**: after a move, `Aggro` is renamed to `(moved) Aggro`.
- **No dependencies**: just Python's standard library.

## Requirements

- Python 3.8 or newer
- A Clone Hero library and one or more *unzipped* video dumps on your computer

Built and used on Windows. The keypress handling also has a macOS/Linux path.

> This tool does not download or distribute any videos or songs. Bring your own files, and
> make sure you have the right to use them. It is an unofficial fan tool and is not
> affiliated with Clone Hero or its developers.

## Install

Download `place_videos.py` (or clone this repo) and put it anywhere. That's it.

```
git clone https://github.com/<your-username>/clone-hero-video-placer.git
```

## Folder layout it expects

```
Documents\
├── Clone Hero\
│   └── Songs\
│       ├── Guitar Hero World Tour\
│       │   └── The Mars Volta - L'Via L'Viaquez\    <- has song.ini / notes.chart / notes.mid
│       └── Guitar Hero\Guitar Hero\Quickplay\
│           └── Audioslave - Cochise\                 <- nesting depth doesn't matter
└── Video Dumps\
    └── Guitar Hero World Unzipped Video Dump\
        ├── L_Via L_Viaquez\video.webm
        └── Cochise\video.mp4
```

- A **song** is any folder under `Songs` that contains `song.ini`, `notes.chart` or
  `notes.mid`. Nesting by game, "Quickplay", "Bonus" and so on is fine.
- A **dump** is any folder under your dumps folder that contains a video file
  (`.mp4 .webm .avi .mkv .mov .m4v .mpg .mpeg .ogv .vp8`).

By default the script looks in `Documents\Clone Hero\Songs` and `Documents\Video Dumps`
inside your user folder. If yours are elsewhere (including a Documents folder redirected
to OneDrive), pass `--songs` and `--dumps`, or edit `SONGS_ROOT` / `DUMPS_ROOT` near the
top of the script.

## Quick start

1. **Unzip** the video dumps into your dumps folder, one folder per song.
2. Open a terminal (Command Prompt or PowerShell) in the folder with the script.
3. **Preview first.** Nothing is moved:
   ```
   python place_videos.py --dry-run
   ```
   On Windows, use `py place_videos.py --dry-run` if `python` isn't recognized.
4. **Place the obvious ones automatically:**
   ```
   python place_videos.py --auto
   ```
   Exact matches are moved without asking. It stops to ask about everything else.
5. **Run it normally for what's left:**
   ```
   python place_videos.py
   ```
6. Check `place_videos.log` (next to the script) for a full record.

### Keys

| Key | What it does |
| --- | --- |
| `y` | Do it |
| `n` | Skip this one (it will come up again next run) |
| `q` | Quit (Ctrl+C also quits) |
| `1`-`9` | Choose one of several possible songs |

## Options

| Option | Meaning |
| --- | --- |
| `--songs PATH` | Your Clone Hero `Songs` folder |
| `--dumps PATH` | Folder holding the unzipped video dumps |
| `--dry-run` | Show what would happen; change nothing |
| `--copy` | Copy the video instead of moving it (the dump folder is left untouched) |
| `--auto` | Place clear-cut matches without asking (see below) |
| `--auto-min SCORE` | With `--auto`, the lowest match score (0-1) accepted without asking. Default `1.0` = exact matches only. `0.9` also accepts close guesses |
| `--no-clear` | Don't clear the screen between questions |
| `--log PATH` | Write the action log somewhere else |

### What `--auto` still asks about

- **Several possible songs**: you pick from the numbered list.
- **A guess**: a fuzzy or "contains" match below the `--auto-min` score.
- **Replacing a video**: the song already has a `video.*` file.

Automatic placements are tagged `[auto]` in the log, and the final line reports how many
there were.

## What a session looks like

Each question gets a fresh screen, with the counters and the last action at the top:

```
[6/340]  done 5   skipped 0   no match 2
Last: MOVE Guitar Hero World Unzipped Video Dump\Cochise\video.mp4 -> C:\Users\YourName\Documents\Clone Hero\Songs\...\Audioslave - Cochise\video.mp4   [folder renamed to "(moved) Cochise"]
------------------------------------------------------------------------------
Dump: Guitar Hero World Unzipped Video Dump\Are You Gonna Go My Way\video.webm
   Several possible matches:
     1) Guitar Hero World Tour\Lenny Kravitz - Are You Gonna Go My Way   [exact name match]
     2) Guitar Hero Smash Hits\Lenny Kravitz - Are You Gonna Go My Way   [exact name match]
   Press 1-2 to pick, [n] to skip, [q] to quit
```

## How matching works

Both names are normalized (lowercased, accents removed, everything except letters and
digits dropped), so `L_Via L_Viaquez` and `L'Via L'Viaquez` both become `lvialviaquez`.
The first stage that finds anything wins:

1. **Exact** match on the title, on "artist + title", or on the song folder's name.
2. **Contains**: one name sits inside the other (handles extras like `(Live)`).
   Ignored for very short names.
3. **Fuzzy**: close spelling, using Python's `difflib`.

If several songs tie, the words in the dump's parent folder (such as "Guitar Hero World")
are compared with the song's own folder path to put the likeliest one first.

You can tune `FUZZY_CUTOFF`, `MIN_SUBSTRING_LEN`, `MAX_CANDIDATES`, `VIDEO_EXTS` and
`MOVED_PREFIX` at the top of the script.

## What it changes on disk

- Moves (or copies) the video into the song folder, renamed to `video` plus its original
  extension.
- After a **move**, renames the dump folder to `(moved) <name>`. If that name is taken it
  uses `(moved) <name> (2)`. If Windows refuses the rename (say the folder is open in
  Explorer), the video is still moved and the log says `folder NOT renamed`.
  Folders starting with `(moved) ` are skipped on later runs.
- If a song **already has** a video, it asks before replacing it. Nothing is replaced
  without a `y`.
- Appends to `place_videos.log`. Nothing else is created, edited or deleted.

`--dry-run` and `--copy` never rename dump folders.

## The log

One line per action, in the same style as the `--dry-run` output:

```
04:23:25  MOVE Guitar Hero World Unzipped Video Dump\Cochise\video.mp4 -> C:\Users\YourName\Documents\Clone Hero\Songs\...\video.mp4   [folder renamed to "(moved) Cochise"]   [auto]
04:23:25  SKIP Guitar Hero World Unzipped Video Dump\Everlong\video.webm (you pressed n)
04:23:26  NO MATCH Guitar Hero World Unzipped Video Dump\Totally Unknown Song\video.webm
```

The log contains paths from your own computer, so don't publish it (`.gitignore` already
excludes it).

## Troubleshooting

- **"No match found" for a song I know I have.** The song folder needs a `song.ini`,
  `notes.chart` or `notes.mid`. Songs packed as a single `.sng` file aren't supported.
  Also check the dump folder isn't named very differently from the song title.
- **It suggests the wrong song.** Press `n` and it will be listed again next time. For
  duplicates across games, the numbered list shows every candidate.
- **Folders not found.** Pass `--songs` and `--dumps` explicitly. See the layout section
  above.
- **The video doesn't play in Clone Hero.** The script only places files; it doesn't
  convert them. Check which video formats your Clone Hero version supports.

## Contributing

Issues and pull requests are welcome. When you report a bad match, include the dump
folder name and the song's folder name (leave out personal paths).
