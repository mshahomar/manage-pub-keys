import boto3
import json
import os
from datetime import datetime, timedelta


region = "ap-southeast-1"
# profile = "profile2"

# sess = boto3.session.Session(profile_name=profile, region_name=region)
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
sender_email = "system1@myemail.com"
recipient_email_1 = "user1@example.com"
# recipient_email_2 = "user1@example.com"
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
        print(f"Age: {age}")
        remaining_days = days_threshold - age.days
        print(f"Remaining days before key expired: {remaining_days}")

        if 0 < remaining_days <= notification_threshold:
            subject = f"Public key in {bucket}/{prefix} will expire in {remaining_days} days"
            body = f"The public key {obj['Key']} in {bucket}/{prefix} will expire in {remaining_days} days. Please update."
            print("send_email()")
            #send_email(subject, body, recipient_emails)

        if remaining_days <= 0:
            print(f"Key in {bucket}/{prefix} has expired: {obj['Key']}")

        #if remaining_days > 0:
        #    print(f"Key in {bucket}/{obj['Key']} will expire in {remaining_days} days")
        #else:
        #    print(f"Public Key in {bucket}/{obj['Key']} has expired")


def check_transfer_user_keys(username, days_threshold, recipient_emails):
    response = transfer_client.list_ssh_public_keys(ServerId=tf_server_id)
    print(f"SSHPublicKeys: {response['SshPublicKeys']}")
    
    for key in response['SshPublicKeys']:
        uploaded_at = key['DateUploaded'].replace(tzinfo=None)
        print(f"PubKey uploaded at: {uploaded_at}")
        age = datetime.now() - uploaded_at
        print(f"PubKey age: {age}")
        print(f"timedelta(days=days_threshold): {timedelta(days=days_threshold)}")
        
        remaining_days = days_threshold - age.days
        
        if 0 < remaining_days <= notification_threshold:
            subject = f"Transfer user {username}'s key will expire in {remaining_days} days"
            body = f"The public key {key['SshPublicKeyId']} for Transfer user {username} will expire in {remaining_days} days. Please update."

            print("send_email()")            
            # send_email(subject, body, recipient_emails)

        if remaining_days <= 0:
            print(f"Transfer user {username}'s key has expired: {key['SshPublicKeyId']}")
            
        
def check_transfer_pub_keys(username, days_threshold, recipient_emails):
    resp = transfer_client.describe_user(ServerId=tf_server_id, UserName=username)
    users = resp.get('User', [])
    
    date_imported = ''
    pub_key_id = []
    pub_key_body = []
    
    for keys in users['SshPublicKeys']:
        date_imported = keys['DateImported'].replace(tzinfo=None)
        pub_key_id.append(keys['SshPublicKeyId'])
        pub_key_body.append(keys['SshPublicKeyBody'])
        
    age = datetime.now() - date_imported
    remaining_days = days_threshold - age.days
        
    print(f"There are {len(pub_key_body)} key(s) for user {username}")
    for key in pub_key_body:
        print(f"Public Keys: {key}. \nDate Imported: {date_imported}.")
        
        if 0 < remaining_days <= notification_threshold:
            print(f"This key will expire in {remaining_days} days")
            subject = f"Transfer user {username}'s key will expire in {remaining_days} days"
            body = f"The public key {key} for Transfer user {username} will expire in {remaining_days} days. Please upload a new public key."

            print("send_email()")            
            send_email(subject, body, recipient_emails)

        if remaining_days <= 0:
            print(f"Transfer user {username}'s key has expired. Public Key: {key}")
    

def lambda_handler(event, context):
    # Check PubKeys in S3 Buckets
    buckets = [bucket['Name'] for bucket in s3_client.list_buckets()['Buckets']]

    # Check each S3 bucket for key expiration
    for bucket in buckets:
        print(f"Bucket: {bucket}")
        check_key_expiration(bucket, s3_folder, s3_key_threshold, notification_threshold, [recipient_email_1])
        # check_key_expiration(bucket, s3_folder, s3_key_threshold, notification_threshold, [recipient_email_1, recipient_email_2])
        
    # List all AWS Transfer Family users
    response = transfer_client.list_users(ServerId=tf_server_id)
    transfer_users = [user['UserName'] for user in response['Users']]
    
    ## Replace 'transfer_user_1' and 'transfer_user_2' with your actual Transfer Family user names
    #transfer_users = ['transfer_user_1', 'transfer_user_2']
    
    # Check Transfer Family user keys for expiration
    
    for user in transfer_users:
        check_transfer_pub_keys(user, transfer_key_threshold, [recipient_email_1])
        # resp = transfer_client.describe_user(ServerId=tf_server_id, UserName=user)
        # users = resp.get('User', [])
        
        # date_imported = ''
        # pub_key_id = ''
        # pub_key_body = []
        
        # for keys in users['SshPublicKeys']:
        #     date_imported = keys['DateImported']
        #     pub_key_id = keys['SshPublicKeyId']
        #     pub_key_body.append(keys['SshPublicKeyBody'])
            
        # print(f"There are {len(pub_key_body)} key(s) for user {user}")
        # for key in pub_key_body:
        #     print(f"PubKey ID: {pub_key_id}. Public Keys: {key}. Date Imported: {date_imported}")

    
    return {
        'statusCode': 200,
        'body': json.dumps('DONE!')
    }
