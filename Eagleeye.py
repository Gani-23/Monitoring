import boto3
import os

# Function to create an S3 bucket
def create_bucket(bucket_name):
    s3 = boto3.client('s3')
    try:
        res = s3.create_bucket(
            Bucket=bucket_name,
            CreateBucketConfiguration={
                'LocationConstraint': 'ap-northeast-2'
            }
        )
        print("Bucket created:", res)
        return res
    except Exception as e:
        print("Error creating bucket:", e)

# Function to upload files to S3 bucket
def uploadfolders(bucket_name, folder_path):
    s3 = boto3.client('s3')
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            s3.upload_file(os.path.join(root, file), bucket_name, file)
            print("Uploaded:", file)

# Main process function to create bucket and upload files
def process():
    bucket_name = "monitorbeluga"
    folder_path = "C:/Users/eagleye/Desktop/FOCUS/Samplefiles"
    create_bucket(bucket_name)
    uploadfolders(bucket_name, folder_path)

# Function to create an EC2 instance
def create_ec2_instance():
    ec2 = boto3.resource('ec2')
    instance = ec2.create_instances(
        ImageId='ami-062cf18d655c0b1e8',  # Use a valid AMI ID
        MinCount=1,
        MaxCount=1,
        InstanceType='t2.micro',
        KeyName='Gani_reborne',  # Make sure you have this key pair created
        TagSpecifications=[
            {
                'ResourceType': 'instance',
                'Tags': [
                    {
                        'Key': 'Name',
                        'Value': 'EagleEye'
                    }
                ]
            }
        ],
        UserData='''#!/bin/bash
                    sudo apt update -y
                    sudo apt install nginx -y
                    service nginx start
'''
    )
    instance[0].wait_until_running()
    instance[0].reload()
    print(instance)
    security_groups = instance[0].security_groups
    print("Security Groups:", security_groups)
    print("Security Groups:", [sg['GroupName'] for sg in security_groups])
    print("EC2 Instance created:", instance[0].id)
    return instance[0]

# Function to create a launch configuration
def create_launch_configuration():
    asg = boto3.client('autoscaling')
    try:
        response = asg.create_launch_configuration(
            LaunchConfigurationName='EagleEyeLaunchConfig',
            ImageId='ami-062cf18d655c0b1e8',
            InstanceType='t2.micro',
            KeyName='Gani_reborne',
            SecurityGroups=['default']
        )
        print("Launch Configuration created:", response)
        return response
    except Exception as e:
        print("Error creating launch configuration:", e)

# Function to create an Auto Scaling Group (ASG)
def create_autoscaling_group():
    asg = boto3.client('autoscaling')
    create_launch_configuration()
    try:
        response = asg.create_auto_scaling_group(
            AutoScalingGroupName='EagleEyeASG',
            LaunchConfigurationName='EagleEyeLaunchConfig',
            MinSize=1,
            MaxSize=3,
            DesiredCapacity=1,
            DefaultCooldown=300,
            AvailabilityZones=[
                'ap-northeast-2a',
                'ap-northeast-2b',
            ],
            Tags=[
                {
                    'Key': 'Name',
                    'Value': 'EagleEye',
                    'PropagateAtLaunch': True
                },
            ],
        )
        print("Auto Scaling Group created:", response)
        return response
    except Exception as e:
        print("Error creating Auto Scaling Group:", e)

# Function to create a target group
def create_target_group(vpc_id):
    elbv2 = boto3.client('elbv2')
    response = elbv2.create_target_group(
        Name='EagleEyeTG',
        Protocol='HTTP',
        Port=80,
        VpcId=vpc_id,
        HealthCheckProtocol='HTTP',
        HealthCheckPort='80',
        HealthCheckEnabled=True,
        HealthCheckPath='/',
        HealthCheckIntervalSeconds=30,
        HealthCheckTimeoutSeconds=5,
        HealthyThresholdCount=5,
        UnhealthyThresholdCount=2,
        TargetType='instance',
    )
    target_group_arn = response['TargetGroups'][0]['TargetGroupArn']
    print("Target Group created:", target_group_arn)
    return target_group_arn

# Function to create a load balancer and attach it to the target group
def attach_load_balancer(target_group_arn):
    ec2 = boto3.resource('ec2', region_name='ap-northeast-2')
    client = boto3.client('ec2', region_name='ap-northeast-2')

    # Fetch the default VPC
    default_vpc = list(ec2.vpcs.filter(Filters=[{'Name': 'isDefault', 'Values': ['true']}]))[0]

    # Fetch all subnets in the specified availability zones
    specified_subnets = client.describe_subnets(
        Filters=[
            {'Name': 'availability-zone', 'Values': ['ap-northeast-2a', 'ap-northeast-2b']}
        ]
    )['Subnets']

    if len(specified_subnets) < 2:
        raise ValueError("At least two subnets are required in the specified availability zones.")

    # Fetch subnets in the default VPC
    default_vpc_subnets = list(default_vpc.subnets.all())

    if not default_vpc_subnets:
        raise ValueError("No subnets found in the default VPC.")

    # Combine the subnets (one from default VPC and two specified subnets)
    combined_subnets = [default_vpc_subnets[0].id] + [subnet['SubnetId'] for subnet in specified_subnets[:2]]

    elbv2 = boto3.client('elbv2', region_name='ap-northeast-2')
    response = elbv2.create_load_balancer(
        Name='EagleEyeELB',
        Scheme='internet-facing',
        Subnets=combined_subnets,  
        Tags=[
            {
                'Key': 'Name',
                'Value': 'EagleEye',
            },
        ]
    )
    load_balancer_arn = response['LoadBalancers'][0]['LoadBalancerArn']
    listener = elbv2.create_listener(
        LoadBalancerArn=load_balancer_arn,
        Protocol='HTTP',
        Port=80,
        DefaultActions=[
            {
                'Type': 'forward',
                'TargetGroupArn': target_group_arn,
            }
        ]
    )
    print("Load Balancer created and listener attached:", load_balancer_arn)
    return load_balancer_arn

# Function to register targets to the target group
def register_targets(target_group_arn, instance_id):
    elbv2 = boto3.client('elbv2')
    response = elbv2.register_targets(
        TargetGroupArn=target_group_arn,
        Targets=[
            {
                'Id': instance_id,
                'Port': 80
            },
        ]
    )
    print("Instance registered to Target Group:", response)
    return response

# Execute the process function
process()

# Create EC2 instance
instance = create_ec2_instance()

# Create Target Group
ec2 = boto3.resource('ec2')
vpc_id = list(ec2.vpcs.all())[0].id  # Get the first VPC ID
target_group_arn = create_target_group(vpc_id)

# Attach Load Balancer
load_balancer_arn = attach_load_balancer(target_group_arn)

# Register the EC2 instance with the Target Group
register_targets(target_group_arn, instance.id)

# Create Auto Scaling Group
create_autoscaling_group()
