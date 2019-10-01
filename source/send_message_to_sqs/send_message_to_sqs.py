import boto3
import json
import os

def lambda_handler(event, context):

    payload = json.loads(event.get('body'))

    data = {
        "destination_phone_number" : payload.get("destination_phone_number"),
        "message_body"             : payload.get("message_body"),
    }

    print(data)

    send_sqs(data)

    return {
        'statusCode': 200,
        'body': json.dumps('Done!')
    }

def send_sqs(data):

    SQS_URL = os.environ['SQS_URL']

    sqs = boto3.client('sqs')

    result = sqs.send_message(
        QueueUrl     = SQS_URL,
        DelaySeconds = 0,
        MessageBody  = (
            json.dumps(data)
        )
    )

