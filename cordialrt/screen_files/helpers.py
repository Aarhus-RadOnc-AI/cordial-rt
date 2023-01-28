import numpy as np

def planned_fractions(patient):
    plan_fractions = list()
    if len(patient.studies) == 1:     
        for uid, plan in patient.one_study.plans.items():
            plan_fractions.append([plan['data_set'].RTPlanLabel, plan['data_set'].FractionGroupSequence[0].NumberOfFractionsPlanned])
        return(plan_fractions)
    
def fractions_main_plan(planned_fractions):
    if type(planned_fractions) is list:
        main_fractions = 0
        for plan in planned_fractions:
            if int(plan[1]) > main_fractions:
                main_fractions = int(plan[1])
        return(main_fractions)
    else:
        return(np.nan)

def get_plan_info(patient):
    all_plan_info = list()
    for study_uid, study in patient.studies.items():
        for plan_uid, plan in study.plans.items():
            plan_info = {
                'plan_name': plan['data_set'].RTPlanLabel,
                'fractions': plan['data_set'].FractionGroupSequence[0].NumberOfFractionsPlanned,
                'plan_date': str(plan['data_set'].StudyDate),
                'approve': plan['data_set'].ApprovalStatus,
                'study_uid': study_uid,
                'plan_uid': plan_uid
            }
            all_plan_info.append(plan_info)
            
    return(all_plan_info)

def diff_dates(plan_info):
    unique_dates = list()
    for plan in plan_info:
        if plan['plan_date'] in unique_dates:
            pass
        else: 
            unique_dates.append(plan['plan_date'])
    return(unique_dates)