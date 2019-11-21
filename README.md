# alos-palsar-to-geotiff
ALOS/ALOS-2 PALSAR/PALSAR-2 Data Wrangling Script. 

Overview
========

This script downloads ALOS tiles from the JAXA FTP and combines them by band, COGs, writes the metadata and uploads to S3. 

Requirements
========

This script requires the following libraries: 

* GDAL < 3.0
* Rasterio
* Boto3 (AWS Python API)


Description of Files
========

# Python files
* `alos_process.py` - Contains the processing chain for the individual tiles. This file contains `run_one()` which takes a tile string, working and output directories and S3 bucket/path information. The `run_one()` process downloads the files (`download_files()`), generates cogs (`combine_cog()`), writes the metadata file (`metadata_file()`), and uploads to S3 (`upload_to_s3()`). 
* `run_job.py` - Contains the code that reads the individual messages from the AWS SQS queue, runs `run_one()` on them abd then deletes messages once they are completed. 
* `filenames.py` - Generates the tiles from a UL and LR bounding box of Africa.
* `add_to_queue.py` - Adds the tiles from `filenames.py` to the AWS SQS queue.
* `get_uuid.py` - An ODC Tools script that generates an unique UUID based on a series of uniquely identifiable specifications. For ALOS the uniqu specifications are year, tile and spacecraft (ALOS or ALOS2). `get_uuid.py` is used within `metadata_file()` in `alos_process.py`

# Docker files
* `Dockerfile` - contains the docker commands to generate the container.
* `requirements.txt` - contains the requirements to build the Docker container

# K8s files
* `*-africa-alos.yaml` - Deployment or pod files for K8s.

How to run
========

# Locally for a single tile
Edit `alos_process.py` to input a specific tile in a YEAR/TILE string as well as S3 information if necessary, else comment out. Run `alos_process.py` 

# Using AWS K8s
Build the docker file using `docker build . --tag ******/alos-cogger` Where `******` is the repository within Dockerhub where you have access.
Push the docker container to DockerHub using `docker push *****/alos-cogger`.
Edit `add_to_queue.py` with the relevant AWS environment variables (queue names, S3 path/key) for your setup. 
Use `add_to_queue.py` to add tiles to queue. 
Edit the pod/deployment yamls with the relevant AWS environment variables.
Deploy a K8s pods/deployment using `kubectl apply -f *-africa-alos.yaml` Where `*` is the `pod` or `deployment`. 
