"""Fucntionality for creating a pandas dataframe containing information about all DICOM files in a folder 
we assume only has DICOM data for one patient"""

import time
import os
from collections import deque

import pandas as pd

from cordialrt.screen_files.base.core import Study, Patient
from cordialrt.screen_files.base.folder_utilities import fast_scandir, load_dicom_files_in_folder

def clear_print_output():
    os.system( 'cls' )

def patient_ids_in_dicom_files(dicom_files):
    patient_ids = list()
    for path, dicom_file in dicom_files.items():
        patient_ids.append(dicom_file.PatientID)

    patient_ids = list(dict.fromkeys(patient_ids))
    return(patient_ids)

def study_ids_in_dicom_files(dicom_files):
    study_ids = list()
    for path, dicom_file in dicom_files.items():
        study_ids.append(dicom_file.StudyInstanceUID)

    study_ids = list(dict.fromkeys(study_ids))
    return(study_ids)

def open_dicom_files(parent_folder, max_no_folders = None, folder_paths = False):
    """ Main function to screen dicom files. Returns a dataframe  with patient obejcts that was open correctly and a
    lists of folders that failed checks."""
    
    start_time = time.time()
    print(start_time)
    ok_patients = deque()
    error_messages = list()
    counter = 0

    if not parent_folder: 
        folders = folder_paths
    else:
        if max_no_folders:
            folders = fast_scandir(parent_folder)[0:max_no_folders]
        else:
            folders = fast_scandir(parent_folder)        

    for path in folders: 
        counter = counter +1
        if counter in list(range(0,2100,100)):
            print(f'{counter}/{len(folders)}')
        dicom_files = load_dicom_files_in_folder(path+ '\\')
        study_ids = study_ids_in_dicom_files(dicom_files)
        patient_ids = patient_ids_in_dicom_files(dicom_files)
        data = dict()

        if len(patient_ids) == 1:
            patient = Patient(patient_ids[0])            
            if len(study_ids) == 0: 
                error_messages .append(f'{patient_ids[0]} : No studies in folder {path}')                
            else:
                ok_patients.append(patient)
                for study_id in study_ids:
                    study = Study(study_id)
                    study.load_dicom_files(dicom_files)
                    patient.add_study(study)
        elif len(patient_ids) == 0:
            error_messages.append(f'No patient id found in folder {path}') 
        else:
            error_messages.append(f'{patient_ids} : Multipe patient_ids found in folder {path}') 

  
    # Create Data Frame
    ok_patient_ids = list()
    number_of_studies = list()
    number_of_plans = list()
    number_of_cts = list()
    number_of_structures = list()
    number_of_doses = list()
    plan_names = list()
    patient_objects = list()

    for patient in ok_patients:
        ok_patient_ids.append(patient.patient_id)
        number_of_plans_counter = 0 
        number_of_cts_counter = 0 
        number_of_structures_counter = 0
        number_of_doses_counter = 0
        patient_plan_names = list()
        patient_objects.append(patient)

        for uid, study in patient.studies.items():
            number_of_plans_counter = number_of_plans_counter + len(study.plans)
            number_of_cts_counter = number_of_cts_counter + len(study.cts)
            number_of_structures_counter  = number_of_structures_counter + len(study.structures)
            number_of_doses_counter  = number_of_doses_counter  + len(study.doses)

            for key, plan in study.plans.items():
                plan = plan['data_set']
                patient_plan_names.append(plan.RTPlanLabel)
            
        plan_names.append(patient_plan_names)
        number_of_cts.append(number_of_cts_counter)
        number_of_plans.append(number_of_plans_counter)
        number_of_structures.append(number_of_structures_counter)
        number_of_doses.append(number_of_doses_counter)
        number_of_studies.append(len(patient.studies))

    data['patient_id'] = ok_patient_ids
    data['number_of_studies'] = number_of_studies
    data['number_of_plans'] = number_of_plans
    data['number_of_cts'] = number_of_cts
    data['number_of_structures'] = number_of_structures
    data['number_of_doses'] = number_of_doses
    data['plan_names'] = plan_names
    data['patient_object'] = patient_objects
    data_frame = pd.DataFrame(data)

    print("--- %s seconds ---" % (time.time() - start_time))        
    return(data_frame, error_messages)       


def run(api, patient_folder):
    open_dicom_files(patient_folder)