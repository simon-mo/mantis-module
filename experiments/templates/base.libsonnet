{ config(name, cmdline):: 
    assert std.length(name) > 0;
    assert std.length(cmdline) > 0;
    assert std.isArray(cmdline);
    
    {
  apiVersion: 'batch/v1',
  kind: 'Job',
  metadata: {
    name: name,
  },
  spec: {
    backoffLimit: 0,
    template: {
      metadata: {
        labels: {
          app: 'mantis-controller',
        },
      },
      spec: {
        serviceAccountName: 'controller-role',
        restartPolicy: 'Never',
        containers: [
          {
            name: 'controller',
            imagePullPolicy: 'Always',
            image: 'fissure/py:latest',
            command: [
              'mantis',
              'run-controller',
            ] + cmdline,
            volumeMounts: [
              {
                mountPath: '/data',
                name: 'data-volume',
              },
            ],
            env: [
              {
                name: 'AWS_ACCESS_KEY_ID',
                valueFrom: {
                  secretKeyRef: {
                    name: 'aws-s3-creds',
                    key: 'AWS_ACCESS_KEY_ID',
                  },
                },
              },
              {
                name: 'AWS_SECRET_ACCESS_KEY',
                valueFrom: {
                  secretKeyRef: {
                    name: 'aws-s3-creds',
                    key: 'AWS_SECRET_ACCESS_KEY',
                  },
                },
              },
              {
                name: 'SLACK_ENDPOINT',
                valueFrom: {
                  secretKeyRef: {
                    name: 'slack-endpoint',
                    key: 'SLACK_ENDPOINT',
                  },
                },
              },
            ],
            resources: {
              requests: {
                'mantis.com/concurrent': 1,
              },
              limits: {
                'mantis.com/concurrent': 1,
              },
            },
          },
        ],
        initContainers: [
          {
            name: 'copy-traces',
            image: 'fissure/traces:latest',
            command: [
              'sh',
              '-c',
              'cp -r /data/* /trace-data/',
            ],
            volumeMounts: [
              {
                mountPath: '/trace-data',
                name: 'data-volume',
              },
            ],
          },
        ],
        volumes: [
          {
            name: 'data-volume',
            hostPath: {
              path: '/trace-data',
              type: 'DirectoryOrCreate',
            },
          },
        ],
      },
    },
  },
} }
