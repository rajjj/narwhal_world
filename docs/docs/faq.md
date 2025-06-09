#FAQ

###What to do if the Prefect worker goes down?

The workers for the Narwhal workpools are running in the AWS Elastic Container Service (ECS). They will need to be redeployed if they go down.

Here are the steps:

1. Go to the AWS ECS console.
2. Navigate to the cluster in the correct region (use the table below to help with this).

    | Workpool      |    Region                      |Cluster               | Worker        |
    |:-------------:|:------------------------------:|:--------------------:|:-------------:|
    | narpool-aws-us| us-east-1 (N. Virginia)        | nps-prod             |nps-worker-prod|
    | narpool-aws-eu|eu-west-1 (Ireland)             | nps-prod-eu          |nps-worker-prod|


3. Click on the nps-worker-prod service that needs to be redeployed and hit the `Update service` button on the top right.
4. Select `Force new deployment` and update the service.
5. Monitor the new deployment and ensure that the new worker changes status from `Pending` to `Started`.

Important Considerations:

- Only force a new deployment if the worker is confirmed to be down. Forcing a new deployment will stop running flows on an active worker.
- Ensure that you are redeploying a worker in the correct region.
