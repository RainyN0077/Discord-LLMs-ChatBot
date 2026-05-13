# Stage 1: Build the Svelte app
FROM node:20-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .
RUN npm run build

# Stage 2: Serve the app with Nginx
FROM nginx:stable-alpine

COPY --from=build /app/dist /usr/share/nginx/html

# --- 新增的关键行 ---
# 复制我们自定义的Nginx配置文件，覆盖掉默认的配置
COPY nginx/nginx.conf /etc/nginx/conf.d/default.conf
# ------------------

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
