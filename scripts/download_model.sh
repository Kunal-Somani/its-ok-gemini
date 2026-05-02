#!/usr/bin/env bash
set -e

MODEL_DIR="models"
MODEL_FILE="qwen2.5-coder-7b-instruct-q4_k_m.gguf"
HF_REPO="Qwen/Qwen2.5-Coder-7B-Instruct-GGUF"

echo "Archon — Downloading Qwen2.5-Coder-7B-Instruct Q4_K_M GGUF (~4.5GB)"
echo "Source: https://huggingface.co/${HF_REPO}"
echo ""

mkdir -p "${MODEL_DIR}"

if [ -f "${MODEL_DIR}/${MODEL_FILE}" ]; then
  echo "Model already exists at ${MODEL_DIR}/${MODEL_FILE}. Skipping download."
  exit 0
fi

if command -v huggingface-cli &> /dev/null; then
  echo "Using huggingface-cli..."
  huggingface-cli download "${HF_REPO}" "${MODEL_FILE}" --local-dir "${MODEL_DIR}"
else
  echo "huggingface-cli not found. Falling back to wget..."
  wget -c \
    "https://huggingface.co/${HF_REPO}/resolve/main/${MODEL_FILE}" \
    -O "${MODEL_DIR}/${MODEL_FILE}"
fi

echo ""
echo "Download complete: ${MODEL_DIR}/${MODEL_FILE}"
echo "You can now start Archon: docker compose up -d --build"
