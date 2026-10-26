---
title: Selecting many exercises
linkTitle: Selecting many
weight: 5
description: The checkboxes of a deck's page — ranges, tags, copying and moving to another deck, Set to new, deleting, and cramming a selection.
---

Every row of [a deck's page](deck-page.md) has a checkbox, and the bar under
the filters works on what is ticked: tag twenty exercises at once, move a
lesson's worth into a deck of its own, start a chapter over, or cram just
the ones for tomorrow's test.

## Choosing what to select

- **A checkbox** selects one exercise.
- **Shift with a click** selects everything between the last one you ticked
  and this one — on a checkbox or anywhere on a row. The same on a row that
  is already selected **deselects** the range instead. The tip under the
  bar reminds you: *Shift-click a checkbox or exercise row to select or
  deselect a range.*
- **Select all** selects every exercise of the deck, shown or not, and
  **Deselect all** lets everything go.
- **Select shown** adds only the rows the filters show — pick the tag
  `food` in the filters, then **Select shown**, and you have the food.
- **Deselect shown** is its opposite: it lets go of the rows the filters
  show, and whatever they hide stays selected. **Select all**, then the
  type *Flashcard* in the filters and **Deselect shown**, and you have
  every exercise but the flashcards.
- **Select by tag** asks for a tag — every tag of the deck is offered — and
  **Select matching** makes the selection exactly the exercises with it
  (what was selected before is let go). A deck with no tags says *This deck
  has no exercise tags yet*.

`3 selected`, beside these buttons, always says how many there are.

A range follows the rows **as they are shown**, so with a filter on it
takes only what you see between the two clicks — and an exercise the filter
hides keeps whatever state it had. The selection itself lasts: changing the
filters, adding or removing tags, copying, even leaving the page and coming
back in the same tab leaves it as it was. An exercise that is deleted drops
out of it.

## What to do with them

The buttons stay dimmed until something is selected.

### Copying and moving to another deck

**Copy to deck…** and **Move to deck…** ask for the **Destination deck**:
every other deck of the **same language** (with none, you are told to
*Create another deck in this language first*).

| | **Copy to deck** | **Move to deck** |
|---|---|---|
| The exercises here | stay | leave this deck |
| In the other deck | new copies, **starting as new** | the same exercises, **with their schedule and history** |
| Tags, pictures, recordings | come along | come along |
| Where they came from | kept | kept |

*Copies keep their tags and start with fresh scheduling*, as the copy dialog
puts it; *Scheduling and tags travel with moved exercises*, as the move
dialog does. The pictures and recordings they name are copied into the other
deck's folders, under another name if that deck already has a different
file of the same name — exactly as a copy from a document. A copy is not
checked against what the other deck already holds. In the other deck they
count as just added, so a new one waits after the new exercises already
there.

**A pair travels whole.** When both sides of a [linked
pair](deck-page.md#linked-cards) are among the selected exercises, they
arrive as a linked pair in the other deck, front first. A side chosen
without the other arrives linked with nothing — a link never crosses from
one deck to another — and a **move** of one side leaves the other, in this
deck, linked with nothing too.

**After a move of the selection** you are taken to the other deck, with the
moved exercises selected there, and told how many moved — so you can go on
working on them where they now are. Each row also has its own **Copy to
deck…** and **Move to deck…**, for one exercise: moving a row that is part
of the selection takes you along in the same way; moving one that is not
leaves you where you were.

### Tags

- **Add tag…** asks for one tag and puts it on every selected exercise. A
  tag may hold spaces; it is kept in lower case (`Week 1` becomes
  `week 1`).
- **Remove tag…** offers the tags the selected exercises carry, and takes
  the one you pick off all of them.

The selection stays after both, so replacing an old tag with a new one is
**Remove tag…** and **Add tag…** in a row, without selecting again.

Tags come into a deck with the exercises copied from a document (the
document's tags), and can then be added and removed here. They are the
deck's own: changing a document's tags afterwards changes nothing in the
deck.

### Set to new

**Set to new** asks *Set 3 exercises to new?* — *Their review history and
scheduling will be cleared. They will remain selected.* The exercises then
come back as if they had never been studied — new, with no reviews and no
lapses, in their place among the new exercises (the order they were first
added in). Use it to start a chapter over after a long break.

### Make a follow-up chain of these…

**Make a follow-up chain of these…** takes the selected exercises, in the order
of the list, as the steps of a new [follow-up](../dialect-exercises/follow-up.md)
and opens its form with them already in. A box under the steps — not ticked —
offers to take the originals out of the deck once the chain is saved (their study
history goes with them). It needs two exercises, and one that needs attention,
one that is a follow-up and one that is a side of a linked pair cannot be a step:
the button says which, and nothing opens.

### Delete

**Delete** asks *Delete 3 exercises?* — *Their scheduling will be deleted
too.* — and **Delete selected** removes them and their histories for good.

When a selected exercise is one side of a [linked
pair](deck-page.md#linked-cards) whose other side is **not** selected, the
question is asked **once**, for the whole selection: *3 picked exercises are
one side of a pair whose other side is not picked*, with the other sides
listed. **Delete their other sides too** takes them with the selection;
**Delete only the selected** leaves them, each linked with nothing from then
on; **Cancel** does nothing. Select both sides of a pair, and there is
nothing to ask.

### Cram

**Cram exercises** — which says **Cram 3 exercises** once three are selected
— practises the selection in [cram mode](cram.md): all of it, in random
order, with no effect on the schedule.

### Export to HTML

**Export selected to HTML**, beside it, makes the selection one HTML page
that crams it, to put on a website for students who have no Parseh: see
[Cram mode](cram.md#as-a-page-for-a-website).

## Working by tag {#by-tag}

Put together, the tag tools make a deck easy to slice. A deck filled from
several lessons, each document tagged with its lesson, can be:

1. studied a lesson at a time in cram mode — **Select by tag**, `lesson-3`,
   **Cram**;
2. split — make a deck of the same language with **+ New deck** on the
   decks page, then **Select by tag** and **Move to deck…** into it;
3. started over — **Select by tag**, then **Set to new**.
