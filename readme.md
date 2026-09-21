# API Deployment and Usage

Follow these steps to initialize and interact with the translation pipeline in a standard environment.

*   Execute the deployment script to build the Docker images and start the internal network containers:
    ```bash
    ./build_and_deploy.sh
    ```
*   Open a web browser and navigate to the interactive UI at `http://localhost`.
*   Upload a document using the `file` parameter and specify the target language using the `language` form field (default is `polish`). Has to be name of the language, not code.
*   Execute the request to process the document and receive the translated PDF as a direct file download.

---

# Air-Gapped Environment Migration

To deploy the system on a machine without internet access, export the required dependencies from a connected machine and import them to the offline target.

## Export (Online Machine)

*   Save the compiled Docker images to self-contained tar archives using the `docker save` command:
    ```bash
    docker save -o ocr-service.tar ocr-service:latest
    docker save -o translate-service.tar translate-service:latest
    docker save -o api-gateway.tar api-gateway:latest
    ```
*   Verify the required model weights (e.g., the `Hy-MT2-7B` directory) and font assets are fully downloaded to your local filesystem.
*   Compress the model directory and fonts into a portable archive:
    ```bash
    tar -czvf assets.tar.gz ./translate/Hy-MT2-7B ./fonts
    ```

## Import (Offline Machine)

*   Transfer the exported `.tar` and `.tar.gz` archives to the offline machine using physical media.
*   Load the Docker images directly into the local Docker daemon to bypass image registry pulls:
    ```bash
    docker load -i ocr-service.tar
    docker load -i translate-service.tar
    docker load -i api-gateway.tar
    ```
*   Extract the model and font archives into the persistent volume directory referenced by your deployment configuration:
    ```bash
    tar -xzvf assets.tar.gz
    ```
*   Run `build_and_deploy.sh` to start the initialized services utilizing the locally cached images and assets.