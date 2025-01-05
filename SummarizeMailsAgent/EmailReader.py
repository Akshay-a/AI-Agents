from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import pickle
import os
import base64
from email.mime.text import MIMEText
from datetime import datetime

"""
This class is responsible for reading emails from Gmail. 
It uses Oauth2.0 for authentication and the root  of this project must have a credentials.json file to authenticate.
It uses the Gmail API to fetch the latest emails from the user's inbox.
"""
class GmailReader:
    def __init__(self):
        self.SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
        self.creds = None
        self.service = None
    
    def authenticate(self, credentials_file='credentials.json', token_file='token.pickle'):
        """Authenticate using OAuth 2.0"""
        if os.path.exists(token_file):
            with open(token_file, 'rb') as token:
                self.creds = pickle.load(token)
        
        # If credentials are invalid or don't exist, let's create new ones
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(credentials_file, self.SCOPES)
                self.creds = flow.run_local_server(port=0)
            
            # Save the credentials for future runs
            with open(token_file, 'wb') as token:
                pickle.dump(self.creds, token)
        
        self.service = build('gmail', 'v1', credentials=self.creds)
        return True

    def get_latest_emails(self, max_results=5):
        """Fetch latest emails from Gmail"""
        if not self.service:
            raise Exception("Not authenticated. Call authenticate() first.")
        
        try:
            # Get messages
            results = self.service.users().messages().list(
                userId='me',
                labelIds=['INBOX'],
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            emails = []
            
            for message in messages:
                msg = self.service.users().messages().get(
                    userId='me',
                    id=message['id'],
                    format='full'
                ).execute()
                
                # Extract headers
                headers = msg['payload']['headers']
                subject = next(h['value'] for h in headers if h['name'].lower() == 'subject')
                sender = next(h['value'] for h in headers if h['name'].lower() == 'from')
                date = next(h['value'] for h in headers if h['name'].lower() == 'date')
                
                # Get message body
                body = ""
                if 'parts' in msg['payload']:
                    for part in msg['payload']['parts']:
                        if part['mimeType'] == 'text/plain':
                            body = base64.urlsafe_b64decode(
                                part['body']['data'].encode('UTF-8')
                            ).decode('utf-8')
                            break
                elif 'body' in msg['payload'] and 'data' in msg['payload']['body']:
                    body = base64.urlsafe_b64decode(
                        msg['payload']['body']['data'].encode('UTF-8')
                    ).decode('utf-8')
                
                emails.append({
                    'id': message['id'],
                    'subject': subject,
                    'sender': sender,
                    'date': date,
                    'body': body
                })
            
            return emails
        
        except Exception as e:
            print(f"An error occurred: {str(e)}")
            return []

# Example usage
if __name__ == "__main__":
    gmail_reader = GmailReader()
    
    try:
        # Authenticate
        gmail_reader.authenticate()
        
        # Get latest emails
        emails = gmail_reader.get_latest_emails(max_results=5)
        
        # Print emails
        for email in emails:
            print("\n" + "="*50)
            print(f"Subject: {email['subject']}")
            print(f"From: {email['sender']}")
            print(f"Date: {email['date']}")
            print(f"Body Preview: {email['body']}...")
            
    except Exception as e:
        print(f"Error: {str(e)}")