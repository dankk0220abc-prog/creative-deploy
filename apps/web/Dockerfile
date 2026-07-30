ARG NODE_IMAGE=node:24.17.0-alpine3.23@sha256:7c70d1235c0b4c2bc9eeed5393d19f1bbdde6885ba0d58ba62bb385d7b0f3ff1
ARG NGINX_IMAGE=nginxinc/nginx-unprivileged:1.28.1-alpine@sha256:4655ddff4704d6b6c85f5a5862b5d0840941fcc95a4f4668f04b1d6f85858e7c

FROM ${NODE_IMAGE} AS builder
ENV COREPACK_HOME=/corepack
RUN corepack enable \
    && corepack prepare pnpm@11.14.0 --activate
WORKDIR /build
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
RUN pnpm install --frozen-lockfile
COPY apps/web apps/web
ARG VITE_RUNTIME_PROFILE=artifact-smoke
ENV VITE_RUNTIME_PROFILE=${VITE_RUNTIME_PROFILE}
RUN pnpm --filter @creativedeploy/web build

FROM ${NGINX_IMAGE} AS runtime
COPY deploy/nginx.conf /etc/nginx/nginx.conf
COPY deploy/security-headers.conf /etc/nginx/security-headers.conf
COPY --from=builder /build/apps/web/dist /usr/share/nginx/html
USER 101:101
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=6 \
    CMD ["wget", "-qO-", "http://127.0.0.1:8080/health/live"]
