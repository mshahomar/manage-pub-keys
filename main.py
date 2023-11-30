import boto3
import json
import os
from datetime import datetime, timedelta

region = "ap-southeast-1"
sess = boto3.session.Session(region_name=region)

# Boto3 clients
s3_client = sess.client('s3', verify=False)
ses_client = sess.client('ses', aws_access_key_id=os.environ['AWS_ACCESS_KEY'], aws_secret_access_key=os.environ['AWS_SECRET_KEY'])
transfer_client = sess.client('transfer', verify=False)

# Make necessary changes here
s3_key_threshold = 30
s3_folder = 'KEY/'
file_extension = '.pub'
transfer_key_threshold = 30
notification_threshold = 10
deletion_threshold = s3_key_threshold + notification_threshold + 10
sender_email = "system1@myemail.com"
recipient_email_1 = "user1@example.com"
tf_server_id = "s-xxxxxxxxxxx"

def send_email(subject, body, recipients):
    sender = sender_email  # Replace with your SES verified sender email address
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

def check_key_expiration(bucket, prefix, days_threshold, notification_threshold, deletion_threshold, recipient_emails):
    response = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)

    for obj in response.get('Contents', []):
        if obj['Key'] == prefix:
            continue

        if not obj['Key'].lower().endswith(file_extension):
            continue

        last_modified = obj['LastModified'].replace(tzinfo=None)
        age = datetime.now() - last_modified
        remaining_days = days_threshold - age.days

        if 0 < remaining_days <= notification_threshold:
            subject = f"Public key in {bucket}/{prefix} will expire in {remaining_days} days"
            body = f"The public key {obj['Key']} in {bucket}/{prefix} will expire in {remaining_days} days. Please update."
            send_email(subject, body, recipient_emails)

        if remaining_days <= 0:
            print(f"Key in {bucket}/{prefix} has expired: {obj['Key']}")
            # Add deletion logic here if needed
            if age.days > deletion_threshold:
                print(f"Deleting expired key: {obj['Key']}")
                # Delete the public key logic (replace with your actual deletion logic)

def check_transfer_user_keys(username, days_threshold, recipient_emails):
    response = transfer_client.list_ssh_public_keys(ServerId=tf_server_id)
    
    for key in response['SshPublicKeys']:
        uploaded_at = key['DateUploaded'].replace(tzinfo=None)
        age = datetime.now() - uploaded_at
        remaining_days = days_threshold - age.days

        if 0 < remaining_days <= notification_threshold:
            subject = f"Transfer user {username}'s key will expire in {remaining_days} days"
            body = f"The public key {key['SshPublicKeyId']} for Transfer user {username} will expire in {remaining_days} days. Please update."
            send_email(subject, body, recipient_emails)

        if remaining_days <= 0:
            print(f"Transfer user {username}'s key has expired: {key['SshPublicKeyId']}")
            # Add deletion logic here if needed
            if age.days > deletion_threshold:
                print(f"Deleting expired key: {key['SshPublicKeyId']}")
                # Delete the public key logic (replace with your actual deletion logic)

def check_transfer_pub_keys(username, days_threshold, recipient_emails):
    resp = transfer_client.describe_user(ServerId=tf_server_id, UserName=username)
    users = resp.get('User', [])
    
    date_imported = ''
    pub_key_body = []
    
    for keys in users['SshPublicKeys']:
        date_imported = keys['DateImported'].replace(tzinfo=None)
        pub_key_body.append(keys['SshPublicKeyBody'])
        
    age = datetime.now() - date_imported
    remaining_days = days_threshold - age.days
        
    print(f"There are {len(pub_key_body)} key(s) for user {username}")
    for key in pub_key_body:
        print(f"Public Keys: {key}. \nDate Imported: {date_imported}.")
        
        if 0 < remaining_days <= notification_threshold:
            print(f"This key will expire in {remaining_days} days")
            subject = f"Transfer user {username}'s key will expire in {remaining_days} days"
            body = f"The public key for Transfer user {username} will expire in {remaining_days} days. Please upload a new public key."
            send_email(subject, body, recipient_emails)

        if remaining_days <= 0:
            print(f"Transfer user {username}'s key has expired. Public Key: {key}")
            # Add deletion logic here if needed
            if age.days > deletion_threshold:
                print(f"Deleting expired key for user {username}")
                # Delete the public key logic (replace with your actual deletion logic)

def lambda_handler(event, context):
    # Check PubKeys in S3 Buckets
    buckets = [bucket['Name'] for bucket in s3_client.list_buckets()['Buckets']]

    # Check each S3 bucket for key expiration
    for bucket in buckets:
        print(f"Bucket: {bucket}")
        check_key_expiration(bucket, s3_folder, s3_key_threshold, notification_threshold, deletion_threshold, [recipient_email_1])

    # List all AWS Transfer Family users
    response = transfer_client.list_users(ServerId=tf_server_id)
    transfer_users = [user['UserName'] for user in response['Users']]

    # Check Transfer Family user keys for expiration
    for user in transfer_users:
        check_transfer_pub_keys(user, transfer_key_threshold, [recipient_email_1])

    return {
        'statusCode': 200,
        'body': json.dumps('DONE!')
    }

# For testing purposes
if __name__ == '__main__':
    sample_event = {
        'Records': [
            {
                's3': {
                    'bucket': {'name': 'your-s3-bucket'},
                    'object': {'key': 'KEY/your-file.pub'}
                }
            }
        ]
    }
    lambda_handler(sample_event, {})
