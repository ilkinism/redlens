"use strict";

/* The guided walk.
 *
 * The comparison happens on the server; this file is about reading one change
 * at a time and building the reply as you go. The note is composed server-side
 * too, so what is copied is exactly what the tested code produces -- the page
 * never writes prose of its own. */

const el = (id) => document.getElementById(id);

const state = {
  before: null,          // {name, base64}
  after: null,
  changes: [],
  setAside: [],
  verdicts: new Map(),   // change index -> "accepted" | "queried"
  current: -1,
  request: 0,            // guards against a slow comparison landing last
  forced: false,         // the user chose to compare seemingly unrelated files
};

/* ---------- reading files ---------- */

function toBase64(buffer) {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  const step = 0x8000;                       // chunked: apply() has an arg limit
  for (let i = 0; i < bytes.length; i += step) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + step));
  }
  return btoa(binary);
}

async function chooseFile(input, slot, noteId) {
  const file = input.files && input.files[0];
  const note = el(noteId);
  if (!file) {
    state[slot] = null;
    note.textContent = "No file chosen";
    note.classList.remove("chosen");
    return;
  }
  note.textContent = "Reading " + file.name + "…";
  note.classList.add("chosen");
  try {
    const base64 = toBase64(await file.arrayBuffer());
    state[slot] = { name: file.name, base64 };
    note.textContent = file.name;
  } catch (error) {
    state[slot] = null;
    note.textContent = "That file could not be read from disk.";
    note.classList.remove("chosen");
  }
  state.forced = false;
  readyToCompare();
}

function readyToCompare() {
  el("compare").disabled = !(state.before && state.after);
}

/* ---------- talking to the server ---------- */

function payload() {
  return {
    before: state.before.base64, before_name: state.before.name,
    after: state.after.base64, after_name: state.after.name,
  };
}

async function post(path, body) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  let data = {};
  try { data = await response.json(); } catch (error) { data = {}; }
  return { ok: response.ok, data };
}

async function compareNow() {
  if (!state.before || !state.after) {
    setProblem("");
    return;
  }
  const ticket = ++state.request;
  reset();
  el("count-line").textContent = "Reading the returned version…";

  let result;
  try {
    result = await post("/api/compare", payload());
  } catch (error) {
    if (ticket !== state.request) { return; }
    setProblem("The comparison could not be run. Is Redlens still running?");
    el("count-line").textContent = "Choose the version you sent and the version that came back.";
    el("empty").hidden = false;
    showChooser(true);
    return;
  }
  if (ticket !== state.request) { return; }   // a newer comparison has started

  if (!result.ok) {
    setProblem(result.data.error || "Those files could not be compared.");
    el("count-line").textContent = "Choose the version you sent and the version that came back.";
    el("empty").hidden = false;
    showChooser(true);
    return;
  }
  setProblem("");
  render(result.data);
}

/* ---------- rendering ---------- */

function showChooser(show) {
  el("chooser").hidden = !show;
  el("chosen-bar").hidden = show || !(state.before && state.after);
  if (state.before && state.after) {
    el("chosen-names").textContent =
      state.before.name + "  \u2192  " + state.after.name;
  }
}

function reset() {
  state.changes = [];
  state.setAside = [];
  state.verdicts = new Map();
  state.current = -1;
  el("reading").hidden = true;
  el("unrelated").hidden = true;
  el("empty").hidden = true;
  el("changes").replaceChildren();
  el("set-aside").hidden = true;
  el("nothing").hidden = true;
  el("copied").textContent = "";
  refreshNote();
}

function sentence(summary) {
  const changes = summary.changes;
  const aside = summary.set_aside;
  if (changes === 0) {
    return aside === 0
      ? "Nothing changed at all."
      : "Nothing substantive changed. " + aside +
        (aside === 1 ? " difference was" : " differences were") + " formatting only.";
  }
  // "2 duration" is not English. Each kind gets the phrase that reads.
  const phrasing = { money: "to money", duration: "to durations",
                     date: "to dates", number: "to numbers",
                     wording: "to wording" };
  const kinds = Object.keys(summary.by_kind)
    .map((kind) => summary.by_kind[kind] + " " + (phrasing[kind] || "to " + kind))
    .join(", ");
  const head = changes + (changes === 1 ? " change" : " changes") + " to look at";
  const tail = aside === 0 ? "" : ", " + aside + " set aside as formatting";
  return head + tail + " — " + kinds + ".";
}

function render(data) {
  state.changes = data.changes;
  state.setAside = data.set_aside;

  if (data.unrelated && !state.forced) {
    el("count-line").textContent =
      "These two files have almost nothing in common.";
    el("unrelated-detail").textContent =
      "Only " + data.summary.matched + " of " + data.summary.paragraphs_before +
      " paragraphs are recognisably the same. Are these versions of the same " +
      "document? Comparing unrelated files produces findings that are all noise.";
    el("unrelated").hidden = false;
    showChooser(false);
    return;
  }

  el("count-line").textContent = sentence(data.summary);
  el("reading").hidden = false;
  showChooser(false);

  const list = el("changes");
  list.replaceChildren();
  state.changes.forEach((change, position) => {
    list.appendChild(changeNode(change, position));
  });
  el("nothing").hidden = state.changes.length !== 0;

  if (state.setAside.length > 0) {
    el("set-aside-count").textContent =
      state.setAside.length + " difference" + (state.setAside.length === 1 ? "" : "s") +
      " set aside as formatting";
    const asideList = el("set-aside-list");
    asideList.replaceChildren();
    state.setAside.forEach((pair) => {
      const item = document.createElement("li");
      const was = document.createElement("div");
      was.textContent = "Was: " + pair.before;
      const now = document.createElement("div");
      now.textContent = "Now: " + pair.after;
      item.append(was, now);
      asideList.appendChild(item);
    });
    el("set-aside").hidden = false;
  }

  if (state.changes.length > 0) { focusChange(0); }
  refreshNote();
}

function marked(pieces, side) {
  const holder = document.createElement("p");
  holder.className = "text";
  if (pieces.length === 0) {
    const absent = document.createElement("span");
    absent.className = "absent";
    absent.textContent = side === "before" ? "This clause is new." : "This clause was removed.";
    holder.appendChild(absent);
    return holder;
  }
  pieces.forEach((piece, position) => {
    // Runs hold words, not spacing, so the separator goes between them as
    // plain text -- that keeps the mark tight around the words themselves
    // rather than striking through the space beside them.
    if (position > 0) { holder.appendChild(document.createTextNode(" ")); }
    let node;
    if (piece.mark === "removed") {
      node = document.createElement("del");
    } else if (piece.mark === "added") {
      node = document.createElement("ins");
    } else {
      node = document.createElement("span");
    }
    node.textContent = piece.text;
    holder.appendChild(node);
  });
  return holder;
}

function changeNode(change, position) {
  const item = document.createElement("li");
  const section = document.createElement("section");
  section.className = "change";
  section.id = "change-" + change.index;
  section.tabIndex = 0;
  section.setAttribute("aria-labelledby", "change-heading-" + change.index);

  const heading = document.createElement("h3");
  heading.className = "change-heading";
  heading.id = "change-heading-" + change.index;

  const kind = document.createElement("span");
  kind.className = "kind";
  kind.textContent = change.nature === "edited" ? change.kind : change.nature;
  const words = document.createElement("span");
  words.textContent = change.headline;
  const verdict = document.createElement("span");
  verdict.className = "verdict";
  heading.append(kind, words, verdict);
  section.appendChild(heading);

  const pair = document.createElement("div");
  pair.className = "pair";
  [["The version you sent", change.marked_before, "before"],
   ["The version that came back", change.marked_after, "after"]].forEach(([label, pieces, side]) => {
    const box = document.createElement("div");
    box.className = "side";
    const tag = document.createElement("span");
    tag.className = "side-label";
    tag.textContent = label;
    box.append(tag, marked(pieces, side));
    pair.appendChild(box);
  });
  section.appendChild(pair);

  const decide = document.createElement("div");
  decide.className = "decide";
  const accept = document.createElement("button");
  accept.type = "button";
  accept.className = "secondary";
  accept.textContent = "Accept";
  accept.addEventListener("click", () => decideOn(position, "accepted"));
  const query = document.createElement("button");
  query.type = "button";
  query.className = "secondary";
  query.textContent = "Query";
  query.addEventListener("click", () => decideOn(position, "queried"));
  decide.append(accept, query);
  section.appendChild(decide);

  section.addEventListener("focus", () => markCurrent(position));
  item.appendChild(section);
  return item;
}

/* ---------- deciding ---------- */

function nodeFor(position) {
  const change = state.changes[position];
  return change ? el("change-" + change.index) : null;
}

function markCurrent(position) {
  state.current = position;
  state.changes.forEach((change, index) => {
    const node = el("change-" + change.index);
    if (node) { node.classList.toggle("current", index === position); }
  });
  el("position").textContent = state.changes.length === 0 ? "" :
    "Change " + (position + 1) + " of " + state.changes.length;
}

function focusChange(position) {
  const node = nodeFor(position);
  if (!node) { return; }
  markCurrent(position);
  node.focus();
}

function decideOn(position, verdict) {
  const change = state.changes[position];
  if (!change) { return; }
  if (state.verdicts.get(change.index) === verdict) {
    state.verdicts.delete(change.index);       // pressing it again undoes it
  } else {
    state.verdicts.set(change.index, verdict);
  }
  const node = el("change-" + change.index);
  const decided = state.verdicts.get(change.index);
  node.classList.toggle("accepted", decided === "accepted");
  node.classList.toggle("queried", decided === "queried");
  node.querySelector(".verdict").textContent =
    decided === "accepted" ? "Accepted" : decided === "queried" ? "Queried" : "";
  refreshNote();
  if (decided && position + 1 < state.changes.length) { focusChange(position + 1); }
}

/* ---------- the note ---------- */

function queried() {
  return state.changes
    .filter((change) => state.verdicts.get(change.index) === "queried")
    .map((change) => change.index);
}

let noteTicket = 0;

async function refreshNote() {
  const wanted = queried();
  const ticket = ++noteTicket;
  const button = el("copy-note");
  if (wanted.length === 0) {
    el("note").hidden = true;
    el("note").textContent = "";
    el("note-state").textContent = "Query a change and it starts writing itself.";
    button.disabled = true;
    return;
  }
  el("note-state").textContent =
    wanted.length + (wanted.length === 1 ? " query" : " queries") + " so far.";
  const body = Object.assign(payload(), { queried: wanted });
  let result;
  try {
    result = await post("/api/note", body);
  } catch (error) {
    return;
  }
  if (ticket !== noteTicket) { return; }
  if (!result.ok) { return; }
  el("note").textContent = result.data.note;
  el("note").hidden = false;
  button.disabled = false;
}

async function copyNote() {
  const text = el("note").textContent;
  if (!text) { return; }
  try {
    await navigator.clipboard.writeText(text);
    el("copied").textContent = "Copied. Paste it into your reply.";
  } catch (error) {
    // Clipboard access can be refused; selecting the text still works.
    const range = document.createRange();
    range.selectNodeContents(el("note"));
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    el("copied").textContent = "The note is selected — press Ctrl+C to copy it.";
  }
}

/* ---------- problems ---------- */

function setProblem(message) {
  const box = el("problem");
  box.textContent = message;
  box.hidden = !message;
}

/* ---------- wiring ---------- */

el("before-file").addEventListener("change", (event) =>
  chooseFile(event.target, "before", "before-note"));
el("after-file").addEventListener("change", (event) =>
  chooseFile(event.target, "after", "after-note"));
el("copy-note").addEventListener("click", copyNote);
el("compare").addEventListener("click", () => { state.forced = false; compareNow(); });
el("change-files").addEventListener("click", () => {
  showChooser(true);
  el("before-file").focus();
});
el("unrelated-continue").addEventListener("click", () => {
  state.forced = true;
  compareNow();
});

document.addEventListener("keydown", (event) => {
  const typing = ["INPUT", "TEXTAREA", "SELECT"].indexOf(event.target.tagName) !== -1;
  if (typing || event.ctrlKey || event.metaKey || event.altKey) { return; }
  const key = event.key.toLowerCase();
  if (key === "j" || event.key === "ArrowDown") {
    if (state.changes.length === 0) { return; }
    event.preventDefault();
    focusChange(Math.min(state.current + 1, state.changes.length - 1));
  } else if (key === "k" || event.key === "ArrowUp") {
    if (state.changes.length === 0) { return; }
    event.preventDefault();
    focusChange(Math.max(state.current - 1, 0));
  } else if (key === "a" && state.current >= 0) {
    event.preventDefault();
    decideOn(state.current, "accepted");
  } else if (key === "q" && state.current >= 0) {
    event.preventDefault();
    decideOn(state.current, "queried");
  } else if (key === "c" && !el("copy-note").disabled) {
    event.preventDefault();
    copyNote();
  }
});
