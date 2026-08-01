# Stage 1: 构建 Vue 应用（vue-tsc 类型检查 + vite build）
FROM node:20-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# Stage 2: 使用 Nginx 托管构建产物
FROM nginx:stable-alpine

COPY --from=build /app/dist /usr/share/nginx/html

# 复制自定义 Nginx 配置（SPA fallback + /api 反向代理）
COPY nginx/nginx.conf /etc/nginx/conf.d/default.conf

# 非 root 用户运行（nginx 以 app 用户启动，监听 8080 高位端口无需特权）
# pid 重定向到 /tmp：新版 nginx:stable-alpine 主配置 pid 指向 /run/nginx.pid，
# 非 root 用户无 /run 写权限，需改用可写路径（-g 覆盖会触发 duplicate 报错，故 sed 主配置）
RUN addgroup -S app && adduser -S app -G app \
    && sed -i 's|pid.*/run/nginx.pid;|pid /tmp/nginx.pid;|' /etc/nginx/nginx.conf \
    && chown -R app:app /usr/share/nginx/html /var/cache/nginx /var/log/nginx /etc/nginx/conf.d
USER app

EXPOSE 8080

# 健康检查使用 127.0.0.1 而非 localhost：自定义 default.conf 时镜像的 IPv6 监听
# 自动配置脚本不生效，nginx 仅监听 IPv4，而容器内 localhost 解析为 ::1，wget 会连接失败
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -qO- http://127.0.0.1:8080/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
