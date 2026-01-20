# Docker Deployment Guide

This document explains how to build and run the EcoFlow Power Management Orchestrator using Docker.

## 🐳 Quick Start with Docker

### Prerequisites
- Docker installed and running
- A `.env` file configured (copy from `.env-example`)
- Access to a local MQTT broker (or configure to use a remote one)

### Option 1: Using Docker Compose (Recommended)

1. **Build and start the container:**
   ```bash
   docker-compose up -d
   ```

2. **View logs:**
   ```bash
   docker-compose logs -f
   ```

3. **Stop the container:**
   ```bash
   docker-compose down
   ```

### Option 2: Using Docker CLI

1. **Build the image:**
   ```bash
   docker build -t ecoflow-power-management:latest .
   ```

2. **Run the container:**
   ```bash
   docker run -d \
     --name ecoflow-orchestrator \
     --env-file .env \
     --restart unless-stopped \
     ecoflow-power-management:latest
   ```

3. **View logs:**
   ```bash
   docker logs -f ecoflow-orchestrator
   ```

4. **Stop and remove:**
   ```bash
   docker stop ecoflow-orchestrator
   docker rm ecoflow-orchestrator
   ```

## 📦 Using Pre-built Images from GitHub Container Registry

After the first successful CI/CD run, you can pull pre-built images:

```bash
# Pull the latest version
docker pull ghcr.io/joshuadodds/ecoflow-power-management:latest

# Or pull a specific version
docker pull ghcr.io/joshuadodds/ecoflow-power-management:2026.01.20.11

# Run the pre-built image
docker run -d \
  --name ecoflow-orchestrator \
  --env-file .env \
  --restart unless-stopped \
  ghcr.io/joshuadodds/ecoflow-power-management:latest
```

## 🔧 Configuration

The container expects environment variables to be provided via:
- An `.env` file (when using `--env-file` or docker-compose)
- Individual `-e` flags (e.g., `-e MQTT_HOST=mosquitto`)
- Docker secrets (for production deployments)

### Required Environment Variables

See `.env-example` for a complete list. Key variables include:

```bash
# EcoFlow Cloud Credentials
ECOFLOW_USERNAME=your-email@example.com
ECOFLOW_PASSWORD=your-password
ECOFLOW_ACCESS_KEY=AK_xxxxxxxxxxxx
ECOFLOW_SECRET_KEY=SK_xxxxxxxxxxxx

# Device Configuration
ECOFLOW_DEVICE_LIST=R631ZEB4WH123456

# MQTT Broker
MQTT_HOST=localhost  # Use 'host.docker.internal' on Mac/Windows to reach host
MQTT_PORT=1883

# Policy Settings
POLICY_SOC_MIN=10
POLICY_DEBOUNCE_SEC=180
```

## 🏥 Health Checks

The container includes a built-in health check that verifies the main process is running:

```bash
# Check container health status
docker inspect --format='{{.State.Health.Status}}' ecoflow-orchestrator
```

## 🔍 Troubleshooting

### Container exits immediately
Check logs for errors:
```bash
docker logs ecoflow-orchestrator
```

Common issues:
- Missing or invalid `.env` file
- Cannot connect to MQTT broker (check `MQTT_HOST`)
- Invalid EcoFlow credentials

### Cannot connect to MQTT broker on host machine

If your MQTT broker runs on the host machine:
- **Linux:** Use `--network host` or set `MQTT_HOST=172.17.0.1` (Docker bridge IP)
- **Mac/Windows:** Use `MQTT_HOST=host.docker.internal`

### View running processes inside container
```bash
docker exec ecoflow-orchestrator ps aux
```

## 🚀 GitHub Actions CI/CD

The repository includes automated builds via GitHub Actions (`.github/workflows/main.yml`):

- **Trigger:** Push to `main` branch or manual workflow dispatch
- **Platforms:** Multi-architecture builds for `linux/amd64` and `linux/arm64`
- **Registry:** Images pushed to GitHub Container Registry (ghcr.io)
- **Versioning:** CalVer format (YYYY.MM.DD.HH) + `latest` tag
- **Releases:** Automatic GitHub releases with generated notes

### Skipping CI Builds

Include `skip ci` in your commit message:
```bash
git commit -m "Update documentation [skip ci]"
```

## 📊 Monitoring

### View real-time logs
```bash
docker-compose logs -f ecoflow-orchestrator
```

### Check resource usage
```bash
docker stats ecoflow-orchestrator
```

## 🔄 Updating

### Using Docker Compose
```bash
docker-compose pull
docker-compose up -d
```

### Using Docker CLI
```bash
docker pull ghcr.io/joshuadodds/ecoflow-power-management:latest
docker stop ecoflow-orchestrator
docker rm ecoflow-orchestrator
docker run -d --name ecoflow-orchestrator --env-file .env --restart unless-stopped ghcr.io/joshuadodds/ecoflow-power-management:latest
```

## 🛡️ Security Notes

- The container runs as a non-root user (`ecoflow`, UID 1000)
- No privileged access required
- Environment variables should be protected (use Docker secrets in production)
- The `.env` file is excluded from the Docker image via `.dockerignore`
