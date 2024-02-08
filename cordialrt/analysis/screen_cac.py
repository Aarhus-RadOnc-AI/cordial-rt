import pandas as pd
import numpy as np
import glob
import cv2
import gc
import datetime
import math
from cordialrt.analysis.treatments_from_collection import init_treatments_from_collection
import cordialrt.database.database as rtdb 

class StructError(Exception):
    """Base class for other exceptions"""
    pass

def patients_already_screened(center, screen_files_folder_path):
    screened_patient_ids = list()
    
    #set the date as wildcard
    cac_status_paths = glob.glob(f'{screen_files_folder_path}/cac_status_{center}_*')

    for path in cac_status_paths:
        df_excel = pd.read_excel(path)
        screened_patient_ids = screened_patient_ids + df_excel.patient_id.unique().tolist()

    #keep only the unique
    screened_patient_ids = list(set(screened_patient_ids))    
    print(f'Patients screened from {center}:', len(screened_patient_ids))
    return(screened_patient_ids)

def heart_contour_info(treatment, heart_struct, deep_learning_collection_id, deep_learning_structure_name):
    """ Returns dict with Key: CT UID,  Value: [x, y] contour coordinates for slices containg the heart"""
    structure_id = None

    if heart_struct == 'deep_learning':
        if ((deep_learning_collection_id is None) or (deep_learning_structure_name is None)):
            raise StructError('deep_learning_collection_name and deep_learning_structure_name not provided')
        else:    
            treatment.reset_structure_information()
            path_collection_names = treatment.get_augmented_structures_for_patient(structure_collection_id = deep_learning_collection_id )
            if len (path_collection_names) == 0:
                raise StructError(f'No deep learning structure file for {treatment.patient_id}')
            else:
                if path_collection_names[1] == deep_learning_collection_id:
                    
                    treatment.change_structure_for_treatment(path_collection_names[0])
                    structures = treatment.get_structure()
                    roi_names = structures.GetStructures()
                    structure_id = None
                    for index, roi in roi_names.items():
                        if (roi['name'].lower() == deep_learning_structure_name) and not (roi['empty']):
                            structure_id = roi['id']
                    if structure_id is None:
                        raise StructError(f'No deep learning structure for {treatment.patient_id}')
        
    elif heart_struct == 'treatment':    
        treatment.add_new_roi('heart')
        structure_id = treatment.roi_by_name('heart').get_priority_synonym()['structure_id']   
    else:
        #try using the name for heart_struct
        _,_,_,structure_id = treatment.get_structure_information(heart_struct)
        if structure_id is None:
            raise StructError(f'{treatment.patient_id} No structure named {heart_struct} found')
    
    ct_heart_slices = dict()

    for roi_contour_sequence in treatment.get_structure().ds.ROIContourSequence:   
        if roi_contour_sequence.ReferencedROINumber == structure_id: 
            for contour_sequence in roi_contour_sequence.ContourSequence:   
                for image_contour_sequence in contour_sequence.ContourImageSequence:  
                    xs = contour_sequence.ContourData[::3]
                    ys = contour_sequence.ContourData[1::3]
                    zs = contour_sequence.ContourData[2::3]

                    ct_heart_slices[image_contour_sequence.ReferencedSOPInstanceUID] = [xs, ys]
                    xs=[]
                    ys=[]
                    zs=[]  

    return(ct_heart_slices)

def crop_ct_to_heart(ct, ct_heart_slice): 
   
    ct_pixels = ct.ds.pixel_array
    # The coordinates to match the slice
    xs = ct_heart_slice[0]
    ys = ct_heart_slice[1]

    # remember to take patient orientation into acocunt. May differ 
    xs = [(x -ct.ds.ImagePositionPatient[0])/ct.ds.PixelSpacing[0] for x in xs]
    ys = [(y -ct.ds.ImagePositionPatient[1])/ct.ds.PixelSpacing[0]for y in ys]

    xy_set = list()
    for i, x in enumerate(xs):
            xy_set.append([x, ys[i]])

    #Use heart contour to set pixelvalues = 0 outside the heart
    heart_contour = np.array(xy_set).reshape((-1,1,2)).astype(np.int32)
    heart_mask = np.zeros(ct_pixels.shape, np.uint8)
    cv2.drawContours(heart_mask,[heart_contour], 0, (255,255,255), -1)
    heart_mask_bool = np.array(heart_mask, dtype = bool)
    ct_pix_crop= np.where(heart_mask_bool , ct_pixels, 0)

    # Crop the ct to a box around the heart
    first_pix_y = int(round(min(ys),0))
    last_pix_y = int(round(max(ys),0))
    first_pix_x = int(round(min(xs),0))
    last_pix_x = int(round(max(xs),0))
    ct_pix_crop = ct_pix_crop[first_pix_y:last_pix_y,first_pix_x:last_pix_x]

    # Number of pixels in the heart to report the heart volume used
    pixels_in_heart_slice = heart_mask_bool.sum()
    return(ct_pix_crop, pixels_in_heart_slice)

def create_cac_mask(ct, ct_cropped):
    # Create a houndsfield (HU) unit version of the CT
    hu_pix_crop = ct_cropped * ct.ds.RescaleSlope + ct.ds.RescaleIntercept

    # Create a mask of HU abover 130
    cac_mask = (hu_pix_crop >= 130) & (hu_pix_crop < 1300)
    cac_in_heart_mask = np.zeros_like(hu_pix_crop)
    cac_in_heart_mask[cac_mask] = 255
    cac_in_heart_mask= np.uint8(cac_in_heart_mask)

    return(cac_in_heart_mask)

def conutour_and_get_cac_data(patient_id, ct, ct_cropped, cac_in_heart_mask):
    d = list()
    contours = list()
    ret, thresh = cv2.threshold(cac_in_heart_mask, 0, 1, cv2.THRESH_BINARY)
    contours, hierarchy = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)

    for contour in contours:
        if cv2.contourArea(contour) > 1: # exclude ares of 1 pixel
            if (cv2.contourArea(contour)* ct.ds.PixelSpacing[0] * ct.ds.PixelSpacing[1]) >= 1: # exclude areas <1mm
                data = dict()
                data['patient_id'] = patient_id
                data['ct_uid'] = ct.ds.SOPInstanceUID
                data['ct_number'] = ct.ds.InstanceNumber
                data['cac_area'] = cv2.contourArea(contour)
                data['slice_thickness'] = ct.ds.SliceThickness
                data['pixel_spacing_1'] = ct.ds.PixelSpacing[0]
                data['pixel_spacing_2'] = ct.ds.PixelSpacing[1]
                data['croped_slice_shape'] = cac_in_heart_mask.shape
                data['energy'] = ct.ds.KVP

                #minimum enclosing circle
                (x,y),radius = cv2.minEnclosingCircle(contour)
                center_min_circle = (int(x),int(y))
                radius_min_circle = int(radius)

                convex = cv2.isContourConvex(contour)

                data['center_min_circle']= center_min_circle
                data['radius_min_circle'] = radius_min_circle
                data['is_convex'] = convex
                d.append(data)

                # evalaute pixel values
                hu_pix_crop = ct_cropped * ct.ds.RescaleSlope + ct.ds.RescaleIntercept
                pixel_values = list()
                x_y_pixel_values = list()
                # Iterate over each point in the contour
                for point in contour:
                    # Extract x and y coordinates of the point
                    xp, yp = point[0]
                    
                    # Get the pixel value at this coordinate
                    pixel_value = hu_pix_crop[yp, xp]  # Note the reverse order of x and y
                    pixel_values.append(pixel_value)
                    x_y_pixel_values.append([xp,yp,pixel_value])

                data['pixel_values_hu'] =  pixel_values
                data['x_y_pixel_values_hu'] = x_y_pixel_values
    return(d)

def save_data_to_files(cac_slice_data_center, cac_status_center,center, screen_files_folder_path):
    time_stamp = f'{datetime.datetime.now().date()}_{datetime.datetime.now().hour}_{datetime.datetime.now().minute}'

    if len(cac_slice_data_center) > 0:
        df_cac_slices = pd.DataFrame(cac_slice_data_center)
        df_cac_slices.to_excel(f'{screen_files_folder_path}/cac_slices_{center}_{time_stamp}.xlsx')

    if len(cac_status_center) > 0:   
        df_cac_status = pd.DataFrame(cac_status_center)
        df_cac_status.to_excel(f'{screen_files_folder_path}/cac_status_{center}_{time_stamp}.xlsx')

def main(center:str, screen_files_folder_path:str, heart_struct:str,select_patients:list,
        max_number_of_patients = None, 
        deep_learning_collection_id = None, 
        deep_learning_structure_name = None, ):

    cac_status_center = list()
    cac_slice_data_center = list()

    screened_patient_ids = patients_already_screened(center, screen_files_folder_path)
    patinets_not_screened = list(set(select_patients)- set(screened_patient_ids))

    if max_number_of_patients is not None:
        if max_number_of_patients <= len(patinets_not_screened):
            patinets_not_screened = patinets_not_screened[0:max_number_of_patients]

    for patient_id in patinets_not_screened:
        cac_slice_data_patient= list()
        cac_status_patient = dict()
        pixels_in_the_heart = 0 

        treatments = init_treatments_from_collection(54, departments= [center], 
        select_patients= [patient_id])    

        for treatment in treatments:
            treatment.load_ct_data()
            try:
                ct_heart_slices = heart_contour_info(treatment, heart_struct, deep_learning_collection_id, deep_learning_structure_name)
            except StructError as e:
                print(e)
                continue
            
            ct_numbers_in_heart = list()
            for ct in treatment.cts:
                if ct.ds.SOPInstanceUID in ct_heart_slices.keys():
                    ct_numbers_in_heart.append(ct.ds.InstanceNumber)
                    ct_cropped, pixels_in_heart_slice = crop_ct_to_heart(ct, ct_heart_slices[ct.ds.SOPInstanceUID]) 
                    cac_in_heart_mask = create_cac_mask(ct, ct_cropped)
                    pixels_in_the_heart = pixels_in_the_heart + pixels_in_heart_slice
                    if cac_in_heart_mask.sum() == 0:
                        continue
                    else:
                        cac_slice_data = conutour_and_get_cac_data(treatment.patient_id, ct, ct_cropped, cac_in_heart_mask)       
                        cac_slice_data_patient = cac_slice_data_patient + cac_slice_data

            # Data for patient cac status
            cac_status_patient['patient_id'] = treatment.patient_id
            cac_status_patient['heart_volume'] = pixels_in_the_heart*ct.ds.PixelSpacing[0]*ct.ds.PixelSpacing[1]*ct.ds.SliceThickness/1000
            cac_status_patient['non_zero_cac_slices'] = len(cac_slice_data_patient)
            cac_status_patient['ct_numbers_in_heart'] = ct_numbers_in_heart
            
            del(ct)
            gc.collect()
                        
        cac_slice_data_center = cac_slice_data_center + cac_slice_data_patient
        
        if cac_status_patient: #check if empty
            cac_status_center.append(cac_status_patient) 

        try:
            del(treatments)
            del(treatment)
            gc.collect()
        except UnboundLocalError:
            pass
    
    save_data_to_files(cac_slice_data_center,cac_status_center,center, screen_files_folder_path)

