import boto3
from datetime import datetime, timedelta


# Boto3 clients
s3_client = boto3.client('s3')
ses_client = boto3.client('ses')

# Make necessary changes here
s3_key_threshold = 90
s3_folder = 'KEY/'
file_extension = '.sql'
transfer_key_threshold = 90
notification_threshold = 5  # To send notification 5 days before expiration 
sender_email = "myfictitious@gmail.com"
recipient_email_1 = "brader1@gmail.com"
recipient_email_2 = "brader2@gmail.com"


def send_email(subject, body, recipients):
    sender = sender_email  # Replace with your SES verified sender email address
    charset = 'UTF-8'
    
    response = ses_client.send_email(
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
        },
        Source=sender,
    )

    print(f"Email sent to {', '.join(recipients)}. Message ID: {response['MessageId']}")


def check_key_expiration(bucket, prefix, days_threshold, notification_threshold, recipient_emails):
    response = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)

    for obj in response.get('Contents', []):
        # Skip entries that are 'root folder'
        if obj['Key'] == prefix:
            continue

        # Check only '*.pub' extension, others we will ignore. So before upload to S3, ensure the file extension is .pub
        if not obj['Key'].lower().endswith(file_extension):
            continue

        last_modified = obj['LastModified'].replace(tzinfo=None)
        print(f"Last Modified: {last_modified}")
        age = datetime.now() - last_modified
        remaining_days = days_threshold - age.days

        if 0 < remaining_days <= notification_threshold:
            subject = f"Public key in {bucket}/{prefix} will expire in {remaining_days} days"
            body = f"The public key {obj['Key']} in {bucket}/{prefix} will expire in {remaining_days} days. Please update."
            send_email(subject, body, recipient_emails)

        if remaining_days <= 0:
            print(f"Key in {bucket}/{prefix} has expired: {obj['Key']}")

        #if remaining_days > 0:
        #    print(f"Key in {bucket}/{obj['Key']} will expire in {remaining_days} days")
        #else:
        #    print(f"Public Key in {bucket}/{obj['Key']} has expired")


#def check_transfer_user_keys(username, days_threshold):
#    transfer_client = boto3.client('transfer')
#    response = transfer_client.list_ssh_public_keys(ServerId=username)
#    
#    for key in response['SshPublicKeys']:
#        uploaded_at = key['DateUploaded'].replace(tzinfo=None)
#        age = datetime.now() - uploaded_at
#        if age > timedelta(days=days_threshold):
#            print(f"Transfer user {username}'s key expired: {key['SshPublicKeyId']}")


buckets = [bucket['Name'] for bucket in s3_client.list_buckets()['Buckets']]

# Check each S3 bucket for key expiration
for bucket in buckets:
    print(f"Bucket: {bucket}")
    check_key_expiration(bucket, s3_folder, s3_key_threshold, notification_threshold, [recipient_email_1, recipient_email_2])

## Replace 'transfer_user_1' and 'transfer_user_2' with your actual Transfer Family user names
#transfer_users = ['transfer_user_1', 'transfer_user_2']

## Check Transfer Family user keys for expiration
#for user in transfer_users:
#    check_transfer_user_keys(user, transfer_key_threshold)
#
