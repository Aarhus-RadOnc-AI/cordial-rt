"""Defintion of DicomFile class used only in the screening"""

import pydicom

class DicomFile:
    def __init__(self, file_path, dicom_dataset = None):     
        self.file_path = file_path
        if dicom_dataset is not None:
            self.data_set = dicom_dataset

    def read_data(self, stop_before_pixels = True):
        if self.file_path:
            self.data_set = pydicom.dcmread(self.file_path, stop_before_pixels = stop_before_pixels)
        else:
            print("No path for DICOM")

    