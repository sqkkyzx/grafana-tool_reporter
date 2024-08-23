FROM python:3.12-slim

WORKDIR /usr/src/myapp

# 安装依赖
RUN pip install --upgrade pip && \
    pip install playwright httpx pandas openpyxl PyYAML APScheduler boto3 openai && \
    pip cache purge

RUN apt-get update &&  \
    apt-get install fonts-noto-cjk && \
    playwright install chromium && \
    playwright install-deps && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

COPY . .

# 启动应用程序
CMD ["python", "main.py"]