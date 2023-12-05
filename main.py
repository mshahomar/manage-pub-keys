import boto3
import json
import os
from datetime import datetime, timedelta

region = "ap-southeast-1"
sess = boto3.session.Session(region_name=region)

# Boto3 clients
s3_client = sess.client('s3')
ses_client = sess.client('ses', aws_access_key_id=os.environ['SES_ACCESS_KEY'], aws_secret_access_key=os.environ['SES_SECRET_ACCESS_KEY'])
transfer_client = sess.client('transfer')

# Make necessary changes here
s3_key_threshold = 8
s3_folder = 'KEY/'
file_extension = '.pub'
transfer_key_threshold = 8
notification_threshold = 5
deletion_threshold = transfer_key_threshold + 5
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

    # Sort the keys by their DateImported, and keep the latest one
    pub_keys.sort(key=lambda x: x['DateImported'], reverse=True)
    latest_key = pub_keys[0]

    print(f"{len(pub_keys)} key(s) found for user {username}:")
    for key in pub_keys:
        key_date_imported = key['DateImported'].replace(tzinfo=None)
        print(f"\nPublic Key ID: {key['SshPublicKeyId']}. \nDate Imported: {key_date_imported} \nPublic Key Body: {key['SshPublicKeyBody']}.")
        print("-" * 100)

    date_imported = min(keys['DateImported'].replace(tzinfo=None) for keys in pub_keys)
    print(f"date_imported: {date_imported}")
    age = datetime.now() - date_imported
    print(f"age: {age}")
    remaining_days = days_threshold - age.days
    print(f"remaining_days: {remaining_days}")
    # remaining_days = days_threshold - (datetime.now() - latest_key['DateImported'].replace(tzinfo=None)).days

    if len(pub_keys) == 1:
        # If user has only one key
        if 85 < remaining_days <= 90:
            print(f"Sending email for Transfer user {username} public key which will expire in {remaining_days} days.")
            # send_email(subject, body, recipient_emails)

        if remaining_days <= 0:
            # If key has exceeded the deletion threshold
            if age.days > deletion_threshold:
                print(f"Deleting expired key for user {username} with ID {latest_key['SshPublicKeyId']} as it has exceeded the deletion threshold of {deletion_threshold} days")
                # Delete the public key logic
                delete_key(username, latest_key['SshPublicKeyId'])
            else:
                print(f"Key for user {username} has either not expired or has not exceeded the deletion threshold.")

    if len(pub_keys) > 1:
        # If user has more than one key
        oldest_key = pub_keys[-1]
        remaining_days_oldest = days_threshold - (datetime.now() - oldest_key['DateImported'].replace(tzinfo=None)).days

        if remaining_days_oldest <= 0:
            # If oldest key has exceeded the deletion threshold
            if remaining_days_oldest <= -deletion_threshold:
                print(f"Deleting expired key for user {username} with ID {oldest_key['SshPublicKeyId']} as it has exceeded the deletion threshold of {deletion_threshold}")
                # Delete the public key logic
                delete_key(username, oldest_key['SshPublicKeyId'])
            else:
                print(f"Oldest key for user {username} has either not expired or has not exceeded the deletion threshold.")
        else:
            # If user has more than 2 keys
            print(f"All keys for user {username} have either not expired or have not exceeded the deletion threshold.")


def lambda_handler(event, context):
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
