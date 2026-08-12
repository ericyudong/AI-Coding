FROM golang:1.22-alpine AS builder
WORKDIR /src
COPY go.mod ./
COPY main.go ./
RUN CGO_ENABLED=0 GOOS=linux go build -o /app/server main.go

FROM alpine:3.20
RUN adduser -D -u 1000 appuser
USER appuser
WORKDIR /home/appuser
COPY --from=builder /app/server /home/appuser/server
EXPOSE 8080
ENV PORT=8080
CMD ["/home/appuser/server"]
