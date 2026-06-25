# Recall-first detection; tracking is the false-positive filter

The detector runs at a deliberately low confidence threshold (~0.15–0.20) so faint,
very small birds are not missed. This intentionally lets noise (clouds, sensor
specks) into the Detections Sidecar. We accept that because the next phase — ByteTrack
(see ADR-0001) — is the natural false-positive filter: real birds persist across
frames and form tracks, whereas single-frame noise does not.

Implication for future readers: a low `--conf` default and a noisy sidecar are *by
design*, not a bug. Do not raise the threshold to "clean up" the sidecar without
accounting for the recall loss on small birds — the cleanup belongs in the tracking
stage, not the detector.
