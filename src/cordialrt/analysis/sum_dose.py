import datetime
import os

from dicompylercore import dicomparser
from dicompylercore import dose as dc_dose

import cordialrt.helpers.user_config
import cordialrt.database.database as rtdb
import cordialrt.helpers.exceptions as rtex

user_config = cordialrt.helpers.user_config.read_user_config()
DICOM_FOLDER = user_config["dicom_file_parent_folder"]


def create_sum_dose_file(
    dose_paths,
    patient_id,
    treatment_id,
    plans,
    main_reference_dose,
    main_dose_scale_factor,
    boost_reference_dose,
    boost_dose_scale_factor,
    write_line_in_db=True,
):
    """Sum dose files, save the resulting DICOM file and return the path (None if errors).

    This is written with Danish breast cancer patients in mind. If used to sum
    primary/boost plans with another fractionation scheme, the logic for identifying
    which plan is the primary, will have to be modified.
    """
    dose_path_scale_pairs, patient_id = prepare_dose_sum_files_dbcg01(
        dose_paths,
        patient_id,
        treatment_id,
        plans,
        main_reference_dose,
        main_dose_scale_factor,
        boost_reference_dose,
        boost_dose_scale_factor,
        write_line_in_db=True,
    )

    try:
        summed_dose_dicom_file, log = sum_doses(dose_path_scale_pairs, patient_id)
    except rtex.SumDoseError as e:
        raise e

    if summed_dose_dicom_file is None:
        return None

    local_sum_dose_path, summed_dose_dicom_file = save_sum_dose_file(
        summed_dose_dicom_file,
        dose_paths,
        patient_id,
        treatment_id,
        log,
        write_line_in_db=True,
    )

    return local_sum_dose_path, summed_dose_dicom_file


def prepare_dose_sum_files_dbcg01(
    dose_paths,
    patient_id,
    treatment_id,
    plans,
    main_reference_dose,
    main_dose_scale_factor,
    boost_reference_dose,
    boost_dose_scale_factor,
    write_line_in_db=True,
):
    """Prepare dose files for summation according to DBCG01 protocol.

    Args:
        dose_paths: List of paths to dose files
        patient_id: Patient identifier
        treatment_id: Treatment identifier
        plans: List of treatment plans
        main_reference_dose: Reference dose for main treatment
        main_dose_scale_factor: Scale factor for main dose
        boost_reference_dose: Reference dose for boost treatment
        boost_dose_scale_factor: Scale factor for boost dose
        write_line_in_db: Whether to write to database

    Returns:
        Tuple of (dose path and scale factor pairs, patient_id)

    Raises:
        SumDoseError: If dose summation preparation fails
    """
    dose_path_scale_pairs = list()
    if len(plans) == 1:
        # primary plan scaled, SIB plan scaled, primary plan (multi doses) summed,
        # primary (multi doses) summed + scaled
        if main_reference_dose != 0:
            for path in dose_paths:
                dose_path_scale_pairs.append([path, main_dose_scale_factor])
        else:
            raise rtex.SumDoseError("Sum dose error, main reference dose == 0")
    else:
        if len(plans) > len(dose_paths):
            plan_names = list()
            for plan in plans:
                plan_names.append(plan.GetPlan()["label"])
            raise rtex.SumDoseError(
                f"Failed for patinet: {patient_id} More plans than dose files. Plans: {plan_names}"
            )

        # primary (multi plans) summed + scaled or primary (multi plans) summed
        if boost_reference_dose == 0:
            for path in dose_paths:
                dose_path_scale_pairs.append([path, main_dose_scale_factor])
        else:
            if boost_dose_scale_factor == 1 and main_dose_scale_factor == 1:
                # mulit dose primary plan and mulitdose boost plan, no scaling.
                for path in dose_paths:
                    dose_path_scale_pairs.append([path, 1])
            else:
                from collections import defaultdict

                # Group dose files by referenced plan UID
                # handles both single dose per plan and per-beam dose exports
                dose_by_plan = defaultdict(list)
                for path in dose_paths:
                    ref_plan = dicomparser.DicomParser(path).GetReferencedRTPlan()
                    dose_by_plan[ref_plan].append(path)

                # get fractions per plan, sort ascending (boost first)
                fractions_plan_uid = list()
                for plan in plans:
                    no_fractions = plan.ds.FractionGroupSequence[0].NumberOfFractionsPlanned
                    fractions_plan_uid.append([no_fractions, plan.GetSOPInstanceUID()])

                fractions_plan_uid.sort(key=lambda x: x[0])

                if main_reference_dose == 50:
                    main_fractions = 25
                elif main_reference_dose == 48:
                    main_fractions = 24
                elif main_reference_dose == 40:
                    main_fractions = 15
                else:
                    raise rtex.SumDoseError(
                        f"Failed for patient: {patient_id} main_reference dose is not standard but {main_reference_dose}"
                    )

                if boost_reference_dose == 16:
                    boost_fractions = 8
                elif boost_reference_dose == 10:
                    boost_fractions = 5
                else:
                    raise rtex.SumDoseError(
                        f"Failed for patient: {patient_id} boost_reference dose is not standard but {boost_reference_dose}"
                    )

                # if main_dose scale is larger than the max_scale, we cannot be sure
                # that the plan with the most fractions is the main dose.
                max_scale = main_fractions / (boost_fractions + 1)

                if main_dose_scale_factor > max_scale:
                    raise rtex.SumDoseError(
                        f"Failed for patinet: {patient_id}. Unable to identify main plan. Main dose scale factor is {main_dose_scale_factor}"
                    )

                boost_plan_uid = fractions_plan_uid[0][1]
                main_plan_uid = fractions_plan_uid[1][1]

                # add all boost beam doses
                for path in dose_by_plan.get(boost_plan_uid, []):
                    dose_path_scale_pairs.append([path, boost_dose_scale_factor])

                # add all main beam doses
                for path in dose_by_plan.get(main_plan_uid, []):
                    dose_path_scale_pairs.append([path, main_dose_scale_factor])
    return dose_path_scale_pairs, patient_id


def save_sum_dose_file(
    summed_dose_dicom_file,
    dose_paths,
    patient_id,
    treatment_id,
    log,
    write_line_in_db=True,
):
    """Save the summed dose DICOM file and create associated log file.

    Args:
        summed_dose_dicom_file: The DICOM file containing the summed dose
        dose_paths: List of paths to original dose files
        patient_id: Patient identifier
        treatment_id: Treatment identifier
        write_line_in_db: Whether to write to database (default: True)

    Returns:
        Tuple of (local_sum_dose_path, summed_dose_dicom_file)
    """
    # Make a new directory
    path = dose_paths[0]
    if path.startswith(DICOM_FOLDER):
        path = path[len(DICOM_FOLDER):]
    institution_folder = path.split("/")[0]
    institution_folder_sum = f"{institution_folder}_dose_sum"
    new_folder_path = "/".join([institution_folder_sum, patient_id])
    local_folder_path = "/".join([DICOM_FOLDER, new_folder_path])

    if os.path.exists(local_folder_path):
        pass
    else:
        try:
            os.makedirs(local_folder_path, exist_ok=True)
        except OSError:
            print(
                f"{patient_id} - Creation of the directory {local_folder_path} failed"
            )

    sum_dose_path = f"/{new_folder_path}/treatment_{treatment_id}_sum_dose.dcm"
    local_sum_dose_path = f"{local_folder_path}/treatment_{treatment_id}_sum_dose.dcm"

    # save the file:
    summed_dose_dicom_file.save_dcm(local_sum_dose_path)
    # load the saved file:
    summed_dose_dicom_file = dicomparser.DicomParser(local_sum_dose_path)

    with open(
        f"{local_folder_path}/log_treatment_{treatment_id}.txt", "w", encoding="utf-8"
    ) as f:
        for item in log:
            f.write("%s\n" % item)

    if write_line_in_db:
        row_data = [
            treatment_id,
            "sum_dose",
            sum_dose_path,
            summed_dose_dicom_file.GetSOPInstanceUID(),
        ]
        with rtdb.DatabaseCall() as db:
            db.insert_row_in_table(
                "dicom_files",
                ["treatment_id", "file_type", "file_path", "file_uid"],
                row_data,
            )

    return (local_sum_dose_path, summed_dose_dicom_file)


def sum_doses(dose_path_scale_pairs, patient_id):
    """Return DICOM file with the summed dose (None if errors)
    and log list. Ignores dose files with max_dose < 1 Gy"""
    log = list()
    log.append(f"Log creacted {datetime.datetime.now()}")
    log.append("Summed doses:")
    log.append(dose_path_scale_pairs)

    dose_grid_sum = None

    for pair in dose_path_scale_pairs:
        path = pair[0]
        scale_factor = pair[1]

        # If this is the first file without Error:
        if dose_grid_sum is None:
            try:
                dose_grid = dc_dose.DoseGrid(path)
            except Exception as e:
                raise rtex.SumDoseError(
                    f"Failed for patient: {patient_id}."
                    f"Error initializing DoseGrid: {e}. File: {path}"
                )

            # check max dose to skip files without dose
            dose_data = dicomparser.DicomParser(path).GetDoseData()
            max_dose = dose_data["dosegridscaling"] * dose_data["dosemax"]

            # The lowest doses are dose per beam,
            # and they should be more than 1 Gy max
            if max_dose > 1:
                dose_grid.multiply(scale_factor)
                dose_grid_sum = dose_grid
                log.append(path)
                log.append(f"with max dose: {max_dose}")
            else:
                log.append(f"Max dose < 1 Gy {path}")
                log.append(f"with max dose: {max_dose}")
        else:
            # This is not the first dose and must be added to the sum
            try:
                dose_grid = dc_dose.DoseGrid(path)
            except Exception as exc:
                raise rtex.SumDoseError(
                    f"Failed for patinet: {patient_id}."
                    f"Error, failed to init DoseGrid in"
                    f"sum_doses for, file: {path}"
                ) from exc

            # check max dose to skip files without dose
            dose_data = dicomparser.DicomParser(path).GetDoseData()
            max_dose = dose_data["dosegridscaling"] * dose_data["dosemax"]

            if max_dose > 1:
                dose_grid.multiply(scale_factor)
                dose_grid_sum.add(dose_grid, force=True)
                log.append(path)
                log.append(f"with max dose: {max_dose}")
            else:
                log.append(f"Max dose < 1 Gy {path}")
                log.append(f"with max dose: {max_dose}")

    return (dose_grid_sum, log)
