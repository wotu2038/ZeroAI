# ZeroAI 后端服务

ZeroAI 知识图谱应用的后端服务，基于 FastAPI 构建，提供文档解析、实体关系提取、语义搜索和需求文档生成等 API 服务。

## 📋 目录

- [功能特性](#功能特性)
- [技术栈](#技术栈)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [服务说明](#服务说明)
- [数据库迁移](#数据库迁移)
- [API 文档](#api-文档)
- [开发指南](#开发指南)
- [常见问题](#常见问题)

## ✨ 功能特性

### 核心功能

- **文档管理**
  - 支持 Word 文档上传和解析
  - 文档版本管理
  - 文档分块策略（按标题级别、固定Token等）
  - 自动提取图片和 OLE 对象

- **知识图谱构建**
  - 基于 Graphiti 框架的实体和关系提取
  - Episode（事件）管理
  - Entity（实体）和 Edge（关系）提取
  - Community（社区）自动构建

- **语义搜索**
  - 基于向量嵌入的语义搜索
  - 支持 Episode、Entity、Edge、Community 检索
  - 跨文档搜索支持

- **需求文档生成**
  - 基于 LangGraph 的多智能体工作流
  - 自动检索相关内容
  - 文档质量评估和优化
  - 支持 Markdown 和 Word 格式导出

- **智能问答**
  - 基于知识图谱的问答系统
  - 支持 DeepSeek、Qwen、Kimi API
  - 多阶段检索和记忆注入
  - Mem0 对话记忆管理

## 🛠 技术栈

- **框架**: FastAPI 0.104.1
- **知识图谱**: Graphiti Core 0.24.3
- **图数据库**: Neo4j 5.26.0
- **关系数据库**: MySQL 8.0
- **任务队列**: Celery + Redis
- **LLM**: 支持 DeepSeek、Qwen、Kimi API（OpenAI 兼容接口）
- **Embedding**: Ollama (bge-m3)
- **记忆管理**: Mem0（对话记忆持久化）

## 🚀 快速开始

### 前置要求

- Docker & Docker Compose
- 至少 8GB 可用内存
- 磁盘空间：至少 10GB

### 安装步骤

1. **获取项目**

```bash
# 下载或获取项目代码
cd ZeroAI-backend
```

2. **配置环境变量**

```bash
# 复制环境变量示例文件
cp .env.example .env

# 编辑 .env 文件，填入实际配置
vim .env
```

3. **启动服务**

```bash
# 使用 Docker Compose 启动所有后端服务
docker-compose -f docker-compose.backend.yml up -d

# 查看服务状态
docker-compose -f docker-compose.backend.yml ps
```

4. **访问服务**

- **后端 API**: http://localhost:8000
- **API 文档**: http://localhost:8000/docs
- **Neo4j Web UI**: http://localhost:7474

## ⚙️ 配置说明

### 环境变量配置

所有配置都在 `.env` 文件中管理。**复制 `.env.example` 为 `.env` 并填入实际值**。

#### 必需配置

| 变量 | 说明 | 示例 |
|------|------|------|
| `NEO4J_URI` | Neo4j 连接地址 | `bolt://neo4j:7687` |
| `NEO4J_USER` | Neo4j 用户名 | `neo4j` |
| `NEO4J_PASSWORD` | Neo4j 密码 | `your_strong_password` |
| `MYSQL_HOST` | MySQL 主机 | `mysql` |
| `MYSQL_PORT` | MySQL 端口 | `3306` |
| `MYSQL_USER` | MySQL 用户名 | `zero_ai` |
| `MYSQL_PASSWORD` | MySQL 密码 | `your_strong_password` |
| `MYSQL_DATABASE` | MySQL 数据库名 | `zero_ai` |
| `REDIS_HOST` | Redis 主机 | `redis` |
| `REDIS_PORT` | Redis 端口 | `6379` |
| `REDIS_DB` | Redis 数据库号 | `0` |
| `JWT_SECRET_KEY` | JWT 签名密钥 | 使用下方命令生成 |

**生成 JWT 密钥**：
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

#### LLM 配置

支持以下三种 LLM API（至少配置一种）：

**DeepSeek API**:
```env
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_API_BASE=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_TIMEOUT=30
DEEPSEEK_MAX_RETRIES=3
```

**Qwen API**:
```env
QWEN_API_KEY=your_qwen_api_key
QWEN_API_BASE=https://dashscope.aliyuncs.com
QWEN_MODEL=qwen-turbo
QWEN_TIMEOUT=30
QWEN_MAX_RETRIES=3
```

**Kimi API**:
```env
KIMI_API_KEY=your_kimi_api_key
KIMI_API_BASE=https://api.moonshot.cn
KIMI_MODEL=moonshot-v1-8k
KIMI_TIMEOUT=30
KIMI_MAX_RETRIES=3
```

#### Embedding 配置

```env
OLLAMA_BASE_URL=http://your_ollama_host:port
OLLAMA_EMBEDDING_MODEL=bge-m3
```

#### Milvus 配置（可选，用于向量存储）

```env
MILVUS_HOST=your_milvus_host
MILVUS_PORT=19530
MILVUS_USERNAME=your_milvus_username  # 可选
MILVUS_PASSWORD=your_milvus_password  # 可选
```

#### 默认管理员配置（可选）

首次启动时自动创建管理员账户。如不设置，将不会自动创建。

```env
DEFAULT_ADMIN_USERNAME=super
DEFAULT_ADMIN_PASSWORD=your_admin_password
DEFAULT_ADMIN_EMAIL=admin@example.com
```

### 安全提示

- ⚠️ **生产环境必须使用强密码**
- ⚠️ **`.env` 文件包含敏感信息，请勿提交到版本控制系统**
- ⚠️ **JWT_SECRET_KEY 必须设置为随机生成的强密钥**
- ⚠️ **API密钥等敏感信息请妥善保管，不要泄露**
- ✅ **`.env.example` 是配置模板，使用占位符，可以提交到版本控制系统**

## 🏗 服务说明

### Docker 服务

后端包含以下 Docker 服务：

| 服务 | 端口 | 说明 |
|------|------|------|
| `neo4j` | 7474, 7687 | 图数据库 |
| `neo4j_init` | - | Neo4j 索引初始化（一次性） |
| `mysql` | 3306 | 关系数据库 |
| `redis` | 6380 | 缓存和任务队列 |
| `backend` | 8000 | FastAPI 后端服务 |
| `celery_worker` | - | 异步任务处理 |

### Neo4j 索引自动初始化

`neo4j_init` 服务会在 Neo4j 启动后自动创建 Graphiti 所需的所有索引：

- **Range 索引**：Entity、Episodic、Community、RELATES_TO、MENTIONS、HAS_MEMBER
- **Fulltext 索引**：episode_content、node_name_and_summary、community_name、edge_name_and_fact

如果重建 Neo4j 数据卷，索引会自动重新创建。

## 🗄 数据库迁移

### 迁移脚本说明

数据库迁移脚本位于 `backend/migrations/` 目录，用于创建和更新数据库表结构。

### 执行方式

#### 方式一：在 Docker 容器中执行（推荐）

```bash
# 进入后端容器
docker-compose -f docker-compose.backend.yml exec backend bash

# 在容器内执行迁移脚本
python /app/migrations/<脚本名称>.py
```

#### 方式二：直接执行（容器外）

```bash
# 直接执行迁移脚本
docker-compose -f docker-compose.backend.yml exec backend python /app/migrations/<脚本名称>.py
```

#### 方式三：使用 Python 模块方式

```bash
# 在容器内执行
docker-compose -f docker-compose.backend.yml exec backend python -m app.migrations.<脚本名称>
```

### 迁移脚本列表

#### 1. 基础表结构迁移（首次安装必须执行）

按以下顺序执行：

**① 创建用户表**
```bash
docker-compose -f docker-compose.backend.yml exec backend python /app/migrations/create_users.py
```
- 功能：创建 `users` 表
- 说明：如果表已存在，会自动跳过

**② 添加用户角色字段**
```bash
docker-compose -f docker-compose.backend.yml exec backend python /app/migrations/add_role_to_users.py
```
- 功能：为 `users` 表添加 `role` 字段（admin/common）
- 说明：支持用户角色管理

**③ 创建知识库表**
```bash
docker-compose -f docker-compose.backend.yml exec backend python /app/migrations/create_knowledge_bases.py
```
- 功能：创建 `knowledge_bases` 表
- 说明：知识库管理功能的基础表

**④ 为文档表添加知识库字段**
```bash
docker-compose -f docker-compose.backend.yml exec backend python /app/migrations/add_kb_fields_to_documents.py
```
- 功能：为 `document_uploads` 表添加知识库相关字段
- 说明：关联文档和知识库

#### 2. 功能增强迁移（按需执行）

**⑤ 添加对话历史表**
```bash
docker-compose -f docker-compose.backend.yml exec backend python /app/migrations/add_chat_history_table.py
```
- 功能：创建 `chat_histories` 表
- 说明：支持对话历史持久化功能

**⑥ 添加文档库相关表**
```bash
docker-compose -f docker-compose.backend.yml exec backend python /app/migrations/add_document_library_tables.py
```
- 功能：创建 `document_folders` 和 `document_library` 表
- 说明：支持文档库管理功能

**⑦ 添加文档库关联字段**
```bash
docker-compose -f docker-compose.backend.yml exec backend python -m app.migrations.add_library_document_id_to_document_upload
```
- 功能：为 `document_uploads` 表添加 `library_document_id` 字段
- 说明：关联文档库和文档上传记录

**⑧ 添加LLM模板字段**
```bash
docker-compose -f docker-compose.backend.yml exec backend python /app/migrations/add_llm_template_fields.py
```
- 功能：为模板表添加LLM生成相关字段
- 说明：支持LLM自动生成模板功能

**⑨ 创建数据库索引**
```bash
docker-compose -f docker-compose.backend.yml exec backend python /app/migrations/create_indexes.py
```
- 功能：为常用查询字段创建索引
- 说明：提升查询性能

#### 3. 数据清理脚本（谨慎使用）

**⑩ 清理历史数据**
```bash
docker-compose -f docker-compose.backend.yml exec backend python -m app.migrations.cleanup_historical_data
```
- 功能：删除所有 `document_uploads` 和 `task_queue` 记录及相关文件
- ⚠️ **警告**：此操作会删除所有文档上传记录和任务记录，请谨慎使用
- 使用场景：开发环境重置、测试数据清理

### 首次安装迁移顺序

如果是首次安装，建议按以下顺序执行迁移脚本：

```bash
# 1. 创建用户表
docker-compose -f docker-compose.backend.yml exec backend python /app/migrations/create_users.py

# 2. 添加用户角色字段
docker-compose -f docker-compose.backend.yml exec backend python /app/migrations/add_role_to_users.py

# 3. 创建知识库表
docker-compose -f docker-compose.backend.yml exec backend python /app/migrations/create_knowledge_bases.py

# 4. 为文档表添加知识库字段
docker-compose -f docker-compose.backend.yml exec backend python /app/migrations/add_kb_fields_to_documents.py

# 5. 添加对话历史表（可选，如果需要对话历史功能）
docker-compose -f docker-compose.backend.yml exec backend python /app/migrations/add_chat_history_table.py

# 6. 添加文档库相关表（可选，如果需要文档库功能）
docker-compose -f docker-compose.backend.yml exec backend python /app/migrations/add_document_library_tables.py

# 7. 添加文档库关联字段（如果执行了步骤6）
docker-compose -f docker-compose.backend.yml exec backend python -m app.migrations.add_library_document_id_to_document_upload

# 8. 添加LLM模板字段（可选）
docker-compose -f docker-compose.backend.yml exec backend python /app/migrations/add_llm_template_fields.py

# 9. 创建索引（可选，建议执行以提升性能）
docker-compose -f docker-compose.backend.yml exec backend python /app/migrations/create_indexes.py
```

### 迁移脚本执行注意事项

1. **执行顺序**：基础表结构迁移必须按顺序执行，功能增强迁移可以按需执行
2. **幂等性**：大部分迁移脚本支持重复执行（会检查表/字段是否已存在）
3. **备份数据**：执行迁移前建议备份数据库（特别是生产环境）
4. **查看日志**：执行迁移时注意查看输出日志，确认执行结果

### 验证迁移结果

执行迁移后，可以通过以下方式验证：

```bash
# 进入MySQL容器
docker-compose -f docker-compose.backend.yml exec mysql mysql -uroot -p${MYSQL_PASSWORD} ${MYSQL_DATABASE}

# 查看所有表
SHOW TABLES;

# 查看表结构
DESCRIBE users;
DESCRIBE knowledge_bases;
DESCRIBE document_uploads;
```

### 常用命令

```bash
# 启动所有后端服务
docker-compose -f docker-compose.backend.yml up -d

# 停止所有服务
docker-compose -f docker-compose.backend.yml down

# 查看服务状态
docker-compose -f docker-compose.backend.yml ps

# 查看日志
docker-compose -f docker-compose.backend.yml logs -f

# 查看特定服务日志
docker-compose -f docker-compose.backend.yml logs -f backend
docker-compose -f docker-compose.backend.yml logs -f celery_worker

# 重启服务
docker-compose -f docker-compose.backend.yml restart [服务名]

# 进入容器
docker-compose -f docker-compose.backend.yml exec backend bash

# 执行数据库迁移（详见"数据库迁移"章节）
docker-compose -f docker-compose.backend.yml exec backend python /app/migrations/<脚本名称>.py
```

## 📚 API 文档

启动服务后，访问以下地址查看 API 文档：

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### 主要 API 端点

- `POST /api/document-upload/upload` - 上传文档
- `POST /api/document-upload/{id}/parse` - 解析文档
- `POST /api/document-upload/{id}/split` - 文档分块
- `POST /api/document-upload/{id}/process` - 创建 Episode
- `POST /api/document-upload/{id}/build-communities-async` - 构建 Community
- `POST /api/requirements/generate-async` - 生成需求文档
- `GET /api/tasks` - 查询任务列表
- `GET /api/tasks/{task_id}` - 查询任务详情

## 💻 开发指南

### 本地开发

```bash
# 进入后端目录
cd backend

# 安装依赖
pip install -r requirements.txt

# 启动开发服务器
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 代码结构

```
ZeroAI-backend/
├── backend/                     # 后端代码
│   ├── app/
│   │   ├── api/                # API 路由
│   │   ├── core/               # 核心配置
│   │   │   ├── config.py       # 配置管理（从 .env 读取）
│   │   │   ├── celery_app.py   # Celery 配置
│   │   │   ├── graphiti_client.py  # Graphiti 客户端
│   │   │   ├── llm_client.py   # LLM 客户端
│   │   │   └── mysql_client.py # MySQL 客户端
│   │   ├── models/             # 数据模型
│   │   ├── services/           # 业务逻辑
│   │   ├── tasks/              # Celery 任务
│   │   └── utils/              # 工具函数
│   │       └── init_default_user.py  # 默认管理员初始化
│   ├── migrations/             # 数据库迁移脚本
│   ├── Dockerfile
│   ├── init_mysql.sql          # MySQL 初始化（字符集设置）
│   └── requirements.txt
├── docker-compose.backend.yml  # Docker Compose 配置
├── .env.example                # 环境变量示例（提交到 Git）
├── .env                        # 实际配置（不提交到 Git）
└── README.md                   # 本文档
```

## ❓ 常见问题

### 1. 服务启动失败

**问题**: Docker 服务无法启动

**解决方案**:
- 检查 Docker 是否运行: `docker info`
- 检查端口是否被占用: `lsof -i :8000`
- 查看详细日志: `docker-compose -f docker-compose.backend.yml logs [服务名]`
- 检查 `.env` 文件配置是否正确且完整

### 2. 配置读取失败

**问题**: 提示缺少环境变量

**解决方案**:
- 确保 `.env` 文件存在且配置完整
- 对照 `.env.example` 检查是否遗漏配置项
- 检查环境变量名称是否正确（区分大小写）

### 3. Neo4j 索引缺失

**问题**: 任务失败，提示 `no such fulltext schema index`

**解决方案**:
- `neo4j_init` 服务会自动创建索引
- 检查 `neo4j_init` 日志: `docker logs zero-ai-neo4j-init`
- 如需手动重建，删除 Neo4j 数据卷后重启服务

### 4. 任务一直处于 pending 状态

**问题**: Celery 任务无法执行

**解决方案**:
- 检查 Celery worker 是否运行: `docker-compose -f docker-compose.backend.yml ps celery_worker`
- 查看 Celery 日志: `docker-compose -f docker-compose.backend.yml logs -f celery_worker`
- 检查 Redis 连接是否正常
- 重启 Celery worker: `docker-compose -f docker-compose.backend.yml restart celery_worker`

### 5. 数据库连接失败

**问题**: MySQL 或 Neo4j 连接被拒绝

**解决方案**:
- 检查 `.env` 中的密码是否与数据库实际密码一致
- 如果修改过密码，需要删除数据卷重新初始化：
  ```bash
  docker-compose -f docker-compose.backend.yml down -v
  docker-compose -f docker-compose.backend.yml up -d
  ```

### 6. 向量搜索无结果

**问题**: 语义搜索返回空结果

**解决方案**:
- 确保 Ollama 服务正常运行
- 检查 Embedding 模型是否正确加载
- 确认文档已成功创建 Episode 并提取实体
- 检查 Neo4j 中是否有数据

## 📝 许可证

[添加许可证信息]

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📧 联系方式

[添加联系方式]

---

**注意**: 这是一个开发中的项目，生产环境使用前请仔细测试。
