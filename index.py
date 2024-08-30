import json
import boto3
import time
import os
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
import cfnresponse

def handler(event, context):
    try:
        print("Received event: " + json.dumps(event, indent=2))
        client = boto3.client('opensearchserverless')
        service = 'aoss'
        region = os.environ.get('REGION')
        credentials = boto3.Session().get_credentials()
        awsauth = AWS4Auth(credentials.access_key, credentials.secret_key,
                        region, service, session_token=credentials.token)

        response = client.batch_get_collection(
            names=[os.environ['AOSS_COLLECTION_NAME']])

        while (response['collectionDetails'][0]['status']) == 'CREATING':
            print('Creating collection...')
            time.sleep(30)
            response = client.batch_get_collection(
                names=[os.environ['AOSS_COLLECTION_NAME']])

        opensearch_host = (response['collectionDetails'][0]['collectionEndpoint'])
        host = opensearch_host.replace("https://", "")
        
        client = OpenSearch(
            hosts=[{'host': host, 'port': 443}],
            http_auth=awsauth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            timeout=300
        )
        # It can take up to a minute for data access rules to be enforced
        time.sleep(45)

        # Create index
        index_name = os.environ['AOSS_INDEX_NAME']
        index_body = {
            'mappings': {
                'properties': {
                'AMAZON_BEDROCK_METADATA': {
                    'type': 'text',
                    'index': False
                  },
                  'AMAZON_BEDROCK_TEXT_CHUNK': {
                    'type': 'text'
                  },
                  'vector': {
                    'type': 'knn_vector',
                    'dimension': 1024,
                    'method': {
                      'engine': 'faiss',
                      'space_type': 'l2',
                      'name': 'hnsw',
                      'parameters': {}
                    }
                  }
                }
            },
            'settings': {
                'index': {
                  'knn': True
                }
            }
        }

        response = client.indices.create(index=index_name, body=index_body)
        time.sleep(180)
        print('\nCreating index:')
        print(response)
        cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
    except Exception as e:
        print("Error: " + str(e))
        cfnresponse.send(event, context, cfnresponse.FAILED, {})

