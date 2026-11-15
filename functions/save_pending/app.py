import os
import boto3

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['TABLE_NAME'])

def lambda_handler(event, context):
    match = event['match']
    task_token = event['taskToken']

    table.put_item(Item={
        "PK": f"MATCH#{match['noticeId']}",
        "SK": "PENDING",
        "TaskToken": task_token,
        "SeekerId": match['seekerId'],
        "HelperId": match['helperId'],
        "HelperName": match['helperName'],
        "Reason": match['reason'],
        "CompatibilityScore": str(match['score'])
    })
    return {"status": "WAITING_FOR_HELPER"}
