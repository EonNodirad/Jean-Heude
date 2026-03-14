FROM node:20-slim AS builder

RUN corepack enable && corepack prepare pnpm@latest --activate

WORKDIR /app
COPY package.json pnpm-lock.yaml .npmrc ./
RUN pnpm install --frozen-lockfile

COPY . .

# L'URL est injectée via build arg — priorité max (écrase .env.production)
ARG PUBLIC_URL_SERVEUR_PYTHON=http://localhost:8000
RUN echo "PUBLIC_URL_SERVEUR_PYTHON=${PUBLIC_URL_SERVEUR_PYTHON}" > .env.local
RUN pnpm run build

FROM node:20-slim
RUN corepack enable && corepack prepare pnpm@latest --activate
COPY --from=builder /app/build ./build
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/node_modules ./node_modules

EXPOSE 3000
ENV NODE_ENV=production
CMD ["node", "build/index.js"]
