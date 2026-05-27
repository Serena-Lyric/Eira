FROM node:20-alpine AS builder
WORKDIR /repo
RUN corepack enable
COPY pnpm-workspace.yaml package.json pnpm-lock.yaml ./
COPY packages ./packages
COPY apps/web-user ./apps/web-user
RUN pnpm install --frozen-lockfile
RUN pnpm --filter @eira/web-user build

FROM nginx:alpine AS runtime
COPY --from=builder /repo/apps/web-user/dist /usr/share/nginx/html
COPY deploy/nginx/spa.conf /etc/nginx/conf.d/default.conf
