""" Core classes used in the screening functions """
import pydicom
import numpy as np
import glob

class Patient:
    """Patient class holding all treatment data related to that patient_id """
    def __init__(self, patient_id):
        self.patient_id = patient_id
        self.studies = dict()

    def add_study(self, study):
        self.studies[study.study_id] = study

    @property
    def id (self):
        return(self.patient_id)

    @property 
    def one_study (self):
        if len(self.studies) == 1:
            return(self.studies[list(self.studies.keys())[0]])
        else:    
            return(None)

    def plans_by_name(plan_name):
        plans = list()
        for study in self.studies:
            for plan in study.plans:
                if plan.RTPlanLabel == plan_name:
                    plans.append(plan)
        return plans

class Study:
    def __init__(self, study_id):
        self.study_id = study_id
        self.cts = dict()  
        self.plans = dict()
        self.structures = dict()
        self.doses = dict()  
        self.other_files = dict() 

    @property 
    def one_plan (self):
        if len(self.plans) == 1:
            return(self.plans[list(self.plans.keys())[0]])
        else:    
            return(None)

    @property 
    def one_structure(self):
        if len(self.structures) == 1:
            return(self.structures[list(self.structures.keys())[0]])
        else:    
            return(None)        

    @property 
    def one_dose(self):
        if len(self.doses) == 1:
            return(self.doses[list(self.doses.keys())[0]])
        else:    
            return(None)
    
    def load_dicom_files(self, dicom_files):
        for path, dicom_file in dicom_files.items():
            if dicom_file.StudyInstanceUID == self.study_id:

                if dicom_file.Modality == 'CT':
                    if dicom_file.SOPInstanceUID in self.cts.keys():
                        print('CT already in study')
                    else:
                        self.cts[dicom_file.SOPInstanceUID] = {'path' : path, 'data_set': dicom_file}          
                elif dicom_file.Modality == 'RTPLAN':
                    if dicom_file.SOPInstanceUID in self.plans.keys():
                        print('Plan already in study')
                    else: 
                        self.plans[dicom_file.SOPInstanceUID] = {'path' : path, 'data_set': dicom_file}    
                elif dicom_file.Modality == 'RTDOSE':
                    if dicom_file.SOPInstanceUID in self.doses.keys():
                        print('Dose already in study')
                    else:    
                        self.doses[dicom_file.SOPInstanceUID] = {'path' : path, 'data_set': dicom_file}      
                elif dicom_file.Modality == 'RTSTRUCT':
                    if dicom_file.SOPInstanceUID in self.structures.keys():
                        print('Struct already in study')
                    else:    
                        self.structures[dicom_file.SOPInstanceUID] = {'path' : path, 'data_set': dicom_file}       
                else:
                    if dicom_file.SOPInstanceUID in self.other_files.keys():
                        print('Other file already in study')
                    else:    
                        self.other_files[dicom_file.SOPInstanceUID] = {'path' : path, 'data_set': dicom_file}    
            else: 
                pass   
                 
        return(None)

    def load_pixel_data_for_cts(self):
        if len(self.cts) == 0:
            pass
        else:
            for uid, dicom_file in self.cts.items():
                self.cts[uid] = pydicom.dcmread(dicom_file.filename, stop_before_pixels = False)

    def plans_by_name(plan_name):
        plans = list()
        for plan in study.plans:
            if plan.RTPlanLabel == plan_name:
                plans.append(plan)
        return plans
