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


# def import_ssh_public_key(user_name):
#     bucket_name = user_name.replace('_', '-')
#     s3_folder = 'KEY'
#     key_prefix = f'{s3_folder}/'

#     # Initialize S3 client
#     s3_client = boto3.client('s3')

#     # Get the list of objects in the S3 bucket's KEY folder
#     response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=key_prefix)

#     if 'Contents' in response:
#         # Sort the objects based on the LastModified timestamp
#         objects = sorted(response['Contents'], key=lambda x: x['LastModified'], reverse=True)

#         if objects:
#             # Check if the most recent object is a .pub file
#             if objects[0]['Key'].endswith('.pub'):
#                 # Import a new SSH public key
#                 new_key_content = s3_client.get_object(Bucket=bucket_name, Key=objects[0]['Key'])['Body'].read().decode('utf-8')
#                 import_ssh_key_response = boto3.client('transfer').import_ssh_public_key(
#                     ServerId=user_name,
#                     SshPublicKeyBody=new_key_content,
#                     UserName=user_name
#                 )
#                 print(f"Imported new SSH public key for user {user_name}. Key ID: {import_ssh_key_response['SshPublicKeyId']}")
#             else:
#                 print(f"Skipping non-.pub file found for user {user_name}")

#         if len(objects) >= 2:
#             # Delete the SSH public key that has exceeded 90 days
#             if (datetime.now() - objects[1]['LastModified'].replace(tzinfo=None)) > timedelta(days=90):
#                 ssh_key_id = objects[1]['Key'].split('_')[-1]
#                 delete_ssh_public_key(ssh_key_id)

#     else:
#         # Import a new SSH public key if no key is found
#         print(f"No existing SSH public key found for user {user_name}. Importing a new key.")
#         new_key_content = s3_client.get_object(Bucket=bucket_name, Key=f'{s3_folder}/{user_name}_new_ssh_public_key.pub')['Body'].read().decode('utf-8')
#         import_ssh_key_response = boto3.client('transfer').import_ssh_public_key(
#             ServerId=user_name,
#             SshPublicKeyBody=new_key_content,
#             UserName=user_name
#         )
#         print(f"Imported new SSH public key for user {user_name}. Key ID: {import_ssh_key_response['SshPublicKeyId']}")


# def delete_ssh_public_key(ssh_key_id):
#     # Delete the SSH public key
#     transfer_client.delete_ssh_public_key(SshPublicKeyId=ssh_key_id)
#     print(f"Deleted SSH public key with ID {ssh_key_id}")


def check_key_expiration(bucket, prefix, days_threshold, notification_threshold, deletion_threshold, recipient_emails):
    # To handle difference between _ and - of TF username and S3 bucket
    bucket_name = bucket.replace('_', '-')
    response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)

    for obj in response.get('Contents', []):
        if obj['Key'] == prefix:
            continue

        if not obj['Key'].lower().endswith(file_extension):
            continue

        last_modified = obj['LastModified'].replace(tzinfo=None)
        age = datetime.now() - last_modified
        remaining_days = days_threshold - age.days

        if 0 < remaining_days <= notification_threshold:
            subject = f"Public key in {bucket_name}/{prefix} will expire in {remaining_days} days"
            body = f"The public key {obj['Key']} in {bucket_name}/{prefix} will expire in {remaining_days} days. Please update."
            print(f"Sending Email on expiration of public key {obj['Key']} in {bucket_name}/{prefix} which will expire in {remaining_days} days.")
            # send_email(subject, body, recipient_emails)

        if remaining_days <= 0:
            print(f"Key in {bucket_name}/{prefix} has expired: {obj['Key']}")
            # Add deletion logic here if needed
            if age.days > deletion_threshold:
                print(f"Deleting expired key: {obj['Key']} as it has exceeded deletion threshold of: {deletion_threshold}")
                # TODO: Delete the public key logic 

                    
def delete_key(username, key_id):
    print(f"****DELETING {key_id}****")
    #transfer_client.delete_ssh_public_key(ServerId=tf_server_id, UserName=username, SshPublicKeyId=key_id)

def check_transfer_pub_keys(username, days_threshold, recipient_emails):
    resp = transfer_client.describe_user(ServerId=tf_server_id, UserName=username)
    user = resp.get('User', {})

    date_imported = ''
    pub_keys = user.get('SshPublicKeys', [])

    if not pub_keys:
        print(f"No keys found for user {username}.")
        return

    date_imported = min(keys['DateImported'].replace(tzinfo=None) for keys in pub_keys)
    age = datetime.now() - date_imported
    remaining_days = days_threshold - age.days

    print(f"{len(pub_keys)} key(s) found for user {username}:")
    for key in pub_keys:
        key_date_imported = key['DateImported'].replace(tzinfo=None)
        print(f"\nPublic Key ID: {key['SshPublicKeyId']}. \nDate Imported: {key_date_imported} \nPublic Key Body: {key['SshPublicKeyBody']}.")

    if 0 < remaining_days <= notification_threshold:
        print(f"This key will expire in {remaining_days} days")
        subject = f"Transfer user {username}'s key will expire in {remaining_days} days"
        body = f"The public key for Transfer user {username} will expire in {remaining_days} days. Please upload a new public key."
        print(f"Sending email for Transfer user {username} public key which will expire in {remaining_days} days.")
        # send_email(subject, body, recipient_emails)

    if remaining_days <= 0:
        # Only delete the public key if there are more than one keys available in TF user 
        # and always ensure one key is available in case both keys have exceeded the deletion_threshold
        keys_to_delete = []  # List to store keys to delete
        for key in pub_keys:
            key_date_imported = key['DateImported'].replace(tzinfo=None)
            key_id = key['SshPublicKeyId']
            if age.days > deletion_threshold:
                print(f"Marking key for deletion: {key_id}")
                keys_to_delete.append(key_id)

        if keys_to_delete and len(pub_keys) > 1:
            for key_id in keys_to_delete:
                print(f"Deleting expired key for user {username} with ID {key_id} as it has exceeded the deletion threshold of {deletion_threshold}")
                # Delete the public key logic
                delete_key(username, key_id)
        else:
            print(f"Key for user {username} has either not expired or has not exceeded the deletion threshold or is the only key.")


def lambda_handler(event, context):
    # Check PubKeys in S3 Buckets
    buckets = [bucket['Name'] for bucket in s3_client.list_buckets()['Buckets']]

    # Check each S3 bucket for key expiration
    for bucket in buckets:
        print(f">>>> Checking Key Expiration in Bucket: {bucket}")
        check_key_expiration(bucket, s3_folder, s3_key_threshold, notification_threshold, deletion_threshold, [recipient_email_1])

    # List all AWS Transfer Family users
    response = transfer_client.list_users(ServerId=tf_server_id)
    transfer_users = [user['UserName'] for user in response['Users']]


    # Check Transfer Family user keys for expiration
    for user in transfer_users:
        print(f">>>> Checking Key Expiration in TF for user {user}")
        check_transfer_pub_keys(user, transfer_key_threshold, [recipient_email_1])

    return {
        'statusCode': 200,
        'body': json.dumps('DONE!')
    }    
