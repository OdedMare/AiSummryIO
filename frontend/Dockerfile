# Frontend image.
#
# `next build` compiles the /api/* rewrite target into the build output, so
# BACKEND_URL is not honoured as a plain runtime variable: whatever value was
# present at build time is what `next start` proxies to. The image is built
# against a sentinel host instead, and docker-entrypoint.sh substitutes the
# real BACKEND_URL on every container start — one image runs against any
# backend, with no rebuild and no build args.

FROM node:20-alpine AS build
WORKDIR /app

# Deliberately unresolvable: if substitution ever fails, the request fails with
# a DNS error naming this host rather than silently proxying to the frontend
# container itself.
ARG BACKEND_SENTINEL=http://backend-url-placeholder.invalid

COPY package*.json ./
RUN npm ci
COPY . .
RUN BACKEND_URL=$BACKEND_SENTINEL npm run build
RUN npm prune --omit=dev

# Record which artifacts carry the sentinel and keep a pristine copy of each.
# The list is discovered rather than hard-coded, so a Next upgrade that moves
# the compiled rewrite fails this build instead of failing at runtime. The
# templates make the substitution idempotent: every start regenerates from
# them, so restarting with a changed BACKEND_URL takes effect.
RUN printf '%s' "$BACKEND_SENTINEL" > .backend-url-sentinel \
    && { grep -rl "$BACKEND_SENTINEL" .next > .backend-url-files || true; } \
    && if [ ! -s .backend-url-files ]; then \
         echo "no build artifact contains $BACKEND_SENTINEL — next.config.ts no longer bakes the rewrite, or Next changed where it writes it" >&2; \
         exit 1; \
       fi \
    && while IFS= read -r artifact; do cp "$artifact" "$artifact.template"; done < .backend-url-files

FROM node:20-alpine
WORKDIR /app
ENV NODE_ENV=production \
    PORT=3000

COPY --from=build /app ./

# The entrypoint rewrites the recorded artifacts in place, so they must stay
# writable for the arbitrary non-root UID OpenShift assigns. Group 0 with
# g=u covers both that and the fixed UID below, mirroring the backend image.
RUN chmod 755 docker-entrypoint.sh \
    && chgrp -R 0 .next .backend-url-files .backend-url-sentinel \
    && chmod -R g=u .next .backend-url-files .backend-url-sentinel

# The `node` user in node:20-alpine.
USER 1000

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD node -e "fetch('http://127.0.0.1:'+(process.env.PORT||3000)+'/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["npm", "start"]
