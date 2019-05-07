# Copyright 2019 DataStax, Inc. All rights reserved.

import common
import yaml
import random
import string

URL_BASE = 'https://www.googleapis.com/compute/v1/projects/'

def GenerateConfig(context):
  """Generates the configuration."""

  config = {'resources': []}

  # Release tag for ddac-gcp-install tarball in a GCP bucket
  release = 'master'
  # DDAC release tarball
  ddac_tarball = 'ddac-5.1.12-bin.tar.gz'
  # DDAC GCP marketplace bucket
  ddac_gcp_mp_bucket = 'ddac-gcp-marketplace'
  # ddac-gcp-install bucket item name
  ddac_repo = 'ddac-gcp-install'
  # ddac-gcp-install release
  ddac_repo_dir = ddac_repo + '-' + release
  ddac_install_pkg = ddac_repo_dir + '.tar.gz'
  ddac_install_pkg_uri = ddac_gcp_mp_bucket + '/' + ddac_install_pkg

  deployment = context.env['deployment']
  cluster_size = str(context.properties['clusterSize'])
  # GCP Instance Templates
  dse_seed_0_it = deployment + '-dse-seed-0-it'
  dse_seed_1_it = deployment + '-dse-seed-1-it'
  dse_non_seed_it = deployment + '-dse-non-seed-it'
  dev_ops_it = deployment + '-dev-ops-it'
  # GCP Instance Group Manager
  dse_seed_0_igm = deployment + '-dse-seed-0-igm'
  dse_seed_1_igm = deployment + '-dse-seed-1-igm'
  dse_non_seed_pool_igm = deployment + '-dse-non-seed-pool-igm'
  dev_ops_igm = deployment + '-dev-ops-igm'

  # GCP subnet
  region = context.properties['region']
  # Hardcode DDAC subnet's CIDR to 10.8.0.0/16
  cidr = '10.8.0.0/16'
  dse_subnet = deployment + '-dse-subnet-' + region
  ddac_network_name = context.properties['network']
  ddac_network = URL_BASE + context.env['project'] + '/global/networks/' + ddac_network_name
  
  # DDAC firewall
  ddac_fw = deployment + '-ddac-fw'  

  # DSE seed 0 and seed 1 IP addresses based on user provided CIDR
  # In GCP, auto IP address assignment for first and second IP addresses are .2 and .3
  int_ip_octet = cidr.split(".")
  int_ip_prefix = int_ip_octet[0] + "."  + int_ip_octet[1] + "." + int_ip_octet[2] 
  dse_seed_0_ip_addr = int_ip_prefix + ".2"
  dse_seed_1_ip_addr = int_ip_prefix + ".3"
  seeds = dse_seed_0_ip_addr + ',' + dse_seed_1_ip_addr

  # DSE cluster info
  cluster_name = context.properties['clusterName']
  cluster_size = str(context.properties['clusterSize'])
  dc_name = context.properties['dcName']

  # 400 seconds more than the GCP marketplace 60 minsutes max timeout
  ddac_timeout = 4000

  # Generate a random bucket name for each deployment
  bucket_suffix = ''.join([random.choice(string.ascii_lowercase + string.digits) for n in xrange(10)])
  deployment_bucket = context.env['deployment'] + '-deployment-bucket-' + bucket_suffix

  # Check DDAC cluster ready script
  check_ddac_cluster_ready_script= '''
  #!/usr/bin/env bash
  cluster_size=''' + cluster_size + '''
  size=`/usr/share/dse/bin/nodetool status | grep -o 'UN' | wc -l`
  if [ $size -ne $cluster_size ]; then
     echo The Current DDAC cluster size is $size
     echo DDAC cluster size has not reached $cluster_size yet
     exit 1
  fi
  '''

  # DSE seed node startup script
  dse_seed_0_script = '''
      #!/usr/bin/env bash

      # Install Java
      echo "Performing package OpenJDK install"
      # check for lock
      echo -e "Checking if apt/dpkg running, start: $(date +%r)"
      while ps -A | grep -e apt -e dpkg >/dev/null 2>&1; do sleep 10s; done;
      echo -e "No other procs: $(date +%r)"
      apt-get -y update
      apt-get -y install openjdk-8-jdk

      pushd ~ubuntu
      # Install and configure the dse seed 0
      # Download ddac-gcp-install module
      ddac_install_pkg_uri=''' + ddac_install_pkg_uri + '''
      gsutil cp gs://$ddac_install_pkg_uri .
      ddac_install_pkg=''' + ddac_install_pkg + '''
      tar -xvf $ddac_install_pkg
      ddac_repo_dir=''' +  ddac_repo_dir + '''
      ddac_repo=''' + ddac_repo + '''
      # Standardize repo name: ddac-gcp-install
      mv $ddac_repo_dir $ddac_repo
      ddac_tarball=''' +  ddac_tarball + '''
      mv $ddac_repo/$ddac_tarball .

      # Deploy DDAC
      cluster_name=''' + cluster_name + '''
      dc_name=''' + dc_name + '''
      seeds=''' + seeds + '''
      ./$ddac_repo/deploy-dse.sh $cluster_name $dc_name $seeds

      # Send flag to start seed 1 install 
      deployment_bucket=''' + deployment_bucket + '''
      echo seed_0 > seed_0
      gsutil cp ./seed_0 gs://$deployment_bucket/
      popd
      '''

  dse_seed_1_script = '''

      # Install Java
      echo "Performing package OpenJDK install"
      # check for lock
      echo -e "Checking if apt/dpkg running, start: $(date +%r)"
      while ps -A | grep -e apt -e dpkg >/dev/null 2>&1; do sleep 10s; done;
      echo -e "No other procs: $(date +%r)"
      apt-get -y update
      apt-get -y install openjdk-8-jdk

      pushd ~ubuntu
      deployment_bucket=''' + deployment_bucket + '''
      gsutil cp gs://$deployment_bucket/seed_0 .
      while [ $? -ne 0 ]
      do
          sleep 10s
          gsutil cp gs://$deployment_bucket/seed_0 . 
      done

      # Install and configure the dse seed 1
      # Download ddac-gcp-install module
      ddac_install_pkg_uri=''' + ddac_install_pkg_uri + '''
      gsutil cp gs://$ddac_install_pkg_uri .
      ddac_install_pkg=''' + ddac_install_pkg + '''
      tar -xvf $ddac_install_pkg
      ddac_repo_dir=''' +  ddac_repo_dir + '''
      ddac_repo=''' + ddac_repo + '''
      # Standardize repo name: ddac-gcp-install
      mv $ddac_repo_dir $ddac_repo
      ddac_tarball=''' +  ddac_tarball + '''
      mv $ddac_repo/$ddac_tarball .

      # Deploy DDAC
      cluster_name=''' + cluster_name + '''
      dc_name=''' + dc_name + '''
      seeds=''' + seeds + '''
      ./$ddac_repo/deploy-dse.sh $cluster_name $dc_name $seeds

      # Send flag to start non-seed nodes install
      echo seed_1 > seed_1
      gsutil cp ./seed_1 gs://$deployment_bucket/

      # Wait until all DSE nodes are up and have joined the cluster:
      cluster_size=''' + cluster_size + '''
      size=`/usr/share/dse/bin/nodetool status | grep -o 'UN' | wc -l`
      while [ $size -lt $cluster_size ]; do
          echo The Current DSE cluster size is $size
          echo Keep looping until the DSE cluster size reaches $cluster_size
          sleep 10s
          size=`/usr/share/dse/bin/nodetool status | grep -o 'UN' | wc -l`
      done

      # Once all up and joined the cluster, ready to start dev ops vm install
      echo dev_ops > dev_ops
      gsutil cp ./dev_ops gs://$deployment_bucket/
      popd
      '''

  dse_non_seed_script = '''
      #!/usr/bin/env bash

      # Install Java
      echo "Performing package OpenJDK install"
      # check for lock
      echo -e "Checking if apt/dpkg running, start: $(date +%r)"
      while ps -A | grep -e apt -e dpkg >/dev/null 2>&1; do sleep 10s; done;
      echo -e "No other procs: $(date +%r)"
      apt-get -y update
      apt-get -y install openjdk-8-jdk

      pushd ~ubuntu
      deployment_bucket=''' + deployment_bucket + '''
      gsutil cp gs://$deployment_bucket/seed_1 .
      while [ $? -ne 0 ]
      do
          sleep 10s
          gsutil cp gs://$deployment_bucket/seed_1 .        
      done

      # Install and conifgure non-seed node
      # Download ddac-gcp-install module
      ddac_install_pkg_uri=''' + ddac_install_pkg_uri + '''
      gsutil cp gs://$ddac_install_pkg_uri .
      ddac_install_pkg=''' + ddac_install_pkg + '''
      tar -xvf $ddac_install_pkg
      ddac_repo_dir=''' +  ddac_repo_dir + '''
      ddac_repo=''' + ddac_repo + '''
      # Standardize repo name: ddac-gcp-install
      mv $ddac_repo_dir $ddac_repo
      ddac_tarball=''' +  ddac_tarball + '''
      mv $ddac_repo/$ddac_tarball .

      # Deploy DDAC
      cluster_name=''' + cluster_name + '''
      dc_name=''' + dc_name + '''
      seeds=''' + seeds + '''
      ./$ddac_repo/deploy-dse.sh $cluster_name $dc_name $seeds
      popd
      '''

  dev_ops_script = '''
      #!/usr/bin/env bash

      # Install Java
      echo "Performing package OpenJDK install"
      # check for lock
      echo -e "Checking if apt/dpkg running, start: $(date +%r)"
      while ps -A | grep -e apt -e dpkg >/dev/null 2>&1; do sleep 10s; done;
      echo -e "No other procs: $(date +%r)"
      apt-get -y update
      apt-get -y install openjdk-8-jdk

      pushd ~ubuntu
      deployment_bucket=''' + deployment_bucket + '''

      gsutil cp gs://$deployment_bucket/dev_ops .
      while [ $? -ne 0 ]
      do
          sleep 10s
          gsutil cp gs://$deployment_bucket/dev_ops .
      done

      # install and configure the dev ops vm below
      echo install Dev Ops VM software components
      sleep 120
      gsutil rm gs://$deployment_bucket/*
      popd
      '''
 
  # Create a dictionary which represents the resources
  # (Intstance Template, IGM, etc.)
  resources = [
      {
        'name': deployment_bucket,
        'type': 'storage.v1.bucket',
        'properties': {
            'name': deployment_bucket,
            'lifecycle': {
          	"rule": [ {
      		    "action": {"type": "Delete"},
      		    "condition": {  "age": 1 }
                }]
            }
        }
      },
      {
          'name': ddac_network_name,
          'type': 'compute.v1.network',
          'properties': {
                'name': ddac_network_name,
                'description': 'VPC network for DDAC cluster deployment',
                'autoCreateSubnetworks': False,
          }
      },
      {
          'name': dse_subnet,
          'type': 'compute.v1.subnetwork',
          'properties': {
                'name': dse_subnet,
                'description': 'Subnetwork of %s in %s' % (ddac_network_name, dse_subnet),
                'ipCidrRange': cidr,
                'region': region,
                'network': ddac_network,
          },
          'metadata': {
                'dependsOn': [
                     ddac_network_name,
                ]
          }
      },
      {
          'name': ddac_fw,
          'type': 'compute.v1.firewalls',
          'properties': {
                'name': ddac_fw,
                'description': 'firewall rule for DDAC cluster',
                'network': ddac_network,
                'sourceRanges': ["0.0.0.0/0"],
                'allowed': [{
                       'IPProtocol': 'TCP',
                       'ports': ["0-65535"]
	            },
                    {
                       'IPProtocol': 'UDP',
                       'ports': ["0-65535"]
                    }]
          },
          'metadata': {
                'dependsOn': [
                    ddac_network_name,
                ]
          }
      },
      {
         'name': 'software-status',
         'type': 'software_status.py',
         'properties': {
             'timeout': ddac_timeout,
             'waiterDependsOn': [
                 dse_seed_0_igm
             ]
         }
      },
      {
         'name': 'ddac-software-status-script',
         'type': 'software_status_script.py',
         'properties': {
             'initScript': dse_seed_0_script,
             'checkScript': check_ddac_cluster_ready_script
         }
      },
      {
          # Create the Instance Template
          'name': dse_seed_0_it,
          'type': 'compute.v1.instanceTemplate',
          'properties': {
              'properties': {
                  'machineType':
                      context.properties['machineType'],
                  'networkInterfaces': [{
                      'network': ddac_network,
                      'subnetwork': '$(ref.%s.selfLink)' % dse_subnet,
                      'accessConfigs': [{
                          'name': 'External NAT',
                          'type': 'ONE_TO_ONE_NAT'
                      }]
                  }],
                  'disks': [{
                      'deviceName': 'boot-disk',
                      'type': 'PERSISTENT',
                      'boot': True,
                      'autoDelete': True, 
                      'initializeParams': {
                          'sourceImage':
                            URL_BASE + 'datastax-public/global/images/datastax-enterprise-ubuntu-1604-xenial-v20180824'
                      }
                    }, 
		    {
                      'deviceName': 'vm-data-disk',
                      'type': 'PERSISTENT',
                      'boot': False,
                      'autoDelete': True,
                      'initializeParams': {
                          'diskType': context.properties['dataDiskType'],
                          'diskSizeGb': context.properties['dataDiskSize']
                      }
                    }
                  ],
                  'serviceAccounts': [{
                     'email': 'default',
                     'scopes': ['https://www.googleapis.com/auth/compute', 'https://www.googleapis.com/auth/cloudruntimeconfig', 'https://www.googleapis.com/auth/devstorage.full_control']
                  }],
                  'metadata': {
                      'dependsOn': [
                          dse_subnet,
                      ],
                      'items': [ {
                          'key': 'startup-script',
                          'value': '$(ref.ddac-software-status-script.startup-script)'
                      },
                      {
                          'key': 'status-config-url',
                          'value': '$(ref.software-status.config-url)'   
                      },
                      {
                          'key': 'status-variable-path',
                          'value': '$(ref.software-status.variable-path)'
                      },
                      {
                          'key': 'status-uptime-deadline',
                          'value': ddac_timeout
                      }]
                  }
              }
          }
      },
      {
          # Create the Instance Template
          'name': dse_seed_1_it,
          'type': 'compute.v1.instanceTemplate',
          'properties': {
              'properties': {
                  'machineType':
                      context.properties['machineType'],
                  'networkInterfaces': [{
                      'network': ddac_network,
                      'subnetwork': '$(ref.%s.selfLink)' % dse_subnet,
                      'accessConfigs': [{
                          'name': 'External NAT',
                          'type': 'ONE_TO_ONE_NAT'
                      }]
                  }],
                  'disks': [{
                      'deviceName': 'boot-disk',
                      'type': 'PERSISTENT',
                      'boot': True,
                      'autoDelete': True,
                      'initializeParams': {
                          'sourceImage':
                            URL_BASE + 'datastax-public/global/images/datastax-enterprise-ubuntu-1604-xenial-v20180824'
                      }
                    },
                    {
                      'deviceName': 'vm-data-disk',
                      'type': 'PERSISTENT',
                      'boot': False,
                      'autoDelete': True,
                      'initializeParams': {
                          'diskType': context.properties['dataDiskType'],
                          'diskSizeGb': context.properties['dataDiskSize']
                      }
                    }
                  ],
                  'serviceAccounts': [{
                     'email': 'default',
                     'scopes': ['https://www.googleapis.com/auth/compute', 'https://www.googleapis.com/auth/cloudruntimeconfig', 'https://www.googleapis.com/auth/devstorage.full_control']
                  }],
                  'metadata': {
                      'dependsOn': [
                          dse_subnet,
                      ],
                      'items': [ {
                          'key': 'startup-script',
                          'value': dse_seed_1_script
                      }]
                  }
              }
          }
      },
      {
          # Create the Instance Template
          'name': dse_non_seed_it,
          'type': 'compute.v1.instanceTemplate',
          'properties': {
              'properties': {
                  'machineType':
                      context.properties['machineType'],
                  'networkInterfaces': [{
                      'network': ddac_network,
                      'subnetwork': '$(ref.%s.selfLink)' % dse_subnet,
                      'accessConfigs': [{
                          'name': 'External NAT',
                          'type': 'ONE_TO_ONE_NAT'
                      }]
                  }],
                  'disks': [{
                      'deviceName': 'boot-disk',
                      'type': 'PERSISTENT',
                      'boot': True,
                      'autoDelete': True,
                      'initializeParams': {
                          'sourceImage':
                            URL_BASE + 'datastax-public/global/images/datastax-enterprise-ubuntu-1604-xenial-v20180824'
                      }
                    },
                    {
                      'deviceName': 'vm-data-disk',
                      'type': 'PERSISTENT',
                      'boot': False,
                      'autoDelete': True,
                      'initializeParams': {
                          'diskType': context.properties['dataDiskType'],
                          'diskSizeGb': context.properties['dataDiskSize']
                      }
                    }
                  ],
                  'serviceAccounts': [{
                     'email': 'default',
                     'scopes': ['https://www.googleapis.com/auth/compute', 'https://www.googleapis.com/auth/cloudruntimeconfig', 'https://www.googleapis.com/auth/devstorage.full_control']
                  }],
                  'metadata': {
                      'dependsOn': [
                          dse_subnet,
                      ],
                      'items': [ {
                          'key': 'startup-script',
                          'value': dse_non_seed_script
                      }]
                  }
              }
          }
      },
      {   
          # Create the Instance Template
          'name': dev_ops_it,
          'type': 'compute.v1.instanceTemplate',
          'properties': {
              'properties': {
                  'machineType':
                      context.properties['machineType'],
                  'networkInterfaces': [{
                      'network': ddac_network,
                      'subnetwork': '$(ref.%s.selfLink)' % dse_subnet,
                      'accessConfigs': [{
                          'name': 'External NAT',
                          'type': 'ONE_TO_ONE_NAT'
                      }]
                  }],
                  'disks': [{
                      'deviceName': 'boot-disk',
                      'type': 'PERSISTENT',
                      'boot': True, 
                      'autoDelete': True, 
                      'initializeParams': {
                          'sourceImage':
                            URL_BASE + 'datastax-public/global/images/datastax-enterprise-ubuntu-1604-xenial-v20180824'
                      }
                    },
                    { 
                      'deviceName': 'vm-data-disk',
                      'type': 'PERSISTENT',
                      'boot': False,
                      'autoDelete': True, 
                      'initializeParams': {
                          'diskType': context.properties['dataDiskType'],
                          'diskSizeGb': context.properties['dataDiskSize']
                      }
                    }
                  ],
                  'serviceAccounts': [{
                     'email': 'default',
                     'scopes': ['https://www.googleapis.com/auth/compute', 'https://www.googleapis.com/auth/cloudruntimeconfig', 'https://www.googleapis.com/auth/devstorage.full_control']
                  }],
                  'metadata': {
                      'dependsOn': [
                          dse_subnet,
                      ],
                      'items': [ {
                          'key': 'startup-script',
                          'value': dev_ops_script
                      }]
                  }
              }
          }
      },
      {
          # Instance Group Manager
          'name': dse_seed_0_igm,
          'type': 'compute.v1.regionInstanceGroupManager',
          'properties': {
              'region': region,
              'baseInstanceName': deployment + '-dse',
              'instanceTemplate': '$(ref.%s.selfLink)' % dse_seed_0_it,
              'targetSize': 1
          }
      },
      {   
          # Instance Group Manager
          'name': dse_seed_1_igm,
          'type': 'compute.v1.regionInstanceGroupManager',
          'properties': {
              'region': region,
              'baseInstanceName': deployment + '-instance',
              'instanceTemplate': '$(ref.%s.selfLink)' % dse_seed_1_it,
              'targetSize': 1
          },
          'metadata': {
              'dependsOn': [
                   dse_seed_0_igm,
              ]
          }
      },
      {
          # Instance Group Manager
          'name': dse_non_seed_pool_igm,
          'type': 'compute.v1.regionInstanceGroupManager',
          'properties': {
              'region': region,
              'baseInstanceName': deployment + '-instance',
              'instanceTemplate': '$(ref.%s.selfLink)' % dse_non_seed_it,
              'targetSize': context.properties['clusterSize'] - 2
          },
          'metadata': {
              'dependsOn': [
                   dse_seed_1_igm,
              ]
          }
      },
      {
          # Instance Group Manager
          'name': dev_ops_igm,
          'type': 'compute.v1.regionInstanceGroupManager',
          'properties': {
              'region': region,
              'baseInstanceName': deployment + '-instance',
              'instanceTemplate': '$(ref.%s.selfLink)' % dev_ops_it,
              'targetSize': 1
          },
          'metadata': {
              'dependsOn': [
                   dse_non_seed_pool_igm,
              ]
          }
      }
  ]

  config['resources'] = resources
  outputs = [
        {
            'name': 'project',
            'value': context.env['project']
        },
        {
            'name': 'region',
            'value': region
        },
        {
            'name': 'clusterName',
            'value': cluster_name
        }
  ]
  config['outputs'] = outputs

  return yaml.dump(config)

