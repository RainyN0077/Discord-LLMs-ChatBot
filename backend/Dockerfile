# 从官方Python镜像开始（AstrBot 要求 >=3.12）
FROM python:3.12-slim

# 设置容器内的工作目录
WORKDIR /app

# 复制 requirements.txt 并安装依赖
# 这一步保持不变
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- 【【【核心修改区】】】 ---

# 复制 app 目录到容器的 /app/app 子目录
COPY ./backend/app ./app

# 复制 plugins 目录到容器的 /app/plugins 子目录
COPY ./backend/plugins ./plugins

# 复制 scripts 目录到容器的 /app/scripts 子目录
COPY ./scripts ./scripts

# 复制 astrbot_stars 目录到容器的 /app/astrbot_stars 子目录（AstrBot Star 插件）
COPY ./backend/astrbot_stars ./astrbot_stars

# 复制 providers 目录到容器的 /app/astrbot_stars/providers 子目录
# （astrbot_stars/providers 已经在上面包含了，不需要额外复制）

# --- 【【【修改结束】】】 ---

# 暴露端口，供外部访问
EXPOSE 8000

# 修改启动命令，以适应新的目录结构
# 我们现在从顶层启动，所以需要告诉 uvicorn 在 app 包里找 main 模块
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-use-colors"]
