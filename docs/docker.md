# Docker image and autonomous installation

The [Dockerfile](../Dockerfile) packages everything a comparison needs:

| Component | Version | Source |
|---|---|---|
| Chrome for Testing | 153.0.8010.47 (same as the GitHub Action) | official archive, SHA-256 checked |
| Node.js | 22.23.4, Debian bookworm slim | `node` image pinned by digest |
| uv / Python | uv 0.13.7, Python from `analysis/.python-version` | `ghcr.io/astral-sh/uv` pinned by digest |
| perfgate collector | compiled from this checkout, `pnpm-lock.yaml` | `--frozen-lockfile`, production deps only |
| perfgate analysis | `analysis/uv.lock` | `uv sync --locked --no-dev` |
| pnpm | 11.7.0 | for `compare-refs` configurations that call it |

The entry point is `perfgate`; `perfgate comment ...` runs the
[comment renderer](pr-comments.md). Reports go to the mounted working directory `/work`.

## Build

```sh
docker build --platform linux/amd64 -t perfgate:$(git rev-parse --short HEAD) .
```

Chrome for Testing has no Linux ARM build, so the measurement image is
`linux/amd64`. On an ARM machine the build still succeeds (JavaScript is compiled
in a native build stage), but Chrome **cannot measure under QEMU emulation**: on
an Apple Silicon/colima host every load failed with `Target closed`, and perfgate
correctly reported the comparison as invalid (exit 2). Use an x86-64 host for
real measurements.

For a native ARM smoke image there is a clearly separate variant:

```sh
docker build --build-arg CHROME_SOURCE=debian -t perfgate:debian .
```

It installs Debian's current `chromium` package (156.0.8078.79 when last built),
which is **not pinned** and must not be pooled or compared with results from the
pinned browser. Raw records keep the binary version (`env.chromeBinaryVersion`),
and `/opt/perfgate/chrome-version.txt` records it in the image.

## Run

Both application versions must be reachable from inside the container. On Linux
the simplest way is the host network:

```sh
mkdir -p results
docker run --rm --network host --shm-size=2g -v "$PWD/results:/work" perfgate:<tag> \
  compare --url http://127.0.0.1:4173/ --pr-url http://127.0.0.1:4174/ \
  --runs 20 --app home --out /work/my-comparison
```

- `--shm-size=2g`: Docker's default 64 MB `/dev/shm` is too small for Chrome.
- Exit codes are those of `perfgate compare` (0 / 1 / 2 / 3, see the [user guide](user-guide.md)).
- Recorded data can be re-analyzed without Chrome:
  `... perfgate:<tag> compare --input /work/runs.jsonl --runs 20 --out /work/replay`.
- To reduce noise from neighbours, pin the container to dedicated CPUs
  (`--cpuset-cpus`) and keep other workloads off the machine. Container limits do
  not make two machines comparable: compare base and PR on the same machine in
  the same job, which perfgate's interleaved order does.
- The image runs as root because CI systems mount workspaces with varying owners;
  Chrome already runs with `--no-sandbox` inside the collector. Run it only on
  disposable CI workers when it executes untrusted pull request code.

`compare-refs` also works in the container if the application's own toolchain is
present (extend the image) and the repository is mounted. Git refuses repositories
owned by another user; add `-e GIT_CONFIG_COUNT=1 -e GIT_CONFIG_KEY_0=safe.directory
-e GIT_CONFIG_VALUE_0=/repo` when mounting it at `/repo`.

## Autonomous (offline) installation

perfgate itself makes no network requests other than to the measured URLs: the
browser, Node packages, Python and its packages are all inside the image. To
install on a machine without Internet access:

```sh
# on a connected machine
docker build --platform linux/amd64 -t perfgate:1 .
docker save perfgate:1 | gzip > perfgate-1.tar.gz
sha256sum perfgate-1.tar.gz > perfgate-1.tar.gz.sha256

# on the isolated machine, after copying both files
sha256sum -c perfgate-1.tar.gz.sha256
gunzip -c perfgate-1.tar.gz | docker load
docker run --rm perfgate:1 --help
```

Alternatively push the image to an internal registry (`docker tag`/`docker push`)
and reference it by digest in CI. The build itself needs network access to
Docker Hub, GHCR, the npm registry, PyPI/Python downloads and the Chrome for
Testing bucket; mirror those or build on a connected machine.

Without Docker, the same pieces can be installed from a source checkout:
Node 22 and pnpm 11.7.0, `pnpm install --frozen-lockfile` (offline: `pnpm fetch`
on a connected machine, then `pnpm install --offline`), uv and
`uv sync --locked --directory analysis` (offline: copy the uv cache and the managed
Python, then `uv sync --locked --offline`), and the Chrome archive from the URL in
the Dockerfile with its SHA-256. Set `CHROME_PATH` to the extracted `chrome`.

## Verification (5 November 2026)

- `linux/amd64` image (pinned Chrome for Testing 153.0.8010.47) built on an Apple
  Silicon host under emulation, about 2 minutes with cached base layers, ~530 MB.
  `perfgate --help`, recorded-data `compare --input` (exit 1 on a synthetic
  regression) and `perfgate comment render` worked. Live measurement under
  emulation failed as described above and was reported as invalid.
- Native `linux/arm64` `CHROME_SOURCE=debian` image: two live 10-load comparisons
  of the demo heavy page served inside the container — A/A: no regression
  detected (exit 0); `script-delay:179`: regression (exit 1; FCP +7.5%, LCP +6.0%).
  About 7 minutes each. Reports: [docs/results/2026-11-05/docker-smoke](results/2026-11-05/docker-smoke).
  These are functional smoke tests with an unpinned browser, not research data.
- The native x86-64 build and live check with the pinned browser is automated in
  `.github/workflows/docker-smoke.yml`; it has not run on hosted CI yet.
