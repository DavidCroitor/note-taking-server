import os
import json
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/drive']


def get_drive_service():
    creds = None
    token_json_str = os.getenv('GOOGLE_TOKEN_JSON')
    
    if token_json_str:
        token_dict = json.loads(token_json_str)
        creds = Credentials.from_authorized_user_info(token_dict, SCOPES)
    elif os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                os.environ['GOOGLE_TOKEN_JSON'] = creds.to_json()
            except:
                creds = None 
        
        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
            os.environ['GOOGLE_TOKEN_JSON'] = creds.to_json()

        if not token_json_str:
            with open('token.json', 'w') as token:
                token.write(creds.to_json())
            
    return build('drive', 'v3', credentials=creds)