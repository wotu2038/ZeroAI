FROM node:18-alpine as builder

WORKDIR /app

# 复制package文件
COPY package*.json ./

# 安装依赖
RUN npm install

# 构建参数（必须在COPY之前声明，但ENV在COPY之后设置）
ARG VITE_API_BASE_URL=/api

# 复制源代码
COPY . .

# 设置环境变量（Vite在构建时会读取）
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

# 构建
RUN npm run build

# 生产环境使用nginx
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html

# 复制nginx配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

