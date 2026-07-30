# Retail Surveillance Demo

## Feasibility

SceneThread can already ingest and answer questions about one selected surveillance
video. It can locate supported actions, objects, anonymous people, and timestamps. It
must describe potential theft as suspicious or possible concealment unless the footage
also shows the relevant checkout/exit context.

The system should answer “who” with evidence-based anonymous descriptions such as
`person_2` or “the person wearing a gray hoodie.” Face recognition, biometric identity,
and legal determinations of guilt are outside scope.

## Recommended demo data

The safest primary demo is three short, consented, staged MP4 recordings from one fixed
camera:

- Day 1: normal browsing.
- Day 2: selection followed by visible payment.
- Day 3: a distinctive item is picked up, concealed, and carried toward the exit.

Keep each clip under the configured 15-minute limit and make the product, clothing, bag,
checkout, and exit visible. Public alternatives include:

- [CAVIAR](https://groups.inf.ed.ac.uk/vision/DATASETS/CAVIAR/CAVIARDATA1/) —
  acted shopping-center surveillance with synchronized views and CC BY-SA usability;
  useful for browsing, shop entry/exit, and unattended-package scenarios.
- [UCF-Crime](https://www.crcv.ucf.edu/research/real-world-anomaly-detection-in-surveillance-videos/) —
  long surveillance videos with robbery, stealing, and shoplifting categories; review
  content and redistribution terms before a public demo.
- [AI City Challenge datasets](https://www.aicitychallenge.org/ai-city-challenge-dataset-access/) —
  retail checkout/product-counting data useful for object and checkout context.
- [VIRAT](https://viratdata.org/index.html) — realistic stationary and multi-camera
  surveillance for general activity tracking; not primarily retail theft and subject to
  its data agreement.

Download dataset clips locally and convert unsupported containers to MP4 when necessary.
For live URL ingestion, host the MP4 at a direct public HTTP(S) media URL.

## Work required for multi-day questions

The present contracts and QA runtime require one `video_id`. A true query such as “search
all Store 01 recordings this week” needs:

1. `store_id`, `camera_id`, and absolute `recorded_at` metadata.
2. Chunking of day-long footage into bounded assets.
3. Collection/date-range discovery before per-video search.
4. Cross-video TwelveLabs search orchestration.
5. Wall-clock conversion for relative scene timestamps.
6. Confidence-bounded anonymous person tracking across clips.
7. Multi-video evidence references in the answer contract and UI.

Until that extension is implemented, ingest each clip separately and ask questions about
the selected video. Do not present current single-video QA as collection-wide search.
