import datetime
import pandas as pd

import cordialrt.analysis.treatment_class as rtclass
import cordialrt.database.database as rtdb
import cordialrt.helpers.exceptions as rtex

import cordialrt.helpers.user_config

user_config = cordialrt.helpers.user_config.read_user_config()
DICOM_FOLDER_PATH = user_config["dicom_file_parent_folder"]


def init_treatment_from_patient(
    treatment_collection_id,
    patient_id,
    ct_paths,
    structure_path,
    department,
    log_failed_path=None,
):
    """Initialse treatment objectives from a patient object and performs initialization checks."""

    treatment = rtclass.Treatment(patient_id, patient_id, treatment_collection_id)
    treatment.treatment_place = department

    treatment.ct_paths = ct_paths
    treatment.structure_paths = [structure_path]
    log = list()

    try:
        treatment.init_check_no_dose()

    except (rtex.SumDoseError, rtex.InitError) as e:
        print(e)
        if log_failed_path:
            # patient_id;treatment_id;error_message
            log.append(f"{patient_id};{e}")

    if log_failed_path:
        with open(f"{log_failed_path}", "a+") as f:
            for item in log:
                f.write("%s\n" % item)

    return treatment


# treatment_rows = init_treatments_from_collection(1)

# treatments = list()
# treatment_row = treatment_rows[0]
# t = Treatment(treatment_row[0], treatment_row[1])
# t.load_file_paths()

# t.load_all_dicom_data()
