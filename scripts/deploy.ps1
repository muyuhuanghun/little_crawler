Param(
  [ValidateSet("up", "down", "logs", "ps")]
  [string]$Action = "up"
)

$composeFile = "deploy/docker-compose.prod.yml"

if (!(Test-Path ".env.production")) {
  Copy-Item ".env.production.example" ".env.production"
  Write-Host "Created .env.production from .env.production.example. Please update secrets before production use."
}

switch ($Action) {
  "up" {
    docker compose --env-file .env.production -f $composeFile up -d --build
  }
  "down" {
    docker compose --env-file .env.production -f $composeFile down
  }
  "logs" {
    docker compose --env-file .env.production -f $composeFile logs -f app celery-worker celery-beat
  }
  "ps" {
    docker compose --env-file .env.production -f $composeFile ps
  }
}
