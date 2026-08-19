#!/usr/bin/env python3
"""Compile locked movie commentary plans into an executable ChatCut manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"missing file: {path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid JSON in {path}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object in {path}")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ms_to_frame(milliseconds: int, fps: int) -> int:
    value = Fraction(milliseconds * fps, 1000)
    return value.numerator // value.denominator + (
        1 if value.numerator % value.denominator * 2 >= value.denominator else 0
    )


def validate_visual_edit(plan: dict[str, Any]) -> None:
    clips = plan.get("clips")
    if not isinstance(clips, list) or not clips:
        raise ValueError("visual edit must contain at least one clip")
    duration_ms = plan.get("duration_ms")
    if not isinstance(duration_ms, int) or duration_ms < 1000:
        raise ValueError("visual edit duration_ms must be an integer >= 1000")

    cursor = 0
    ids: set[str] = set()
    for index, clip in enumerate(clips):
        if not isinstance(clip, dict):
            raise ValueError(f"clip {index} must be an object")
        clip_id = clip.get("id")
        if not isinstance(clip_id, str) or not clip_id:
            raise ValueError(f"clip {index} has no id")
        if clip_id in ids:
            raise ValueError(f"duplicate clip id: {clip_id}")
        ids.add(clip_id)
        start = clip.get("timeline_start_ms")
        end = clip.get("timeline_end_ms")
        source_start = clip.get("source_start_ms")
        source_end = clip.get("source_end_ms")
        if not all(isinstance(value, int) for value in (start, end, source_start, source_end)):
            raise ValueError(f"clip {clip_id} time fields must be integers")
        if start != cursor:
            raise ValueError(f"clip {clip_id} starts at {start}, expected continuous {cursor}")
        if end <= start:
            raise ValueError(f"clip {clip_id} has a non-positive timeline range")
        if source_start < 0 or source_end <= source_start:
            raise ValueError(f"clip {clip_id} has an invalid source range")
        cursor = end
    if cursor != duration_ms:
        raise ValueError(f"clips end at {cursor}, but duration_ms is {duration_ms}")


def validate_audio_plan(plan: dict[str, Any], duration_ms: int) -> None:
    if plan.get("duration_ms") != duration_ms:
        raise ValueError("audio and visual plans must have the same duration_ms")
    events = plan.get("events")
    if not isinstance(events, list):
        raise ValueError("audio mix plan events must be an array")
    ids: set[str] = set()
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            raise ValueError(f"audio event {index} must be an object")
        event_id = event.get("id")
        if not isinstance(event_id, str) or not event_id:
            raise ValueError(f"audio event {index} has no id")
        if event_id in ids:
            raise ValueError(f"duplicate audio event id: {event_id}")
        ids.add(event_id)
        event_type = event.get("type")
        if event_type not in {"narration", "source_dialogue", "ambience", "silence", "music"}:
            raise ValueError(f"audio event {event_id} has an invalid type")
        start = event.get("start_ms")
        end = event.get("end_ms")
        if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end <= start:
            raise ValueError(f"audio event {event_id} has an invalid timeline range")
        if end > duration_ms:
            raise ValueError(f"audio event {event_id} exceeds the plan duration")
        source_start = event.get("source_start_ms")
        if source_start is not None and (not isinstance(source_start, int) or source_start < 0):
            raise ValueError(f"audio event {event_id} has an invalid source_start_ms")


def asset_key(value: str) -> str:
    return value


def add_requirement(
    requirements: dict[str, dict[str, Any]], source: str, asset_type: str, role: str
) -> str:
    key = asset_key(source)
    existing = requirements.get(key)
    if existing and existing["type"] != asset_type:
        raise ValueError(f"asset {source} is used as both {existing['type']} and {asset_type}")
    if existing:
        if role not in existing["roles"]:
            existing["roles"].append(role)
    else:
        requirements[key] = {"key": key, "source": source, "type": asset_type, "roles": [role]}
    return key


def resolve_asset(asset_map: dict[str, Any], key: str) -> str | None:
    assets = asset_map.get("assets", {})
    if not isinstance(assets, dict):
        raise ValueError("asset map assets must be an object")
    value = assets.get(key)
    if isinstance(value, str) and value:
        return value
    if isinstance(value, dict):
        asset_id = value.get("asset_id")
        if isinstance(asset_id, str) and asset_id:
            return asset_id
    return None


def compile_manifest(
    visual: dict[str, Any],
    audio: dict[str, Any],
    *,
    visual_path: Path,
    audio_path: Path,
    asset_map: dict[str, Any],
    fps: int,
    width: int,
    height: int,
    timeline_name: str,
    batch_size: int,
) -> dict[str, Any]:
    validate_visual_edit(visual)
    validate_audio_plan(audio, visual["duration_ms"])
    if visual.get("film_id") != audio.get("film_id"):
        raise ValueError("visual and audio plan film_id values must match")

    requirements: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    visual_items: list[dict[str, Any]] = []
    for clip in visual["clips"]:
        source = clip.get("source", visual["source"])
        if not isinstance(source, str) or not source:
            raise ValueError(f"clip {clip['id']} has no usable source")
        ref = add_requirement(requirements, source, "video", "picture")
        from_frame = ms_to_frame(clip["timeline_start_ms"], fps)
        end_frame = ms_to_frame(clip["timeline_end_ms"], fps)
        duration_frames = end_frame - from_frame
        if duration_frames < 1:
            raise ValueError(f"clip {clip['id']} becomes shorter than one frame")
        source_duration_ms = clip["source_end_ms"] - clip["source_start_ms"]
        playback_rate = source_duration_ms * fps / (duration_frames * 1000)
        if playback_rate < 0.25 or playback_rate > 4:
            warnings.append(f"clip {clip['id']} requires unusual playbackRate {playback_rate:.6f}")
        visual_items.append(
            {
                "binding_id": f"clip:{clip['id']}",
                "type": "video",
                "asset_ref": ref,
                "track_ref": "picture",
                "fromFrame": from_frame,
                "durationInFrames": duration_frames,
                "sourceStartFromInSeconds": clip["source_start_ms"] / 1000,
                "playbackRate": round(playback_rate, 8),
                "fit": clip.get("fit", "cover"),
                "decibelAdjustment": 0 if clip.get("source_audio") else -60,
                "editorial": {
                    "pace": clip["pace"],
                    "purpose": clip["purpose"],
                    "source_end_ms": clip["source_end_ms"],
                },
            }
        )

    audio_items: list[dict[str, Any]] = []
    manual_audio_events: list[dict[str, Any]] = []
    track_ranges: dict[str, list[tuple[int, int, str]]] = {}
    for event in audio["events"]:
        event_type = event["type"]
        if event_type == "silence":
            manual_audio_events.append({**event, "reason": "silence creates no ChatCut item"})
            continue
        source = event.get("source")
        if event_type == "narration" and not source:
            source = visual["narration"]
        if event_type in {"source_dialogue", "ambience"} and not source:
            manual_audio_events.append(
                {**event, "reason": "no independent audio source; resolve against picture audio"}
            )
            continue
        if not isinstance(source, str) or not source:
            raise ValueError(f"audio event {event['id']} requires source")
        default_track_ref = {
            "narration": "narration",
            "music": "music",
            "source_dialogue": "source-audio",
            "ambience": "source-audio",
        }[event_type]
        track_ref = event.get("track_key", default_track_ref)
        if not isinstance(track_ref, str) or not track_ref:
            raise ValueError(f"audio event {event['id']} has an invalid track_key")
        for prior_start, prior_end, prior_id in track_ranges.setdefault(track_ref, []):
            if event["start_ms"] < prior_end and event["end_ms"] > prior_start:
                raise ValueError(
                    f"audio events {prior_id} and {event['id']} overlap on track {track_ref}; "
                    "assign a different track_key"
                )
        track_ranges[track_ref].append((event["start_ms"], event["end_ms"], event["id"]))
        ref = add_requirement(requirements, source, "audio", track_ref)
        from_frame = ms_to_frame(event["start_ms"], fps)
        end_frame = ms_to_frame(event["end_ms"], fps)
        duration_frames = end_frame - from_frame
        if duration_frames < 1:
            raise ValueError(f"audio event {event['id']} becomes shorter than one frame")
        if "source_start_ms" in event:
            source_start_ms = event["source_start_ms"]
        elif event_type == "narration":
            source_start_ms = event["start_ms"]
        else:
            source_start_ms = 0
        item = {
            "binding_id": f"audio:{event['id']}",
            "type": "audio",
            "asset_ref": ref,
            "track_ref": track_ref,
            "fromFrame": from_frame,
            "durationInFrames": duration_frames,
            "sourceStartFromInSeconds": source_start_ms / 1000,
            "decibelAdjustment": event.get("gain_db", 0),
            "editorial": {"event_type": event_type, "purpose": event.get("purpose", "")},
        }
        audio_items.append(item)

    asset_requirements = []
    missing_assets = []
    for key, requirement in requirements.items():
        asset_id = resolve_asset(asset_map, key)
        resolved = {**requirement, "asset_id": asset_id}
        asset_requirements.append(resolved)
        if not asset_id:
            missing_assets.append(key)

    items = visual_items + audio_items
    batches = []
    for start in range(0, len(items), batch_size):
        batch_items = items[start : start + batch_size]
        batches.append(
            {
                "id": f"items-{start // batch_size + 1:03d}",
                "validate_first": True,
                "items": batch_items,
            }
        )

    duration_frames = ms_to_frame(visual["duration_ms"], fps)
    sample_frames = sorted(
        {
            0,
            max(0, duration_frames - 1),
            *(item["fromFrame"] for item in visual_items if item["editorial"]["pace"] == "climax"),
        }
    )[:9]
    target_project_id = asset_map.get("project_id")
    target_timeline_id = asset_map.get("timeline_id")
    missing_targets = [
        name
        for name, value in (
            ("project_id", target_project_id),
            ("timeline_id", target_timeline_id),
        )
        if not isinstance(value, str) or not value
    ]
    track_roles: dict[str, tuple[str, str, str | None]] = {
        "picture": ("video", "Picture", None),
        "narration": ("audio", "Narration", "anchor"),
        "source-audio": ("audio", "Source Audio", "anchor"),
        "music": ("audio", "Music", "follower"),
    }
    used_track_refs = {"picture", *(item["track_ref"] for item in audio_items)}
    track_specs = []
    for key in sorted(used_track_refs, key=lambda value: (value != "picture", value)):
        track_type, name, role = track_roles.get(key, ("audio", key, None))
        if key not in track_roles:
            event_types = {
                item["editorial"]["event_type"] for item in audio_items if item["track_ref"] == key
            }
            role = "follower" if event_types == {"music"} else "anchor"
        track_specs.append({"key": key, "type": track_type, "name": name, "role": role})

    manifest = {
        "$schema": "../../../../schemas/chatcut-timeline-manifest.schema.json",
        "schema_version": 1,
        "film_id": visual["film_id"],
        "ready": not missing_assets and not missing_targets,
        "source_locks": {
            "visual_edit": {"path": str(visual_path), "sha256": sha256_file(visual_path)},
            "audio_mix_plan": {"path": str(audio_path), "sha256": sha256_file(audio_path)},
        },
        "target": {
            "project_id": target_project_id,
            "timeline_id": target_timeline_id,
            "timeline_name": timeline_name,
        },
        "canvas": {"fps": fps, "width": width, "height": height},
        "duration_frames": duration_frames,
        "asset_requirements": asset_requirements,
        "missing_assets": missing_assets,
        "missing_targets": missing_targets,
        "track_specs": track_specs,
        "item_batches": batches,
        "manual_audio_events": manual_audio_events,
        "caption_plan": {
            "enabled": any(event["type"] == "narration" for event in audio["events"]),
            "source_track_ref": "narration",
            "source_mode": "explicit-track",
        },
        "verification": {
            "expected_duration_frames": duration_frames,
            "continuous_track_ref": "picture",
            "expected_picture_items": len(visual_items),
            "expected_audio_items": len(audio_items),
            "viewer_frames": sample_frames,
        },
        "warnings": warnings,
    }
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--visual-edit", required=True, type=Path)
    parser.add_argument("--audio-mix-plan", required=True, type=Path)
    parser.add_argument("--asset-map", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeline-name", default="Movie Commentary | ChatCut")
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1920)
    parser.add_argument("--batch-size", type=int, default=40)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.fps not in {24, 25, 30, 50, 60}:
        print("fps must be one of 24, 25, 30, 50, 60", file=sys.stderr)
        return 2
    if args.width < 16 or args.height < 16:
        print("width and height must be >= 16", file=sys.stderr)
        return 2
    if not 1 <= args.batch_size <= 100:
        print("batch-size must be between 1 and 100", file=sys.stderr)
        return 2
    try:
        visual_path = args.visual_edit.expanduser().resolve()
        audio_path = args.audio_mix_plan.expanduser().resolve()
        visual = load_json(visual_path)
        audio = load_json(audio_path)
        asset_map = load_json(args.asset_map.expanduser().resolve()) if args.asset_map else {}
        manifest = compile_manifest(
            visual,
            audio,
            visual_path=visual_path,
            audio_path=audio_path,
            asset_map=asset_map,
            fps=args.fps,
            width=args.width,
            height=args.height,
            timeline_name=args.timeline_name,
            batch_size=args.batch_size,
        )
    except ValueError as error:
        print(f"ChatCut manifest compilation failed: {error}", file=sys.stderr)
        return 1

    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    status = "ready" if manifest["ready"] else "waiting for asset ids"
    print(f"ChatCut manifest written ({status}): {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
