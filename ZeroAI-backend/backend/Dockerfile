FROM python:3.10-slim

WORKDIR /app

# 配置使用阿里云 Debian 镜像源（解决国内网络访问问题）
# 兼容 Debian 12 (bookworm) 和 Debian 13 (trixie)
RUN if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
        sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources && \
        sed -i 's|security.debian.org|mirrors.aliyun.com/debian-security|g' /etc/apt/sources.list.d/debian.sources; \
    else \
        echo "deb http://mirrors.aliyun.com/debian/ bookworm main" > /etc/apt/sources.list && \
        echo "deb http://mirrors.aliyun.com/debian-security/ bookworm-security main" >> /etc/apt/sources.list && \
        echo "deb http://mirrors.aliyun.com/debian/ bookworm-updates main" >> /etc/apt/sources.list; \
    fi

# 安装系统依赖（优化：分步安装，减少内存占用）
# 先更新包列表
RUN apt-get update

# 安装 gcc 及其最小依赖（避免安装完整 build-essential）
RUN apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

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

