---
title: Recording a YouTube video's sound
linkTitle: A YouTube video's sound
weight: 6
description: How the cut editor records the stretch of a YouTube video from the browser tab, what Chrome asks, the reach row, and what each message means.
---

A YouTube video plays inside a frame of YouTube's own, and no script on
the page can read its sound; there is no file of it anywhere the toolbox
can reach. What **Chrome and Edge on a computer** do allow, once you say
so, is a recording of **the tab itself**, sound and all. So for a YouTube
video the cut editor first plays the stretch of the video once and records
the tab while it plays, and then cuts the clip out of that recording, in
the browser.

## Where it works

Anywhere else **🔊 cut the audio…** is greyed out, and the note under it
says why:

| Under the button | Why, and what to do |
|---|---|
| … only Chrome and Edge, on a computer, can record the sound of a tab | Firefox, Safari, a phone or a tablet: open the video in Chrome or Edge on a computer |
| … recording this tab needs the page opened at this computer’s address, or at the https address from another device, in Chrome or Edge | the page was opened over plain `http://` (a `localhost` address apart): use the toolbox's `https://` address |
| … this browser cannot read the sound of a shared tab | a Chromium browser too old for it |
| the YouTube player has not loaded, so there is no sound to record | wait: the button turns on by itself when the player is there |

The page asks for a browser built on **Chromium**, as Chrome and Edge are,
so another one built on it passes too.

## Recording, step by step

1. **cut the audio…** opens the editor on a sentence saying what is about
   to happen — *A YouTube video’s sound is cut from a recording of this
   tab: the stretch 11.13–15.40 s plays once, sound on, while it is
   recorded. Chrome asks first: press “Allow”, and leave “Also allow tab
   audio” turned on.* — and a **● record** button, which **Enter** presses
   too.
2. **Press it.** Chrome asks whether to share this tab, with **Also allow
   tab audio** switched on. **Leave it on**, and press **Allow**. While the
   tab is shared, Chrome says so in a bar across the top of the page, with
   a **Stop sharing** button, and the page moves down a little to make
   room for it.
3. **The video plays the stretch** the strip will show — the sentence and
   a second either side — from half a second before it to half a second
   after, sound on, at full volume and at normal speed, while a bar in the
   editor fills and the status line counts the seconds: *recording
   11.13–15.40 s of the video: 2.10 of 4.27 s*. The toolbox's own players
   on the page are silenced meanwhile. Afterwards the video goes back to
   where it stood, with its own mute, volume and speed.
4. **Then the editor works on that recording** as it would on a
   narration: *recorded 10.63–15.90 s: move the edges by ear, then save
   the clip*. The strip, the rows, the keys and the previews are the ones
   described in [Cutting the audio](cutting-the-audio.md); the previews
   play the recording, not the video, and the waveform is drawn in the
   browser from the recording itself, ffmpeg or not.
5. **save clip** cuts the clip out of the recording there and then, as a
   WAV with 8 ms of fade at each end, and sends it to the clip tray, which
   keeps it as an MP3 (or the best format the server's ffmpeg writes) when
   the server has ffmpeg, and as the WAV when it has not.

A pass in which the video stopped to load, or whose timing did not hold
together, is played once more, and the status line says so — *(once more:
the first time did not hold together)*.

**One Allow lasts while the page stays open.** Every later clip, and every
frame captured for a card ([A frame of the video](recordings-and-frames.md#a-frame-of-the-video)),
uses the same share, and Chrome does not ask again: with the tab already
shared, sound and all, the recording starts as soon as the editor opens,
and its sentence no longer speaks of Chrome. A share given **without** its
sound (*Also allow tab audio* turned off for a frame, say) still takes
frames, but the next cut lets it go and asks again, and the share given
then takes the frames too. Stop sharing, or reload the page, and Chrome
asks the next time.

## The recording holds only what was played

You may move an edge beyond what was recorded — the strip shows the
stretch — but a clip that reaches past the recording is not saved:
*the recording holds 10.63–15.90 s: record again to take in the edges*.
A preview there says *that is outside the recording: record again to hear
it*. **● record again** records the stretch the strip shows now, a second
past the moved edge.

### When the caption is not where the sentence is

YouTube's transcript cuts a sentence across often enough: the words you
want begin a second or two before the caption does, or run on after it,
and the strip has nothing there to drag an edge into. The **reach** row
under the two edges says how much further **● record again** should go —
seconds typed into its two boxes, **start** and **end**, *negative
earlier and positive later*, up to a minute either way. **Enter** in
either box records at once.

What comes back is a longer recording, and the strip grows to show all of
it, so the edges reach into what the caption left out. The numbers are
measured from the stretch itself, not from the last recording, so pressing
**● record again** twice with the same numbers goes to the same place
rather than creeping further out each time.

A clip saved before a new recording is dimmed, and the status line says
*the clip saved is of the recording before this one: “use this clip” cuts
it again, from this one*; **save clip** or **use this clip** cuts it again
from the new recording, and the old clip leaves the tray.

## What the editor may say

| It says | What happened, and what to do |
|---|---|
| the tab was not shared, so nothing was recorded: press “record” and, when Chrome asks, press “Allow” | **Cancel** was pressed in Chrome's question, or it was closed |
| the tab was shared without its sound: press “record” and, when Chrome asks, leave “Also allow tab audio” turned on | that switch was off in Chrome's question |
| no sound was captured — is the video muted? Turn its sound on and record again | nothing but near-silence reached the recording, though the page turns the video's own sound on to record it: check that the video can be heard, and record again |
| the tab stopped being shared while it recorded: press “record” again, and Chrome asks once more | **Stop sharing** was pressed |
| the video kept stopping to load while it was recorded: record again | the video stopped to load while the stretch played, and the second pass was no better |
| the recording holds … s: record again to take in the edges | an edge is outside what was recorded: **● record again**, and **reach** to go further still |
| Chrome could not share the tab (…): press “record” again | Chrome did not start the share, for the reason in brackets |
| Chrome shares a tab only straight after a click: press “record” again | the share was asked for too long after the click |
| any other sentence ending in *record again* | the video would not go to the stretch, did not play all of it or did not say where it was, or Chrome sent no sound: nothing exact can be cut from that pass. Record again |
