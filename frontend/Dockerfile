# frontend 镜像：多阶段构建（T-1.6 Vue3+Vite 真工程取代 T-0.4 静态占位）。
# 阶段一 node 构建：npm ci（锁文件）→ vite build 产 dist；
# 阶段二 nginx 托管静态产物 + 反代 backend（/api/ 规则在 nginx.conf，唯一对外入口）。
FROM node:20-alpine AS build

WORKDIR /app

# 先拷锁文件再 npm ci：package.json/package-lock.json 变更才触发依赖层重建
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
