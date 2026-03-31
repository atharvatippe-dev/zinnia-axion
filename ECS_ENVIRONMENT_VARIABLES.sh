#!/bin/bash
# ============================================================================
# ECS Environment Variables Configuration
# ============================================================================
# This file shows the exact environment variables needed for ECS deployment
# Copy these to your Terraform/CloudFormation/ECS task definition
# ============================================================================

# DATABASE CONNECTION (Critical for AWS ECS)
DATABASE_URI="postgresql://axion:axion%231234@lcdevpg.ckify2o8ll3o.us-east-1.rds.amazonaws.com:5432/lcdevpg"

# BACKEND CONFIGURATION
FLASK_HOST="0.0.0.0"
FLASK_PORT="5000"
DEMO_MODE="true"

# GUNICORN (Production WSGI server)
GUNICORN_WORKERS="4"

# TRACKER CONFIGURATION
POLL_INTERVAL_SEC="10"
BATCH_INTERVAL_SEC="60"
BUCKET_SIZE_SEC="60"
CONFIDENCE_THRESHOLD="0.60"

# REDIS CACHE (Local development - update for production Redis endpoint)
CACHE_ENABLED="true"
REDIS_URL="redis://localhost:6379/0"
REDIS_HOST="localhost"
REDIS_PORT="6379"
REDIS_DB="0"

# CACHE TTL (Time-To-Live) in seconds
CACHE_TTL_USER_DATA="300"      # 5 minutes
CACHE_TTL_TEAM_HIERARCHY="900"  # 15 minutes
CACHE_TTL_DASHBOARD="60"        # 1 minute

# DATABASE CONNECTION POOLING
DB_POOL_SIZE="10"
DB_POOL_RECYCLE="3600"
DB_POOL_PRE_PING="true"
DB_MAX_OVERFLOW="20"

# CLOUDWATCH METRICS
CLOUDWATCH_ENABLED="true"
AWS_REGION="us-east-1"
CLOUDWATCH_NAMESPACE="ZinniaAxion/Backend"
CLOUDWATCH_ENVIRONMENT="development"

# PRODUCTIVITY THRESHOLDS
PRODUCTIVE_INTERACTION_THRESHOLD="12"
PRODUCTIVE_KEYSTROKE_THRESHOLD="6"
PRODUCTIVE_MOUSE_THRESHOLD="6"
MOUSE_MOVEMENT_THRESHOLD="48"
IDLE_AWAY_THRESHOLD="30"
MOUSE_MOVEMENT_MIN_SAMPLES="3"
MIN_ZERO_SAMPLE_RATIO="0.25"
MIN_DISTINCT_VALUES="3"

# DECISION TREE V2 RULES
PRODUCTIVE_DOMINANT_RATIO="0.70"
NON_PROD_DOMINANT_RATIO="0.6667"
MEETING_DOMINANT_RATIO="0.50"
DISTRACTION_CONFIDENCE_MULT="0.70"
NON_PROD_MIX_WEIGHT="0.50"
ANTI_CHEAT_CONFIDENCE_MULT="0.30"
DISTRACTION_MIN_RATIO="0.3"

# APP CLASSIFICATION
MEETING_APPS="zoom,microsoft teams,google meet,webex,facetime,slack huddle,discord call,skype,around,tuple,gather"
BROWSER_APPS="safari,google chrome,chrome,firefox,microsoft edge,msedge,brave browser,brave,arc,chromium"
PRODUCTIVE_APPS="visual studio code,vscode,pycharm,intellij,android studio,xcode,sublime text,atom,vim,emacs,cursor,figma,sketch,adobe photoshop,adobe illustrator,blender,unity,unreal engine,docker,postman,tableau,excel,word,powerpoint,outlook,notion,obsidian,roam research,jira,confluence,linear,asana,trello,monday.com"
NON_PRODUCTIVE_APPS="youtube,netflix,reddit,twitter,x.com,instagram,facebook,tiktok,twitch,discord,spotify,steam,epic games,league of legends,fortnite,valorant,minecraft,roblox"

# WINDOW TITLE PRIVACY
WINDOW_TITLE_MODE="redacted"
DROP_TITLES="false"

# RATE LIMITING
MAX_REQUEST_SIZE_KB="512"
RATE_LIMIT_PER_DEVICE="120/minute"

# DATA RETENTION
DATA_RETENTION_DAYS="14"
TIMEZONE="Asia/Kolkata"

# ============================================================================
# HOW TO USE IN TERRAFORM:
# ============================================================================
# 
# In your Terraform file (e.g., main.tf):
# 
# resource "aws_ecs_task_definition" "fargate_task_definition" {
#   container_definitions = jsonencode([
#     {
#       name  = "zinnia-axion"
#       image = "YOUR_ECR_REPO:latest"
#       environment = [
#         { name = "DATABASE_URI", value = "postgresql://axion:axion%231234@lcdevpg.ckify2o8ll3o.us-east-1.rds.amazonaws.com:5432/lcdevpg" },
#         { name = "FLASK_HOST", value = "0.0.0.0" },
#         { name = "FLASK_PORT", value = "5000" },
#         { name = "DEMO_MODE", value = "true" },
#         { name = "GUNICORN_WORKERS", value = "4" },
#         ... (add all other variables here)
#       ]
#     }
#   ])
# }
# 
# ============================================================================
# IMPORTANT NOTES:
# ============================================================================
# 1. DATABASE_URI points to RDS (NOT localhost)
# 2. Schema is "axion" (defined in SQLAlchemy models)
# 3. Update REDIS_* for production Redis endpoint
# 4. Update AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY for CloudWatch
# 5. For production, use AWS Secrets Manager instead of env vars
# ============================================================================
