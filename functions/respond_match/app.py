import json
import os
import boto3

dynamodb = boto3.resource('dynamodb')
sfn = boto3.client('stepfunctions')
table = dynamodb.Table(os.environ['TABLE_NAME'])

def resp(code, body):
    return {
        "statusCode": code,
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS"
        },
        "body": json.dumps(body)
    }

def lambda_handler(event, context):
    body = json.loads(event.get('body') or '{}')
    notice_id = body['noticeId']

    pending_item = table.get_item(Key={"PK": f"MATCH#{notice_id}", "SK": "PENDING"}).get('Item')
    if not pending_item:
        return resp(404, {"error": "Pending match not found or already accepted"})

    task_token = pending_item['TaskToken']
    helper_id = pending_item['HelperId']
    seeker_id = pending_item['SeekerId']

    # Resume paused Step Functions execution (triggers DynamoDB +25 TrustScore update)
    sfn.send_task_success(
        taskToken=task_token,
        output=json.dumps({"accepted": True, "helperId": helper_id})
    )

    helper_profile = table.get_item(Key={"PK": f"USER#{helper_id}", "SK": "PROFILE"}).get('Item', {})
    seeker_profile = table.get_item(Key={"PK": f"USER#{seeker_id}", "SK": "PROFILE"}).get('Item', {})

    table.delete_item(Key={"PK": f"MATCH#{notice_id}", "SK": "PENDING"})
    table.put_item(Item={
        "PK": f"MATCH#{notice_id}",
        "SK": "ACCEPTED",
        "noticeId": notice_id,
        "seekerName": seeker_profile.get('name', seeker_id),
        "seekerContact": seeker_profile.get('contact', ''),
        "helperName": helper_profile.get('name', helper_id),
        "helperContact": helper_profile.get('contact', ''),
        "reason": pending_item.get('Reason', ''),
        "score": pending_item.get('CompatibilityScore', '95%')
    })

    return resp(200, {
        "message": "Match accepted! Contact details unlocked and +25 Trust Points awarded.",
        "helperContact": helper_profile.get('contact'),
        "seekerContact": seeker_profile.get('contact')
    })
