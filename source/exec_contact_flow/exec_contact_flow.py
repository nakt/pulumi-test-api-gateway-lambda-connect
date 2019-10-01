import json
import boto3
import os

ec2 = boto3.client('ec2', region_name=boto3.session.Session().region_name)
connect = boto3.client('connect')

def lambda_handler(event, context):

    for record in event['Records']:
        payload    = record["body"]
        parameters = json.loads(payload)

    print(parameters)

    call(parameters['message_body'], parameters['destination_phone_number'])

def call(message, destination_phone_number):

    connect.start_outbound_voice_contact(
        DestinationPhoneNumber = destination_phone_number,
        SourcePhoneNumber      = os.environ['SOURCE_PHONE_NUMBER'],
        ContactFlowId          = os.environ['CONTACT_FLOW_ID'],
        InstanceId             = os.environ['INSTANCE_ID'],

        Attributes = {
            'message': message
        }
    )
