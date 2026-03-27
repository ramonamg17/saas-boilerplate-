FROM runpod/base:0.6.2-cuda12.2.0

# Use python3.11 explicitly throughout — the base image has pip wired to 3.11
# but the `python3` symlink may point to a different version.

# Install PyTorch with CUDA 12.1 support first (compatible with CUDA 12.2 base image).
# Done separately so pip can resolve kokoro-fastapi deps without hitting the cu129 index issue.
RUN python3.11 -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121 --no-cache-dir

# Install kokoro-fastapi from source (no [gpu] extra — torch already installed above)
RUN git clone https://github.com/remsky/kokoro-fastapi /root/kokoro-fastapi && \
    cd /root/kokoro-fastapi && \
    python3.11 -m pip install -e "." --no-cache-dir

# Pre-download model weights into the expected path so cold starts skip HuggingFace download.
# handler.py sets MODEL_DIR=src/models with cwd=/root/kokoro-fastapi,
# so the resolved path is /root/kokoro-fastapi/src/models/v1_0.
RUN python3.11 -c "\
import huggingface_hub; \
huggingface_hub.snapshot_download(\
    'hexgrad/Kokoro-82M', \
    local_dir='/root/kokoro-fastapi/src/models/v1_0'\
)"

# Install RunPod SDK
RUN python3.11 -m pip install runpod requests --no-cache-dir

COPY handler.py /handler.py

CMD ["python3.11", "-u", "/handler.py"]
