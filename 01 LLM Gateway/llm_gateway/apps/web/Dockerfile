FROM node:22-alpine AS build
WORKDIR /workspace
COPY package.json pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
COPY packages/contracts/package.json packages/contracts/package.json
RUN corepack enable && pnpm install --filter @llm-gateway/web...
COPY apps/web apps/web
COPY packages/contracts packages/contracts
RUN pnpm --filter @llm-gateway/web build

FROM nginx:1.27-alpine
COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /workspace/apps/web/dist /usr/share/nginx/html
