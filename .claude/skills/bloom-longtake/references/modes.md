# Long-take modes

Each mode is a route through one world. Lengths are for the whole video, and a station is one `## scene`.
The numbers come from the iart.ai product-demo, youtube-intro-outro, explainer-video and isometric packs,
adapted to Bloom's voice-led timing (each scene is its voice line plus about 0.9 s).

## Contents
1. intro (default)
2. demo / walkthrough
3. explainer (how it works)
4. release / what's new

## 1. intro (default)

Use it for an open-source project, an app, a product, a team or a person. The viewer leaves knowing what it is,
what it does and why it matters to them.

| Station | Words | On screen |
|---|---|---|
| hook (≤ 4 s) | the problem or the promise in one line | the first station already building; the name can wait |
| what | the name and a one-line definition | the main block builds, its screen lights, the name is pinned |
| does ×2–4 | one capability each, as cause → effect | something goes in and something comes out: a file drops in, a voice wave rises, a video plays |
| proof (optional) | one concrete number or user | a counter counts on its block, or a real result |
| end | the hook out: a question to the viewer, or the next part teased | pull-out to the whole world assembled, the question card, then `.end-cut` / `.end-fade` |

- Length 45–90 s (a README hero 30–60 s), with 5–7 stations.
- Use at most one analogy for the whole video (a factory line, a kitchen, a post office) and keep it throughout.
- The name lands on its word, big, once. After that it stays as a pin on its block.
- A call to action (a URL, "ลองได้ที่ GitHub") goes with the source line before the cut, small. The question is the last thing said.

## 2. demo / walkthrough

Use it to show how to use something, from screenshots or a mock UI. Never use a jittery screen recording.

- The demo loop per step: settle on the screen 0.5–1 s → cursor travels 0.4–0.8 s (ease in-out, an arc) → click: a ripple and the screen's change on the same frame (0.2–0.3 s) → zoom to the part that matters, at most 2×, hold 2–4 s → one benefit phrase as a pinned caption.
- Move the camera or the cursor, never both at once.
- Screens live in the world as panels standing on blocks (`data-face`) or as flat cards on the floor. The camera pushes into one to "enter" the app and pulls out to change screens; use that one move between every pair of screens.
- Capture screenshots at 2× (device scale factor 2) so a 2× zoom stays sharp, put them in the project, and use them as `<img>` inside the face.
- Length 30–90 s, one feature per station. Start with the result ("this is what you'll get"), then show how.

## 3. explainer (how it works)

Use it for the mechanism inside something: a pipeline, an architecture, a data flow, a process.

- The world is the machine, and the camera follows one thing (a packet, a file, a request) through it. Every stage is a station: the thing arrives, changes state, and leaves along a drawn path (`.draw` on the route, `.flow` for continuous traffic).
- Show cause and effect instead of labels: what each stage visibly does to the thing (a script becomes a waveform, the waveform becomes a mouth moving).
- A gauge or counter that persists across stations turns a sequence into a chain (`data-after` keeps it).
- Reveal progressively: nodes, then links, then labels. Hold each for 0.5–1.5 s.
- Length 60–180 s for YouTube, with 3–7 stages. The recap at the end is the pull-out, not a list.

## 4. release / what's new

Use it for a new version or a changelog worth watching.

- Open on the biggest change, stamped with the version (`v0.3`), instead of on the list.
- Each change is a station with before → after on the same block: the old state, then it rebuilds into the new one (`data-until` takes the old part away, `data-after` builds the new one).
- Length 30–60 s with 3–5 changes. Smaller changes can share a station as pins.
- End with the next version teased and cut off on the reveal (the next part rule): a block under a sheet, a silhouette (`.tease`), "เวอร์ชันหน้า…" and black.
