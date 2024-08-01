import datetime 
import pandas as pd

import cordialrt.analysis.treatment_class as rtclass
import cordialrt.database.database as rtdb
import cordialrt.helpers.exceptions as rtex

import cordialrt.helpers.user_config
user_config = cordialrt.helpers.user_config.read_user_config()
DICOM_FOLDER_PATH = user_config['dicom_file_parent_folder']

def init_treatments_from_collection(treatment_collection_id, treatment_limit = None, departments =None, 
                                    exclude_patients = None, select_patients = None, log_failed_path = False):   

    """Initialse treatment objectives from the database and performs initialization checks. Set log_fail_path to a .txt file 
    to log errors. """                                
    with rtdb.DatabaseCall() as db:
        treatment_rows = db.get_treatments_from_collection(treatment_collection_id, departments, exclude_patients, select_patients)
   
    treatments = list()
    log = list()
    log.append(f'collection_id: {treatment_collection_id}, treatment_limit: {treatment_limit}, departments: {departments}')

    # use treatment limit if you only want some of the treatements for testing
    if treatment_limit is None:
        limit = len(treatment_rows)
    else:
        limit = treatment_limit

    for treatment_row in treatment_rows[0:limit]:
        treatment = rtclass.Treatment(treatment_row[0],treatment_row[1],treatment_collection_id)
        treatment.treatment_place = treatment_row[3]
        treatment.main_dose_scale_factor = treatment_row[4]
        treatment.main_reference_dose = treatment_row[5]
        treatment.boost_reference_dose = treatment_row[6]
        treatment.boost_dose_scale_factor = treatment_row[7]
      
        treatment.load_file_paths()

        try:
            if treatment.init_check():
                treatments.append(treatment)

        except (rtex.SumDoseError, rtex.InitError) as e:
            print(e)
            if log_failed_path:
                # patient_id;treatment_id;error_message
                log.append(f'{treatment_row[1]};{treatment_row[0]};{e}')
    
    if log_failed_path:
        with open(f'{log_failed_path}', 'a+') as f:
            for item in log:
                f.write("%s\n" % item)
   
    return(treatments)

    





#treatment_rows = init_treatments_from_collection(1)

#treatments = list()
#treatment_row = treatment_rows[0]
#t = Treatment(treatment_row[0], treatment_row[1])
#t.load_file_paths()

#t.load_all_dicom_data()