import csv

def cpr_convert(cpr):
    cpr = str(cpr)
    if len(cpr) == 9:
        cpr = '0'+cpr
        
    if cpr[7] != '-':
        cpr = cpr[:6] +'-'+cpr[6:]
    return cpr

def get_convert_dict():
    with open('Z:\lasref01\documentLibrary\IDReport_all_man.txt', mode='r') as infile:
        reader = csv.reader(infile, delimiter=';' )   
        id_dict = {rows[0]:rows[1] for rows in reader}
    return(id_dict)


def convert_cpr_to_id(cpr):
    convert_dict = get_convert_dict()
    try:
        return(convert_dict[cpr])
    except KeyError:
        return(None)

def convert_id_to_cpr(id):
    convert_dict = get_convert_dict()    
    cpr = list(convert_dict.keys())[list(convert_dict.values()).index(id)]
    return(cpr)
     

def convert_cpr_list_to_id(cprs):
    patient_ids = list()
    cpr_id_pairs = list()
    with open('Z:\lasref01\documentLibrary\IDReport_all_man.txt', mode='r') as infile:
        reader = csv.reader(infile)
        with open('coors_new.csv', mode='w') as outfile:
            writer = csv.writer(outfile)
            id_dict = {rows[0]:rows[1] for rows in reader}
    
    for cpr in cprs:
        cpr_11 = (cpr_convert(cpr))
        patient_id = id_dict[cpr_11]
    
        patient_ids.append(patient_id)
        cpr_id_pairs.append({cpr_11 : patient_id})

    return(patient_ids, cpr_id_pairs)


def convert_id_list_to_cpr(ids):
    patient_cprs = list()
    id_cpr_pairs = list()
    with open('Z:\lasref01\documentLibrary\IDReport_all_man.txt', mode='r') as infile:
        reader = csv.reader(infile)
        with open('coors_new.csv', mode='w') as outfile:
            writer = csv.writer(outfile)
            id_dict = {rows[1]:rows[0] for rows in reader}
    
    for id in ids:
        patient_cpr = id_dict[id]
    
        patient_cprs.append(patient_cps)
        id_cpr_pairs.append({id : patient_cpr})

    return(patient_cprs, id_cpr_pairs)

