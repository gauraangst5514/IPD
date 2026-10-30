# Build the upstream source; public minio/minio images are no longer reliable.
# Upstream release: RELEASE.2025-10-15T17-29-55Z
# https://github.com/minio/minio/releases/tag/RELEASE.2025-10-15T17-29-55Z
FROM golang:1.24.8-bookworm AS build
ENV CGO_ENABLED=0 GOMAXPROCS=2 GOFLAGS="-p=2"
RUN go install -trimpath github.com/minio/minio@9e49d5e7a648f00e26f2246f4dc28e6b07f8c84a

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /go/bin/minio /usr/local/bin/minio
LABEL org.opencontainers.image.source="https://github.com/minio/minio" \
      org.opencontainers.image.revision="9e49d5e7a648f00e26f2246f4dc28e6b07f8c84a" \
      org.opencontainers.image.licenses="AGPL-3.0-or-later"
EXPOSE 9000 9001
VOLUME ["/data"]
ENTRYPOINT ["/usr/local/bin/minio"]
CMD ["server", "/data", "--console-address", ":9001"]
