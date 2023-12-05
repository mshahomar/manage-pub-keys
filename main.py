import boto3
import json
import os
from datetime import datetime, timedelta

region = "us-west-1"
sess = boto3.session.Session(region_name=region)

# Boto3 clients
s3_client = sess.client('s3')
ses_client = sess.client('ses', aws_access_key_id=os.environ['SES_ACCESS_KEY'], aws_secret_access_key=os.environ['SES_SECRET_ACCESS_KEY'])
transfer_client = sess.client('transfer')

# Make necessary changes here
s3_key_threshold = 90
s3_folder = 'KEY/'
file_extension = '.pub'
transfer_key_threshold = 90
notification_threshold = 5
deletion_threshold = s3_key_threshold + 10
sender_email = os.environ['SES_SENDER_EMAIL']
recipient_email_1 = os.environ['SES_RECIPIENT_1']
recipient_email_2 = os.environ['SES_RECIPIENT_1']
tf_server_id = os.environ['TF_SERVER_ID']


# Send email using AWS SES
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


# def check_key_expiration(bucket, prefix, days_threshold, notification_threshold, deletion_threshold, recipient_emails):
#     # To handle difference between _ and - of TF username and S3 bucket
#     bucket_name = bucket.replace('_', '-')
#     response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)

#     for obj in response.get('Contents', []):
#         if obj['Key'] == prefix:
#             continue

#         if not obj['Key'].lower().endswith(file_extension):
#             continue

#         last_modified = obj['LastModified'].replace(tzinfo=None)
#         age = datetime.now() - last_modified
#         remaining_days = days_threshold - age.days

#         if 0 < remaining_days <= notification_threshold:
#             subject = f"Public key in {bucket_name}/{prefix} will expire in {remaining_days} days"
#             body = f"The public key {obj['Key']} in {bucket_name}/{prefix} will expire in {remaining_days} days. Please update."
#             print(f"Sending Email on expiration of public key {obj['Key']} in {bucket_name}/{prefix} which will expire in {remaining_days} days.")
#             # send_email(subject, body, recipient_emails)

#         if remaining_days <= 0:
#             print(f"Key in {bucket_name}/{prefix} has expired: {obj['Key']}")
#             # Add deletion logic here if needed
#             if age.days > deletion_threshold:
#                 print(f"Deleting expired key: {obj['Key']} as it has exceeded deletion threshold of: {deletion_threshold}")
#                 # TODO: Delete the public key logic 

                    
# def delete_key(username, key_id):
#     print(f"****DELETING {key_id}****")
#     #transfer_client.delete_ssh_public_key(ServerId=tf_server_id, UserName=username, SshPublicKeyId=key_id)

def check_transfer_pub_keys(username):
    resp = transfer_client.describe_user(ServerId=tf_server_id, UserName=username)
    users = resp.get('User', [])

    keys = []
    for key in users['SshPublicKeys']:
        date_imported = key['DateImported'].replace(tzinfo=None)
        age = (datetime.now() - date_imported).days
        keys.append((key['SshPublicKeyId'], key['SshPublicKeyBody'], age))

    for pub_key_id, pub_key_body, age in keys:
        if notification_threshold <= age < deletion_threshold:
            subject = f"Transfer user {username}'s key will expire in {deletion_threshold - age} days"
            body = f"The public key {pub_key_id} for Transfer user {username} will expire in {deletion_threshold - age} days. Please update."
            send_email(subject, body, [recipient_email_1, recipient_email_2])
        elif age >= deletion_threshold:
            transfer_client.delete_ssh_public_key(UserName=username, SshPublicKeyId=pub_key_id)

    # # Sort keys by age in descending order
    # keys.sort(key=lambda x: x[2], reverse=True)

    # for i, (pub_key_id, pub_key_body, age) in enumerate(keys):
    #     if i == 0:  # Skip the latest public key
    #         continue
    #     if notification_threshold <= age < deletion_threshold:
    #         subject = f"Transfer user {username}'s key will expire in {deletion_threshold - age} days"
    #         body = f"The public key {pub_key_id} for Transfer user {username} will expire in {deletion_threshold - age} days. Please update."
    #         print(f"Sending Email on expiration of public key {pub_key_id} for Transfer user {username} which will expire in {deletion_threshold - age} days.")
    #         #send_email(subject, body, [recipient_email_1, recipient_email_2])
    #     elif age >= deletion_threshold:
    #         print(f"Deleting expired key: {pub_key_id} as it has exceeded deletion threshold of: {deletion_threshold}")
    #         #transfer_client.delete_ssh_public_key(UserName=username, SshPublicKeyId=pub_key_id)


def lambda_handler(event, context):
    # List all AWS Transfer Family users
    response = transfer_client.list_users(ServerId=tf_server_id)
    transfer_users = [user['UserName'] for user in response['Users']]


    # Check Transfer Family user keys for expiration
    for user in transfer_users:
        print(f">>>> Checking Key Expiration in TF for user {user}")
        check_transfer_pub_keys(user)

    return {
        'statusCode': 200,
        'body': json.dumps('DONE!')
    }    
