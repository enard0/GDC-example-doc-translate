# Document Translation System

## Prerequisites
To run this software, you need the following tools and environment:
* Docker
* Linux or WSL
* A machine with internet access for the initial setup

## API Deployment and Usage
Follow these steps to initialize and interact with the translation pipeline in a standard environment:

1. Execute the deployment script to build and start the services:
   ```bash
   ./build_and_deploy.sh
   ```
2. Open a web browser and navigate to the interactive UI at `http://localhost`.
3. Upload a document and specify the target language using the form fields.
4. Execute the request to process the document and receive the translated PDF as a direct file download.

## Air-Gapped Environment Migration
Follow these steps to create a portable package that can be moved to a machine with no internet access.

### 1. Export (Online Machine)
* Ensure the service has been initialized correctly by following the standard deployment steps.
* Run the provided gathering script:
  ```bash
  ./gather.sh target_directory
  ```
* If the target directory does not exist, the script will create it. 
* The target directory must not contain any files prior to execution.

### 2. Import (Offline Machine)
* Transfer the created folder to the offline machine.
* Run the deployment script to unpack the images and start the service locally:
  ```bash
  ./deploy.sh
  ```