FROM python:3.13-slim

ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app:/app/bot \
    TZ=Asia/Shanghai

WORKDIR /app

COPY requirements.txt /app/bot/requirements.txt
RUN pip install --no-cache-dir -i ${PIP_INDEX_URL} -r /app/bot/requirements.txt

COPY wm_helper /app/wm_helper
COPY data /app/data
COPY bot /app/bot

WORKDIR /app/bot
CMD ["python", "bot.py"]
