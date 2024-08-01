from cordialrt.analysis.treatments_from_collection import init_treatments_from_collection
import cordialrt.helpers.exceptions as crtex


#Move to user config?
NON_DVH_ROI_DATAPOINT_SURFIXES = ['synonyms_found','calculation_time']

CT_PARAMETERS = {'ct_slice_thickness' : 'SliceThickness',
                    'ct_manufacturer': 'Manufacturer',
                    'ct_kvp': 'KVP', 
                    'ct_software_version':'SoftwareVersions', 
                    'ct_pixel_spacing':'PixelSpacing'}

NON_ROI_DATAPOINTS = ['study_date',     
                        'fractions',
                        'plan_names',
                        'main_reference_dose',         
                        'boost_reference_dose',
                        'main_dose_scale_factor',              
                        'boost_dose_scale_factor',
                        'centre',
                        'dose_file_path',
                        'structure_file_path',        
                        'treatment_max_dose',
                        'laterality',
                        'left_right_dose_ratio',
                        'ct_slice_thickness',] + list(CT_PARAMETERS.keys())



class DataPoint():
    def __init__(self, name):
        self.name = name
        self.value = None
        self.value_string = None
        self.value_num = None

    def get_value(self):
        if self.value_num is not None:
            self.value = self.value_num
        elif self.value_string is not None:   
            self.value = self.value_string
        return self.value

    def print_name(self):
        print(self.name, 'printed')
    
    def describe(self):
        print('Name:', self.name)
        print('Value:', self.get_value())
        try:
            print('ROI standard name:', self.roi_standard_name)
        except AttributeError:
            pass
        try:
            print('DVH point:', self.dvh_point)
        except AttributeError:
            pass
        try:
            print('DVH point output type:', self.output_type)
        except AttributeError:
            pass
            
class GenericDataPoint(DataPoint):
    def __init__(self, parameter):
        self.parameter = parameter
        super(GenericDataPoint, self).__init__(parameter)
        self.name = parameter 

class RoiDataPoint(GenericDataPoint):
    def __init__(self, roi_standard_name, parameter):
        self.parameter = parameter
        self.roi_standard_name = roi_standard_name
        super(RoiDataPoint, self).__init__(parameter)
        self.name = f'{roi_standard_name}_{parameter}'

class DvhDataPoint(RoiDataPoint):
    def __init__(self, roi_standard_name, dvh_point, output_type):
        parameter = f'{dvh_point}_{output_type}'
        self.dvh_point = dvh_point
        self.output_type = output_type
        self.roi_standard_name = roi_standard_name
        super(DvhDataPoint, self).__init__(roi_standard_name, parameter)
        self.name = f'{roi_standard_name}_{parameter}'

def deconstruct_dvh_point_string(dvh_point_str):
    """ parameterize dvh point string name"""
    dvh_point_split = dvh_point_str.split('_')
    output_type = ''
    dvh_point = ''
    data_point_type = ''
    standard_name = '_'.join(dvh_point_split[:-2])

    if dvh_point_split[-1] in NON_DVH_ROI_DATAPOINT_SURFIXES:
        output_type = ''
        dvh_point = ''
        standard_name = dvh_point_split[-2]
        data_point_type = 'roi_other'

    elif dvh_point_split[-1] in ['abs', 'rel']:
        output_type = dvh_point_split[-1] 
        dvh_point = dvh_point_split[-2]
        standard_name = '_'.join(dvh_point_split[:-2])
        data_point_type = 'roi_dvh'

    elif dvh_point_split[-1] in ['mean','volume']:
        output_type = '' 
        dvh_point = 'mean'
        standard_name = '_'.join(dvh_point_split[:-1])
        data_point_type = 'roi_dvh'
   
    return (standard_name, dvh_point, output_type, data_point_type)

def extract_data_from_patient(
        collection_id,
        patient_id,
        data_points,
        log_path=None,  # create a log 
        structure_collection_id=None):  # Use alternative structure set

    """ Extracts data for a list of GenericDataPoints, RoiDataPoints
    and DvhDataPoints for a patient  """
    treatments = init_treatments_from_collection(collection_id, 
                                                 select_patients=[patient_id],
                                                 log_failed_path=log_path)
    
    if len(treatments) == 0:
        raise crtex.DataExtractionFailed(f'No treatments initiated for {patient_id}')
    else:
        treatment = treatments[0]
   
    if len(treatment.dose_paths) == 0:
        raise Exception

    # check if augmented structure set is to be used
    if structure_collection_id is None:
        pass
    else:
        try:
            augmented_structure_path = treatment.get_augmented_structures_for_patient(structure_collection_id)[0]
            treatment.reset_structure_information()
            treatment.change_structure_for_treatment(augmented_structure_path)
        except IndexError:
            raise crtex.AugmentedStructureMissing(f'no augmented struct for {treatment.patient_id}')

    for data_point in data_points: 
        if type(data_point) == GenericDataPoint:

            if data_point.parameter == 'study_date':
                data_point.value = treatment.get_study_date()
                
            elif data_point.parameter == 'fractions':
                data_point.value = treatment.get_plan_fractions()

            elif data_point.parameter == 'plan_names':
                data_point.value = treatment.get_plan_names()

            elif data_point.parameter == 'main_reference_dose':
                data_point.value = treatment.main_reference_dose
                    
            elif data_point.parameter == 'boost_reference_dose':
                data_point.value = treatment.boost_reference_dose

            elif data_point.parameter == 'main_dose_scale_factor':
                data_point.value = treatment.main_dose_scale_factor          
                    
            elif data_point.parameter == 'boost_dose_scale_factor':
                data_point.value = treatment.boost_dose_scale_factor

            elif data_point.parameter == 'centre':
                data_point.value = treatment.treatment_place

            elif data_point.parameter == 'dose_file_path':
                data_point.value = treatment.dose_path
            
            elif data_point.parameter == 'structure_file_path':
                data_point.value = treatment.structure_path
            
            elif data_point.parameter == 'treatment_max_dose':
                try:
                    data_point.value = treatment.get_max_dose()
                except MemoryError:
                    print(f'Memory Error with max_dose. Skipped treatment for {treatment.patient_id}')
                    raise Exception

            elif data_point.parameter  == 'laterality':
                try:
                    data_point.value = treatment.get_latterality()
                except MemoryError:
                    print(f'Memory Error with laterality. Skipped treatment for {treatment.patient_id}')
                    raise Exception
            
            elif data_point.parameter == 'left_right_dose_ratio':
                data_point.value = treatment.left_right_dose_ratio

            #CT characteristics: 
            
            elif data_point.parameter in CT_PARAMETERS.keys():
 
                try:
                    treatment.load_first_ct_data()
                    data_point.value = treatment.first_ct.ds[CT_PARAMETERS[data_point.parameter]].value
                except (MemoryError, KeyError):
                    print(f'Failed for {CT_PARAMETERS[data_point.parameter]}')
                    data_point.value = None
            else:
                print(f'Did not recognise the parameter {data_point.parameter}')

        # Dvh extraction        
        elif type(data_point) in [RoiDataPoint, DvhDataPoint]:

            #Both types needs a roi
            try:
                treatment.add_new_roi(data_point.roi_standard_name)
                roi = treatment.roi_by_name(data_point.roi_standard_name)
            except crtex.RoiAlreadyExists:
                roi = treatment.roi_by_name(data_point.roi_standard_name)

            if type(data_point) == RoiDataPoint:
                if data_point.parameter == 'synonyms_found':
                    data_point.value = roi.find_synonyms()
                elif data_point.parameter == 'priority_synonym':
                    data_point.value = roi.get_priority_synonym()

            if type(data_point) == DvhDataPoint:
                if structure_collection_id == structure_collection_id:
                    prioritize_roi_name = True
                else:
                    prioritize_roi_name = False

                data_point = roi.get_value_for_dvh_data_point(data_point, prioritize_roi_name = prioritize_roi_name) 

    return(data_points)