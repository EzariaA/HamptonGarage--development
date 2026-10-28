# Turns the live site back ON. Run with: .\vault-on.ps1

# Start the database and wait until it's ready
aws rds start-db-instance --db-instance-identifier hamptongarage-db | Out-Null
aws rds wait db-instance-available --db-instance-identifier hamptongarage-db

# Turn the app server back on (1 server)
$asg = aws elasticbeanstalk describe-environment-resources --environment-name hamptongarage-env --query "EnvironmentResources.AutoScalingGroups[0].Name" --output text
aws autoscaling update-auto-scaling-group --auto-scaling-group-name $asg --min-size 1 --max-size 1 --desired-capacity 1
Write-Host "Server starting. Run 'eb status' in about 5 minutes and look for Green."
