#!/usr/bin/env bash
# Creates a self-contained build + Python environment in .toolchain/ (no sudo).
# Remove the directory to uninstall. Safe to re-run.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TC="$ROOT/.toolchain"
MAMBA="$TC/bin/micromamba"
ENV="$TC/env"

mkdir -p "$TC/bin"
if [ ! -x "$MAMBA" ]; then
  echo "[toolchain] downloading micromamba"
  curl -fsSL -o "$MAMBA" \
    https://github.com/mamba-org/micromamba-releases/releases/latest/download/micromamba-linux-64
  chmod +x "$MAMBA"
fi

export MAMBA_ROOT_PREFIX="$TC/mamba-root"
PKGS=(python=3.12 cxx-compiler c-compiler cmake ninja ccache make matplotlib-base pytest)

if [ ! -x "$ENV/bin/python" ]; then
  echo "[toolchain] creating environment at $ENV"
  "$MAMBA" create -y -q -p "$ENV" -c conda-forge "${PKGS[@]}"
else
  echo "[toolchain] environment exists, ensuring packages"
  "$MAMBA" install -y -q -p "$ENV" -c conda-forge "${PKGS[@]}"
fi

echo "[toolchain] versions"
"$ENV/bin/python" --version
"$ENV/bin/cmake" --version | head -1
"$ENV/bin/ninja" --version
"$ENV/bin/ccache" --version | head -1
ls "$ENV"/bin/*-gnu-c++ | head -1
echo "[toolchain] done"
