import boto3

# Creating an EC2 instance & installing Nginx
def create_ec2_instance():
    ec2 = boto3.resource('ec2')
    instance = ec2.create_instances(
        ImageId='ami-062cf18d655c0b1e8', 
        MinCount=1,
        MaxCount=1,
        InstanceType='t2.micro',
        KeyName='Gani_reborne',  
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
    print(instance)
    instance[0].wait_until_running()
    instance[0].reload()
    print("EC2 Instance created:", instance[0].id)
    print(instance)
    return instance[0]

instance = create_ec2_instance()
security_groups = instance.security_groups
print("Security Groups:", security_groups)