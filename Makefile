# Variables
AWS_REGION ?= eu-west-1
ECR_REPO ?= bpma/xtract
LAMBDA_FUNCTION ?= bpma-extract
IMAGE_TAG ?= latest
ECR_URI = $(shell aws sts get-caller-identity --query Account --output text).dkr.ecr.$(AWS_REGION).amazonaws.com/$(ECR_REPO)

.PHONY: push-ssm build push-ecr update-lambda deploy clean-rebuild help

# Push environment variables to AWS SSM Parameter Store
push-ssm:
	PYTHONPATH=. uv run utils/push_ssm.py

# Run the main application
run:
	PYTHONPATH=. uv run src/run.py

# Run LLM evaluation
eval:
	PYTHONPATH=. uv run src/eval/run.py

# Build Docker image for AWS Lambda (Docker v2 schema manifest)
build: ecr-login
	docker buildx build \
		--platform linux/amd64 \
		--push \
		-t $(ECR_URI):$(IMAGE_TAG) \
		--provenance=false \
		--sbom=false \
		--output=type=registry,oci-mediatypes=false,compression=gzip \
		.

# Get ECR login token and login to ECR
ecr-login:
	aws ecr get-login-password --region $(AWS_REGION) | docker login --username AWS --password-stdin $(shell echo $(ECR_URI) | cut -d'/' -f1)

# Build and push image directly to ECR with proper manifest format
push-ecr: ecr-login
	docker push $(ECR_URI):$(IMAGE_TAG)

# Update Lambda function with new image
update-lambda:
	aws lambda update-function-code \
		--function-name $(LAMBDA_FUNCTION) \
		--image-uri $(ECR_URI):$(IMAGE_TAG)

# Full deployment: build, push to ECR, and update Lambda
deploy: build push-ecr update-lambda
	@echo "Deployment complete!"

# Show available commands
help:
	@echo "Available commands:"
	@echo "  run           Run the main application"
	@echo "  eval          Run LLM evaluation"
	@echo "  push-ssm      Push environment variables to AWS SSM Parameter Store"
	@echo "  build         Build Docker image locally"
	@echo "  ecr-login     Login to ECR"
	@echo "  push-ecr      Push Docker image to ECR"
	@echo "  update-lambda Update Lambda function with new image"
	@echo "  deploy        Full deployment (build + push + update)"
	@echo "  help          Show this help message"
	@echo ""
	@echo "Variables (can be overridden):"
	@echo "  AWS_REGION=$(AWS_REGION)"
	@echo "  ECR_REPO=$(ECR_REPO)"
	@echo "  LAMBDA_FUNCTION=$(LAMBDA_FUNCTION)"
	@echo "  IMAGE_TAG=$(IMAGE_TAG)"
	@echo "  ECR_URI=$(ECR_URI)"
