import json
import time
import logging
import requests
import boto3
from copy import deepcopy
from hashlib import md5

logger = logging.getLogger()
logger.setLevel(logging.INFO)

SUCCESS = 'SUCCESS'
FAILED = 'FAILED'
TIMEOUT = 300

class CfnLambdaExecutionTimeout(Exception):
  def __init__(self,state={}):
    self.state = state

def date_handler(obj):
  if hasattr(obj, 'isoformat'):
    return obj.isoformat()
  elif type(obj) is bytes:
    return obj.decode('utf-8')
  else:
    return str(obj)

def physical_resource_id(stack_id, resource_id):
  m = md5()
  id = (stack_id + resource_id).encode('utf-8')
  m.update(id)
  return m.hexdigest()

def callback(url, data):
  try:
    headers = {'Content-Type': ''}
    r = requests.put(url, data=data, headers=headers)
    r.raise_for_status()
    logger.debug("Request to CloudFormation succeeded")
  except requests.exceptions.HTTPError as e:
    logger.error("Callback to CloudFormation failed with status %d" % e.response.status_code)
    logger.error("Response: %s" % e.response.text)
  except requests.exceptions.RequestException as e:
    logger.error("Failed to reach CloudFormation: %s" % e)

def invoke(event,context):
  event['EventStatus'] = 'Poll'
  boto3.client('lambda').invoke(
    FunctionName=context.function_name,
    InvocationType='Event',
    Payload=json.dumps(event, default=date_handler))

def sanitize(response, secure_attributes):
  if response.get('Data'):
    sanitized = deepcopy(response)
    sanitized['Data'] = {k:'*******' if k in secure_attributes else v for k,v in sanitized['Data'].items() }
    return json.dumps(sanitized, default=date_handler)
  else:
    return json.dumps(response, default=date_handler)

def cfn_handler(func, base_response=None, secure_attributes=[]):
  def decorator(event, context):
    response = {
      "StackId": event["StackId"],
      "RequestId": event["RequestId"],
      "LogicalResourceId": event["LogicalResourceId"],
      "Status": SUCCESS,
    }

    # Get stack status if enabled
    if event['RequestType'] in ['Update', 'Delete']:
      cfn_status = ('UNKNOWN','UNKNOWN')
      try:
        cfn_status = next((
          (stack.get('StackStatus','UNKNOWN'),stack.get('StackStatusReason','UNKNOWN'))
          for stack in boto3.client('cloudformation').describe_stacks(
            StackName=event['StackId']
          )['Stacks']
        ), cfn_status)
      except Exception as e:
        logger.info("Exception raised getting stack status - have you granted DescribeStacks permissions?")
      finally:
        event['StackStatus'] = cfn_status[0]
        event['StackStatusReason'] = cfn_status[1]

    # Set physical resource ID
    if event.get("PhysicalResourceId"):
      response["PhysicalResourceId"] = event["PhysicalResourceId"]
    else:
      response["PhysicalResourceId"] = physical_resource_id(event["StackId"], event["LogicalResourceId"])
    
    if base_response:
      response.update(base_response)
    logger.debug("Received %s request with event: %s" % (event['RequestType'], json.dumps(event, default=date_handler)))

    # Add event creation time 
    event['CreationTime'] = event.get('CreationTime') or int(time.time())
    timeout = event.get('Timeout') or TIMEOUT
    try: 
      if timeout:
        finish = event['CreationTime'] + timeout
        if int(time.time()) > finish:
          logger.info("Function reached maximum timeout of %d seconds" % timeout)
          response.update({ 
            "Status": FAILED,
            "Reason": "The custom resource operation failed to complete within the user specified timeout of %d seconds" % timeout
          })
        else:
          response.update(func(event, context))
      else:
        response.update(func(event, context))
    except CfnLambdaExecutionTimeout as e:
      logger.info("Function approaching maximum Lambda execution timeout...")
      logger.info("Invoking new Lambda function...")
      try:
        event['EventState'] = e.state
        invoke(event, context)
      except Exception as e:
        logger.exception("Failed to invoke new Lambda function after maximum Lambda execution timeout: " + str(e))
        response.update({
          "Status": FAILED,
          "Reason": "Failed to invoke new Lambda function after maximum Lambda execution timeout"
        })
      else:
        return
    except:
      logger.exception("Failed to execute resource function")
      response.update({
        "Status": FAILED,
        "Reason": "Exception was raised while handling custom resource"
      })
    # Remove any request fields that may have been added to the response
    response.pop("ResourceProperties", None)
    response.pop("OldResourceProperties", None)
    response.pop("ServiceToken", None)
    response.pop("ResponseURL", None)
    response.pop("RequestType", None)
    response.pop("CreationTime", None)
    response.pop("ResourceType", None)
    response.pop("StackStatus", None)
    response.pop("StackStatusReason", None)
    serialized = json.dumps(response, default=date_handler)
    sanitized = sanitize(response, secure_attributes)
    logger.info("Responding to '%s' request with: %s" % (event['RequestType'], sanitized))
    callback(event['ResponseURL'], serialized)

  return decorator

class Handler:
  def __init__(self, decorator=cfn_handler, secure_attributes=[]):
    self._handlers = dict()
    self._decorator = decorator
    self._secure_attributes = secure_attributes

  def __call__(self, event, context):
    request = event.get('EventStatus') or event['RequestType']
    return self._handlers.get(request, self._empty())(event, context)

  def _empty(self):
    @self._decorator
    def empty(event, context):
      return {
        'Status': FAILED,
        'Reason': 'No handler defined for request type %s' % event['RequestType'],
      }
    return empty

  def create(self, func):
    self._handlers['Create'] = self._decorator(func, secure_attributes=self._secure_attributes)
    return func

  def update(self, func):
    self._handlers['Update'] = self._decorator(func, secure_attributes=self._secure_attributes)
    return func

  def delete(self, func):
    self._handlers['Delete'] = self._decorator(func, secure_attributes=self._secure_attributes)
    return func

  def poll(self, func):
    self._handlers['Poll'] = self._decorator(func, secure_attributes=self._secure_attributes)
    return func