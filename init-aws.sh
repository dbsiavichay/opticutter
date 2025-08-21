#!/bin/bash
awslocal dynamodb create-table \
   --table-name certificates \
   --attribute-definitions \
      AttributeName=id,AttributeType=S \
      AttributeName=serial_number,AttributeType=S \
   --key-schema \
      AttributeName=id,KeyType=HASH \
   --global-secondary-indexes \
      "IndexName=SerialNumberIndex,KeySchema=[{AttributeName=serial_number,KeyType=HASH}],Projection={ProjectionType=ALL},ProvisionedThroughput={ReadCapacityUnits=5,WriteCapacityUnits=5}" \
   --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5 \
   --region us-east-1
