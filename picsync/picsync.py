import os
import time
import sys
import getopt
import subprocess

def machine_up(hostname):
    response = os.system("ping -c 1 " + hostname)

    response_bool = response == 0

    print(f'Is \'{hostname}\' up: {response_bool}')

    return response_bool

def sync(hostname, username, source, target):
    print('Starting sync...')

    print(f'Source: {source}')
    print(f'Target: {hostname}:{target}')

    password = os.environ.get('SSHPASS_PASSWORD')
    bashCommand = ['sshpass', 
                   '-p', 
                   f'"{password}"', 
                   'rsync', 
                   '-hazL', 
                   '--progress', 
                   '--delete', 
                   '-v', 
                   source, 
                   f'{username}@{hostname}:{target}',
                   '-e',
                   '"ssh -o StrictHostKeyChecking=no"'
    ]

    try:
        subprocess.run(bashCommand, 
                       capture_output=True,
                       check=True)
    except subprocess.CalledProcessError as err:
        print(err.output)
        raise

    print('Sync completed!')

def main(argv):
    hostname = ''
    username = ''
    source = ''
    target = ''
    try:
        opts, args = getopt.getopt(argv, "h:u:s:t:")
      
    except:
        print("Error")
  
    for opt, arg in opts:
        if opt in ['-h']:
            hostname = arg
        elif opt in ['-u']:
            username = arg
        elif opt in ['-s']:
            source = arg
        elif opt in ['-t']:
            target = arg

    while not machine_up(hostname):
        # sleep 10 minutes
        time.sleep(600)
        
    sync(hostname, username, source, target)
        
if __name__ == "__main__":
    main(sys.argv[1:])