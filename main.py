import boto3
import json
import os
from botocore.exceptions import BotoCoreError, ClientError
from datetime import datetime, timedelta

region = "ap-southeast-1"
sess = boto3.session.Session(region_name=region)

# Boto3 clients
s3_client = sess.client('s3')
ses_client = sess.client('ses', aws_access_key_id=os.environ['SES_ACCESS_KEY'], aws_secret_access_key=os.environ['SES_SECRET_ACCESS_KEY'])
transfer_client = sess.client('transfer')

# Make necessary changes here
notification_threshold = 85 # 85
deletion_threshold = 100    # 100
sender_email = os.environ['SES_SENDER_EMAIL']
recipient_email_1 = os.environ['SES_RECIPIENT_1']
recipient_email_2 = os.environ['SES_RECIPIENT_1']
tf_server_id = os.environ['TF_SERVER_ID']


# Send email using AWS SES
def send_email(subject, body, recipients):
    sender = sender_email 
    charset = 'UTF-8'

    response = ses_client.send_email(
        Source=sender_email,
        Destination={
            'ToAddresses': recipients,
        },
        Message={
            'Body': {
                'Text': {
                    'Charset': charset,
                    'Data': body,
                },
            },
            'Subject': {
                'Charset': charset,
                'Data': subject,
            },
        }
    )

    print(f"Email sent to {', '.join(recipients)}. Message ID: {response['MessageId']}")


def get_s3_pub_keys(s3_bucket_name):
    response = s3_client.list_objects_v2(Bucket=s3_bucket_name, Prefix='KEY/')
    pub_keys = []
    for obj in response.get('Contents', []):
        if obj['Key'].endswith('.pub'):
            pub_key_response = s3_client.get_object(Bucket=s3_bucket_name, Key=obj['Key'])
            pub_key_body = pub_key_response['Body'].read().decode('utf-8')
            last_modified = pub_key_response['LastModified']
            pub_keys.append((pub_key_body, last_modified))
    return pub_keys 


def check_transfer_pub_keys(username):
    resp = transfer_client.describe_user(ServerId=tf_server_id, UserName=username)
    users = resp.get('User', [])

    keys = []
    
    print(f"Checking {username}'s public key in Transfer Family:")

    if len(users['SshPublicKeys']) < 1:
        print(f"No public key found in Transfer Family for user {username}")
    else:
        print(f"{len(users['SshPublicKeys'])} public key(s) found in Transfer Family for user {username}")
        for key in users['SshPublicKeys']:
            date_imported = key['DateImported'].replace(tzinfo=None)
            age = (datetime.now() - date_imported).days
            keys.append((key['SshPublicKeyId'], key['SshPublicKeyBody'], age))
            
        for pub_key_id, pub_key_body, age in keys:
            print(f"PubKeyId: {pub_key_id} \nPubKeyBody: {pub_key_body} \nAge: {age}")
            print("-" * 40)
            if notification_threshold <= age < deletion_threshold:
                subject = f"Transfer Family user {username}'s key will expire in {deletion_threshold - age} days"
                body = f"Public key {pub_key_id} for Transfer Family user {username}: \n{pub_key_body} \nwill expire in {deletion_threshold - age} days. Please update."
                print(f"Sending email to notify that {pub_key_id} with public key body: \n{pub_key_body} \nfor Transfer Family user {username} will expire in {deletion_threshold - age} days.")
                send_email(subject, body, [recipient_email_1, recipient_email_2])
            elif age >= deletion_threshold:
                print(f"Deleting expired key: {pub_key_id} as it has exceeded deletion threshold of: {deletion_threshold}")
                transfer_client.delete_ssh_public_key(UserName=username, SshPublicKeyId=pub_key_id)

    
    # Extract the user's S3 bucket name
    s3_bucket_name = users['HomeDirectoryMappings'][0]['Target'].split('/')[1]
    print(f"Checking {username}'s public key in S3 bucket {s3_bucket_name}:")
    
    s3_pub_keys = get_s3_pub_keys(s3_bucket_name)
    if not s3_pub_keys:
        print(f"No public key found on {s3_bucket_name} bucket for user {username}")
        return
    
    for s3_pub_key_body, s3_last_modified in s3_pub_keys:
        s3_key_age = (datetime.now() - s3_last_modified.replace(tzinfo=None)).days
        for pub_key_id, pub_key_body, age in keys:
            if s3_pub_key_body == pub_key_body:
                print(f"Public key in S3 bucket: {s3_pub_key_body} \nPublic key in Transfer Family: {pub_key_body} \nBoth keys are similar for user {username}. This key will not be imported.")
            elif s3_pub_key_body != pub_key_body and s3_key_age < notification_threshold:
                print(f"Public key in S3 bucket: {s3_pub_key_body} \nPublic key in Transfer Family: {pub_key_body} \nBoth keys are different for user {username}. This key will be imported.")
                try:
                    transfer_client.import_ssh_public_key(UserName=username, SshPublicKeyBody=s3_pub_key_body, ServerId=tf_server_id)
                    print(f"Imported public key to Transfer Family user: {username}")
                except (BotoCoreError, ClientError) as error:
                    if error.response['Error']['Code'] == 'ResourceExistsException':
                        print(f"Public key already exists for user {username}.")
                    else:
                        raise


def lambda_handler(event, context):
    # List all AWS Transfer Family users
    response = transfer_client.list_users(ServerId=tf_server_id)
    transfer_users = [user['UserName'] for user in response['Users']]

    # Check Transfer Family user keys for expiration
    for user in transfer_users:
        title = f"Checking SSH Public Keys for TF user {user}"
        print("*" * (len(title) + 6))
        print(f"{'*' * 2} {title} {'*' * 2}")
        print("*" * (len(title) + 6))
        check_transfer_pub_keys(user)

    return {
        'statusCode': 200,
        'body': json.dumps('DONE!')
    }       
