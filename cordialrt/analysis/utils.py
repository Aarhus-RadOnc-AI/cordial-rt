import pandas as pd
import cordialrt.database.database as rtdb
from Levenshtein import ratio
from dicompylercore import dicomparser
import cordialrt.helpers.user_config

user_config = cordialrt.helpers.user_config.read_user_config()
USER_NAME = user_config['user']
DICOM_FOLDER_PATH = user_config['dicom_file_parent_folder']


def structure_count(total_roi_list):
    """Counts the number of times the same structure name are found in the new dataset"""
    new_list = list()
    for roi_list in total_roi_list: #Manipulation of the list
        for roi in roi_list:
            new_list.append(roi)
    rois = pd.Series(new_list)
    pd.set_option('display.max_rows', rois.shape[0]+1)
    rois_counted = rois.value_counts()
    roi_names = rois.value_counts().index
    return rois_counted, roi_names

def prepare_list(rois_counted):
    #Just a function to unpack the list.. There is probarbly a smarter way to do this
    roi_cou = list()
    for roi in rois_counted:
        roi_cou.append(roi)
    return roi_cou

def remove_duplicates_in_roi_lists(rois_counted, roi_names, standard_name):
    """Removes duplicates between the roi list from the new data and the synonyms in the database"""
    with rtdb.DatabaseCall() as db:
        synonym_list = db.get_synonyms_from_standard_name(standard_name)
    
    rois_count = prepare_list(rois_counted)
    roi_name = prepare_list(roi_names)
    new_roi_names = list()
    new_rois_counted = list()
    for n in range(len(rois_count)):
        if roi_name[n] not in synonym_list:
            new_rois_counted.append(rois_count[n])
            new_roi_names.append(roi_name[n])
    return new_rois_counted, new_roi_names, synonym_list

def find_synonyms_from_new_data(standard_name, NUMBER_OF_VALUES_DISPLAYED, rois_counted, roi_names, metric_value):
    """Finds possible synonyms/misspellings of the standard_names with the Levenshtein-distance"""
    #This function uses Levenshtein to find possible synonyms to the SKAGEN names. 
    #Input: A synonym list, which is what we want to search from.
            #standard_name: 'standard_name', you want to search for
            #Number of values displayed: How many possible misspelling you want to see
            #rois_counted and roi_names: Counted rois from you new data. Is found through rtclass-Treatment.structure_count()
            #metric: where is the cut-off levenshtein distance
    #Output: The possible misspelling printed out. 
            #NB! You have to manually pick out the newly found synonyms, you want to add to the DB
    new_rois_counted, new_roi_names, synonyms = remove_duplicates_in_roi_lists(rois_counted, roi_names, standard_name)
    new_list = list()
    for synonym in synonyms:
        metric = 0
        name_list = list()
        for name in new_roi_names:
            new_metric = ratio(name, synonym)
            if (name not in new_list) and (new_metric > metric) and (new_metric > metric_value):
                metric = new_metric
                name_list.append(name)
        new_list.extend(name_list[-NUMBER_OF_VALUES_DISPLAYED:])
        print(synonym, ':\t\t\t', name_list[-NUMBER_OF_VALUES_DISPLAYED:])
    print('You have now found the possible synonyms/misspellings, \n you need to update the databse MANUALLY, with the correct synonyms')

def get_structure_names_from_id(patient_ids, collection_id): 
    """Returns a DataFrame with a count of all structure names in the patient treatments""" 
    data = list()
    with rtdb.DatabaseCall() as db:
        treatments = db.get_treatments_from_collection(collection_id, departments=None, exclude_patients =None, select_patients = patient_ids)
    
    for i, treatment in enumerate(treatments):
        if i in range(0,9000,100):
            print(f'{i}/{len(treatments)}')
            
        treatment_id = treatment[0]
        with rtdb.DatabaseCall() as db:
            files = db.get_file_paths_from_treatment(treatment_id)
        
        for file in files: 
            if file[2] == 'structure':
                structure = dicomparser.DicomParser(DICOM_FOLDER_PATH + file[3]) 
                struct_info = structure.GetStructures()

                for key, value in struct_info.items():
                    d = {'name': value['name'],
                        'center': file[3].split('/')[1],
                        'patient_id':file[3].split('/')[2],
                        'empty':value['empty'] } 
                    data.append(d)


    df_structs = pd.DataFrame(data)

    # with rtdb.DatabaseCall() as db:                
    #     sql_string ='SELECT synonym FROM skagen_synonyms WHERE priority_count > 0'
    #     synonyms = db.execute(sql_string).fetchall()
    # # synonyms = cursor.execute(sql_string).fetchall()

    # synonym_strings = list()
    # for s in synonyms:
    #     synonym_strings.append(s[0])

    # df_synonyms_counts = pd.DataFrame(df_structs.name.value_counts())
    # df_synonyms_counts['in_synonym_table'] = False

    # df_synonyms_counts.loc[df_synonyms_counts.index.str.lower().isin(synonym_strings), 'in_synonym_table'] = True

    return(df_structs)
