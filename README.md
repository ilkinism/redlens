# Redlens

*[Azərbaycan dili](README.az.md)*

The contract came back clean. Here is what actually changed.

![Six changes found in a returned contract, marked the way a person marks up a page](docs/screenshots/02-what-actually-changed.png)

## What it does

Choose the version you sent and the version that came back. Redlens reads both,
separates the changes that matter from the ones that do not, and walks you
through them one at a time:

> **MONEY — Clause 9.2: £1,000,000 → £250,000**
> 9.2 Liability. The Supplier's total liability shall not exceed ~~£1,000,000~~ / £250,000.

Accept a change or query it. What you query becomes the note you send back:

> Comparing round-two.docx with round-three.docx, we have queries on 2 changes:
>
> 1. Clause 9.2: the figure has changed from £1,000,000 to £250,000.
>    Was: "9.2 Liability. The Supplier's total liability shall not exceed £1,000,000."
>    Now: "9.2 Liability. The Supplier's total liability shall not exceed £250,000."
>
> 2. Clause 2: the period has changed from 24 months to 36 months.
>    …
>
> Please confirm whether these were intended.

Both documents are read on your own machine. Neither is uploaded and neither is
stored — nothing survives the comparison.

## Why it exists

A negotiated contract comes back without tracked changes, and the only honest
way to review it is to read forty pages against the version you sent. The tools
that automate this are built for developers reading source code: they show a
moved comma and a halved liability cap as the same kind of thing, character by
character, which is exactly what makes a redline exhausting.

Redlens is built around the opposite claim: **most differences between two
rounds of a contract are not worth a second of your attention, and a small
number are worth a paragraph in your reply.** So it:

- separates **money, dates, durations and numbers** from wording, and orders
  them that way;
- treats a smart quote, an em dash and a double space as **formatting** — set
  aside with a count you can open, never silently dropped;
- pairs paragraphs across an inserted or deleted clause **by clause number
  first**, so removing clause 5 does not misalign everything after it;
- says plainly when two files are **not versions of the same document**, rather
  than producing a hundred meaningless findings.

## Running it

Python 3.10 or newer. No dependencies, no build step, no installation.

```
python run.py
```

Then open <http://127.0.0.1:3300/>.

To use a different port:

```
REDLENS_PORT=4300 python run.py
```

Or edit `config.json`. `config.example.json` shows every setting.

## What it reads

| Format | Read |
|---|---|
| `.docx` (Word 2007 and later) | Yes — this is what negotiated rounds arrive as |
| `.txt`, `.md`, plain text | Yes |
| `.doc` (Word 97–2003) | No — open it in Word and save as `.docx` |
| PDF | No — a PDF is usually the signed end of a negotiation, not a round of it |
| Scanned or photographed pages | No — there is no text in an image to compare |

Redlens says which of these it is looking at and what to do about it, rather
than failing silently.

## Using it

| Key | Does |
|---|---|
| `J` / `↓` | next change |
| `K` / `↑` | previous change |
| `A` | accept the current change |
| `Q` | query it |
| `C` | copy the note |

Accepting or querying moves to the next change, so the whole review is `Q`, `A`,
`A`, `Q`, `C` without touching the mouse.

![Choosing the two versions](docs/screenshots/01-choose-the-two-versions.png)

## What counts as a change

A paragraph is **cosmetic** if the two versions are the same once curly quotes,
dashes, ellipses, non-breaking spaces and runs of whitespace are folded and case
is ignored. Everything else is **substantive** and is reported by kind:

- **money** — `£1,000,000 → £250,000`
- **duration** — `24 months → 36 months`
- **date** — `1 January 2026 → 1 March 2026`
- **number** — a figure that is none of the above
- **wording** — the paragraph changed but no value in it did

When a money, duration or date change explains the paragraph, the bare numbers
inside it are not also reported: one finding, not four.

Clauses that were **inserted** or **removed** are reported separately, because a
new clause is a different kind of event from an edited one.

## What it does not do

- It does not tell you whether a change is acceptable. That is your judgement,
  and the note it writes is a set of questions, not an opinion.
- It does not read tracked changes, comments or formatting — only what the
  document says.
- It does not open PDFs, and it will not guess at scanned pages.
- It does not touch the network. There is no client of any kind in the code,
  and the page is served with a policy that forbids the browser from making an
  outbound request.

## Privacy

Contracts are the most confidential documents most people handle, so:

- both files are sent to `127.0.0.1` and held in memory for the length of one
  request;
- nothing is written to disk — there is no database, no cache and no log of
  what you compared;
- the page is served with `Content-Security-Policy: default-src 'self';
  connect-src 'self'`, so the browser cannot send your contract anywhere even
  if the page tried;
- the server binds the loopback address only.

## Limits

| Limit | Default | Setting |
|---|---|---|
| File size | 20 MB | `max_document_bytes` |
| Unpacked document | 128 MB | fixed |
| Paragraphs per document | 20,000 | `max_paragraphs` |
| Changes reported | 2,000 | `max_changes` |

A 2,000-paragraph contract compared against an edited copy takes about 90 ms.

Hostile documents are refused rather than opened: a `.docx` that unpacks to
gigabytes, and one carrying a document type declaration — which Word never
writes, and which can be used to expand a kilobyte into hundreds of megabytes or
to read a file off your machine.

## Tests

```
python -m pytest
```

80 tests: the comparison rules, the note, the document reader (including
deliberately hostile files), the HTTP API, the three user stories from the
design brief, and a subprocess test that `python run.py` actually starts the app
from a fresh clone.

## Licence

MIT. See [LICENSE](LICENSE).
