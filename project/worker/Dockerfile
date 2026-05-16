FROM rust:1.78-alpine AS builder
RUN apk add --no-cache musl-dev
WORKDIR /app

# Cache dependencies: build a stub binary first so cargo fetches crates
COPY Cargo.toml Cargo.lock ./
RUN mkdir -p src && echo "fn main() {}" > src/main.rs \
    && cargo build --release \
    && rm -rf src

# Build the real binary
COPY src ./src
RUN touch src/main.rs && cargo build --release

FROM alpine:3.19
RUN adduser -D -u 1000 worker
USER worker
COPY --from=builder /app/target/release/worker /worker
EXPOSE 8080
ENTRYPOINT ["/worker"]
