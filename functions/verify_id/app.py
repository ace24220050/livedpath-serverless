import json
import os
import boto3

s3 = boto3.client('s3')
rekognition = boto3.client('rekognition')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['TABLE_NAME'])
BUCKET = os.environ['BUCKET_NAME']

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
    path = event.get('path', '')
    body = json.loads(event.get('body') or '{}')

    if path == '/upload-url':
        user_id = body['userId']
        id_key = f"kyc/{user_id}/gov_id.jpg"
        selfie_key = f"kyc/{user_id}/selfie.jpg"
        id_url = s3.generate_presigned_url('put_object', Params={'Bucket': BUCKET, 'Key': id_key, 'ContentType': 'image/jpeg'}, ExpiresIn=300)
        selfie_url = s3.generate_presigned_url('put_object', Params={'Bucket': BUCKET, 'Key': selfie_key, 'ContentType': 'image/jpeg'}, ExpiresIn=300)
        return resp(200, {"idUploadUrl": id_url, "selfieUploadUrl": selfie_url, "idKey": id_key, "selfieKey": selfie_key})

    if path == '/verify':
        user_id = body['userId']
        id_key = f"kyc/{user_id}/gov_id.jpg"
        selfie_key = f"kyc/{user_id}/selfie.jpg"

        try:
            face_res = rekognition.compare_faces(
                SourceImage={'S3Object': {'Bucket': BUCKET, 'Name': id_key}},
                TargetImage={'S3Object': {'Bucket': BUCKET, 'Name': selfie_key}},
                SimilarityThreshold=80
            )
            text_res = rekognition.detect_text(
                Image={'S3Object': {'Bucket': BUCKET, 'Name': id_key}}
            )
            face_matches = face_res.get('FaceMatches', [])
            detected_words = [t['DetectedText'] for t in text_res.get('TextDetections', []) if t['Type'] == 'LINE']

            # Zero-retention privacy: purge sensitive ID images from S3 immediately after check
            s3.delete_object(Bucket=BUCKET, Key=id_key)
            s3.delete_object(Bucket=BUCKET, Key=selfie_key)

            if len(face_matches) > 0 and len(detected_words) > 0:
                similarity = round(face_matches[0]['Similarity'], 2)
                table.update_item(
                    Key={"PK": f"USER#{user_id}", "SK": "PROFILE"},
                    UpdateExpression="SET verified = :v ADD trustScore :inc",
                    ExpressionAttributeValues={":v": True, ":inc": 50}
                )
                return resp(200, {
                    "verified": True,
                    "similarity": similarity,
                    "privacyNote": "Government ID & Selfie permanently purged from S3 after Rekognition check.",
                    "trustPointsAwarded": 50
                })
            else:
                return resp(400, {"verified": False, "reason": "Face mismatch or unreadable ID document. Raw images deleted for privacy."})

        except Exception as e:
            return resp(400, {"verified": False, "error": str(e)})

    return resp(400, {"error": "Invalid path"})
