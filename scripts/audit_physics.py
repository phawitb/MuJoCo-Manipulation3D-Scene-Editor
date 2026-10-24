"""Rehearse then audit contact at every 1 ms step. Optional native close-up video.

Run from the repository: .venv/bin/python scripts/audit_physics.py --output audit.json
Add --example kalas-bowl-left --video /tmp/example06.mp4 for visual evidence.
"""

import argparse
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mujoco
import numpy as np
from backend.examples import example_catalog, example_scene
from backend.grasp import jaw_contacts
from backend.planning import calculate_plan
from backend.simulation import Simulation


def audit(example, video=None):
    sim = Simulation(example_scene(example))
    plan = calculate_plan(sim)
    if not plan["verified"]:
        return dict(example=example, success=False, message=plan["message"])
    sim.policy.configuration = plan["configuration"]
    sim.start_policy()
    source = sim.scene.task.source
    body_name = f"object_{source}"
    z0 = float(sim.data.body(body_name).xpos[2])
    max_z = z0
    max_gap = gap = max_penetration = 0.0
    min_force = float("inf")
    held_steps = secure_steps = 0
    phases = []
    renderer = encoder = None
    if video:
        from PIL import Image, ImageDraw

        Path(video).parent.mkdir(parents=True, exist_ok=True)
        renderer = mujoco.Renderer(sim.model, height=480, width=640)
        encoder = subprocess.Popen(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "rgb24",
                "-s",
                "640x520",
                "-r",
                "25",
                "-i",
                "-",
                "-an",
                "-c:v",
                "libx264",
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(video),
            ],
            stdin=subprocess.PIPE,
        )
        sim.model.vis.headlight.ambient[:] = [0.4, 0.4, 0.4]
        sim.model.vis.headlight.diffuse[:] = [0.8, 0.8, 0.8]
    last_phase = None
    try:
        for step in range(round(30 / sim.model.opt.timestep)):
            sim.step(1)
            assert not sim.data.eq_active.any(), "Unexpected non-contact attachment"
            grip = jaw_contacts(sim, source)
            max_z = max(max_z, float(sim.data.body(body_name).xpos[2]))
            if sim.policy.held:
                held_steps += 1
                secure_steps += int(grip["secure"])
                gap = 0 if grip["secure"] else gap + sim.model.opt.timestep
                max_gap = max(max_gap, gap)
                max_penetration = max(max_penetration, grip["maxPenetration"])
                if grip["secure"]:
                    min_force = min(min_force, grip["leftForce"], grip["rightForce"])
            changed = sim.policy.phase != last_phase
            if changed:
                phases.append(
                    dict(phase=sim.policy.phase, time=float(sim.data.time), grip=grip)
                )
                last_phase = sim.policy.phase
            if renderer and (step % 40 == 0 or changed):
                camera = mujoco.MjvCamera()
                camera.lookat[:] = (
                    sim.data.body(body_name).xpos
                    + sim.data.site("gripperframe").xpos
                ) / 2
                camera.distance = 0.34
                camera.azimuth = 45
                camera.elevation = -25
                option = mujoco.MjvOption()
                option.geomgroup[3:] = 0
                option.sitegroup[:] = 0
                renderer.update_scene(sim.data, camera, scene_option=option)
                frame = Image.new("RGB", (640, 520), "#152024")
                frame.paste(Image.fromarray(renderer.render()), (0, 0))
                draw = ImageDraw.Draw(frame)
                draw.text(
                    (12, 485),
                    f"{example} | {sim.data.time:.2f}s | {sim.policy.phase}",
                    fill="white",
                )
                draw.text(
                    (12, 502),
                    f"Jaw forces: L {grip['leftForce']:.2f} N / R {grip['rightForce']:.2f} N | No attachment",
                    fill="#bce8d5",
                )
                if changed and sim.policy.phase in (
                    "Lift",
                    "Transfer",
                    "Place",
                    "Release",
                    "Verify",
                    "Complete",
                ):
                    frame.save(
                        Path(video).with_name(
                            Path(video).stem + "-" + sim.policy.phase.lower() + ".png"
                        )
                    )
                if step % 40 == 0:
                    encoder.stdin.write(np.asarray(frame).tobytes())
            if sim.policy.status in ("failed", "succeeded"):
                break
    finally:
        if renderer:
            renderer.close()
            encoder.stdin.close()
            if encoder.wait() != 0:
                raise RuntimeError("Video encoding failed")
    return dict(
        example=example,
        success=sim.policy.success,
        message=sim.policy.message,
        seconds=float(sim.data.time),
        attempts=plan["attempts"],
        configuration=plan["configuration"],
        lift=max_z - z0,
        heldSteps=held_steps,
        secureSteps=secure_steps,
        maxUnsupportedSeconds=max_gap,
        maxJawPenetration=max_penetration,
        minimumJawForce=None if not np.isfinite(min_force) else min_force,
        phases=phases,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--example", choices=[e["id"] for e in example_catalog()])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--video", type=Path)
    args = parser.parse_args()
    if args.video and not args.example:
        parser.error("--video requires one --example")
    results = []
    for name in (
        [args.example] if args.example else [e["id"] for e in example_catalog()]
    ):
        result = audit(name, args.video)
        results.append(result)
        print(
            json.dumps({k: v for k, v in result.items() if k != "phases"}), flush=True
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2))
    sys.exit(0 if all(r["success"] for r in results) else 1)
