cfn-lambda-handler
==================

This package provides a decorator for Python Lambda functions handling AWS CloudFormation custom resources.

This package is derived from the `CFN Wrapper package`_ and adds the ability to recursively generate new Lambda functions for long running CloudFormation custom resource tasks that run longer than the current AWS maximum Lambda function time of 5 minutes.

See `CloudFormation custom resources`_ for further information.

.. _CFN Wrapper package: https://github.com/ryansb/cfn-wrapper-python/
.. _CloudFormation custom resources: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/template-custom-resources.html

Usage
-----

This package provides four event decorators:

- Create - used to handle CloudFormation 'Create' requests
- Update - used to handle CloudFormation 'Update' requests
- Delete - used to handle CloudFormation 'Delete' requests
- Poll - a special decorator used for CloudFormation resources that have long running tasks that exceed the current maximum 5 minute Lambda execution time

The purpose of the decorators is to execute your custom resource provisioning logic and perform the CloudFormation callback action to publish your custom resource provisioning results to CloudFormation.

In many cases, the core `Create`, `Update` and `Delete` decorators will be sufficient for your needs.  

Defining the Handler
^^^^^^^^^^^^^^^^^^^^

The following demonstrates how to create a handler object that will be used as the entrypoint for various CloudFormation event requests:

.. code:: python
  
  from cfn_lambda_handler import Handler
  handler = Handler()

The handler object can then be used as a decorator for various CloudFormation events:

.. code:: python
  
  from cfn_lambda_handler import Handler
  
  handler = Handler()

  # This will be used as the entrypoint for CloudFormation 'Create' requests
  @handler.create
  def handle_create(event, context):
    print(event)
    ...
    ...
    if failed:
      return { "Status": "FAILURE": "Reason": "Some failure occurred" }
    else:
      return { "Status": "SUCCESS", "PhysicalResourceId": "1234" }

  # This will be used as the entrypoint for CloudFormation 'Update' requests
  @handler.update
  def handle_update(event, context):
    ...
    ...

  # This will be used as the entrypoint for CloudFormation 'Delete' requests
  @handler.delete
  def handle_delete(event, context):
    ...
    ...

In your Lambda configuration, you specify the name of the handler object as your Lambda function handler.
For example, if your Lambda function was defined in a file called ``my_function.py`` and you created a hander object called ``handler``, you would configure your Lambda handler as ``my_function.handler``.

Stack Status
^^^^^^^^^^^^

For update and delete operations, the handler attempts to query the current status of the CloudFormation stack to determine the current stack status.  This is useful for detecting if your CloudFormation stack is in a rollback state.

The following lists the possible stack status values:

``CREATE_IN_PROGRESS | CREATE_FAILED | CREATE_COMPLETE | ROLLBACK_IN_PROGRESS | ROLLBACK_FAILED | ROLLBACK_COMPLETE | DELETE_IN_PROGRESS | DELETE_FAILED | DELETE_COMPLETE | UPDATE_IN_PROGRESS | UPDATE_COMPLETE_CLEANUP_IN_PROGRESS | UPDATE_COMPLETE | UPDATE_ROLLBACK_IN_PROGRESS | UPDATE_ROLLBACK_FAILED | UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS | UPDATE_ROLLBACK_COMPLETE | REVIEW_IN_PROGRESS``

The status and status reasons are then attached as ``StackStatus`` and ``StackStatusReason`` keys on the ``event`` object passed to your custom resource handler.  

If the status/status reason cannot be determined for any reason, a value of ``UNKNOWN`` will be set.

Note that obtaining the stack status requires to you to grant the ``cloudformation:DescribeStacks`` permission to your custom resource function.

Dynamic References
^^^^^^^^^^^^^^^^^^

`CloudFormation dynamic references`_ for AWS Secrets Manager references are supported by default.  

If any property passed to a CloudFormation custom resource matches the regular expression ``{{resolve:secretsmanager:.*}}``, then the handler will attempt to resolve the dynamic reference.

This feature requires your custom resources to have the following IAM permissions:

- ``secretsmanager:GetSecretValue`` for all secrets referenced
- ``kms:Decrypt`` for any secrets encrypted with a custom KMS key

You can disable this functionality by setting the ``resolve_secrets`` attribute when creating the handler:

.. code:: python
  
  from cfn_lambda_handler import Handler  
  handler = Handler(resolve_secrets=False)
  ...
  ...

.. _CloudFormation dynamic references : https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/dynamic-references.html

Polling
^^^^^^^

A special ``Poll`` decorator provides the ability to extend a CloudFormation custom resource operation longer than current Aws Lambda execution limits.  The poll decorator will be called for any Lambda executions subsequent to the initial CloudFormation Lambda event.

To use this functionality, you decorate an appropriate function with the poll action:

.. code:: python
  
  from cfn_lambda_handler import Handler
  
  handler = Handler()

  # This will be used as the entrypoint for CloudFormation 'Poll' requests
  @handler.poll
  def handle_poll(event, context):
    ...
    ...

To use the polling capability, there are a few things you need to ensure:

- Set a ``Timeout`` property on the event (default value is 300 seconds).  This specifies the maximum amount of time the custom resource operation is allowed to run for.  The decorator uses this value across multiple Lambda executions and will return a failure if the CloudFormation operation does not complete within the specified timeout.

- Set a property on the event that captures any state that should be retained across multiple Lambda executions.  This property should be set or updated prior to invoking a new Lambda execution.  Note that this state must be serializable in a JSON format.

- Determine when the Lambda function is approaching it's maximum execution time and raise a ``CfnLambdaExecutionTimeout`` exception, and pass any state you want to be available for the next invocation.  This signals to the handler to invoke a new execution of the Lambda function and exit the current Lambda execution.  The state you passed to the ``CfnLambdaExecutionTimeout`` will be available in the ``EventState`` property of the ``event`` object.

- Ensure the Lambda function has appropriate IAM privileges to invoke a new execution of itself.

The following is a complete example of ensuring correct polling behaviour:

.. code:: python
  
  import time
  from cfn_lambda_handler import Handler, CfnLambdaExecutionTimeout
  
  handler = Handler()

  def poll(event, context):
    # This performs some polling operation
    some_state = event['EventState']
    while True:
      # If the remaining execution time is < 20 seconds, signal the handler to invoke a new Lambda function
      if context.get_remaining_time_in_millis() < 20000:
        # Here we raise a timeout exception, along with the state we want to persist
        # This state is available in the EventState property of the event
        raise CfnLambdaExecutionTimeout(some_state)
      some_state = check_complete(event)
      if some_state.complete:
        return { "Status":"SUCCESS" }
      # Sleep for 10 seconds
      time.sleep(10)

  @handler.create
  def handle_create(event, context):
    # Set the maximum timeout.  Note it is greater than the current maximum 300 seconds timeout allowed for AWS Lambda
    event['Timeout'] = 1800
    return poll(event, context)

  @handler.poll
  def handle_poll(event, context):
    # The poll handler is called for any invocation of the Lambda function post the initial Create or Update operation
    # Here we just continue the internal polling process
    return poll(event)

Installation
------------

    pip install cfn-lambda-handler

Requirements
------------

- boto3_

.. _boto3: https://github.com/boto/boto3

Authors
-------

- `Justin Menga`_

.. _Justin Menga: https://github.com/mixja
