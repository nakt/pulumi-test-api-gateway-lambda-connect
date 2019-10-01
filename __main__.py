import os
import json
import pulumi
import pulumi_aws as aws


config         = pulumi.Config("pulumi-test-api-gateway-lambda-connect")
current_region = aws.get_region()
caller_ident   = aws.get_caller_identity()

appconfig = {
    "lambda_file_exec_contact_flow": "source/exec_contact_flow.zip",
    "lambda_file_send_message_sqs" : "source/send_message_to_sqs.zip",
    "contact_flow_id"              : config.require("connectContactFlowId"),
    "instance_id"                  : config.require("connectInstanceId"),
    "source_phone_number"          : config.require("connectSourcePhoneNumber"),
}


def label(type = "id"):

    label_tags = {
        "Namespace"  : config.require("tagNamespace"),
        "Environment": config.require("tagEnvironment"),
        "Projectname": config.require("tagProjectName"),
    }

    if type == "tags":
        return label_tags
    elif type == "id":
        return "-".join(label_tags.values())

    return

## Lambda

iam_role = aws.iam.Role(
    resource_name = label("id") + "-lambda-role",
    description = "Role for lambda",
    assume_role_policy = json.dumps({
        "Version": "2012-10-17",
        "Statement": [
            {
                "Action": "sts:AssumeRole",
                "Principal": {
                    "Service" : "lambda.amazonaws.com"
                },
                "Effect": "Allow",
                "Sid": ""
            },
        ]
    }),
    tags = label("tags"),
)

iam_role_policy = aws.iam.Policy(
    resource_name = label("id") + "-lambda-policy",
    description = "Policy for lambda",
    policy = json.dumps({
        "Version": "2012-10-17",
        "Statement": [
            {
                "Action": [
                    "sqs:*"
                ],
                "Effect": "Allow",
                "Resource": "*"
            },
            {
                "Effect": "Allow",
                "Action": [
                    "sqs:ReceiveMessage",
                    "sqs:DeleteMessage",
                    "sqs:GetQueueAttributes",
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                "Resource": "*"
            },
            {
                "Sid": "VisualEditor0",
                "Effect": "Allow",
                "Action": [
                    "connect:StartOutboundVoiceContact",
                    "connect:StopContact"
                ],
                "Resource": "*"
            },
        ]
    }),
)

role_policy_attachment = aws.iam.RolePolicyAttachment(
    resource_name = label("id") + "-policy",
    policy_arn = iam_role_policy.arn,
    role =  iam_role.name,
)

iam_role_apigateway = aws.iam.Role(
    resource_name = label("id") + "-apigateway-role",
    description = "Role for API gateway",
    assume_role_policy = json.dumps({
        "Version": "2012-10-17",
        "Statement": [
            {
                "Action": "sts:AssumeRole",
                "Principal": {
                    "Service" : "apigateway.amazonaws.com"
                },
                "Effect": "Allow",
                "Sid": ""
            },
        ]
    }),
    tags = label("tags"),
)

role_policy_attachment = aws.iam.RolePolicyAttachment(
    resource_name = label("id") + "-apigateway-policy",
    policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs",
    role =  iam_role_apigateway.name,
)

# SQS

sqs_resource = aws.sqs.Queue(
    resource_name             = label("id") + "-connect-queue",
    delay_seconds             = 30,
    max_message_size          = 262144,
    message_retention_seconds = 86400,
    receive_wait_time_seconds = 10,
    tags                      = label("tags"),
)

sqs_resource_policy = aws.sqs.QueuePolicy(
    resource_name = label("id") + "-connect-queue-policy",
    queue_url     = sqs_resource.id,
    policy        = json.dumps({
        "Version": "2012-10-17",
        "Id": "ConnectQueue_Policy_UUID",
        "Statement": [{
            "Sid":"ConnectQueue_AllowAllAction",
            "Effect": "Allow",
            "Principal": {
                "AWS": [
                    caller_ident.account_id,
                ]
            },
            "Resource": "arn:aws:sqs:%s:%s:ConnectOutboundCallData" % (
                current_region.name,
                caller_ident.account_id,
            )
        }]
    })
)

# Lambda

lambda_exec_connect = aws.lambda_.Function(
    resource_name = "exec_connect_contact_flow",
    description   = "Lambda for execute Connect contact flow",
    code          = pulumi.AssetArchive({
        ".": pulumi.FileArchive("./source/exec_contact_flow")
    }),
    role          = iam_role.arn,
    runtime       = "python3.7",
    handler       = "exec_contact_flow.lambda_handler",
    tags          = label("tags"),
    environment   = {
        "variables": {
            "SOURCE_PHONE_NUMBER": appconfig["source_phone_number"],
            "CONTACT_FLOW_ID"    : appconfig["contact_flow_id"],
            "INSTANCE_ID"        : appconfig["instance_id"],
        }
    }
)

lambda_send_sqs = aws.lambda_.Function(
    resource_name = "send_message_to_sqs",
    description   = "Lambda for send message to SQS queue",
    code          = pulumi.AssetArchive({
        ".": pulumi.FileArchive("./source/send_message_to_sqs")
    }),
    role          = iam_role.arn,
    runtime       = "python3.7",
    handler       = "send_message_to_sqs.lambda_handler",
    tags          = label("tags"),
    environment   = {
        "variables": {
            "SQS_URL": sqs_resource.id,
        }
    }
)

# API Gateway

apigateway_account = aws.apigateway.Account(
    resource_name = label("id"),
    cloudwatch_role_arn = iam_role_apigateway.arn,
)

apigateway_rest_api = aws.apigateway.RestApi(
    resource_name = label("id"),
    description   = "API for AWS Connect outbound call test",
    endpoint_configuration = {
        "types" : "REGIONAL"
    },
)

apigateway_resource = aws.apigateway.Resource(
    resource_name = label("id"),
    rest_api      = apigateway_rest_api.id,
    parent_id     = apigateway_rest_api.root_resource_id,
    path_part     = "call",
)

apigateway_apikey = aws.apigateway.ApiKey(
    resource_name = label("id"),
    description = "pulumi-test",
    enabled = "true",
)

apigateway_method = aws.apigateway.Method(
    resource_name    = label("id"),
    rest_api         = apigateway_rest_api.id,
    resource_id      = apigateway_resource.id,
    http_method      = "POST",
    authorization    = "NONE",
    api_key_required = "TRUE",
)

apigateway_integration = aws.apigateway.Integration(
    resource_name           = label("id"),
    rest_api                = apigateway_rest_api.id,
    resource_id             = apigateway_resource.id,
    http_method             = apigateway_method.http_method,
    integration_http_method = "POST",
    type                    = "AWS_PROXY",
    uri                     = lambda_send_sqs.invoke_arn,
    passthrough_behavior    = "WHEN_NO_TEMPLATES"
)

apigateway_deployment = aws.apigateway.Deployment(
    resource_name = label("id"),
    rest_api      = apigateway_rest_api.id,
    stage_name    = "prd",
    opts = pulumi.ResourceOptions(
        depends_on = [
            apigateway_integration
        ]
    )
)

apigateway_method_response = aws.apigateway.MethodResponse(
    resource_name = label("id"),
    rest_api      = apigateway_rest_api.id,
    resource_id   = apigateway_resource.id,
    http_method   = apigateway_method.http_method,
    response_models = {
        "application/json": "Empty"
    },
    status_code   = "200",
)

aws_api_gateway_method_settings = aws.apigateway.MethodSettings(
    resource_name = label("id"),
    rest_api      = apigateway_rest_api.id,
    stage_name    = apigateway_deployment.stage_name,
    method_path   = "*/*",

    settings = {
        "metrics_enabled":        "TRUE",
        "data_trace_enabled":     "TRUE",
        "logging_level":          "INFO",
        "throttling_rate_limit":  "5",
        "throttling_burst_limit": "2",
    }
)

apigateway_usage_plan = aws.apigateway.UsagePlan(
    resource_name = label("id"),
    name = "API Gateway Usage Plan",
    api_stages = [
        {
            "api_id": apigateway_rest_api.id,
            "stage":  apigateway_deployment.stage_name,
        },
    ]
)

apigateway_usage_plan_key = aws.apigateway.UsagePlanKey(
    resource_name = label("id"),
    key_type      = "API_KEY",
    key_id        = apigateway_apikey.id,
    usage_plan_id = apigateway_usage_plan.id,
)

# Lambda event/trigger mapping

lambda_apigateway_permission = aws.lambda_.Permission(
    resource_name = label("id"),
    action        = "lambda:InvokeFunction",
    function      = lambda_send_sqs.name,
    statement_id  = "AllowExecutionFromApiGateway",
    principal     = "apigateway.amazonaws.com",
    source_arn    = apigateway_rest_api.execution_arn.apply(
        lambda execution_arn: execution_arn + "/*/*/*"
    ),
)

lambda_event_map_exec_connect = aws.lambda_.EventSourceMapping(
    resource_name    = label("id") + "-exec-connect",
    event_source_arn = sqs_resource.arn,
    function_name    = lambda_exec_connect.arn,
    enabled          = "true",
)

# Output

pulumi.export('api_base_url', apigateway_deployment.invoke_url)
