# Use the official Ubuntu 22.04 base image
FROM ubuntu:23.04

# Update the package list and install necessary dependencies
RUN apt-get update && \
    apt-get install -y python3 python3-pip iproute2 iputils-ping

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install Flask and other dependencies
RUN pip3 install --break-system-packages Flask

# Expose the port on which Flask will run
EXPOSE 5000

# Define the command to run your application
CMD ["python3", "app.py"]
