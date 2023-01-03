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