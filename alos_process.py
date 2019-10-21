#!/usr/bin/env python3

import logging
import os
import shutil
import subprocess

import boto3
from osgeo import gdal
from rio_cogeo.cogeo import cog_translate

from ruamel.yaml import YAML

from get_uuid import odc_uuid
import datetime
import rasterio


# COG profile
cog_profile = {
    'driver': 'GTiff',
    'interleave': 'pixel',
    'tiled': True,
    'blockxsize': 512,
    'blockysize': 512,
    'compress': 'DEFLATE',
    'predictor': 2,
    'zlevel': 9,
    'nodata': 0
}


def setup_logging():
    logging.basicConfig(level=logging.INFO,
    format='%(asctime)s %(levelname)-8s %(message)s',
    datefmt='%m-%d %H:%M'                    
    )
    logging.getLogger('boto3').setLevel(logging.CRITICAL)
    logging.getLogger('botocore').setLevel(logging.CRITICAL)
    logging.getLogger('s3transfer').setLevel(logging.CRITICAL)
    logging.getLogger('urllib3').setLevel(logging.CRITICAL)
    logging.getLogger('rasterio').setLevel(logging.CRITICAL)


setup_logging()


def run_command(command, work_dir):
    """
    A simple utility to execute a subprocess command
    """
    subprocess.check_call(command, cwd=work_dir)


def make_directories(directories):
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)


def delete_directories(directories):
    logging.info("Deleting directories...")
    for directory in directories:
        for the_file in os.listdir(directory):
            a_file = os.path.join(directory, the_file)
            if os.path.isfile(a_file):
                logging.debug("Deleting file: {}".format(a_file))
                os.unlink(a_file)
            elif os.path.isdir(a_file):
                logging.debug("Deleting directory: {}".format(a_file))
                shutil.rmtree(a_file)


def download_files(WORKDIR, OUTDIR, YEAR, TILE):
    if int(YEAR) > 2010:
        filename = "{}_{}_MOS_F02DAR.tar.gz".format(TILE, YEAR[-2:])
    else:
        filename = "{}_{}_MOS.tar.gz".format(TILE, YEAR[-2:])

    logging.info("Downloading file: {}".format(filename))
    if int(YEAR) > 2010:
        ftp_location = "ftp://ftp.eorc.jaxa.jp/pub/ALOS-2/ext1/PALSAR-2_MSC/25m_MSC/{}/{}".format(
            YEAR, filename
        )
    else:
        ftp_location = "ftp://ftp.eorc.jaxa.jp/pub/ALOS/ext1/PALSAR_MSC/25m_MSC/{}/{}".format(
            YEAR, filename
        )
    tar_file = os.path.join(WORKDIR, filename)

    try:
        if not os.path.exists(tar_file):
            run_command(['wget', '-q', ftp_location], WORKDIR)
        else:
            logging.info("Skipping download, file already exists")
        logging.info("Untarring file")
        run_command(['tar', '-xf', filename], WORKDIR)
    except subprocess.CalledProcessError:
        print('File does not exist')


def combine_cog(PATH, OUTPATH, TILE, YEAR):
    logging.info("Combining GeoTIFFs")
    bands = ['HH', 'HV', 'linci', 'date', 'mask']
    output_cogs = []

    gtiff_abs_path = os.path.abspath(PATH)
    outtiff_abs_path = os.path.abspath(OUTPATH)

    for band in bands:
        # Find all the files
        all_files = []
        for path, subdirs, files in os.walk(gtiff_abs_path):
            for fname in files:
                if int(YEAR) > 2010:
                    if '_{}_'.format(band) in fname and not fname.endswith('.hdr'):
                        in_filename = os.path.join(path, fname)
                        all_files.append(in_filename)
                else:
                    if '_{}'.format(band) in fname and not fname.endswith('.hdr'):
                        in_filename = os.path.join(path, fname)
                        all_files.append(in_filename)


        # Create the VRT
        logging.info("Building VRT for {} with {} files found".format(
            band, len(all_files)))
        vrt_path = os.path.join(gtiff_abs_path, '{}.vrt'.format(band))
        if int(YEAR)>2010:
            cog_filename = os.path.join(outtiff_abs_path, '{}_{}_sl_{}_F02DAR.tif'.format(TILE, YEAR[-2:], band))
        else:
            cog_filename = os.path.join(outtiff_abs_path, '{}_{}_sl_{}.tif'.format(TILE, YEAR[-2:], band))
        vrt_options = gdal.BuildVRTOptions()
        gdal.BuildVRT(
            vrt_path,
            all_files,
            options=vrt_options
        )

        # Default to nearest resampling
        resampling = 'nearest'
        if band in ['HH', 'HV', 'linci']:
            resampling = 'average'

        cog_translate(
            vrt_path,
            cog_filename,
            cog_profile,
            config={"GDAL_TIFF_OVR_BLOCKSIZE": "512"},
            overview_level=5,
            overview_resampling=resampling
        )

        output_cogs.append(cog_filename)

    # Return the list of written files
    return output_cogs


def get_ref_points(OUTDIR, YEAR, TILE):
    if int(YEAR)>2010:
        datasetpath = os.path.join(OUTDIR, '{}_{}_sl_HH_F02DAR.tif'.format(TILE, YEAR[-2:]))
    else:
        datasetpath = os.path.join(OUTDIR, '{}_{}_sl_HH.tif'.format(TILE, YEAR[-2:]))
    dataset = rasterio.open(datasetpath)
    bounds = dataset.bounds
    return {
        'll': {'x': bounds[0], 'y': bounds[1]},
        'lr': {'x': bounds[2], 'y': bounds[1]},
        'ul': {'x': bounds[0], 'y': bounds[3]},
        'ur': {'x': bounds[2], 'y': bounds[3]},
    }


def get_coords(OUTDIR, YEAR, TILE):
    if int(YEAR)>2010:
        datasetpath = os.path.join(OUTDIR, '{}_{}_sl_HH_F02DAR.tif'.format(TILE, YEAR[-2:]))
    else:
        datasetpath = os.path.join(OUTDIR, '{}_{}_sl_HH.tif'.format(TILE, YEAR[-2:]))
    dataset = rasterio.open(datasetpath)
    bounds = dataset.bounds
    return {
        'll': {'lat': bounds[1], 'lon': bounds[0]},
        'lr': {'lat': bounds[1], 'lon': bounds[2]},
        'ul': {'lat': bounds[3], 'lon': bounds[0]},
        'ur': {'lat': bounds[3], 'lon': bounds[2]},
    }


def write_yaml(OUTDIR, YEAR, TILE):
    logging.info("Writing yaml.")
    yaml_filename = os.path.join(OUTDIR, "{}_{}.yaml".format(TILE, YEAR))
    geo_ref_points = get_ref_points(OUTDIR, YEAR, TILE)
    coords = get_coords(OUTDIR, YEAR, TILE)
    creation_date = datetime.datetime.today().strftime("%Y-%m-%dT%H:%M:%S")
    if int(YEAR) > 2010:
        hhpath = '{}_{}_sl_HH_F02DAR.tif'.format(TILE, YEAR[-2:])
        hvpath = '{}_{}_sl_HV_F02DAR.tif'.format(TILE, YEAR[-2:])
        lincipath = '{}_{}_sl_linci_F02DAR.tif'.format(TILE, YEAR[-2:])
        maskpath = '{}_{}_sl_mask_F02DAR.tif'.format(TILE, YEAR[-2:])
        datepath = '{}_{}_sl_date_F02DAR.tif'.format(TILE, YEAR[-2:])
        launch_date = "2014-05-24"
    else:
        hhpath = '{}_{}_sl_HH.tif'.format(TILE, YEAR[-2:])
        hvpath = '{}_{}_sl_HV.tif'.format(TILE, YEAR[-2:])
        lincipath = '{}_{}_sl_linci.tif'.format(TILE, YEAR[-2:])
        maskpath = '{}_{}_sl_mask.tif'.format(TILE, YEAR[-2:])
        datepath = '{}_{}_sl_date.tif'.format(TILE, YEAR[-2:])
        launch_date = "2006-01-26"
    metadata_doc = {
        'id': str(odc_uuid('alos', '1', [], YEAR=YEAR, TILE=TILE)),
        'creation_dt': creation_date,
        'product_type': 'gamma0',
        'platform': {'code': 'ALOS/ALOS-2'},
        'instrument': {'name': 'PALSAR/PALSAR-2'},
        'format': {'name': 'GeoTIFF'},
        'extent': {
            'coord': coords,
            'from_dt': "{}-01-01T00:00:01".format(YEAR),
            'center_dt': "{}-06-15T11:00:00".format(YEAR),
            'to_dt': "{}-12-31T23:59:59".format(YEAR),
        },
        'grid_spatial': {
            'projection': {
                'geo_ref_points': geo_ref_points,
                'spatial_reference': 'EPSG:4326',
            }
        },
        'image': {
            'bands': {
                'hh': {
                    'path': hhpath,
                },
                'hv': {
                    'path': hvpath,
                },
                'linci': {
                    'path': lincipath,
                },
                'mask': {
                    'path': maskpath,
                },
                'date': {
                    'path': datepath,
                }
            }
        },
        'lineage': {'source_datasets': {}},
        'property': {
            'launchdate': launch_date,
            'cf': '83.0 dB',
        }
    }

    with open(yaml_filename, 'w') as f:
        yaml = YAML(typ='safe', pure=False)
        yaml.default_flow_style = False
        yaml.dump(metadata_doc, f)

    return yaml_filename


def upload_to_s3(OUTDIR, S3_BUCKET, path, files):
    logging.info("Commencing S3 upload")
    s3r = boto3.resource('s3')
    if S3_BUCKET:
        logging.info("Uploading to {}".format(S3_BUCKET))
        # Upload data
        for out_file in files:
            data = open(out_file, 'rb')
            key = "{}/{}".format(path, os.path.basename(out_file))
            logging.info("Uploading file {} to S3://{}/{}".format(out_file, S3_BUCKET, key))
            s3r.Bucket(S3_BUCKET).put_object(Key=key, Body=data)
    else:
        logging.warning("Not uploading to S3, because the bucket isn't set.")


def run_one(TILE_STRING, WORKDIR, OUTDIR, S3_BUCKET, S3_PATH):
    YEAR = TILE_STRING.split('/')[0]
    TILE = TILE_STRING.split('/')[1]

    path = TILE_STRING
    if S3_PATH:
        path = S3_PATH + '/' + path

    try:
        make_directories([WORKDIR, OUTDIR])
        download_files(WORKDIR, OUTDIR, YEAR, TILE)
        list_of_cogs = combine_cog(WORKDIR, OUTDIR, TILE, YEAR)
        metadata_file = write_yaml(OUTDIR, YEAR, TILE)
        upload_to_s3(OUTDIR, S3_BUCKET, path, list_of_cogs + [metadata_file])
        delete_directories([WORKDIR, OUTDIR])
        # Assume job success here
        return True
    except Exception as e:
        logging.error("Job failed with error {}".format(e))
        return False


if __name__ == "__main__":
    logging.info("Starting default process")
    TILE_STRING = '2017/N25W020'
    S3_BUCKET = 'test-results-deafrica-staging-west'
    S3_PATH = 'alos'
    WORKDIR = 'data/download'
    OUTDIR = 'data/out'

    run_one(TILE_STRING, WORKDIR, OUTDIR, S3_BUCKET, S3_PATH)
