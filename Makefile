# MCP Reliability Lab - Makefile for Easy Deployment

.PHONY: help build up down logs test deploy verify clean

# Default target
help:
	@echo "MCP Reliability Lab - Deployment Commands"
	@echo ""
	@echo "Development:"
	@echo "  make dev-up          Start development environment"
	@echo "  make dev-down        Stop development environment"
	@echo "  make dev-logs        View development logs"
	@echo ""
	@echo "Production:"
	@echo "  make prod-build      Build production images"
	@echo "  make prod-up         Start production environment"
	@echo "  make prod-down       Stop production environment"
	@echo "  make prod-logs       View production logs"
	@echo "  make prod-verify     Verify production readiness"
	@echo ""
	@echo "Deployment:"
	@echo "  make deploy-docker   Deploy with Docker Compose"
	@echo "  make deploy-k8s      Deploy to Kubernetes"
	@echo "  make rollback        Rollback last deployment"
	@echo ""
	@echo "Database:"
	@echo "  make db-migrate      Run database migrations"
	@echo "  make db-backup       Backup database"
	@echo "  make db-restore      Restore database from backup"
	@echo ""
	@echo "Testing:"
	@echo "  make test            Run all tests"
	@echo "  make test-backend    Run backend tests"
	@echo "  make test-frontend   Run frontend tests"
	@echo "  make test-e2e        Run end-to-end tests"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean           Clean up containers and volumes"
	@echo "  make ssl-generate    Generate SSL certificates"
	@echo "  make monitoring      Open monitoring dashboards"

# Development commands
dev-up:
	docker-compose up -d

dev-down:
	docker-compose down

dev-logs:
	docker-compose logs -f

# Production commands
prod-build:
	docker-compose -f docker-compose.production.yml build

prod-up:
	docker-compose -f docker-compose.production.yml up -d

prod-down:
	docker-compose -f docker-compose.production.yml down

prod-logs:
	docker-compose -f docker-compose.production.yml logs -f

prod-verify:
	python scripts/verify_production.py

# Deployment commands
deploy-docker: prod-verify
	@echo "Deploying with Docker Compose..."
	docker-compose -f docker-compose.production.yml build
	docker-compose -f docker-compose.production.yml run --rm backend alembic upgrade head
	docker-compose -f docker-compose.production.yml up -d
	@echo "Deployment complete! Check status with: make prod-logs"

deploy-k8s: prod-verify
	@echo "Deploying to Kubernetes..."
	kubectl apply -f k8s/production/namespace.yaml
	kubectl apply -f k8s/production/secrets.yaml
	kubectl apply -f k8s/production/configmap.yaml
	kubectl apply -f k8s/production/
	@echo "Deployment complete! Check status with: kubectl get pods -n mcp-reliability"

rollback:
	@echo "Rolling back deployment..."
	kubectl rollout undo deployment/backend-deployment -n mcp-reliability
	kubectl rollout undo deployment/frontend-deployment -n mcp-reliability
	@echo "Rollback complete!"

# Database commands
db-migrate:
	docker-compose -f docker-compose.production.yml run --rm backend alembic upgrade head

db-backup:
	@mkdir -p backups
	docker-compose -f docker-compose.production.yml exec -T postgres pg_dump -U mcp_user mcp_reliability | gzip > backups/mcp_backup_$(shell date +%Y%m%d_%H%M%S).sql.gz
	@echo "Database backed up to backups/mcp_backup_$(shell date +%Y%m%d_%H%M%S).sql.gz"

db-restore:
	@echo "Available backups:"
	@ls -la backups/*.sql.gz
	@echo ""
	@echo "To restore, run: gunzip < backups/[filename].sql.gz | docker-compose -f docker-compose.production.yml exec -T postgres psql -U mcp_user mcp_reliability"

# Testing commands
test:
	@echo "Running all tests..."
	make test-backend
	make test-frontend
	make test-e2e

test-backend:
	cd web/backend && python -m pytest tests/ -v --cov=app

test-frontend:
	cd web/frontend && npm test -- --coverage --watchAll=false

test-e2e:
	python tests/integration/test_e2e_complete_flow.py

# Utility commands
clean:
	docker-compose down -v
	docker-compose -f docker-compose.production.yml down -v
	docker system prune -f

ssl-generate:
	@echo "Generating SSL certificates with Let's Encrypt..."
	sudo certbot certonly --standalone -d mcp-reliability.com -d api.mcp-reliability.com
	mkdir -p ssl
	sudo cp /etc/letsencrypt/live/mcp-reliability.com/fullchain.pem ssl/cert.pem
	sudo cp /etc/letsencrypt/live/mcp-reliability.com/privkey.pem ssl/key.pem
	sudo chown $(USER):$(USER) ssl/*
	@echo "SSL certificates generated in ssl/"

monitoring:
	@echo "Opening monitoring dashboards..."
	@echo "Grafana: http://localhost:3001 (admin/admin)"
	@echo "Prometheus: http://localhost:9090"
	@open http://localhost:3001 || xdg-open http://localhost:3001 || echo "Please open http://localhost:3001 in your browser"

# Installation targets
install-deps:
	@echo "Installing dependencies..."
	cd web/backend && pip install -r requirements.txt
	cd web/frontend && npm install
	npm install -g @modelcontextprotocol/server-filesystem @modelcontextprotocol/server-github

# Quick start for new developers
quickstart: install-deps dev-up
	@echo "Development environment is ready!"
	@echo "Backend API: http://localhost:8000"
	@echo "Frontend: http://localhost:3000"
	@echo "API Docs: http://localhost:8000/docs"

# Production deployment from scratch
full-deploy: prod-verify ssl-generate deploy-docker
	@echo "Full production deployment complete!"
	@echo "Application: https://mcp-reliability.com"
	@echo "API: https://api.mcp-reliability.com"