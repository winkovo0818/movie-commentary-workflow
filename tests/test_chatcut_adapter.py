from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
COMPILER = (
    REPOSITORY_ROOT
    / ".codex"
    / "skills"
    / "movie-chatcut-timeline"
    / "scripts"
    / "compile_chatcut_timeline.py"
)


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def sample_plans() -> tuple[dict[str, object], dict[str, object]]:
    visual = {
        "schema_version": 1,
        "film_id": "synthetic-chatcut-001",
        "duration_ms": 3000,
        "source": "source.mp4",
        "narration": "narration.wav",
        "clips": [
            {
                "id": "c1",
                "timeline_start_ms": 0,
                "timeline_end_ms": 1001,
                "source_start_ms": 1000,
                "source_end_ms": 2001,
                "pace": "normal",
                "purpose": "establish the scene",
            },
            {
                "id": "c2",
                "timeline_start_ms": 1001,
                "timeline_end_ms": 3000,
                "source_start_ms": 5000,
                "source_end_ms": 6999,
                "pace": "climax",
                "purpose": "reveal the turn",
                "source_audio": True,
            },
        ],
    }
    audio = {
        "schema_version": 1,
        "film_id": "synthetic-chatcut-001",
        "duration_ms": 3000,
        "events": [
            {
                "id": "vo-1",
                "type": "narration",
                "start_ms": 0,
                "end_ms": 3000,
                "gain_db": -1.5,
            },
            {
                "id": "room-tone",
                "type": "ambience",
                "start_ms": 1001,
                "end_ms": 3000,
            },
        ],
    }
    return visual, audio


def run_compiler(tmp_path: Path, *, with_assets: bool = True) -> subprocess.CompletedProcess[str]:
    visual, audio = sample_plans()
    visual_path = tmp_path / "visual.json"
    audio_path = tmp_path / "audio.json"
    output_path = tmp_path / "manifest.json"
    write_json(visual_path, visual)
    write_json(audio_path, audio)
    command = [
        sys.executable,
        str(COMPILER),
        "--visual-edit",
        str(visual_path),
        "--audio-mix-plan",
        str(audio_path),
        "--output",
        str(output_path),
        "--batch-size",
        "2",
    ]
    if with_assets:
        asset_map_path = tmp_path / "assets.json"
        write_json(
            asset_map_path,
            {
                "schema_version": 1,
                "project_id": "project-test",
                "timeline_id": "timeline-test",
                "assets": {
                    "source.mp4": "asset-video",
                    "narration.wav": "asset-narration",
                },
            },
        )
        command.extend(["--asset-map", str(asset_map_path)])
    return subprocess.run(command, text=True, capture_output=True, check=False)


def test_compiler_emits_schema_valid_ready_manifest(tmp_path: Path) -> None:
    result = run_compiler(tmp_path)
    assert result.returncode == 0, result.stderr
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    schema = json.loads(
        (REPOSITORY_ROOT / "schemas" / "chatcut-timeline-manifest.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert list(Draft202012Validator(schema).iter_errors(manifest)) == []
    assert manifest["ready"] is True
    assert manifest["missing_targets"] == []
    assert manifest["duration_frames"] == 90
    assert len(manifest["item_batches"]) == 2

    picture_items = [
        item
        for batch in manifest["item_batches"]
        for item in batch["items"]
        if item["type"] == "video"
    ]
    assert [(item["fromFrame"], item["durationInFrames"]) for item in picture_items] == [
        (0, 30),
        (30, 60),
    ]
    assert picture_items[0]["decibelAdjustment"] == -60
    assert picture_items[1]["decibelAdjustment"] == 0
    assert manifest["manual_audio_events"][0]["id"] == "room-tone"


def test_compiler_can_emit_import_plan_before_assets_exist(tmp_path: Path) -> None:
    result = run_compiler(tmp_path, with_assets=False)
    assert result.returncode == 0, result.stderr
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["ready"] is False
    assert manifest["missing_assets"] == ["source.mp4", "narration.wav"]
    assert manifest["missing_targets"] == ["project_id", "timeline_id"]


def test_compiler_rejects_timeline_gaps(tmp_path: Path) -> None:
    visual, audio = sample_plans()
    visual["clips"][1]["timeline_start_ms"] = 1100  # type: ignore[index]
    visual_path = tmp_path / "visual.json"
    audio_path = tmp_path / "audio.json"
    write_json(visual_path, visual)
    write_json(audio_path, audio)
    result = subprocess.run(
        [
            sys.executable,
            str(COMPILER),
            "--visual-edit",
            str(visual_path),
            "--audio-mix-plan",
            str(audio_path),
            "--output",
            str(tmp_path / "manifest.json"),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 1
    assert "expected continuous 1001" in result.stderr


def test_compiler_rejects_overlapping_events_on_one_audio_track(tmp_path: Path) -> None:
    visual, audio = sample_plans()
    audio["events"].append(  # type: ignore[union-attr]
        {
            "id": "vo-2",
            "type": "narration",
            "start_ms": 2500,
            "end_ms": 3000,
        }
    )
    visual_path = tmp_path / "visual.json"
    audio_path = tmp_path / "audio.json"
    write_json(visual_path, visual)
    write_json(audio_path, audio)
    result = subprocess.run(
        [
            sys.executable,
            str(COMPILER),
            "--visual-edit",
            str(visual_path),
            "--audio-mix-plan",
            str(audio_path),
            "--output",
            str(tmp_path / "manifest.json"),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 1
    assert "overlap on track narration" in result.stderr
