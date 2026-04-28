#!/bin/bash
# vLLM Setup Script
# This script helps download and configure vLLM with DeepSeek-Coder or CodeLlama

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║       vLLM & DeepSeek-Coder Setup Wizard                          ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

if ! command -v python &> /dev/null; then
    echo -e "${RED}✗ Python 3.10+ is required but not found${NC}"
    exit 1
fi

if ! command -v nvidia-smi &> /dev/null; then
    echo -e "${YELLOW}⚠ No NVIDIA GPU found. Inference will run on CPU (very slow)${NC}"
    CPU_ONLY=true
else
    echo -e "${GREEN}✓ NVIDIA GPU detected${NC}"
    nvidia-smi --query-gpu=name --format=csv,noheader
fi

echo ""
echo -e "${BLUE}Step 1: Choose Model${NC}"
echo "1) DeepSeek-Coder-V2 (6.7B) - Recommended, 128k context, ~15GB VRAM"
echo "2) CodeLlama-70B (70B) - Better performance, needs 140GB+ VRAM (multi-GPU)"
echo ""
read -p "Select model (1 or 2): " model_choice

case $model_choice in
    1)
        MODEL_NAME="deepseek-coder-v2"
        MODEL_HF="deepseek-ai/deepseek-coder-6.7b-base"
        TENSOR_PARALLEL=1
        DTYPE="bfloat16"
        echo -e "${GREEN}✓ Selected: DeepSeek-Coder-V2${NC}"
        ;;
    2)
        MODEL_NAME="codellama-70b"
        MODEL_HF="meta-llama/CodeLlama-70b-hf"
        TENSOR_PARALLEL=2
        DTYPE="float16"
        echo -e "${GREEN}✓ Selected: CodeLlama-70B${NC}"
        ;;
    *)
        echo -e "${RED}✗ Invalid option${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${BLUE}Step 2: Install Dependencies${NC}"

# Check if venv exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python -m venv venv
fi

source venv/bin/activate

echo -e "${YELLOW}Installing vLLM and transformers...${NC}"
pip install --upgrade pip setuptools wheel
pip install vllm>=0.3.0 transformers>=4.40.0 tokenizers

if [ "$CPU_ONLY" != "true" ]; then
    echo -e "${YELLOW}Installing CUDA-accelerated PyTorch...${NC}"
    pip install torch>=2.1.0 --index-url https://download.pytorch.org/whl/cu121
fi

echo -e "${GREEN}✓ Dependencies installed${NC}"

echo ""
echo -e "${BLUE}Step 3: Download Model${NC}"

MODELS_DIR="./models"
mkdir -p $MODELS_DIR

echo -e "${YELLOW}Downloading ${MODEL_NAME}...${NC}"
echo "This may take 10-30 minutes depending on internet speed"
echo ""

if ! command -v huggingface-cli &> /dev/null; then
    echo -e "${YELLOW}Installing huggingface_hub...${NC}"
    pip install huggingface_hub
fi

huggingface-cli download $MODEL_HF \
    --local-dir "$MODELS_DIR/${MODEL_NAME}" \
    --local-dir-use-symlinks False

echo -e "${GREEN}✓ Model downloaded to $MODELS_DIR/${MODEL_NAME}${NC}"

echo ""
echo -e "${BLUE}Step 4: Update .env Configuration${NC}"

ENV_FILE=".env"

if [ ! -f "$ENV_FILE" ]; then
    echo -e "${YELLOW}Creating .env file...${NC}"
    cp .env.example .env
fi

# Update .env with vLLM settings
sed -i "s|LLM_BACKEND=.*|LLM_BACKEND=vllm|g" $ENV_FILE
sed -i "s|VLLM_ENDPOINT=.*|VLLM_ENDPOINT=http://localhost:8001/v1|g" $ENV_FILE
sed -i "s|VLLM_MODEL=.*|VLLM_MODEL=${MODEL_NAME}|g" $ENV_FILE

echo -e "${GREEN}✓ .env updated${NC}"
cat $ENV_FILE | grep "VLLM_"

echo ""
echo -e "${BLUE}Step 5: Start vLLM Server${NC}"
echo ""
echo -e "${YELLOW}Generated startup command:${NC}"
echo ""

if [ "$CPU_ONLY" = "true" ]; then
    STARTUP_CMD="python -m vllm.entrypoints.openai.api_server \
  --model \"$MODELS_DIR/${MODEL_NAME}\" \
  --device cpu \
  --port 8001"
else
    STARTUP_CMD="python -m vllm.entrypoints.openai.api_server \
  --model \"$MODELS_DIR/${MODEL_NAME}\" \
  --tensor-parallel-size ${TENSOR_PARALLEL} \
  --gpu-memory-utilization 0.9 \
  --dtype ${DTYPE} \
  --port 8001"
fi

echo -e "${GREEN}$STARTUP_CMD${NC}"
echo ""

read -p "Start vLLM server now? (y/n): " start_now

if [ "$start_now" = "y" ]; then
    echo ""
    echo -e "${YELLOW}Starting vLLM server...${NC}"
    echo "Server will be available at: http://localhost:8001/v1"
    echo "Press Ctrl+C to stop"
    echo ""
    
    eval $STARTUP_CMD
else
    echo ""
    echo -e "${YELLOW}To start the server manually, run:${NC}"
    echo -e "${GREEN}source venv/bin/activate${NC}"
    echo -e "${GREEN}$STARTUP_CMD${NC}"
fi

echo ""
echo -e "${BLUE}Step 6: Verify Installation${NC}"
echo ""
echo "In another terminal, run:"
echo -e "${GREEN}curl -X POST http://localhost:8001/v1/chat/completions \\${NC}"
echo -e "${GREEN}  -H \"Content-Type: application/json\" \\${NC}"
echo -e "${GREEN}  -d '{\"model\": \"${MODEL_NAME}\", \"messages\": [{\"role\": \"user\", \"content\": \"say hello\"}]}'${NC}"
echo ""

echo -e "${GREEN}✓ Setup complete!${NC}"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "1. Fill in remaining .env variables (GITHUB_*, GEMINI_*)"
echo "2. Run tests: ${GREEN}make test${NC}"
echo "3. Start the app: ${GREEN}make dev${NC}"
echo ""
echo "For more info, see: VLLM.md"
