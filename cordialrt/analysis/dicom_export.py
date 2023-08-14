from pynetdicom.sop_class import CTImageStorage, RTImageStorage,RTDoseStorage, RTStructureSetStorage,RTBeamsTreatmentRecordStorage, RTPlanStorage
from pydicom import read_file
from pynetdicom import AE
import datetime


def dicom_send(ip,port, ae_title, paths_to_transfer = None,
                treatments_to_transfer = None,
                use_sum_dose = False,
                log_path = None,
                series_in_protocol_path = None, 
                protocol_id = None,
                ):
    
    """ 
    Use DICOM communication C-Store to send dicome fiels to a DICOM SCP. 
    DICOM files can be provided as a list of file-paths, a list of treatments or a combination. 
    When providing treatments, use_sum_dose is used to specify if the sum_dose or the indvidual dose_files are
    sent, when both are present. A log of the transfer is saved if a log_path is provided. A CSV file with seriesUIDS
    and a protocol UID (if needed by the recieving party) is saved if series_in_protocol_path is provided
    """
    
    dicom_transfer_paths = list()

    if paths_to_transfer is not None:
         dicom_transfer_paths = paths_to_transfer
    if treatments_to_transfer is not None:
        for treatment in treatments_to_transfer:
            dicom_transfer_paths = dicom_transfer_paths + treatment.ct_paths + treatment.structure_paths + treatment.plan_paths 
            
            if use_sum_dose:
              dicom_transfer_paths = dicom_transfer_paths + treatment.sum_dose_paths
            else:
               dicom_transfer_paths = dicom_transfer_paths + treatment.dose_paths
    
    if len(dicom_transfer_paths) == 0:
         print('No files send')
         return()
               
    series_in_protocol = list()
    ae = AE(ae_title=ae_title)

    ae.add_requested_context(CTImageStorage)
    ae.add_requested_context(RTImageStorage)
    ae.add_requested_context(RTDoseStorage)
    ae.add_requested_context(RTStructureSetStorage)
    ae.add_requested_context(RTBeamsTreatmentRecordStorage)
    ae.add_requested_context(RTPlanStorage)

    assoc = ae.associate(ip, port,ae_title=ae_title)
    if assoc.is_established:

        if series_in_protocol_path is not None:
            with open(f'{series_in_protocol_path}', 'a+') as f:
                        f.write("%s\n" % f'# {ae_title} {str(datetime.datetime.now())}')

        log_header = 'patient_id,modality,series_instance_uid,sop_instance_uid,time_stamp,c_move_status_code' 
       
        if log_path is not None:
            with open(f'{log_path}', 'a+') as f:
                        f.write("%s\n" % log_header)

        for i, dicom_file_path in enumerate(dicom_transfer_paths): 
            if i % 100 == 0:
                print(f'{i}/{len(dicom_transfer_paths)}')
                
            log_line = list()
            series_line = str()

            try:
                dataset = read_file(dicom_file_path)
            except FileNotFoundError as e:
                print(f'{dicom_file_path} {e}')
                continue 
            
            try:
                log_line.append(dataset.PatientID)
                log_line.append(dataset.Modality)
                log_line.append(dataset.SeriesInstanceUID)
                log_line.append(dataset.SOPInstanceUID)
                log_line.append(str(datetime.datetime.now()))
            except AttributeError as e:
                print(f'{dicom_file_path} {e}')
                continue

            send_status = assoc.send_c_store(dataset)
            status_code = send_status.Status

            if status_code == 0: # Sucecess
                if f'{protocol_id};{dataset.SeriesInstanceUID}' not in series_in_protocol:  
                    series_in_protocol.append(f'{protocol_id};{dataset.SeriesInstanceUID}')
                    series_line = f'{protocol_id};{dataset.SeriesInstanceUID}'
                    
                    if series_in_protocol_path is not None:
                        with open(f'{series_in_protocol_path}', 'a+') as f:
                            f.write("%s\n" % series_line)
            else:
                print(f'{dicom_file_path} send fails. Staus: {status_code}')
                
            log_line.append(str(status_code))

            if log_path is not None:
                with open(f'{log_path}', 'a+') as f:
                    f.write("%s\n" % ','.join(log_line))

        assoc.release()
                # write to log if send fails 
    else:
        print('Associaton not established')        
                    