# Turns the live site OFF to save AWS credits. Run with: .\vault-off.ps1

# Find the Auto Scaling group that runs our app server
$asg = aws elasticbeanstalk describe-environment-resources --environment-name hamptongarage-env --query "EnvironmentResources.AutoScalingGroups[0].Name" --output text

# Turn off the app server (0 servers)
aws autoscaling update-auto-scaling-group --auto-scaling-group-name $asg --min-size 0 --max-size 0 --desired-capacity 0

# Stop the database
aws rds stop-db-instance --db-instance-identifier hamptongarage-db | Out-Null
Write-Host "Turning off. Wait 5-10 minutes before running vault-on.ps1."
