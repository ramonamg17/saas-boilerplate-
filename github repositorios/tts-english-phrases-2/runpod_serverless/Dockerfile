FROM runpod/base:0.6.2-cuda12.2.0

# Install kokoro-fastapi GPU edition from source
RUN git clone https://github.com/remsky/kokoro-fastapi /root/kokoro-fastapi && \
    cd /root/kokoro-fastapi && \
    pip install -e ".[gpu]" --no-cache-dir

# Pre-download model weights into the expected path so cold starts skip HuggingFace download.
# handler.py sets MODEL_DIR=src/models with cwd=/root/kokoro-fastapi,
# so the resolved path is /root/kokoro-fastapi/src/models/v1_0.
RUN python3 -c "\
import huggingface_hub; \
huggingface_hub.snapshot_download(\
    'hexgrad/Kokoro-82M', \
    local_dir='/root/kokoro-fastapi/src/models/v1_0'\
)"

# Install RunPod SDK
RUN pip install runpod requests --no-cache-dir

COPY handler.py /handler.py

CMD ["python", "-u", "/handler.py"]
