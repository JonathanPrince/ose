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
2. **Pre-stage RAKF and MVP at their pins, line-ending-safe, where sysgen clones them.** (Revised after review round 1: validation must come **before** consumption. Sysgen clones MVP and installs its packages within the same step 9, so a check after sysgen would only see bytes that were already used.)
   ```sh
   git -c core.autocrlf=false clone --no-checkout https://github.com/mvslovers/RAKF   <sysgen>/temp/RAKF
   git -C <sysgen>/temp/RAKF config core.autocrlf false
   git -C <sysgen>/temp/RAKF checkout --detach 941b07dc19adb7a1a153caaeba96b659ff2ad3e0
   git -c core.autocrlf=false clone --no-checkout https://github.com/MVS-sysgen/MVP   <sysgen>/MVSCE/MVP
   git -C <sysgen>/MVSCE/MVP config core.autocrlf false
   git -C <sysgen>/MVSCE/MVP checkout --detach 4c004a599f6a49442fade63cdb3cc3a9e0fdf58a
   ```
   Start from a clean `<sysgen>/temp/RAKF` and `<sysgen>/MVSCE/MVP`: remove them first, because `git clone` refuses a non-empty target. The paths follow from `git_clone(out_folder=…)`: RAKF uses the default `temp/`, and MVP uses `MVSCE/`. Sysgen deletes `temp/` only in its final cleanup step, and only without `--keep-temp` (`sysgen.py` l.3080-3082 at the pin; l.3083-3085 once P-01 is applied). So the pre-staged trees survive until they are used. OSE-003 must confirm the paths in a real run.
3. **Validate before sysgen starts.** Any nonzero RC stops the build, and sysgen is not run:
   ```sh
   python3 scripts/lib/pins.py check-clone rakf <sysgen>/temp/RAKF
   python3 scripts/lib/pins.py check-clone mvp  <sysgen>/MVSCE/MVP
   python3 scripts/lib/pins.py check-mvp-packages <sysgen>/MVSCE/MVP
   ```
   Exit codes: `0` everything matches the lock; `1` mismatch (each one is named on stderr as `PIN MISMATCH …`); `2` usage error or missing lock, component or path. Option: `--lock PATH`.
3a. **Run sysgen with `--keep-temp`** (required; review round 2, R13-2). Without it, sysgen's final cleanup deletes `temp/` (`sysgen.py` l.3080-3082 at the pin; the flag is defined at l.3462). That takes `temp/RAKF` with it, and the step 3b RAKF check would then fail with RC 2 after a successful build. `MVSCE/MVP` is not removed. With P-01, steps 8 and 9 find the validated clones and take the existing-clone path. They `fetch`, then `checkout --force --detach <pin>` (a no-op on a clean tree at the pin), then verify `HEAD` and fail with `… is at <sha> but mvslovers.conf pins commit <sha>` on any difference. The tree is reused, not re-cloned. Host test **T-PIN-008** shows both halves: a corrupted pre-staged package is rejected by step 3, and a valid tree passes, is reused unchanged by the patched `git_clone`, and still passes afterwards.
3b. **After sysgen (evidence only, for OSE-003 test 7):** re-run the three step-3 commands and keep their output. A failure here means something changed the tree during the run. Treat the build as invalid; this does not replace step 3. An RC 2 naming a missing `temp/RAKF` means step 3a ran without `--keep-temp`, so the run produced no evidence. Repeat it with the flag. After the evidence is saved, the wrapper may delete `<sysgen>/temp` itself, which is what sysgen would have done.
   - Residual risk: between step 3 and the step 9 install, the only writer is sysgen's own forced checkout. That uses the clone's local `core.autocrlf=false`, which a global setting cannot override. A repository `.gitattributes` would apply both when hashing and at checkout. Step 3b detects any change, but only after the fact.
4. **Hazards found while testing:**
   - `sysgen.py` calls `main()` at module level (l.3575, no `__main__` guard). **Never import it**, not even in tests; `tests/host/test_pins.py` lifts single methods out with `ast`.
   - On Windows Python, `which git` returns an MSYS path that cannot be executed. Sysgen supports Linux only (ADR-0003); the host tests work around this.
   - A clone made with `core.autocrlf=true` corrupts the MVP text packages. `check-mvp-packages` detects that (T-PIN-007).
