FROM python:3.10-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 分步安装依赖，解决 neo4j 版本冲突
# 步骤1: 先安装 neo4j==5.26.0（固定版本，必须在 cognee 之前）
RUN pip install --no-cache-dir neo4j==5.26.0

# 步骤2: 安装其他依赖（排除 cognee[neo4j]，避免版本冲突）
RUN grep -v "cognee\[neo4j\]" requirements.txt > /tmp/requirements_no_cognee.txt && \
    pip install --no-cache-dir -r /tmp/requirements_no_cognee.txt

# 步骤3: 安装 cognee[neo4j]，使用 --no-deps 避免升级 neo4j
RUN pip install --no-cache-dir 'cognee[neo4j]>=0.5.1' --no-deps

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

