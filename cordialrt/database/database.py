"""
All functions interacting with the database. 
"""
import definitions
import sqlite3
import datetime
from contextlib import closing
import cordialrt.helpers.user_config
import glob

user_config = cordialrt.helpers.user_config.read_user_config()
USER_NAME = user_config['user']
DICOM_FOLDER_PATH = user_config['dicom_file_parent_folder']
DATABASE_PATH = f'{definitions.ROOT_DIR}/cordialrt/database.db'

class DatabaseCall():
    def __init__(self):
        try:
            self.connection = sqlite3.connect(DATABASE_PATH)
            self.cursor = self.connection.cursor()

        except sqlite3.Error as err:
            print(err)

    def __enter__(self):
        # This ensure, whenever an object is created using "with"
        self.connection = sqlite3.connect(DATABASE_PATH)
        self.cursor = self.connection.cursor()
        return (self)

    def __exit__(self, exception_type, exception_val, trace):
        # once the with block is over, the __exit__ method would be called
        # with that, you close the connnection
        try:
           self.cursor.close()
           self.connection.close()
        except AttributeError: # isn't closable
           print ('Not closable.')
           return (True) # exception handled successfully

# General dataabse functionality
    def insert_row_in_table(self, table_name, column_names, row_data):
        """ Insert rows into the database and set edit_date and edit_user"""
        column_names_string = ",".join(column_names)
        row_data = row_data + [datetime.datetime.now(), USER_NAME]
        values_place_holder = ','.join(['?']*(len(row_data)))

        sql_string = f"""INSERT INTO {table_name}
                        ({column_names_string}, edit_date, edit_user)
                        VALUES ({values_place_holder})"""
        self.cursor.execute(sql_string, row_data)
        self.connection.commit()    

# Treatment collection
    def create_treatment_collection(self, collection_name):
        """ Creates new treatment collectio. Returns collection_id"""
        self.insert_row_in_table('treatment_collections', 
            ['collection_name'], [collection_name])

        sql_string = "SELECT MAX(collection_id) FROM treatment_collections"
        collection_id = self.cursor.execute(sql_string).fetchone()[0]
        return(collection_id)

    def get_treatments_from_collection(self, collection_id, departments=None, exclude_patients =None, select_patients = None): 
        """ List departments to only select from these. Use a list of patient_ids to exclude_patients or to select_patients """
        
        sql_string ='SELECT * FROM treatments WHERE collection_id = ?'
        variables = [collection_id]

        if departments is not None:
            string_departments = ', '.join(f'"{department}"' for department in departments)
            sql_string = f'{sql_string} AND treatment_place IN ({string_departments})' 

        if exclude_patients is not None:
            string_ids = ', '.join(f'"{id}"' for id in exclude_patients)
            sql_string = f'{sql_string} AND patient_id NOT IN ({string_ids})'

        if select_patients is not None:
            string_ids = ', '.join(f'"{id}"' for id in select_patients)
            sql_string = f'{sql_string} AND patient_id IN ({string_ids})'
        

        treatments = self.cursor.execute(sql_string, variables).fetchall()
        
        return(treatments)
        
    def get_patient_id_from_collection(self, 
                                        collection_id,
                                        department = None, 
                                        exclude_patients = None, 
                                        select_patients = None):

        """Get patient ids from all or subgroup of collection """

        sql_string = 'SELECT patient_id FROM treatments WHERE collection_id = ?'
        variables = [collection_id]

        if department is not None:
            sql_string = f'{sql_string} AND treatment_place = ?' 
            variables.append(department)

        if exclude_patients is not None:
            string_ids = ', '.join(f'"{id}"' for id in exclude_patients)
            sql_string = f'{sql_string} AND patient_id NOT IN ({string_ids})'

        if select_patients is not None:
            string_ids = ', '.join(f'"{id}"' for id in select_patients)
            sql_string = f'{sql_string} AND patient_id IN ({string_ids})'
        
        with closing(self.connection) as self.connection:
            with closing(self.cursor) as self.cursor:
                patient_ids = self.cursor.execute(sql_string, variables).fetchall()
        
        patient_id_lst = []
        for id in patient_ids:
            patient_id_lst.append(id[0])

        return (patient_id_lst)

# Treatments
    def delete_treatment_from_collection(self, patient_ids, collection_id):
        """Delete treatments and associated files from a treatment collection"""

        string_ids = ', '.join(f'"{id}"' for id in patient_ids)
        sql_string = f'SELECT treatment_id FROM treatments WHERE collection_id = {collection_id} AND patient_id IN ({string_ids})'

        treatment_ids = self.cursor.execute(sql_string).fetchall()

        list_treat_ids = list()
        for treatment_id in treatment_ids:
            list_treat_ids.append(treatment_id[0])

        string_treat_ids = ', '.join(f'"{id}"' for id in list_treat_ids)

        sql_delete_files = f'DELETE FROM dicom_files WHERE treatment_id IN ({string_treat_ids})'
        self.cursor.execute(sql_delete_files)
        print(sql_delete_files)

        sql_delete_treat = f'DELETE FROM treatments WHERE treatment_id IN ({string_treat_ids}) and collection_id = {collection_id}'
        print(sql_delete_treat)
        self.cursor.execute(sql_delete_treat)

        self.connection.commit()    

    def add_new_treatment_to_collection_from_plan_names(self,patient, treatment_place, 
                                                        collection_id, plan_names, 
                                                        main_reference_dose,
                                                        boost_reference_dose=0,
                                                        main_dose_scale_factor=1,
                                                        boost_dose_scale_factor=1,                                                   
                                                        study_uid=None):
        """Create a new treatment in a collection by adding all data from the patient related to the plan names specified. 
        Use the study_uid if the patient obejct contains multiple studies. Returns sucess: True/False, error_log"""

        self.insert_row_in_table('treatments',
            ['collection_id', 'patient_id', 'treatment_place', 
            'main_dose_scale_factor', 'boost_dose_scale_factor','main_reference_dose', 'boost_reference_dose'],
            [collection_id, patient.id, treatment_place, 
            main_dose_scale_factor, boost_dose_scale_factor, main_reference_dose, boost_reference_dose])

        sql_string = "SELECT MAX(treatment_id) FROM treatments"
        treatment_id = self.cursor.execute(sql_string).fetchone()[0]

        status, error_log = self.add_files_to_treatment_from_plan_names(patient, treatment_id, plan_names, study_uid)
        return(status, error_log)
    
    def get_file_paths_from_treatment(self, treatment_id):
        """Returns DICOM file information for a treatment"""
        sql_string ='SELECT * FROM dicom_files WHERE treatment_id = ?'
        file_rows = self.cursor.execute(sql_string, [treatment_id]).fetchall()

        return(file_rows)

# Files 
    def add_files_to_treatment(self, treatment_id, files, file_type):
        for uid, file in files.items():
            global_path = file['path'][len(DICOM_FOLDER_PATH):]
            global_path = global_path.replace('\\', '/')

            self.insert_row_in_table('dicom_files',
                ['treatment_id', 'file_path', 'file_type', 'file_uid'],
                [treatment_id, global_path, file_type, uid])

    def add_files_to_treatment_from_plan_names(self, patient, treatment_id, plan_names, study_uid = None):
        """Add all data from the patient related to the plan names specified to the treatment. Returns sucess: True/False, error_log """
        error_log = list()
        plan_infos = dict()

        if study_uid is None:
            for uid, study in patient.studies.items():
                if len(study.plans) > 0:
                    plans = study.plans
                    main_study = study 
                else:
                    error_log.append(f'{patient.id} No plans to add')
        else:
            main_study = patient.studies[study_uid]
            plans = main_study.plans

        for uid, plan in plans.items():
            plan_structure_uids = set()
            for structure_reference in plan['data_set'].ReferencedStructureSetSequence:
                if structure_reference.ReferencedSOPClassUID.name == 'RT Structure Set Storage':
                    plan_structure_uids.add(structure_reference.ReferencedSOPInstanceUID)

            plan_infos[plan['data_set'].RTPlanLabel] = {'uid': uid,
                                                        'structure_uid': plan_structure_uids,
                                                        'path': plan['path']}

        structure_uids = set()
        plan_uids = set()

        plans_out = dict()
        structures_out = dict()
        doses_out = dict()
        cts_out = dict()

        for plan_name in plan_names:
            structure_uids = structure_uids.union(plan_infos[plan_name]['structure_uid'])
            plan_uids.add(plan_infos[plan_name]['uid'])
            plans_out[plan_infos[plan_name]['uid']] = main_study.plans[plan_infos[plan_name]['uid']]

        #Check if all plans have same structure
        if len(structure_uids) == 0:
            error_log.append(f'No structure for {patient.id} , plan {plan_names}')
            return(False, error_log)

        elif len(structure_uids) > 1: 
            error_log.append(f'More than one structure for {patient.id} , plan {plan_names}')
            return(False, error_log)

        elif len(structure_uids) == 1:
            structure_uid = structure_uids.pop()
            try:
                structure_out = main_study.structures[structure_uid]
            except KeyError: #if structure not in main_study look in other studies
                for study_uid_key, study in patient.studies.items():
                    for struct_uid_key, structure_data in study.structures.items():
                        if struct_uid_key == structure_uid:
                            structure_out = structure_data
            
            structures_out[structure_uid] = structure_out

            #check if at least one ct file
            images = structure_out['data_set'].ReferencedFrameOfReferenceSequence[0].RTReferencedStudySequence[0].RTReferencedSeriesSequence[0].ContourImageSequence
            if len(images) == 0:
                error_log.append(f'No CT files for {patient.id} , plan {plan_names}')
                return(False, error_log)

            for image in images:
                if image.ReferencedSOPClassUID.name == 'CT Image Storage':
                    try:
                        cts_out[image.ReferencedSOPInstanceUID] = main_study.cts[image.ReferencedSOPInstanceUID]
                    except KeyError:
                        error_log.append(f'Missing CT file for {patient.id} , CT uid: {image.ReferencedSOPInstanceUID}')

            for uid, dose in main_study.doses.items():
                for reference in dose['data_set'].ReferencedRTPlanSequence:
                    if (reference.ReferencedSOPClassUID.name == 'RT Plan Storage'
                    and reference.ReferencedSOPInstanceUID in plan_uids):
                        doses_out[uid] = dose
            
            #Check if at least one dose file
            if len(doses_out) == 0:
                error_log.append(f'No dose_files for {patient.id} , plan {plan_names}')
                return(False, error_log)

        self.add_files_to_treatment(treatment_id, plans_out, 'plan')
        self.add_files_to_treatment(treatment_id, structures_out, 'structure')
        self.add_files_to_treatment(treatment_id, doses_out, 'dose')
        self.add_files_to_treatment(treatment_id, cts_out, 'ct')
        
        return(True, error_log)

    def delete_sum_dose_files(self, patient_ids, collection_id):
        """ Delete sum dose files and references in db"""

        string_ids = ', '.join(f'"{id}"' for id in patient_ids)
        sql_string = f'SELECT treatment_id FROM treatments WHERE collection_id = {collection_id} AND patient_id IN ({string_ids})'
        treatment_ids = self.cursor.execute(sql_string).fetchall()

        list_treat_ids = list()
        for treatment_id in treatment_ids:
            list_treat_ids.append(treatment_id[0])

        string_treat_ids = ', '.join(f'"{id}"' for id in list_treat_ids)

        sql_delete_files = f'DELETE FROM dicom_files WHERE file_type = "sum_dose" AND treatment_id IN ({string_treat_ids})'
        self.cursor.execute(sql_delete_files)
        print(sql_delete_files)

        self.connection.commit()

# Synonyms
    def create_synonym_collection(self, synonym_collection_name):
        """ Creates new synonym collection. Returns synonym_collection_id"""
        
        self.insert_row_in_table('synonym_collections', ['synonym_collection_name'], [synonym_collection_name])
        sql_string = "SELECT MAX(synonym_collection_id) FROM synonym_collections"

        collection_id = self.cursor.execute(sql_string).fetchone()[0]
        return(collection_id)

    def associate_synonym_collection_with_treatment_colection(self, synonym_collection_id, treatment_collection_id):

        self.insert_row_in_table('synonyms_for_treatment_collections', 
                                ['synonym_collection_id', 'treatment_collection_id'], 
                                [synonym_collection_id, treatment_collection_id])

    def add_synoym_to_synonym_colection(self, synonym_collection_id, synonym, standard_name, laterality = '', priority_count = 0):

        self.insert_row_in_table('synonyms', 
                                ['synonym_collection_id', 'synonym', 'standard_name', 'laterality','priority_count'], 
                                [synonym_collection_id, synonym, standard_name, laterality, priority_count])

    def get_synonym_collection_ids_for_treatment_colection(self, treatment_collection_id):
        sql_string ='SELECT synonym_collection_id FROM synonyms_for_treatment_collections WHERE treatment_collection_id = ?'
        rows = self.cursor.execute(sql_string, [treatment_collection_id]).fetchall()
                
        synonym_collection_ids = list()
        for row in rows:
                synonym_collection_ids.append(row[0])

        return(synonym_collection_ids)

    def get_synonyms_from_standard_name(self, standard_name, treatment_collection_id, priority = None): 

        synonym_collection_ids = self.get_synonym_collection_ids_for_treatment_colection(treatment_collection_id)
        rows = list()

        for synonym_collection_id in synonym_collection_ids:
            if priority is None:
                sql_string ='SELECT synonym FROM synonyms WHERE standard_name = ? AND synonym_collection_id = ?'
                synonyms = self.cursor.execute(sql_string, [standard_name, synonym_collection_id]).fetchall()
               
                for synonym in synonyms:
                    rows.append(synonym[0])
                  
            elif priority is True:
                sql_string ='SELECT synonym, priority_count, laterality FROM synonyms WHERE standard_name = ? AND synonym_collection_id = ?'
                synonyms = self.cursor.execute(sql_string, [standard_name, synonym_collection_id ]).fetchall()

                for synonym in synonyms:
                    rows.append(synonym)

        return(list(set(rows)))

    def update_db_with_priority_count(self, rois_counted, roi_names, synonym_collection_id):
        """Updates the database with a priority_count"""
        ##NB! This should only be used once for each new dataset added in the db
        
        sql_string ='SELECT synonym FROM synonyms WHERE synonym_collection_id = ?'
        all_synonyms = self.cursor.execute(sql_string, [synonym_collection_id]).fetchall()
        synonyms = [f[0] for f in all_synonyms]
        
        n = 0
        for roi in rois_counted:
            roi_name = roi_names[n]
            if roi_name in synonyms:
                count = roi
                sql_string = "SELECT priority_count FROM synonyms WHERE synonym = ? AND synonym_collection_id = ?"
                priority = self.cursor.execute(sql_string,[roi_name, synonym_collection_id]).fetchone()[0]

                if priority == None:
                    sql_string = 'UPDATE synonyms SET priority_count = ? WHERE synonym = ? AND synonym_collection_id = ?'
                    self.connection.execute(sql_string,[count, roi_name, synonym_collection_id])
                    self.connection.commit()
                    
                else:
                    sql_string = 'UPDATE synonyms SET priority_count = priority_count + ? WHERE synonym = ? AND synonym_collection_id '
                    self.connection.execute(sql_string,[count, roi_name, synonym_collection_id])
                    self.connection.commit()
                           
            n = n + 1
        print(f'Updated prioritisation in synonyms fo synonym_collection {synonym_collection_id}')

# Structure collection
    def create_structure_collection(self, collection_name):
        self.insert_row_in_table('structure_collections', 
            ['structure_collection_name'], [collection_name])
        sql_string = "SELECT MAX(structure_collection_id) FROM structure_collections"
        collection_id = self.cursor.execute(sql_string).fetchone()[0]
        return(collection_id)

    def new_structure_collection_from_folder(self, collection_name, folder_path):
        """Create a new structure collection by adding all structure files in a folder orgnaised with > center names > patient_ids """
        collection_id = self.create_structure_collection(collection_name)
        
        file_paths = list()
        center_folders = glob.glob(f'{folder_path}/*')
        print(f'{folder_path}/*')
        print(center_folders)
        for center_folder in center_folders:  
            patient_folders = glob.glob(f'{center_folder}/*')
            for patient_folder in patient_folders:
                file_paths = glob.glob(f'{patient_folder}/*.dcm')
                for file_path in file_paths:
                    file_path = file_path.replace('\\\\', '/')
                    file_path = file_path.replace('\\', '/')
                    file_path = file_path[len(DICOM_FOLDER_PATH):]
                    patient_id = file_path.split('/')[-2]

                    #insert dicom filed in DB
                    self.insert_row_in_table('dicom_files',
                                        ['file_type', 'file_path'],
                                        ['augmented_struct', file_path])

                    #find ID of the file we just inserted
                    sql_string = "SELECT MAX(dicom_file_id) FROM dicom_files WHERE file_type = 'augmented_struct'"
                    dicom_file_id = self.cursor.execute(sql_string).fetchone()[0]

                    #insert new structure in DB 
                    self.insert_row_in_table('structures',
                                        ['structure_collection_id', 'patient_id', 'dicom_file_id'],
                                        [collection_id, patient_id, dicom_file_id])

    def get_structures_from_collection(self, structure_collection_id, departments=None, exclude_patients =None, select_patients = None): 
        """ List departments to only select from these. Use a list of patient_ids to exclude_patients or to select_patients """
        
        sql_string ='SELECT * FROM structures WHERE structure_collection_id = ?'
        variables = [structure_collection_id]

        if departments is not None:
            string_departments = ', '.join(f'"{department}"' for department in departments)
            sql_string = f'{sql_string} AND treatment_place IN ({string_departments})' 

        if exclude_patients is not None:
            string_ids = ', '.join(f'"{id}"' for id in exclude_patients)
            sql_string = f'{sql_string} AND patient_id NOT IN ({string_ids})'

        if select_patients is not None:
            string_ids = ', '.join(f'"{id}"' for id in select_patients)
            sql_string = f'{sql_string} AND patient_id IN ({string_ids})'


        structures = self.cursor.execute(sql_string, variables).fetchall()
        
        return(structures)

    def get_augmented_structure_paths_for_patient (self, patient_id, structure_collection_id = None):
        """ If structure_collection_id == None, all augmented structures for patient will be returned """
        
        structure_path_collection_name = list()
        sql_string ='SELECT dicom_file_id, structure_collection_id FROM structures WHERE patient_id =?'
        variables = [patient_id]
        
        if structure_collection_id == None:
            pass
        else:
            sql_string = sql_string + 'AND structure_collection_id == ?'
            variables.append(structure_collection_id)
            dicom_file_rows = self.cursor.execute(sql_string, variables).fetchall()

            for dicom_file_row in dicom_file_rows:
                dicom_file_id = dicom_file_row[0]
                sql_string = f'SELECT file_path FROM dicom_files WHERE dicom_file_id = {dicom_file_id}'
                dicom_file_path = self.cursor.execute(sql_string).fetchall()
        
                structure_path_collection_name.append([dicom_file_path[0], dicom_file_row[1]])

        return(structure_path_collection_name)

    

  


                    

                    

                    

                    


