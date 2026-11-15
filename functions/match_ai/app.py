import json
import os
import boto3

dynamodb = boto3.resource('dynamodb')
bedrock = boto3.client('bedrock-runtime')
table = dynamodb.Table(os.environ['TABLE_NAME'])
MODEL_ID = os.environ['BEDROCK_MODEL_ID']

def lambda_handler(event, context):
    notice_id = event['noticeId']
    seeker_id = event['seekerId']
    need_text = event['needText']
    age_min = int(event.get('preferredAgeMin', 18))
    age_max = int(event.get('preferredAgeMax', 99))

    items = table.scan().get('Items', [])
    candidates = [
        i for i in items
        if i.get('SK') == 'PROFILE'
        and i.get('verified') is True
        and i.get('userId') != seeker_id
        and age_min <= int(i.get('age', 0)) <= age_max
        and i.get('canHelpWith')
    ]

    if not candidates:
        return {"matchFound": False, "noticeId": notice_id}

    candidate_summary = "\n".join([
        f"- ID: {c['userId']} | Name: {c['name']} | Age: {c['age']} | Lived Experience: {c['canHelpWith']} | TrustScore: {c.get('trustScore', 50)}"
        for c in candidates
    ])

    prompt = f"""You are the LivedPath AI Peer Matching Engine.
A verified user needs help with: "{need_text}" (Preferred helper age: {age_min}-{age_max}).

Verified Peer Candidates:
{candidate_summary}

Select the single best candidate whose lived experience matches the user's need.
Return ONLY valid JSON with these exact keys:
{{"helperId": "...", "helperName": "...", "score": "95%", "reason": "2-sentence explanation of why their lived experience fits."}}"""

    response = bedrock.converse(
        modelId=MODEL_ID,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 300, "temperature": 0.2}
    )

    raw_text = response['output']['message']['content'][0]['text'].strip()
    if "```" in raw_text:
        raw_text = raw_text.split("```")[1].replace("json", "").strip()

    match_data = json.loads(raw_text)
    return {
        "matchFound": True,
        "noticeId": notice_id,
        "seekerId": seeker_id,
        "helperId": match_data['helperId'],
        "helperName": match_data['helperName'],
        "score": str(match_data.get('score', '92%')),
        "reason": match_data['reason']
    }
