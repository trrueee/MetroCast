"""
Integration test for PodcastAudioAssembler.

Prerequisite: ffmpeg and ffprobe must be on PATH.
    winget install ffmpeg   # Windows
    brew install ffmpeg      # macOS
    apt install ffmpeg       # Linux

Usage:
    cd server
    python -m pytest tests/test_assembler.py -v
    # or
    python tests/test_assembler.py
"""
import os
import sys
import json
import shutil
import subprocess
import tempfile
import unittest

# Ensure server/ is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from audio.assembler import (
    PodcastAudioSegment,
    PodcastEpisodeAudioJob,
    PodcastAudioAssembler,
)


def _ffmpeg_available() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["ffprobe", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except FileNotFoundError:
        return False


def _make_beep_mp3(output_path: str, freq: int = 440, duration: float = 2.0) -> str:
    """Generate a short sine beep MP3 for testing (simulates a TTS segment)."""
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"sine=frequency={freq}:duration={duration}:sample_rate=44100",
            "-ar", "44100",
            "-codec:a", "libmp3lame",
            "-b:a", "128k",
            output_path,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )
    return output_path


@unittest.skipUnless(_ffmpeg_available(), "ffmpeg not installed – skipping integration test")
class TestAssemblerIntegration(unittest.TestCase):
    """Full integration: synthetic segments → assembled MP3 → validation."""

    def setUp(self):
        self.workdir = tempfile.mkdtemp(prefix="metrocast_test_")
        self.assembler = PodcastAudioAssembler()

    def tearDown(self):
        shutil.rmtree(self.workdir, ignore_errors=True)

    def test_full_assemble_flow(self):
        """Create 3 synthetic segments, assemble, and verify zero decode errors."""

        # --- 1. Create synthetic "TTS" segments (beeps at different pitches) ---
        seg_paths = []
        for i, freq in enumerate([440, 880, 1320]):  # A4, A5, E6
            seg_path = os.path.join(self.workdir, f"segment_{i:03d}.mp3")
            _make_beep_mp3(seg_path, freq=freq, duration=2.0)
            seg_paths.append(seg_path)

        segments = [
            PodcastAudioSegment(
                segment_id="seg_000",
                audio_path=seg_paths[0],
                pause_after_ms=1000,
            ),
            PodcastAudioSegment(
                segment_id="seg_001",
                audio_path=seg_paths[1],
                pause_after_ms=800,
            ),
            PodcastAudioSegment(
                segment_id="seg_002",
                audio_path=seg_paths[2],
                pause_after_ms=0,
            ),
        ]

        # --- 2. Run assembly ---
        output_dir = os.path.join(self.workdir, "assembled")
        job = PodcastEpisodeAudioJob(
            job_id="test_001",
            segments=segments,
            output_dir=output_dir,
        )

        result = self.assembler.assemble(job)

        # --- 3. Assertions ---
        final_mp3 = result["final_audio_path"]
        self.assertTrue(os.path.isfile(final_mp3))
        self.assertGreater(os.path.getsize(final_mp3), 1000, "MP3 too small – likely empty")

        quality = result["quality"]
        print("\n=== Quality Report ===")
        print(json.dumps(quality, indent=2, ensure_ascii=False))

        # The quality check rightfully flags duration <60s as "failed" for tiny test data.
        # For production-length episodes, status should be "passed".
        # The critical assertion: zero decode errors.
        self.assertEqual(quality["decode_errors"], 0,
                         f"Decode errors found: {quality.get('blocking_issues')}")
        self.assertEqual(quality["channels"], 1)
        self.assertGreater(quality["bitrate_bps"], 128000)
        # 3 × 2s beeps + 1.8s silence ≈ 7-8s
        self.assertGreater(quality["duration_sec"], 6.0)

        # --- 4. External decode verification ---
        verify = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", final_mp3, "-f", "null", "-"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(verify.stderr.strip(), "",
                         f"ffmpeg decode errors on final output: {verify.stderr.strip()[:300]}")

        print(f"\nPASS — final MP3 decodes cleanly: {final_mp3}")
        print(f"Duration: {quality['duration_sec']}s  |  Bitrate: {quality['bitrate_bps']}bps")


class TestAssemblerUnit(unittest.TestCase):
    """Tests that don't require ffmpeg — validate data structures & method signatures."""

    def test_dataclass_creation(self):
        seg = PodcastAudioSegment(
            segment_id="seg_001",
            audio_path="/tmp/test.mp3",
            pause_after_ms=800,
        )
        self.assertEqual(seg.segment_id, "seg_001")
        self.assertEqual(seg.pause_after_ms, 800)
        self.assertIsNone(seg.wav_path)
        self.assertIsNone(seg.silence_path)

    def test_job_creation(self):
        segs = [
            PodcastAudioSegment(segment_id="s1", audio_path="/tmp/a.mp3"),
            PodcastAudioSegment(segment_id="s2", audio_path="/tmp/b.mp3"),
        ]
        job = PodcastEpisodeAudioJob(
            job_id="test_job",
            segments=segs,
            output_dir="/tmp/out",
        )
        self.assertEqual(len(job.segments), 2)
        self.assertEqual(job.sample_rate, 44100)
        self.assertEqual(job.mp3_bitrate, "192k")

    @unittest.skipUnless(_ffmpeg_available(), "ffmpeg not installed")
    def test_validate_valid_mp3(self):
        with tempfile.TemporaryDirectory() as tmp:
            mp3 = os.path.join(tmp, "beep.mp3")
            _make_beep_mp3(mp3, freq=440, duration=1.0)
            assembler = PodcastAudioAssembler()
            result = assembler.validate_segment_audio(mp3)
            self.assertTrue(result["valid"], f"Valid beep should pass: {result}")

    @unittest.skipUnless(_ffmpeg_available(), "ffmpeg not installed")
    def test_validate_corrupt_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = os.path.join(tmp, "bad.mp3")
            with open(bad, "wb") as f:
                f.write(b"this is not an mp3 file at all")
            assembler = PodcastAudioAssembler()
            result = assembler.validate_segment_audio(bad)
            self.assertFalse(result["valid"], "Corrupt file must fail validation")


if __name__ == "__main__":
    unittest.main()
