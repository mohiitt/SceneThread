# Retail Surveillance Demo

## Feasibility

SceneThread can ingest individual surveillance clips and answer across a bounded
collection selected by store, cameras, and absolute recording time. It can locate
supported actions, objects, anonymous people, and timestamps. It must describe potential
theft as suspicious or possible concealment unless the footage also shows the relevant
checkout/exit context.

The system should answer “who” with evidence-based anonymous descriptions such as
`person_2` or “the person wearing a gray hoodie.” Face recognition, biometric identity,
and legal determinations of guilt are outside scope.

## Recommended demo data

The safest primary demo is several short, consented, staged MP4 recordings from two or
more fixed camera positions:

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

## How to prepare the staged footage

The collection extension now implements metadata, date-range discovery, bounded
cross-video TwelveLabs search, wall-clock conversion, and multi-video evidence cards.
Prepare every clip as follows:

1. Use one exact `store_id`, for example `aws-builder-loft-sf`.
2. Give each physical viewpoint a stable `camera_id`, such as `entrance_cam`,
   `shelf_cam`, or `checkout_cam`; do not rename a camera between clips.
3. Enter the real timezone-aware start time shown by your shoot log.
4. Give each asset a unique video ID, such as
   `20260730_entrance_cam_take01`.
5. Keep each clip below 15 minutes and preserve a few seconds before and after the key
   action so temporal questions have context.
6. Ingest every clip before opening **Ask → Recording collection**.

## Remaining boundary

Anonymous labels such as `person_1` are intentionally local to one video. The agent may
connect a sequence across cameras using explicit clothing, carried-object, direction,
and timing evidence, but it must present that as a supported association with
limitations—not biometric identity. Face recognition and perfect cross-video person
re-identification remain outside scope.
