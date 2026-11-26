# Upstream: MVS-sysgen/sysgen

Pin: see `dependencies.lock.json` (`sysgen`). Role: base MVS/CE build. Used unmodified except for the patches below.

## Patches

| ID | File | Purpose | Status | Upstream status |
|---|---|---|---|---|
| P-01 | `patches/0001-pin-mvp-and-rakf-commits.patch` | `mvslovers.conf` gains `[mvp] commit` and `[rakf] commit`. `git_clone(commit=…)` checks the commit out (fresh or existing clone) and refuses a clone whose HEAD differs. `update_manifest` leaves commit-pinned entries alone (and its report loop iterates only the products it handled). 40 changed lines. | host-verified (OSE-013, T-PIN-001…005) | not offered (outreach needs human approval) |

Why P-01: MVP was cloned from its default branch, and an existing clone was `pull --ff-only`ed (sysgen.py l.2734, l.3247). RAKF was pinned by tag only. See research 2026-11-26-sysgen-pins P-1 and P-7.

## Interface for OSE-003 (OSE-013 acceptance test 5)

The OSE-003 wrapper must, in this order:

1. **Check out sysgen line-ending-safe**, then apply P-01:
   ```sh
   git -c core.autocrlf=false clone --no-checkout <cache-or-url> sysgen
   git -C sysgen config core.autocrlf false
   git -C sysgen checkout 4746195d33d9810bb9dfb0e8a3064a33efbb0559
   git -C sysgen apply --check ../upstream/sysgen/patches/0001-pin-mvp-and-rakf-commits.patch
   git -C sysgen apply        ../upstream/sysgen/patches/0001-pin-mvp-and-rakf-commits.patch
   ```
   Any nonzero RC stops the build.
2. **Run sysgen.** P-01 itself makes steps 8 and 9 fail with `… is at <sha> but mvslovers.conf pins commit <sha>` if RAKF or MVP is not at the pinned commit.
3. **Check after the clones** (belt and braces, and evidence for OSE-003 test 7):
   ```sh
   python3 scripts/lib/pins.py check-clone rakf  <sysgen>/temp/RAKF
   python3 scripts/lib/pins.py check-clone mvp   <sysgen>/MVSCE/MVP
   python3 scripts/lib/pins.py check-mvp-packages <sysgen>/MVSCE/MVP
   ```
   Exit codes: `0` everything matches the lock; `1` mismatch (each one is named on stderr as `PIN MISMATCH …`); `2` usage error or missing lock, component or path. Option: `--lock PATH`.

   The clone locations follow from `git_clone(out_folder=…)`: RAKF goes to `temp/RAKF` (default out_folder) and MVP to `MVSCE/MVP`. OSE-003 must confirm these paths in a real run.
4. **Hazards found while testing:**
   - `sysgen.py` calls `main()` at module level (l.3575, no `__main__` guard). **Never import it**, not even in tests; `tests/host/test_pins.py` lifts single methods out with `ast`.
   - On Windows Python, `which git` returns an MSYS path that cannot be executed. Sysgen supports Linux only (ADR-0003); the host tests work around this.
   - A clone made with `core.autocrlf=true` corrupts the MVP text packages. `check-mvp-packages` detects that (T-PIN-007).
