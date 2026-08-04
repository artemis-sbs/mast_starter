"""Stage every template in templates.json and compile it.

Deliberately standalone: it depends on python, curl and the checkout, and NOT on a released
`sbs.pyz`. A gate that needs a tool release before it can test a repo change is a gate that
is off exactly when it is needed.

WHAT THIS CATCHES: MAST syntax errors, a story.json that mixes release lines, and a pin
that was never published as a release asset.

WHAT IT DOES NOT CATCH, and you should know before trusting a green run: a multi-line `{}`
literal. MAST parses line by line, so the first line is an unclosed brace; the parser
desyncs for the rest of the file and the story's main task can end up EMPTY - and the
compiler reports zero errors. Catching that needs a coverage run (`--test`, which reports
`labels 0/N`), not a compile. Keep dict literals on one line or inside `~~ ... ~~`.

Run from the repository root.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()          # run from the repository root
WORK = ROOT / "_ci"
LIB = WORK / "__lib__"


def sbslib_source(pin):
    """(url, filename) for an sbslib pin like `artemis-sbs.sbs_utils.v1.4.0.sbslib`."""
    parts = pin.split(".")
    user, repo = parts[0], parts[1]
    tag = ".".join(parts[2:-1])
    return f"https://github.com/{user}/{repo}/releases/download/{tag}/{pin}", pin


def fetch(url, dest):
    if dest.exists():
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["curl", "-fsSL", "-o", str(dest), url])
    if r.returncode != 0:
        dest.unlink(missing_ok=True)
        return False
    return True


def compile_template(name, folder, mast_rel="story.mast"):
    """Compile one .mast entry point under `folder`, in a SUBPROCESS.

    A subprocess because sbs_utils caches module state and path globals on import; compiling
    a second template in the same interpreter would compile it against the first one's
    library. That is precisely the reused-interpreter trap that makes a bug show up only
    from run 2 onward.
    """
    code = r'''
import sys, json, os
from pathlib import Path
folder, lib = Path(sys.argv[1]), Path(sys.argv[2])
deps = json.loads((folder / "story.json").read_text())
for pin in deps.get("sbslib", []):
    sys.path.insert(0, str(lib / pin))
sys.path.insert(0, str(folder))
from sbs_utils import fs
fs.exe_dir = str(lib.parent.parent)
fs.script_dir = str(folder)
# Explicitly, not transitively. @map and the other story node types are registered by this
# import; leaning on some other module to have pulled it in first is the node-ordering trap
# the library's own notes warn about, and it fails as "@map: unrecognized syntax".
import sbs_utils.mast_sbs.story_nodes
from sbs_utils.mast.mast_run import mast_run
errors = mast_run(str(folder / sys.argv[3]), True) or []
for e in errors:
    print(e)
sys.exit(1 if errors else 0)
'''
    r = subprocess.run([sys.executable, "-c", code, str(folder), str(LIB), mast_rel],
                       capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    sys.stderr.write(r.stderr)
    return r.returncode == 0


def main():
    catalog = json.loads((ROOT / "templates.json").read_text())
    templates = catalog["templates"]
    if WORK.exists():
        shutil.rmtree(WORK)
    LIB.mkdir(parents=True)

    failed = []
    for t in templates:
        tid = t["id"]
        src = ROOT if t.get("path", ".") in (".", "") else ROOT / t["path"]
        dst = WORK / f"ci_{tid}"
        print(f"::group::{tid}")

        # Stage the template the way `sbs create` lays it down: the repo's own scaffolding
        # is not part of anybody's mission.
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns(
            "templates", ".git", ".github", "_ci", "templates.json", "mkdocs", "__pycache__"))

        story = dst / "story.json"
        if not story.exists():
            print(f"::error::template '{tid}' has no story.json")
            failed.append(tid)
            print("::endgroup::")
            continue

        deps = json.loads(story.read_text())
        pins = deps.get("sbslib", [])
        if not pins:
            print(f"::error::template '{tid}' pins no sbslib")
            failed.append(tid)
            print("::endgroup::")
            continue

        # One line, or none. A story.json holding two lines at once is the failure the
        # branch-per-line layout exists to prevent, and it is silent at runtime.
        lines = set()
        for pin in pins + deps.get("mastlib", []):
            parts = pin.split(".")
            head = 2 if pin.endswith(".sbslib") else 3
            lines.add(".".join(parts[head:-1]))
        if len(lines) > 1:
            print(f"::error::template '{tid}' mixes release lines: {sorted(lines)}")
            failed.append(tid)
            print("::endgroup::")
            continue

        ok = True
        for pin in pins:
            url, fname = sbslib_source(pin)
            if not fetch(url, LIB / fname):
                print(f"::error::template '{tid}' pins {pin}, which is not a published release asset")
                ok = False
        if not ok:
            failed.append(tid)
            print("::endgroup::")
            continue

        # Every entry point, not just story.mast. An addon template's own .mast files are
        # reached through its `__init__.mast`, which story.mast never imports - so compiling
        # only story.mast would leave the actual addon untested, which is the one thing an
        # addon template exists to carry.
        entries = ["story.mast"]
        libs = dst / "__lib__.json"
        if libs.exists():
            for addon in json.loads(libs.read_text()).get("mastlib", []):
                init = dst / addon / "__init__.mast"
                if init.exists():
                    entries.append(f"{addon}/__init__.mast")
                else:
                    print(f"::error::template '{tid}' declares mastlib '{addon}' with no __init__.mast")
                    failed.append(tid)

        if tid not in failed and all(compile_template(tid, dst, e) for e in entries):
            print(f"{tid}: OK ({', '.join(sorted(lines))}, {len(entries)} entry point(s))")
        elif tid not in failed:
            print(f"::error::MAST compile failed for template '{tid}'")
            failed.append(tid)
        print("::endgroup::")

    print("")
    if failed:
        print(f"FAILED: {', '.join(failed)}")
        return 1
    print(f"All {len(templates)} template(s) compiled.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
