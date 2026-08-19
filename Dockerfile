# One image for every node service in the stack; the command chooses the role.
FROM node:22-alpine@sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32

WORKDIR /srv

# Dependencies first, so a schema edit does not invalidate the install layer.
COPY package.json package-lock.json ./
COPY packages/schema/package.json packages/schema/
COPY packages/db/package.json packages/db/
RUN npm ci --omit=dev

# The YAML is read at runtime — it is the specification, not a build input.
COPY tsconfig.base.json tsconfig.json types.yaml Folder-layout.yaml ./
COPY packages ./packages

ENV NODE_ENV=production
ENTRYPOINT ["node", "--disable-warning=ExperimentalWarning", "--experimental-strip-types", "packages/db/src/cli.ts"]
CMD ["status"]
