import boto3
import os
import datetime

# Initialize Bedrock client for agent runtime
bedrock_client = boto3.client('bedrock-agent-runtime')
dynamodb = boto3.resource('dynamodb')

def lambda_handler(event, context):

    # extract agentId and agentAliasId

    agent_id = os.environ.get("AGENT_ID")
    alias_id = os.environ.get("ALIAS_ID")
    table_name = os.environ.get("TABLE_NAME")

    print(table_name)

    table = dynamodb.Table(table_name)

    # Extract user input from Lex event
    user_query = event['inputTranscript']
    
    location = event.get('sessionState').get('sessionAttributes').get('Location')
    
    print(event)
    
    session_id = event.get('sessionId')
    
    print(session_id)
    
    property_specifier = f'I am referring to the property with address = {location}. '
    
    user_input = property_specifier + user_query
    
    # setting optional slot in trigger intent
    slots = event.get('sessionState').get('intent').get('slots', {})
    
    slots['Location'] = {
         'value': {
            'originalValue': location,
            'interpretedValue': location,
            'resolvedValues': [location]
        }
        
    }
    
    print(event)
    
    print(user_input)
    response = ""

    # Call the Bedrock agent with required parameters
    try:
        response = bedrock_client.invoke_agent(
            agentId=agent_id,  # Provided agent ID
            agentAliasId=alias_id,  # Provided agent alias ID
            inputText=user_input,  # The user input from Lex
            sessionId=session_id,  # Use sessionId from Lex
            endSession=False  # End the session after response (optional)
        )

    except Exception as e:
        # Handle any error that occurs when calling Bedrock
        print(f"Error calling Bedrock agent: {e}")
        agent_response = "Sorry, I encountered an error processing your request."
    
    result = ""

    try:
        
        # Iterate through the EventStream
        for item in response['completion']:
            print(f"Event: {item}")  # Log each event for debugging
            
            # Check if the event contains a chunk with bytes
            if 'chunk' in item and 'bytes' in item['chunk']:
                # Decode and append the bytes to the result string
                result += item['chunk']['bytes'].decode('utf-8')
            else:
                print(f"Unexpected event format: {item}")  # Log if event is in an unexpected format
                
    except Exception as e:
        print(f"Error reading EventStream: {e}")
        return {
            "messages": [
                {
                    "contentType": "PlainText",
                    "content": "Error processing the response from the Bedrock agent."
                }
            ]
        }
        
        
    print("result")
    print(result)


    try:
        table.put_item(Item={
            'conversationId': session_id,
            'timestamp': datetime.datetime.now().isoformat(),
            'location': location,
            'userQuery': user_query,
            'response': result
        })

    except Exception as e:
        print(f"Error writing to DynamoDB: {e}")

    # Build Lex V2 response format
    return {
        "sessionState": {
            "dialogAction": {
                "type": "Close"  # Close the conversation after responding
            },
            "intent": {
                "name": event['sessionState']['intent']['name'],
                "state": "Fulfilled"  # Mark the intent as completed
            }
        },
        "messages": [
            {
                "contentType": "PlainText",  # The response type
                "content": result  # The response from the Bedrock agent
            }
        ],
        "requestAttributes": event.get('requestAttributes', {}),  # Forward any request attributes
        "sessionId": session_id  # Keep track of session ID
    }