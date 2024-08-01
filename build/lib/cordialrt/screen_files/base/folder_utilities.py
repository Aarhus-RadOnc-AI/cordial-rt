"""Functions for dealing with folders and files"""

import glob
import os
import pydicom
from collections import deque

def list_files_in_folder(path):
    files = glob.glob(path+'/*')
    
    print('files:', files)
    return None

def fast_scandir(dir):
    subfolders= [f.path for f in os.scandir(dir) if f.is_dir()]
    for dir in list(subfolders):
        subfolders.extend(fast_scandir(dir))
    return subfolders

def folder_file_prefix_status(folder_path):
        prefix_file_paths = dict()
        dicom_file_paths = glob.glob(folder_path+"*.dcm")

        for file_path in dicom_file_paths: 
            prefix = file_path[len(folder_path):len(folder_path)+2]
            try: 
                prefix_file_paths[prefix].append(file_path)
            except:
                prefix_file_paths[prefix] = [file_path]
        
        print('DICOM files in folder:',folder_path, len(dicom_file_paths))
        for key in prefix_file_paths:
            print (f'Number of {key} files:', len(prefix_file_paths[key]))
            # connec to structure set 
        return(prefix_file_paths)

def load_dicom_files_in_folder(folder_path):
    dicom_file_paths = glob.glob(folder_path+"*.dcm")
    #dicom_files = deque()
    dicom_files = dict()

    for file_path in dicom_file_paths:
        dicom_file = pydicom.dcmread(file_path, stop_before_pixels = True)
        dicom_files[file_path] = dicom_file
        
    return(dicom_files)