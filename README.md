# Day One → Apple Journal

Move your **Day One** journal into **Apple Journal**, with the original dates and your **photos attached automatically**.

Apple Journal has no import feature. This repo gives you:

- **`dayone_to_journal.py`**: converts a Day One JSON export into one small text file per entry, and sorts your photos by entry. It runs offline on your Mac, so your journal never leaves your computer.
- **An Apple Shortcut** that reads those files and creates each Journal entry with its date, title, text and photos.

Tested with ~200 entries (33 with photos) from Day One to Apple Journal on iPadOS 26.

---

## What carries over

| Day One | Apple Journal |
|---|---|
| Entry text (Markdown) | ✅ Entry text |
| Date & time (in the time zone you wrote it) | ✅ Entry date |
| `# Heading` first line | ✅ Entry title |
| Photos | ✅ Attached automatically |
| Photo-only entries | ✅ Imported with 📷 as the text |
| Location | ⚠️ Optional, added as text (`--add-location`) |
| Tags | ⚠️ Optional, added as `#tags` text (`--add-tags`) |
| Starred, templates, weather | ❌ Not carried over |

---

## Requirements

- A **Mac** with Python 3.9+ (`python3` comes with macOS; the first run may ask to install developer tools, so say yes)
- **Apple Journal** on iPadOS 26 / iOS 26 (run the Shortcut on iPad or iPhone, see [Known issues](#known-issues))
- **iCloud Drive**, to move files between Mac and iPad

---

## Step 1: Export from Day One

1. In Day One, open **Settings → Import/Export → Export** (or the **•••** menu → **Export**).
2. Choose **JSON** and include photos. You'll get a **ZIP** file.
3. AirDrop or copy the ZIP to your Mac (e.g. into **Downloads**).

## Step 2: Convert the export

Download `dayone_to_journal.py` into the same folder, open **Terminal**, and run:

```bash
python3 ~/Downloads/dayone_to_journal.py ~/Downloads/YourExport.zip
```

> Tip: type `python3 ~/Downloads/dayone_to_journal.py ` (with a space), then **drag the ZIP into Terminal** to paste its path.

You'll see something like:

```
✅ Converted 194 entries from 1 journal(s) into 2 batch folder(s).
   After importing, Apple Journal should show 194 entries.
   33 entries had photos/media → see PHOTO_CHECKLIST.txt
```

It creates a **`Journal Import`** folder next to the ZIP:

```
Journal Import/
├── batch_01/            0001.txt … 0100.txt
├── batch_02/            0101.txt … 
├── photos_by_entry/     0042_2025-03-14_1.jpeg …
└── PHOTO_CHECKLIST.txt  which photos belong to which entry
```

Each `.txt` file is one entry:

```
2025-03-14 23:10:05|||Morning pages|||Woke up early. Felt good.|||0042_2025-03-14_1.jpeg
```

`date|||title|||text|||photo files` (the last field is `-` when there are no photos).

### Options

| Option | What it does |
|---|---|
| `--first-line-as-title` | Use each entry's first line as its title (default: only `# Heading` lines) |
| `--add-location` | Add `📍 Place, City, Country` to the end of the entry |
| `--add-tags` | Add Day One tags as `#tags` to the end of the entry |
| `--batch-size 100` | Entries per batch folder |
| `--tz Asia/Colombo` | Time zone for entries with none recorded (default: your Mac's) |
| `--out FOLDER` | Where to write the output |

**Move the `Journal Import` folder into iCloud Drive** so your iPad can see it.

## Step 3: Get the Shortcut

**Option A: install it:** [Day One to Apple Journal (iCloud Shortcut)](https://www.icloud.com/shortcuts/6fb04219462248c3b867aee35a61bc0c)

When you add it, Shortcuts lets you review every action first, so check what it does before you install it.

After adding it, open the Shortcut, find **Get File from Folder**, and set **Folder** to your own **iCloud Drive → Journal Import → photos_by_entry**.

**Option B: build it yourself** (5 minutes, in the Shortcuts app):

```
Select File  (Select Multiple: ON)
Repeat with each item in Files
    Get Text from Input  (Repeat Item)
    Split Text  by Custom: |||
    Get Item from List: First Item of Split Text → Get Dates from Input → Set Variable EntryDate
    Get Item from List: Item at Index 2 of Split Text → Set Variable EntryTitle
    Get Item from List: Item at Index 3 of Split Text → Set Variable EntryBody
    Get Item from List: Item at Index 4 of Split Text → Set Variable EntryPhotos
    If EntryPhotos is "-"
        Journal → Create Entry (Message: EntryBody, Title: EntryTitle, Date: EntryDate)
    Otherwise
        Split Text  EntryPhotos by Custom: ,
        Repeat with each item in Split Text
            Get File from Folder  (Folder: photos_by_entry, Path: Repeat Item 2, Error If Not Found: OFF)
        End Repeat
        Journal → Create Entry (Message: EntryBody, Title: EntryTitle, Date: EntryDate,
                                Media Items: Repeat Results)
    End If
End Repeat
```

In both **Create Entry** actions, set **Open When Run: OFF** and **Add Bookmark: OFF**.
For **Get Item from List** at index 2, 3 and 4, make sure the list is **Split Text**. It defaults to the previous action's result.
Use the **Create Entry** action from **Journal** (Apple), not from Day One.

## Step 4: Test with 3 entries

Run the Shortcut and select 3 files from `batch_01`: one **with photos**, one **📷 photo-only**, and one **without photos** (see `PHOTO_CHECKLIST.txt`).
Check in Journal that the **dates**, **text** and **photos** are right, then delete those 3 test entries.

## Step 5: Import everything

1. **Quit Journal** (swipe it away). Keeping it closed during the import avoids slowdowns.
2. Keep the device **plugged in** with **Auto-Lock → Never**.
3. Run the Shortcut → open `batch_01` → **Select All** → **Open**. Wait until it finishes.
4. Quit Journal again, then do the same for `batch_02` (and so on).
5. Check that Journal's entry count matches the number the script printed.

Keep your Day One export ZIP as a backup until you've checked everything.

---

## Known issues

- **Shortcuts on macOS can't find Journal's actions** on some Macs. Run the Shortcut on **iPad or iPhone** instead.
- **Location can't be set as a real Journal location**: the Shortcut's location field only accepts a place you pick by hand. Use `--add-location` to keep it as text.
- **Imports slow down over time**: quit Journal between batches and keep batches at ~100.
- **Don't run a batch twice**: it creates duplicates. If a batch stops partway, find the newest imported date and run only the remaining files (they're numbered in date order).
- **Avoid entries with blank text**: Journal hides entries with no visible text, and they can't be deleted. The script prevents this by giving photo-only entries 📷 as their text and skipping completely empty entries.

---

## Credits

- Builds on **Felix Wong's** method: [How I Imported Day One Journal Entries into Apple Journal](https://felixwong.com/2026/08/how-i-imported-day-one-into-apple-journal/). The `date|||title|||text` format and Shortcut idea are his.
- Tips on batching and quitting Journal between batches from [James Troutman](https://namelyjt.com/2026/11/09/journaling/).
- This repo adds an offline converter (no AI step), time-zone handling, Day One formatting cleanup, and **automatic photo import**.
- Built with help from Claude (Anthropic).

## License

MIT
