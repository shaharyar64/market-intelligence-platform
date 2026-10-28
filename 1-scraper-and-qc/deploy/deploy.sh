#!/bin/sh
# One-time-ish deploy script: builds the image, pushes to ECR, registers the
# ECS task definition, and creates/updates a weekly EventBridge Scheduler
# rule that runs it every Tuesday.
#
# Required env vars before running:
#   AWS_ACCOUNT_ID            e.g. 123456789012
#   AWS_REGION                e.g. me-central-1
#   ECS_CLUSTER               name of an existing Fargate-enabled ECS cluster
#   SUBNET_IDS                comma-separated subnet IDs for the task ENI
#   SECURITY_GROUP_ID         security group ID for the task ENI
#   EXECUTION_ROLE_ARN        ECS task execution role (pull image, read secrets, write logs)
#   TASK_ROLE_ARN             ECS task role (needs S3 read/write on the output bucket)
#   APP_CONFIG_SECRET_ARN     Secrets Manager ARN of a JSON secret with keys
#                             OPENAI_API_KEY and QC_MODEL
#   SCHEDULE_ROLE_ARN         IAM role EventBridge Scheduler assumes to call ecs:RunTask
#
# Usage: ./deploy/deploy.sh

set -eu

: "${AWS_ACCOUNT_ID:?}" "${AWS_REGION:?}" "${ECS_CLUSTER:?}" "${SUBNET_IDS:?}" \
  "${SECURITY_GROUP_ID:?}" "${EXECUTION_ROLE_ARN:?}" "${TASK_ROLE_ARN:?}" \
  "${APP_CONFIG_SECRET_ARN:?}" "${SCHEDULE_ROLE_ARN:?}"

REPO_NAME="price-scraper"
IMAGE_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${REPO_NAME}:latest"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "[deploy] ensuring ECR repo exists"
aws ecr describe-repositories --repository-names "$REPO_NAME" --region "$AWS_REGION" >/dev/null 2>&1 \
  || aws ecr create-repository --repository-name "$REPO_NAME" --region "$AWS_REGION" >/dev/null

echo "[deploy] logging in to ECR"
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

echo "[deploy] building image"
docker build -t "$REPO_NAME" "$ROOT_DIR"
docker tag "$REPO_NAME:latest" "$IMAGE_URI"

echo "[deploy] pushing image"
docker push "$IMAGE_URI"

echo "[deploy] registering task definition"
TASK_DEF_FILE="$(mktemp)"
sed \
  -e "s#__IMAGE_URI__#${IMAGE_URI}#g" \
  -e "s#__EXECUTION_ROLE_ARN__#${EXECUTION_ROLE_ARN}#g" \
  -e "s#__TASK_ROLE_ARN__#${TASK_ROLE_ARN}#g" \
  -e "s#__AWS_REGION__#${AWS_REGION}#g" \
  -e "s#__APP_CONFIG_SECRET_ARN__#${APP_CONFIG_SECRET_ARN}#g" \
  "$SCRIPT_DIR/task-definition.json" > "$TASK_DEF_FILE"

aws ecs register-task-definition --cli-input-json "file://$TASK_DEF_FILE" --region "$AWS_REGION" >/dev/null
rm -f "$TASK_DEF_FILE"

TASK_DEF_ARN=$(aws ecs describe-task-definition --task-definition price-scraper \
  --region "$AWS_REGION" --query 'taskDefinition.taskDefinitionArn' --output text)
echo "[deploy] registered $TASK_DEF_ARN"

echo "[deploy] creating/updating weekly schedule (Tuesdays 06:00 UTC)"
SUBNETS_JSON=$(echo "$SUBNET_IDS" | awk -F',' '{printf "["; for(i=1;i<=NF;i++){printf "\"%s\"%s", $i, (i<NF?",":"")}; printf "]"}')

SCHEDULE_TARGET=$(cat <<JSON
{
  "Arn": "arn:aws:ecs:${AWS_REGION}:${AWS_ACCOUNT_ID}:cluster/${ECS_CLUSTER}",
  "RoleArn": "${SCHEDULE_ROLE_ARN}",
  "EcsParameters": {
    "TaskDefinitionArn": "${TASK_DEF_ARN}",
    "LaunchType": "FARGATE",
    "NetworkConfiguration": {
      "awsvpcConfiguration": {
        "Subnets": ${SUBNETS_JSON},
        "SecurityGroups": ["${SECURITY_GROUP_ID}"],
        "AssignPublicIp": "ENABLED"
      }
    }
  }
}
JSON
)

aws scheduler create-schedule \
  --name price-scraper-weekly \
  --schedule-expression "cron(0 6 ? * TUE *)" \
  --schedule-expression-timezone "UTC" \
  --flexible-time-window '{"Mode": "OFF"}' \
  --target "$SCHEDULE_TARGET" \
  --region "$AWS_REGION" \
  >/dev/null 2>&1 \
|| aws scheduler update-schedule \
  --name price-scraper-weekly \
  --schedule-expression "cron(0 6 ? * TUE *)" \
  --schedule-expression-timezone "UTC" \
  --flexible-time-window '{"Mode": "OFF"}' \
  --target "$SCHEDULE_TARGET" \
  --region "$AWS_REGION" \
  >/dev/null

echo "[deploy] done. Task runs every Tuesday 06:00 UTC on cluster $ECS_CLUSTER."
