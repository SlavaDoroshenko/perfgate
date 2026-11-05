# perfgate measurement image: pinned Chrome for Testing, Node, uv/Python, the
# compiled perfgate collector and the locked analysis environment.
#
#   docker build --platform linux/amd64 -t perfgate:local .
#   docker run --rm --shm-size=2g -v "$PWD/results:/work" perfgate:local compare ...
#
# Chrome for Testing publishes x86-64 Linux builds only, so measurement images are
# linux/amd64. CHROME_SOURCE=debian builds a native image with Debian's unpinned
# Chromium instead (for example on ARM): usable for smoke tests, not comparable
# with the research corpus. See docs/docker.md.

ARG NODE_IMAGE=node:22.23.4-bookworm-slim@sha256:4b150b48b4116e2a22f2c39cc27025fbf4f153e2078fd3b14d159fdb5c7279da
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.13.7@sha256:96f40d3904aad8d0bd010539001d36c8e2188b981e1334471a90c4a1d93bb490
ARG PNPM_VERSION=11.7.0

FROM ${UV_IMAGE} AS uv

# JavaScript is compiled and production dependencies are resolved on the build
# machine's own architecture: the output is plain JavaScript, and no emulated
# Node/esbuild/TypeScript binaries run during the build.
FROM --platform=$BUILDPLATFORM ${NODE_IMAGE} AS collector
ARG PNPM_VERSION
ENV CI=true PNPM_CONFIG_UPDATE_NOTIFIER=false
RUN npm install -g "pnpm@${PNPM_VERSION}"
WORKDIR /build
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml tsconfig.base.json ./
COPY packages/collector/package.json packages/collector/
RUN pnpm install --frozen-lockfile --filter perfgate --filter @perfgate/collector
COPY packages/collector packages/collector
RUN pnpm --filter @perfgate/collector build
WORKDIR /prod
RUN cp /build/package.json /build/pnpm-lock.yaml /build/pnpm-workspace.yaml . \
 && mkdir -p packages/collector \
 && cp /build/packages/collector/package.json packages/collector/ \
 && cp -r /build/packages/collector/dist packages/collector/dist \
 && pnpm install --frozen-lockfile --prod --ignore-scripts --filter @perfgate/collector

FROM ${NODE_IMAGE}
ARG PNPM_VERSION
ARG CHROME_SOURCE=chrome-for-testing
ARG CHROME_VERSION=153.0.8010.47
ARG CHROME_SHA256=89778cbf7a852726b6f51649b2586b894c00737e81f8031733721560d21bbea7
ENV DEBIAN_FRONTEND=noninteractive

# deb.deps in the Chrome archive lists its shared-library packages; the first
# alternative of each line is installed.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl unzip git \
 && if [ "$CHROME_SOURCE" = chrome-for-testing ]; then \
      curl -fsSLo /tmp/chrome.zip "https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chrome-linux64.zip" \
      && echo "${CHROME_SHA256}  /tmp/chrome.zip" | sha256sum -c - \
      && unzip -q /tmp/chrome.zip -d /opt \
      && mv /opt/chrome-linux64 /opt/chrome \
      && rm /tmp/chrome.zip \
      && apt-get install -y --no-install-recommends $(sed -E 's/ *\(.*//; s/ *\|.*//' /opt/chrome/deb.deps) \
      && /opt/chrome/chrome --version | grep -F "${CHROME_VERSION}"; \
    elif [ "$CHROME_SOURCE" = debian ]; then \
      apt-get install -y --no-install-recommends chromium fonts-liberation \
      && mkdir -p /opt/chrome && ln -s /usr/bin/chromium /opt/chrome/chrome \
      && /opt/chrome/chrome --version; \
    else echo "unknown CHROME_SOURCE=$CHROME_SOURCE" >&2; exit 1; fi \
 && rm -rf /var/lib/apt/lists/*
ENV CHROME_PATH=/opt/chrome/chrome

# pnpm is not needed by perfgate itself; compare-refs configurations often call it.
RUN npm install -g "pnpm@${PNPM_VERSION}" && npm cache clean --force
COPY --from=uv /uv /uvx /usr/local/bin/
ENV UV_PYTHON_INSTALL_DIR=/opt/uv-python \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1
WORKDIR /opt/perfgate
COPY analysis/pyproject.toml analysis/uv.lock analysis/.python-version analysis/
RUN uv sync --locked --no-dev --no-install-project --directory analysis
COPY --from=collector /prod/ ./
# The collector runs `analysis/.venv/bin/python -m perfgate_analysis.compare` with
# analysis/ on PYTHONPATH, so the analysis project itself is not installed.
COPY analysis/perfgate_analysis analysis/perfgate_analysis
COPY schema schema
COPY scripts/comment scripts/comment
COPY examples examples
COPY docker/perfgate /usr/local/bin/perfgate
RUN perfgate --help > /dev/null \
 && PYTHONPATH=analysis analysis/.venv/bin/python -c "import perfgate_analysis.compare" \
 && /opt/chrome/chrome --version > /opt/perfgate/chrome-version.txt

ENV PERFGATE_HOME=/opt/perfgate
WORKDIR /work
ENTRYPOINT ["perfgate"]
CMD ["--help"]
