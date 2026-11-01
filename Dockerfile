# Test image for the pipeline code. It needs no GPU, no video, no KataGo and no whisper.
# Build and run:  docker build -t weiqi-pipeline-tests . && docker run --rm weiqi-pipeline-tests
FROM python:3.12-slim

# Same text settings we want on the real machine: utf-8 everywhere.
ENV PYTHONUTF8=1 \
    PYTHONIOENCODING=utf-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
# numpy is only used by the board recognition tests with synthetic frames.
RUN pip install pytest==8.3.4 numpy==2.1.3

COPY pytest.ini ./
COPY pipeline pipeline
COPY tools tools
COPY data/sgf data/sgf
COPY data/sources data/sources
COPY tests tests

CMD ["python", "-m", "pytest"]
