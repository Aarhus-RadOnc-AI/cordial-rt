import numpy as np
import os
from dicompylercore import dicomparser, dvh, dvhcalc
import pandas as pd

import cordialrt.database.database as rtdb
import cordialrt.analysis.sum_dose as rtsum
import cordialrt.helpers.exceptions as rtex
from Levenshtein import ratio

import cordialrt.helpers.user_config
user_config = cordialrt.helpers.user_config.read_user_config()
DICOM_FOLDER_PATH = user_config['dicom_file_parent_folder']

class Treatment():
    def __init__(self, treatment_id, patient_id, treatment_collection_id):
        self.treatment_id = treatment_id
        self.patient_id = patient_id
        self.treatment_collection_id = treatment_collection_id

        # Factors to scale the dose if the plan does not have all fractions in the treatment
        self.main_dose_scale_factor = None
        self.boost_dose_scale_factor = None

        # The dose that has been prescribed in the treatment
        self.main_reference_dose = None
        self.boost_reference_dose = None
        
        # About the files
        self.structure_paths = list()
        self.plan_paths = list()
        self.dose_paths = list()
        self.ct_paths = list()
        self.sum_dose_paths = list()
        self.augmented_structs = list()

        # Use these paths after init check
        self.sum_dose_path = None
        self.structure_path = None
        self.dose_path = None

        # Contains the dicom files data 
        self.structure = None
        self.plans = list()
        self.dose = None
        self.cts = list()

        #Other properties
        self.treatment_place = None
        self.study_date = None
        self.latterality = None
        self.coordinate_list = None
        self.plane_list = list()
        self.slice_thickness = None
        self.structure_id = None
        self.image_data = None
        self.left_right_dose_ratio = None

        self.rois = list()
    
    # Check data when init and sum doses if needed. 
    def init_check_structure(self):
        """ Raises exepsion if init check fail."""
        # Only one structure is allowed in each treatment
        if len(self.structure_paths) == 0:
            raise rtex.InitError(f"Error, no structure for patient {self.patient_id} , treatment {self.treatment_id}")
        elif len(self.structure_paths) > 1 :
            raise rtex.InitError(f"Error, more than one structure for patient {self.patient_id} , treatment {self.treatment_id}")
            
        self.structure_path = self.structure_paths[0]
        return(True)

    def init_check_cts(self):
        """ Raises exepsion if init check fail."""
        # Only one structure is allowed in each treatment
        if len(self.ct_paths) == 0:
            raise rtex.InitError(f"Error, no cts for patient {self.patient_id} , treatment {self.treatment_id}")
        else:
            return(True)

    def init_check(self): 
        """Returns True if treatment is initated correctly. Also sets the dose, struct to be used"""      
        try:
            self.init_check_structure()    
        except rtex.InitError as e:
            print('Raise')
            raise rtex.InitError(e)

        try:
            self.init_check_cts()    
        except rtex.InitError as e:
            print('Raise')
            raise rtex.InitError(e)
        
        # More plans than doses is a problem. 
        if len(self.plan_paths ) > len(self.dose_paths):
            plan_names =self.get_plan_names()
            raise rtex.InitError(f'Failed for patinet: {self.patient_id} More plans than dose files. Plans: {plan_names}')

        # One dose. We want at most one sum_dose for each treatment. If there is 0, we use the single dose from dose_paths
        if len(self.sum_dose_paths) == 0:
            if len(self.dose_paths) == 1 and self.main_dose_scale_factor == 1:
                    # No sum or scale needed.
                    self.dose_path = self.dose_paths[0]
            else: 
                #We need to sum and/or scale the dose and save a new dose file. 
                try:
                    self.sum_dose_path, self.dose = rtsum.create_sum_dose_file(self.dose_paths, self.patient_id, self.treatment_id, self.get_plans(),
                                self.main_reference_dose, self.main_dose_scale_factor, self.boost_reference_dose, self.boost_dose_scale_factor)
                except rtex.SumDoseError as e:
                    raise e

                if self.sum_dose_path is None:
                    # dose summation failed
                    raise rtex.InitError(f'Failed for patinet: {self.patient_id} Dose summation failed')
                else:
                    self.dose_path =  self.sum_dose_path
        
        # If the doses have already been summed
        elif len(self.sum_dose_paths) == 1:
            #Check if file exisits: 
            if os.path.isfile(self.sum_dose_paths[0]):
                self.sum_dose_path = self.sum_dose_paths[0]
                self.dose_path = self.sum_dose_path
            else:
                # We need to sum the doses, but not create a new line in the db
                try:
                    self.sum_dose_path, self.dose = rtsum.create_sum_dose_file(self.dose_paths, self.patient_id, 
                                                                self.treatment_id, self.get_plans(), self.main_reference_dose, self.main_dose_scale_factor, 
                                                                self.boost_reference_dose, self.boost_dose_scale_factor, write_line_in_db = False)
                except rtex.SumDoseError as e:
                    raise e

                if self.sum_dose_path is None:
                    # dose summation failed
                    raise rtex.InitError(f'Failed for patinet: {self.patient_id} Dose summation failed')
                else:
                    self.dose_path =  self.sum_dose_path
        else:
            raise rtex.InitError(f'Failed for patinet: {self.patient_id} More than one sum_dose for patienttreatment {self.treatment_id}')    
        
        return(True)
         
    # Get functions for varoius treamtent parameters.      
    def get_structure(self):
        """Returns the structure data"""
        if self.structure is None:
            self.structure = dicomparser.DicomParser(self.structure_path)       
        return(self.structure)

    def get_dose(self):
        """Returns the dose data"""
        if self.dose is None:
            self.dose = dicomparser.DicomParser(self.dose_path) 
        return(self.dose)

    def get_plans(self):
        """Returns a list of plan data"""
        if len(self.plans) == 0 and len(self.plan_paths) !=0:
            for path in self.plan_paths:
                self.plans.append(dicomparser.DicomParser(path))             
        return(self.plans)    

    def get_study_date(self):
        """ Returns study date from the first plan of the treatment"""
        plan_dates = list()
        for plan in self.get_plans(): 
            plan_dates.append(plan.ds.StudyDate)
        if len(plan_dates ) == 0:
            self.study_date = None
        else:
            self.study_date = min(plan_dates)
        return(self.study_date)

    def get_plan_fractions(self):
        """Returns a list of fractions for plans in the treatment"""
        fractions = list()
        for plan in self.get_plans():
            fractions.append(plan.ds.FractionGroupSequence[0].NumberOfFractionsPlanned)
        return(fractions)

    def get_plan_names(self):
        """Returns a list of plan names for plans in the treatment"""
        plan_names = list()
        plans = self.get_plans()
        for plan in plans:
            plan_names.append(plan.GetPlan()['label'])
        return(plan_names)

    def get_ct_image_data(self):
        """Return information about the CT from the first image"""
        
        if self.image_data is None:
            try:
                self.image_data = dicomparser.DicomParser(self.ct_paths[0]).GetImageData()
            except IndexError:
                raise rtex.NoCtsError(f'{self.patient_id} has no cts. get_ct_image_data failed')
        return(self.image_data)

    def get_max_dose(self):
        """ Returns the max value of the dosegrid"""
        dose_data = self.get_dose().GetDoseData()
        max_dose = dose_data['dosegridscaling'] * dose_data['dosemax']
        return(max_dose)

    def right_left_dose_grid_ratio(self):
        """ Finds the ration bewteen the right and left side of the CT-scan. Ratio = right integral dose / left integral dose"""
        rt_dose = self.get_dose()
        try:
            ct_mid_position_patient_coordinates = (self.get_ct_image_data()['position'][0] + 
            (self.get_ct_image_data()['columns']*self.get_ct_image_data()['pixelspacing'][0]/2))
        except rtex.NoCtsError as e:
            raise e
            
        dose_grid_ct_mid_position_patient_coordinates = ct_mid_position_patient_coordinates - rt_dose.ds.ImagePositionPatient[0]
        
        dose_grid_mid_pixel = int(abs(round(dose_grid_ct_mid_position_patient_coordinates / rt_dose.ds.PixelSpacing[0],0)))
    
        if rt_dose is None:
            print(self.patien_id, self.treatment_id, 'No dose for treatment')
            return(None)
        else:
            rt_dose.GetDoseData()
            planes = \
                (np.array(rt_dose.ds.GridFrameOffsetVector) \
                * rt_dose.ds.ImageOrientationPatient[0]) \
                + rt_dose.ds.ImagePositionPatient[2]
            # print(planes)
            right_integral_dose = 0
            left_integral_dose = 0

            for index, z in enumerate(planes):
                grid = rt_dose.GetDoseGrid(z)
                r_grid = grid[:, 0:dose_grid_mid_pixel]

                try:
                    right_integral_dose = right_integral_dose + np.percentile(r_grid,95)
                except IndexError:
                    continue
                    
                l_grid = grid[:,dose_grid_mid_pixel:]
                
                try:
                    left_integral_dose = left_integral_dose + + np.percentile(l_grid,95)
                except IndexError:
                    continue

            ratio = right_integral_dose/left_integral_dose
            return(ratio)

    def get_latterality(self):
        """ Translates the left / right dose grid ratios to laterality. 
        The threshold values have been chosen from observation."""
        
        if self.latterality is None:
            try:
                ratio = self.right_left_dose_grid_ratio()
            except rtex.NoCtsError as e:
                left_right_dose_ratio = None
                raise e

            self.left_right_dose_ratio  = ratio
            
            if ratio < 0.8:
                latterality ='left'
            elif ratio > 1.2:
                latterality = 'right'
            else:
                latterality = 'bilat'
            self.latterality = latterality

        return(self.latterality)

    # Load data
    def get_file_paths(self):
        """ Read file paths from the db"""
        with rtdb.DatabaseCall() as db:
            file_rows = db.get_file_paths_from_treatment(self.treatment_id)
        return(file_rows)

    def load_file_paths(self):
        """ Loads the file paths from the db to the treatment"""
        file_rows = self.get_file_paths()

        for file_row in file_rows:
            local_path = f'{DICOM_FOLDER_PATH}{file_row[3]}'
            if file_row[2] == 'ct':
                self.ct_paths.append(local_path)
            elif file_row[2] == 'structure':
                self.structure_paths.append(local_path)
            elif file_row[2] == 'dose':
                self.dose_paths.append(local_path)
            elif file_row[2] == 'plan':
                self.plan_paths.append(local_path)
            elif file_row[2] == 'sum_dose':
                self.sum_dose_paths.append(local_path)
            else:
                print('Error in file type', file_row)

    def load_ct_data(self):
        """Load the CT-DICOM files """
        self.cts = list()
        for path in self.ct_paths:
            self.cts.append(dicomparser.DicomParser(path))
                    
    def load_all_dicom_data(self):
        """ Load all dicom file data into the treatment"""
        self.get_structure()
        self.load_ct_data()
        self.get_plans()
        self.get_dose()

    #Functionality for augmented structures

    def get_augmented_structures_for_patient(self, structure_collection_id = None):
        """ Returns a list of structure paths and structure_collection names"""
        with rtdb.DatabaseCall() as db:
            astructs = db.get_augmented_structure_paths_for_patient(patient_id = self.patient_id, structure_collection_id  =structure_collection_id )
        self.augmented_structs = astructs
        return(astructs)

    def reset_structure_information(self):
        """ Reset the structure information for the treatment to blank"""
        self.structure_paths = list()
        self.coordinate_list = None
        self.plane_list = list()
        self.slice_thickness = None
        self.structure_id = None
        self.rois = list()
        self.structure = None

    def change_structure_for_treatment(self, struct_path):
        """ changes the structure used and resets all DVHs """
        self.reset_structure_information()
        self.structure_path = f'{DICOM_FOLDER_PATH}{struct_path}'
        self.structure = self.get_structure()

    def set_original_structure_for_treatment(self):
        """ Reset the structure information for the treatment to the original structure"""
        self.reset_structure_information()
        self.get_file_paths()
        self.load_file_paths()

    #Roi functions
    def roi_by_name(self, name):
        "Return roi from treatment by its name"
        for roi in self.rois:
            if roi.standard_name == name:
                return(roi)
        return(None)
    
    def add_new_roi(self, roi_standard_name):
        """ Add a new ROi to the treatment"""
        if self.roi_by_name(roi_standard_name) is None:
            new_roi = Roi(roi_standard_name, self)
            self.rois.append(new_roi)
        else:
            print('Roi already exists in treatment')
    
    def extract_roi_names_from_new_data(self):
        """ This function extracts all roi names in a treatment and places it in the list: roi_list """
        roi_list = list()
        structure = self.get_structure()
        structure_info = structure.GetStructures()
        for i in structure_info.keys():
            roi = structure_info[i]['name']
            roi_list.append(roi.lower())
        self.roi_list = roi_list
        return self.roi_list

    def get_structure_information(self, standard_name):
        """Finds the coordinatesets for a given structure at a given treatment"""
        #This function gives the coordinatesets for a given structure at a given treatment
        #       Input:         treatment and the skagen name of the structure of interest
        #       Output: the coordinateset set for the chosen structure in this format: [[x,y,z],...,[xn,yn,z]],...[[x,y,zn],...,[xn,yn,zn]
        with rtdb.DatabaseCall() as db:
            synonym_list = db.get_synonyms_from_standard_name(standard_name, self.treatment_collection_id)
        
        structures = self.get_structure()
        roi_names = structures.GetStructures()
        for index, roi in roi_names.items():
            if (roi['name'].lower() in synonym_list) and not (roi['empty']):
                coordinate_list = list()
                planes = structures.GetStructureCoordinates(roi['id'])
                self.plane_list = planes.keys()
                self.slice_thickness = structures.CalculatePlaneThickness(planes)
                self.structure_id = roi['id']
                self.structure_name = roi['name'].lower
                for key in self.plane_list:
                    set_with_most_pts = list() ##In some cases, two coordinatesets are present for the structures. This removes the coordinateset, with the fewest coordinates. This is not tested on other structures than LADCA! So it's not necessaily a correct assumption for all structures
                    data_pts = planes[key]
                    if len(data_pts) > 1:
                        for i in range(len(data_pts)):
                            set_with_most_pts.append(data_pts[i]['num_points'])
                        max_pts = max(set_with_most_pts)
                        max_index = set_with_most_pts.index(max_pts)
                        coordinate = data_pts[max_index]['data']
                    else:
                        coordinate = data_pts[0]['data']
                    coordinate_list.append(coordinate)
                self.coordinate_list = coordinate_list
                return(self.coordinate_list, self.plane_list, self.slice_thickness, self.structure_id)
        #If nothing is found
        return(None)

    def plot_structure(self):
        """This function allows you to plot the structure in a 3D view"""
        x_coordinates = list()
        y_coordinates = list()
        z_coordinates = list()

        for i in self.coordinate_list:
            for n in i:
                x_coordinates.append(n[0])
                y_coordinates.append(n[1])
                z_coordinates.append(n[2])

        fig = plt.figure()
        ax = fig.add_subplot(projection='3d')
        fig.set_size_inches(18.5, 10.5)
        ax.scatter(x_coordinates,y_coordinates,z_coordinates)
        plt.show()


class Roi():
    """ This class represents  a region of interest, as defined by a standard name. The standard name is linked to a number of synonyms found by investigaitng the data. 
    When a DVH value is requested from a ROI, treatment structure files are searched for these synonyms. """

    def __init__(self, roi_standard_name, treatment):
        self.standard_name = roi_standard_name
        self.treatment = treatment
    
        self.dvh_priority = None   
        self.priority_synonym = None
        self.synonyms_found = list()
        

    def find_synonyms(self):
        """ Get all synonyms linked to the ROI standard name """
        synonyms_standard= list()
        with rtdb.DatabaseCall() as db:
            row_data = db.get_synonyms_from_standard_name(self.standard_name, self.treatment.treatment_collection_id, priority = True)

        for row in row_data:
            if row[2] == None:
                laterality = 'x'
            else:
                laterality = row[2]

            if row[1] == None:
                priority_count = 0
            else:
                priority_count = row[1]

            synonyms_standard.append({'name':row[0],
                                    'priority_count': priority_count,
                                    'laterality': laterality})

        structures_in_file = self.treatment.get_structure().GetStructures()

        for key, structure in structures_in_file.items():
            if any(d['name'] == structure['name'].lower() for d in synonyms_standard) and not (structure['empty']):
                self.synonyms_found.append({'name': structure['name'],
                                            'structure_id': structure['id'],
                                            'priority_count': next((item.get('priority_count') for item in synonyms_standard if item["name"].lower() == structure['name'].lower()), False),
                                            'laterality': next((item.get('laterality') for item in synonyms_standard if item["name"].lower() == structure['name'].lower()), False),
                                            })
        
        # Sort by laterlity, then by negative count ascending (highest original count first)
        self.synonyms_found = sorted(self.synonyms_found, key = lambda i: (i['laterality'], -i['priority_count']))
        return(self.synonyms_found)  

    def calculate_dvh(self, structure_id): 
        """Calculate the DVH for the structure using the main reference dose for relative dose calculation"""
        calcdvh = dvhcalc.get_dvh(self.treatment.structure_path, self.treatment.dose_path, structure_id)
        calcdvh.rx_dose = self.treatment.main_reference_dose
        return(calcdvh)

    def calculate_dvh_for_roi_name(self):
        """Get the DVH for a ROI using the ROI name as the only synonym"""
        structures_in_file = self.treatment.get_structure().GetStructures()
        for key, structure in structures_in_file.items():
            if structure['name'] == self.standard_name:
                structure_id = key
                
        dvh_roi= self.calculate_dvh(structure_id)
        return(dvh_roi)

    def get_priority_synonym(self):
        """Get the synonym with the highest priority (laterality, count)"""
        if self.priority_synonym is None:
            synonyms = self.find_synonyms()
            priority_structure = None

            if len(synonyms) == 0:
                return(None)

            for structure in synonyms:
                if structure['laterality'] == 'i': #ipsilateral"
                    priority_structure = structure
                    break
                if structure['laterality'] == 'l' and self.treatment.get_latterality() == 'left':
                    priority_structure= structure
                    break
                elif structure['laterality'] == 'r' and self.treatment.get_latterality() == 'right':
                    priority_structure = structure
                    break
            
            if priority_structure == None:
                priority_structure  = synonyms[0]
            
            self.priority_synonym = priority_structure

        return(self.priority_synonym)

    def calculate_dvh_for_priority_synonym(self):
        """Calculate the DVH for a ROI by finding the synonym with the highest priority (laterality, count)"""
        priority_structure = self.get_priority_synonym()
        if priority_structure is None:
            dvh_priority = None
        else:
            dvh_priority = self.calculate_dvh(priority_structure['structure_id'])
            self.dvh_priority = dvh_priority
        return(dvh_priority)

    def get_dvh_priority_synonym(self): 
        """Get the DVH for a ROI by finding the synonym with the highest priority (laterality, count)"""
        if self.dvh_priority is None:
            self.dvh_priority = self.calculate_dvh_for_priority_synonym()
        return(self.dvh_priority)

    def dvh_points_from_roi(self, data_dict, dvh_points): 
        """Get multiple dvh points from a ROI, using the synonym with the highest priority. 
            Example of dvh_points: [['mean', ''],['volume', ''],['d0.01cc', 'abs],['d50', 'abs'],['v95', 'rel']] 
            Example of data_dict: {'Patient_id': 123,  }
        """
        try:
            self.get_dvh_priority_synonym()
        except ValueError:
            print('Roi dvh error')
            self.dvh_priority = None
        
        roi_name = self.standard_name

        for dvh_point_input in dvh_points:
            dvh_point = dvh_point_input[0]
            rel_abs = dvh_point_input[1]

            if dvh_point in ['volume', 'mean']:
                try: 
                    data_dict[f'{roi_name}_{dvh_point}'] = getattr(self.dvh_priority, dvh_point)
                except:
                    data_dict[f'{roi_name}_{dvh_point}'] = None
            else:
                if rel_abs == 'rel':
                    try: 
                        data_dict[f'{roi_name}_{dvh_point}_value'] = getattr(self.dvh_priority.relative_volume, dvh_point).value
                        data_dict[f'{roi_name}_{dvh_point}'] = getattr(self.dvh_priority.relative_volume, dvh_point)
                    except:
                        data_dict[f'{roi_name}_{dvh_point}_value'] = None
                        data_dict[f'{roi_name}_{dvh_point}'] = None
                else:
                    try: 
                        data_dict[f'{roi_name}_{dvh_point}_value'] = getattr(self.dvh_priority, dvh_point).value
                        data_dict[f'{roi_name}_{dvh_point}'] = getattr(self.dvh_priority, dvh_point)
                    except:
                        data_dict[f'{roi_name}_{dvh_point}_value'] = None
                        data_dict[f'{roi_name}_{dvh_point}'] = None

        return(data_dict)  
