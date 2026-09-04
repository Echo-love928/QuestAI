# AI闯关学习 MVP

AI闯关学习把用户输入的一段知识转成互动题目，支持逐题反馈、通关结算和 AI 复盘报告。

当前 MVP 范围：

- 文本输入
- DeepSeek 自动生成 3～5 道单选、多选和判断题
- 即时判题与知识讲解
- XP、进度地图和通关结算
- 基于真实作答记录生成复盘报告
- 微信静默登录、个人资料与头像
- MySQL 闯关历史、答案与报告持久化
- URL、文件、PDF 和视频入口保留 UI，暂不接入解析

## 项目结构

```text
backend/      FastAPI + Pydantic + LangChain DeepSeek
frontend/     Taro 4 + React 18 + TypeScript 微信小程序
docs/         需求、方案与 UI 设计文档
prototype/    已确认的 HTML 原型和预览图
```

## 1. 启动后端

Windows PowerShell：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

编辑 `backend/.env`，填写：

```dotenv
DEEPSEEK_API_KEY=你的密钥
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_BASE_URL=https://api.deepseek.com
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=你的数据库用户
MYSQL_PASSWORD=你的数据库密码
MYSQL_DATABASE=AI-learn
WECHAT_APP_ID=你的小程序AppID
WECHAT_APP_SECRET=你的小程序AppSecret
JWT_SECRET=至少32字符的随机密钥
```

首次安装数据库：

```powershell
mysql -u root -p < backend/sql/init_mysql.sql
```

已有数据库按顺序执行 `backend/sql/migrations/` 中尚未执行的迁移。

启动 API：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

接口文档：<http://127.0.0.1:8000/docs>

## 2. 运行后端测试

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest --cov=app --cov-report=term-missing
```

自动测试使用模型替身，不会消耗 DeepSeek Token。

MySQL 集成测试使用独立的 `AI-learn-test` 数据库。先执行
`backend/sql/init_test_mysql.sql`，再参考 `backend/.env.test.example` 设置测试环境变量后运行测试。

手动验证真实 DeepSeek 出题和报告链路：

```powershell
.\.venv\Scripts\python.exe scripts\check_live.py
```

脚本只输出题目数量、正确率和总结行数，不输出密钥或完整题目。

## 3. 构建微信小程序

```powershell
cd frontend
npm install
npm run typecheck
npm run build:weapp
```

使用微信开发者工具导入 `frontend` 目录。项目已配置：

- 小程序产物目录：`frontend/dist`
- 小程序 AppID：在 `frontend/project.config.json` 配置
- 本地 API：`http://127.0.0.1:8000/api/v1`

本地开发者工具已关闭 URL 合法域名校验。真机或上线前必须：

1. 部署后端到 HTTPS 域名。
2. 在微信公众平台配置 request 和 uploadFile 合法域名。
3. 构建时设置生产 API 地址：

```powershell
$env:TARO_APP_API_BASE="https://你的域名/api/v1"
npm run build:weapp
```

## API

### 健康检查

```text
GET /api/v1/health
```

### 生成题目

```text
POST /api/v1/quiz/generate
```

```json
{
  "user_input": "我想学习 RAG 的基本概念和应用场景",
  "question_count": 5,
  "difficulty": "mixed"
}
```

### 生成报告

```text
POST /api/v1/report/generate
```

请求包含题库与每道题的 `selected_answers`、`duration_ms`。正确率、XP 和知识点分类由后端代码计算，DeepSeek 只生成总结与建议。

### 用户系统

```text
POST /api/v1/user/login
GET  /api/v1/user/profile
PUT  /api/v1/user/profile
POST /api/v1/user/avatar
GET  /api/v1/user/quizzes
GET  /api/v1/user/quizzes/{quiz_id}
```

除登录外，用户接口使用 `Authorization: Bearer <token>`。出题和报告接口保持匿名可用；携带有效 Token 时自动保存到用户历史。

## 安全说明

- `backend/.env` 已被 Git 忽略。
- 前端不包含 DeepSeek 密钥，所有模型调用只通过 FastAPI 后端进行。
- 微信 AppSecret、session_key 和 JWT 密钥只保存在后端，JWT 不包含 openid。
- 登录接口带频率限制；Token 失效时前端只自动重新登录并重试一次。
- 本地头像目录适用于 MVP，正式部署应替换为 OSS/COS 等对象存储。
- 自动测试不会连接真实模型。
- 当前 MVP 未接入微信内容安全接口；正式发布前应结合真实 AppID 接入微信内容安全能力。
