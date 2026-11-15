import json
import os
import uuid
import boto3
from decimal import Decimal

dynamodb = boto3.resource('dynamodb')
sfn = boto3.client('stepfunctions')
table = dynamodb.Table(os.environ['TABLE_NAME'])
STATE_MACHINE_ARN = os.environ['STATE_MACHINE_ARN']

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super().default(obj)

def resp(code, body):
    return {
        "statusCode": code,
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS"
        },
        "body": json.dumps(body, cls=DecimalEncoder)
    }

def lambda_handler(event, context):
    path = event.get('path', '')
    method = event.get('httpMethod', '')

    if method == 'GET' and path == '/users':
        items = table.scan().get('Items', [])
        profiles = [i for i in items if i.get('SK') == 'PROFILE']
        pending = [i for i in items if i.get('SK') == 'PENDING']
        completed = [i for i in items if i.get('SK') == 'ACCEPTED']
        return resp(200, {"profiles": profiles, "pendingMatches": pending, "acceptedMatches": completed})

    body = json.loads(event.get('body') or '{}')

    if method == 'POST' and path == '/profile':
        user_id = body.get('userId') or str(uuid.uuid4())[:8]
        item = {
            "PK": f"USER#{user_id}",
            "SK": "PROFILE",
            "userId": user_id,
            "name": body.get('name', 'Anonymous'),
            "age": int(body.get('age', 30)),
            "preferredAgeMin": int(body.get('preferredAgeMin', 25)),
            "preferredAgeMax": int(body.get('preferredAgeMax', 55)),
            "canHelpWith": body.get('canHelpWith', ''),
            "needHelpWith": body.get('needHelpWith', ''),
            "contact": body.get('contact', 'protected@livedpath.io'),
            "verified": bool(body.get('verified', False)),
            "trustScore": int(body.get('trustScore', 10))
        }
        table.put_item(Item=item)
        return resp(200, {"message": "Profile saved", "profile": item})

    if method == 'POST' and path == '/notice':
        notice_id = str(uuid.uuid4())[:8]
        seeker_id = body['seekerId']
        need_text = body['needText']
        age_min = int(body.get('preferredAgeMin', 18))
        age_max = int(body.get('preferredAgeMax', 99))

        table.put_item(Item={
            "PK": f"NOTICE#{notice_id}",
            "SK": "META",
            "noticeId": notice_id,
            "seekerId": seeker_id,
            "needText": need_text,
            "preferredAgeMin": age_min,
            "preferredAgeMax": age_max
        })

        execution = sfn.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            name=f"match-{notice_id}",
            input=json.dumps({
                "noticeId": notice_id,
                "seekerId": seeker_id,
                "needText": need_text,
                "preferredAgeMin": age_min,
                "preferredAgeMax": age_max
            })
        )
        return resp(200, {
            "message": "Notice posted & Step Functions AI workflow triggered",
            "noticeId": notice_id,
            "executionArn": execution['executionArn']
        })

    return resp(400, {"error": "Unsupported route"})
