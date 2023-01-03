from cordialrt.analysis.treatments_from_collection import init_treatments_from_collection
import csv
import pandas as pd 
import os
import gc
import datetime

def dvh_all_patients(
    collection_id,
    excel_folder,
    excel_name,
    centers,
    group_size,
    roi_names,
    max_number_of_patients = None,
    dvh_points = 'default',
    re_run_patients = False,
    plan_max_dose= False,
    laterality = False,
    log_failed_path = False,
    patient_id_only = False,
    ct_slice_thickness = False
    ):

    """ Extracts DVH-values from treatments and saves them to a number of excel files (in the specified excelfolder). 
    If these files already contains patient data, these patients are skipped unless specified by using re_run_patients. 
    Group size is uses to regulate the memory usage """


    print('start', datetime.datetime.now())
  
    #Define whcih DVH points will be extracted
    if dvh_points == 'default':
        all_points = list()
        all_points.append(['mean', ''])
        all_points.append(['volume', ''])

        # Add all dvh points between 0 and 100 in steps of 1Gy
        for i in range(100):
            dvh_point = f'v{i+1}gy'
            all_points.append([dvh_point, 'abs'])

        # Add some relative dvh points
        all_points.append(['d0.01cc', 'abs'])
        all_points.append(['d25', 'abs'])
        all_points.append(['d50', 'abs'])
        all_points.append(['d75', 'abs'])
        all_points.append(['v90', 'rel'])
        all_points.append(['v95', 'rel'])
        all_points.append(['v98', 'rel'])
        all_points.append(['v100', 'rel'])
        all_points.append(['v105', 'rel'])
        all_points.append(['v107', 'rel'])
        all_points.append(['v110', 'rel'])
    
    elif dvh_points == 'moderat':
        all_points = list()
        all_points.append(['mean', ''])
        all_points.append(['volume', ''])

        # Add all dvh points between 0 and 100 in steps of 1Gy
        for i in [5, 10, 17, 20, 38, 40, 42, 44, 45, 50, 55]:
            dvh_point = f'v{i}gy'
            all_points.append([dvh_point, 'abs'])
        
        # Add some relative dvh points
        all_points.append(['d0.01cc', 'abs'])
        all_points.append(['d25', 'abs'])
        all_points.append(['d50', 'abs'])
        all_points.append(['d75', 'abs'])
        all_points.append(['v90', 'rel'])
        all_points.append(['v95', 'rel'])
        all_points.append(['v98', 'rel'])
        all_points.append(['v100', 'rel'])
        all_points.append(['v105', 'rel'])
        all_points.append(['v107', 'rel'])
        all_points.append(['v110', 'rel'])

    else:
        all_points = dvh_points

    # Read excel files to see if patient is already processed:

    first_found = False
    for center in centers: 
        print('start read excel', datetime.datetime.now())
        excel_path_center = f'{excel_folder}/{excel_name}_{center}.xlsx'
        try:
            df_excel_center = pd.read_excel(excel_path_center)
            df_excel_center = df_excel_center.set_index('patient_id')
            
            if not first_found:
                df_excel = df_excel_center
                first_found = True 
            else:
                df_excel = df_excel.append(df_excel_center)
                
        except FileNotFoundError:
            pass

    #Get failed patients from log
    failed_patient_ids = list()

    try:
        with open(log_failed_path, mode='r') as infile:
            reader = csv.reader(infile, delimiter=';' )   
            next(reader)
            for rows in reader:
                failed_patient_ids.append(rows[0])
        print('Failed patients ids',len(failed_patient_ids))
    except FileNotFoundError:
        pass

    # If no file has been found all patients will be processed. 
    if not first_found:
        patients_already_processed = failed_patient_ids
    else:    
        patients_already_processed = df_excel.index.unique()
        patients_already_processed.append(failed_patient_ids)
        del(df_excel)
        del(df_excel_center)
        gc.collect()

    print('Patients in excel:', len(patients_already_processed))

    if re_run_patients:
        print('Number of re run patients', len(re_run_patients)) 
    else:
        pass

    for center in centers:
        print(center)
        excel_path_center = f'{excel_folder}/{excel_name}_{center}.xlsx'
        
        print('start init treatments', datetime.datetime.now())
        if re_run_patients == False:
            treatments = init_treatments_from_collection(collection_id, treatment_limit= max_number_of_patients, 
            departments = [center], exclude_patients=patients_already_processed, log_failed_path = log_failed_path)
        else:
            treatments = init_treatments_from_collection(collection_id, treatment_limit= max_number_of_patients, 
            departments = [center], select_patients=re_run_patients, log_failed_path = log_failed_path)

        print(f'Init {len(treatments)} treatments')

        if len(treatments) == 0:
            continue

        treatment_groups = list()

        #sort by treatment id
        treatments.sort(key=lambda x: x.treatment_id)

        number_of_groups = round(len(treatments)/group_size)
        if number_of_groups == 0:
            number_of_groups = 1

        print('Number of groups:', number_of_groups)

        for i in range(number_of_groups):
            treatment_group = list()

            ix_start = i*group_size
            ix_end = (i+1)*group_size
            if ix_end > len(treatments):
                ix_end = len(treatments)

            for treatment in treatments[ix_start:ix_end]:
                treatment_group.append(treatment)

            treatment_groups.append(treatment_group)

        del(treatments)
        gc.collect()

        for i, treatment_group in enumerate(treatment_groups):
            print('treatment group number:', i)
            print('with length', len(treatment_group))
            data = list()
            for treatment in treatment_group:
                #print(treatment.patient_id, datetime.datetime.now())
                skip_treatment = False
            
                if len(treatment.dose_paths) == 0:
                    print(treatment.patient_id)
                    print('no dose')
                    continue 
                
                if patient_id_only:
                    data_dict = {'patient_id': treatment.patient_id}
                else:   
                    # Data about the treatment
                    data_dict = {        
                        'patient_id': treatment.patient_id,
                        'study_date': treatment.get_study_date(),
                        'fractions': treatment.get_plan_fractions(),
                        'plan_names': treatment.get_plan_names(),
                        'main_reference_dose': treatment.main_reference_dose,
                        'boost_reference_dose': treatment.boost_reference_dose,
                        'main_dose_scale_factor': treatment.main_dose_scale_factor,
                        'boost_dose_scale_factor': treatment.boost_dose_scale_factor,
                        'centre': treatment.treatment_place,   
                        'dose_file_path': treatment.dose_path,
                        'structure_file_path': treatment.structure_path,
                    }

                # More optional data about the treatment
                if plan_max_dose:
                    try: 
                        data_dict['plan_max_dose'] = treatment.get_max_dose()
                    except MemoryError:
                        print(f'Memory Error with max_dose. Skipped treatment for {treatment.patient_id}')
                        continue

                if laterality:
                    try:
                        data_dict['laterality'] = treatment.get_latterality()
                        data_dict['left_right_dose_ratio '] = treatment.left_right_dose_ratio
                    except MemoryError:
                        print(f'Memory Error with laterality. Skipped treatment for {treatment.patient_id}')
                        continue

                for roi_name in roi_names:
                    treatment.add_new_roi(roi_name)
                    roi = treatment.roi_by_name(roi_name)
                    try:
                        data_dict = roi.dvh_points_from_roi(data_dict, all_points)
                    except MemoryError:
                        skip_treatment = True
                        print('memory error' + treatment.patient_id)
                        break
                    data_dict[f'{roi_name}_synonyms_found'] = roi.synonyms_found
                    
                if skip_treatment:
                    print(f'Memory Error. Skipped treatment for {treatment.patient_id}')
                    continue      

                if ct_slice_thickness:
                    try:
                        treatment.load_ct_data()
                        slice_thickness = treatment.cts[0].ds.SliceThickness
                        data_dict['ct_slice_thickness'] = slice_thickness
                    except MemoryError:
                        print(f'Memory Error with ct thickness. Skipped treatment for {treatment.patient_id}')
                        continue
                del(treatment.cts)
                
                data.append(data_dict)
                del(treatment)
                gc.collect()

            if len(data) == 0:
                continue 
            
            df = pd.DataFrame(data)
            df = df.set_index('patient_id')

          
            df['dvh_calc_date'] = [datetime.datetime.now()]*len(df)

            # Save data as excel file
            print('write to excel', datetime.datetime.now())
            
            try: 
                excel_df = pd.read_excel(excel_path_center)   
            except FileNotFoundError:
                excel_df = df
                excel_df.to_excel(excel_path_center)
            else:
                excel_df = excel_df.set_index('patient_id')
            
                if re_run_patients == False:
                    pass
                else:
                    try: # dele row if patient is rerun
                        excel_df = excel_df.drop(df.index.values.tolist())
                    except KeyError: # if patient is rerun, but not in excel, create row
                        pass

                excel_df = excel_df.append(df)
                excel_df.to_excel(excel_path_center)
                del(treatment_group)
                gc.collect()

        if i == len(treatment_groups):
            print(f'Excel now contains {len(excel_df)} patients')
        
        del(treatment_groups)
        gc.collect()