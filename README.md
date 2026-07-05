# Photo Manager

PhotoManager 是一个基于 B/S 架构的图片管理系统，采用 Flask 开发，完成了图片上传、管理、编辑、搜索以及用户认证的完整链路。

## 目录结构树

```
PhotoManager/
├── run.py                    # 启动入口
├── config.py                 # 配置（数据库、上传路径、白名单等）
├── requirements.txt          # 依赖清单
├── .env                      # 环境变量（数据库密码、API Key等）
├── README.md                 # 说明文档
├── app/
│   ├── __init__.py           # 应用工厂与扩展初始化
│   ├── models.py             # User、Image、Tag 模型
│   ├── main_routes.py        # 首页等通用路由
│   ├── auth/                 # 认证蓝图
│   │   ├── __init__.py
│   │   └── routes.py         # 登录、注册、登出
│   ├── image/                # 图片蓝图
│   │   ├── __init__.py
│   │   └── routes.py         # 上传、搜索、编辑、删除等接口
│   ├── agent/                # 智能助手蓝图
│   │   ├── __init__.py
│   │   └── routes.py         # 聊天页面与 API 接口
│   ├── services/             # 业务逻辑服务
│   │   ├── ai_service.py             # AI 标签生成服务
│   │   ├── agent_service.py          # LangGraph Agent 逻辑封装
│   │   ├── image_search_service.py   # 条件图片搜索服务
│   │   └── semantic_search_service.py # SigLIP + Milvus 语义搜图服务
│   ├── static/               # 静态资源
│   │   ├── css/custom.css
│   │   ├── js/main.js
│   │   └── uploads/
│   │       ├── originals/    # 原图
│   │       └── thumbnails/   # 缩略图
│   └── templates/            # 模板
│       ├── base.html
│       ├── index.html
│       ├── auth/login.html
│       ├── auth/register.html
│       ├── image/
│       │   ├── upload.html
│       │   ├── gallery.html
│       │   ├── detail.html
│       │   ├── confirm_tags.html
│       │   ├── search.html
│       │   └── search_results.html
│       └── agent/
│           └── chat.html     # 智能助手聊天界面
```

## 编译运行方式

### 环境依赖

- Python 3.12
- MySQL 8.0
- Milvus 2.x（语义搜图需要）

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 数据库配置

1. 安装并启动 MySQL 8.0。
2. 创建名为 `photomanager` 的数据库（字符集推荐 `utf8mb4`）。
3. 在项目根目录复制 `.env.example` 为 `.env`，并写入数据库密码：

```bash
cp .env.example .env
```

```env
DB_PASSWORD=your_mysql_password
```

### 3. AI 与地图服务配置（可选）

如需使用 AI 智能打标和地理位置解析功能，请在 `.env` 文件中添加以下配置：

```env
# 阿里云通义千问 API Key
API_KEY=sk-xxxxxxxxxxxxxxxx

# 高德地图 Web 服务 Key
AMAP_KEY=your_amap_key

# 语义搜图（可选）
MILVUS_HOST=127.0.0.1
MILVUS_PORT=19530
SIGLIP_MODEL_NAME=google/siglip-base-patch16-224
SIGLIP_DEVICE=auto
```

### 4. 启动应用

首次运行会自动创建数据库表结构。

```bash
python run.py
```

访问地址：[http://127.0.0.1:5000](http://127.0.0.1:5000)

### 本地运行 Flask + Docker 运行 Milvus

如果你习惯用 `python run.py` 启动 Flask，可以只用 Docker 启动 Milvus 依赖服务：

```bash
docker compose up -d etcd minio milvus
```

然后在 `.env` 中保持 Milvus 指向本机端口：

```env
MILVUS_HOST=127.0.0.1
MILVUS_PORT=19530
```

如果 MySQL 也用 Docker，则同时启动数据库：

```bash
docker compose up -d db etcd minio milvus
```

并把 `.env` 中数据库端口设为 Docker 暴露的 `3307`：

```env
DB_HOST=127.0.0.1
DB_PORT=3307
```

最后本地运行：

```bash
pip install -r requirements.txt
python run.py
```

## Docker 容器化部署

本项目支持使用 Docker Compose 进行一键部署，无需手动配置 Python 环境和 MySQL 数据库。

### 1. 准备工作

确保已安装 Docker Desktop 并启动。

### 2. 启动服务

在项目根目录运行：

```bash
docker-compose up -d --build
```

该命令会自动构建镜像并启动 Web 应用（端口 5000）、MySQL 数据库（端口 3307）以及 Milvus 语义检索服务（端口 19530）。

### 3. 初始化数据库

首次运行时，需要在容器内初始化数据库：

```bash
docker-compose exec web python init_db.py
```

访问地址：[http://localhost:5000](http://localhost:5000)

## 网站使用方法

### 1. 注册与登录
- 访问首页，点击“注册”创建账户。
- 密码需包含至少两类字符且长度大于 6 位。
- 注册后使用用户名或邮箱登录。

### 2. 图片上传
- 点击导航栏“上传图片”。
- 选择图片文件（支持 JPG, PNG, WebP 等）。
- 系统会自动解析 EXIF 信息（时间、地点）并生成缩略图。
- 若配置了 AI Key，系统会自动分析图片内容并生成智能标签，上传后可进行确认或删除。

### 3. 图片管理与编辑
- **图库浏览**：按上传时间倒序展示，支持点击“播放幻灯片”进行全屏轮播。
- **详情查看**：点击缩略图进入详情页，查看拍摄时间、地点、分辨率及所有标签。
- **图片编辑**：
  - **旋转**：支持 90°、180°、270° 旋转。
  - **裁剪**：拖动鼠标选择区域进行裁剪。
  - **缩放**：按比例或指定尺寸缩放图片。
  - **调色**：调整亮度、对比度和饱和度。
- **标签管理**：在详情页可手动添加或删除标签。

### 4. 搜索功能
- **普通搜索**：点击导航栏“搜索”，支持按标签、地点、时间范围组合查询。
- **智能助手 (Agent)**：点击首页或导航栏的“智能助手”，使用自然语言（如“帮我找找去年在杭州拍的照片”）进行交互式搜索。
- **语义搜图**：智能助手可调用 `semantic_image_search`，使用 SigLIP + Milvus 检索图片，并返回 `score` 大于最高分 1/5 的相似结果。图片上传后会进入后台队列自动生成 embedding。
