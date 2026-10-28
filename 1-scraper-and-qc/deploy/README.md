## Deploying price-scraper to AWS (weekly, Tuesdays)

This runs as a one-shot **ECS Fargate task** triggered by an **EventBridge
Scheduler** rule every Tuesday at 06:00 UTC — there is no always-on server.

### One-time AWS setup

1. **VPC**: any VPC with at least one subnet that has internet egress (via
   NAT or a public subnet + `AssignPublicIp: ENABLED`, used by `deploy.sh`)
   so the task can reach target sites, S3, and the OpenAI API.
2. **ECS cluster**: `aws ecs create-cluster --cluster-name price-scraper`
3. **IAM roles**:
   - `EXECUTION_ROLE_ARN` — standard `ecsTaskExecutionRole`
     (`AmazonECSTaskExecutionRolePolicy`), plus `secretsmanager:GetSecretValue`
     on the secret below.
   - `TASK_ROLE_ARN` — a role the running container assumes; grant it
     `s3:GetObject`/`s3:PutObject`/`s3:ListBucket` on the output bucket used
     by [s3.py](../s3.py). No static AWS keys are needed in the
     container — `boto3` picks up credentials from this role automatically.
   - `SCHEDULE_ROLE_ARN` — a role EventBridge Scheduler assumes to call
     `ecs:RunTask` with `iam:PassRole` on `EXECUTION_ROLE_ARN`/`TASK_ROLE_ARN`.
4. **Secrets Manager**: store the OpenAI key and QC model name used by
   [qc_agent.py](../qc_agent.py) as a single JSON secret. ECS reads individual
   keys out of it via the `secret-arn:key::` reference syntax in
   [task-definition.json](task-definition.json):
   ```sh
   aws secretsmanager create-secret --name price-scraper/app-config \
     --secret-string '{"OPENAI_API_KEY":"<key>","QC_MODEL":"gpt-5.4-mini"}'
   ```
5. **Session/cookie files**: [sessions/](../sessions) and [cookies/](../cookies)
   hold login state some scrapers need (see
   [generate_session.py](../generate_session.py)). They're baked into the
   image as-is via `COPY . .` in the [Dockerfile](../Dockerfile). If a site's
   session expires, regenerate it locally with `generate_session.py` and
   rebuild/redeploy — or move them to S3 and pull at container startup if
   they need to be refreshed independently of the image.

### Deploy / redeploy

```sh
export AWS_ACCOUNT_ID=...
export AWS_REGION=...
export ECS_CLUSTER=price-scraper
export SUBNET_IDS=subnet-aaa,subnet-bbb
export SECURITY_GROUP_ID=sg-...
export EXECUTION_ROLE_ARN=arn:aws:iam::...:role/ecsTaskExecutionRole
export TASK_ROLE_ARN=arn:aws:iam::...:role/price-scraper-task-role
export APP_CONFIG_SECRET_ARN=arn:aws:secretsmanager:...:secret:price-scraper/app-XXXXXX-...
export SCHEDULE_ROLE_ARN=arn:aws:iam::...:role/price-scraper-scheduler-role

./deploy/deploy.sh
```

Re-running `deploy.sh` rebuilds the image, pushes a new `:latest`, registers
a new task definition revision, and points the schedule at it.

### Logs

Each run's stdout/stderr lands in CloudWatch Logs under
`/ecs/price-scraper`. The run date is whatever `RUN_DATE` is set to, or
today (UTC) by default — see [entrypoint.sh](../entrypoint.sh).

### Manual / one-off run

```sh
aws ecs run-task \
  --cluster price-scraper \
  --launch-type FARGATE \
  --task-definition price-scraper \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-aaa],securityGroups=[sg-...],assignPublicIp=ENABLED}"
```
