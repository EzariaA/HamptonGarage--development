#!/usr/bin/env bash
DB=hamptongarage-db
ENV=hamptongarage-env
status() { aws rds describe-db-instances --db-instance-identifier "$DB" --query "DBInstances[0].DBInstanceStatus" --output text; }

s=$(status)
while [[ "$s" == "stopping" ]]; do echo "Database is still stopping, waiting..."; sleep 30; s=$(status); done
if [[ "$s" == "stopped" ]]; then
  echo "Starting the database..."
  aws rds start-db-instance --db-instance-identifier "$DB" > /dev/null
else
  echo "Database is already $s."
fi
aws rds wait db-instance-available --db-instance-identifier "$DB"
echo "Database ready. Starting the app server..."
aws elasticbeanstalk update-environment --environment-name "$ENV" --option-settings Namespace=aws:autoscaling:asg,OptionName=MinSize,Value=1 Namespace=aws:autoscaling:asg,OptionName=MaxSize,Value=1 > /dev/null
aws elasticbeanstalk wait environment-updated --environment-names "$ENV"
echo "HamptonGarage is ON: http://hamptongarage-env.eba-7hcq7de4.us-east-2.elasticbeanstalk.com"
