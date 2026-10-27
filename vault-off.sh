#!/usr/bin/env bash
DB=hamptongarage-db
ENV=hamptongarage-env
status() { aws rds describe-db-instances --db-instance-identifier "$DB" --query "DBInstances[0].DBInstanceStatus" --output text; }

echo "Turning off the app server..."
aws elasticbeanstalk update-environment --environment-name "$ENV" --option-settings Namespace=aws:autoscaling:asg,OptionName=MinSize,Value=0 Namespace=aws:autoscaling:asg,OptionName=MaxSize,Value=0 > /dev/null

s=$(status)
while [[ "$s" == "starting" || "$s" == "modifying" || "$s" == "backing-up" ]]; do echo "Database is $s, waiting..."; sleep 30; s=$(status); done
if [[ "$s" == "available" ]]; then
  aws rds stop-db-instance --db-instance-identifier "$DB" > /dev/null
  echo "Database is stopping."
else
  echo "Database is already $s."
fi
echo "Done. Reminder: AWS automatically restarts a stopped database after 7 days."
