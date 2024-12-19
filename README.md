# cordial-rt (COllaboRative DIcom AnaLysis for RadioTherapy)

## The short story
A system for curraton, standardisation and analysis of large radiotherpy DICOM datasets. 

This is a beta version developed for breast cancer radiotherapy reseach projects in Denmark.

Please see the examples.ipynb for basic usage. 

Associated paper 
https://pubmed.ncbi.nlm.nih.gov/37705727/

## The long story 

To address the needs for explorative data curation, standardisation and analysis of large DICOM-RT datasets in breast cancer radiotherapy research, we developed the collaborative DICOM analysis for radiotherapy (CORDIAL-RT) solution. 

CORDIAL-RT is an open-source solution that consists of a collection of functionalities and database tables (SQLite) developed in the Python programming language, which allows the user to work with large DICOM-RT datasets. 
### Data Curation 
When collecting large DICOM-RT datasets, sometimes unwanted files are collected in the process. The screening functionality of CORDIAL-RT presents an overview of the number and types of DICOM files collected for each patient and how they are related through the DICOM UID linkage system. This can be combined with any external knowledge about the treatments and be used to do a selection of which files to include in a project and which files to ignore. 

The information about the decisions made in the curation step is stored in the CORIDAL-RT database. When starting a project, a new entity called a treatment collection is created. A treatment collection can include multiple patients each with one treatment. Each treatment consists of one structure file and any number of dose, plan and CT files referencing that structure file. The paths to the relevant DICOM files are stored in the dicom_files database table, where they are related to a specific treatment. All DICOM files that were originally collected are kept in a folder created by the user. Files are never moved or deleted but referenced by treatments and treatment collections and can be used for multiple projects without the need for more storage.

### Data Standardisation
In order to handle all treatments in the same way when doing dose volume histogram (DVH) analysis, the treatment dose files must be standardised. In CORDIAL-RT, this is done by making sure that all treatments have one dose file representing the full dose received by the patient over the whole treatment course. If multiple dose files are assigned to one treatment the system will automatically save a new DICOM dose file, representing the summed dose grids and use this in future analysis. Sequential boost treatments are handled in the same way if they are made using the same image and structure set. Registration of multiple image sets is beyond the scope of this project. 
When patients are replanned during a treatment course, more than one treatment plan will be available for data collection. In the current study, we decided to use the dominant treatment plan with the most fractions delivered, which meant that not all treatment plans contained the full dose delivered to the patient over the entire treatment course. In order to approximate the full dose, the dominant treatment plan was scaled according to the intended/delivered fraction ratio and a new dose file was saved representing the approximation of the full dose. 

The standardised dose files can be used to categorise breast cancer treatment laterality. This is done by projecting the dose grid to the CT-scan and then measuring the integral dose on the left and right side of the scan, assuming that the patient was placed approximately in the centre of the field of view of the scanner. The logarithm of the ratio is used to determine laterality, using 0 as the cut-off point. 

To address the inconsistencies in the nomenclature used for the delineations of organs and targets, CORDIAL-RT uses a structure name-mapping approach, where a standard name is linked to several synonyms, which are organised in synonym collections that can be assigned to treatment collections. A synonym collection consists of multiple synonyms used to map the structure names used in the DICOM structure files to a common name set determined by the user. 

When a dataset of DVH values is extracted from a collection of treatments, the system will automatically use the synonyms. If, for example, the mean dose to the ipsilateral lung is extracted, the system will go through the structure sets of each selected treatment and search for all synonyms related to the ipsilateral lung in the database. If more than one is found, the synonym with the highest priority count is chosen. The priority count can be entered manually by the user or be set automatically by the system which will count the occurrence of the synonym in the treatment collection and use that number, effectively always prioritising the most frequently used names. If more precision is needed, a synonym can also be assigned a laterality value (l: left, r: right, i: ipsilateral), which will overrule the priority count when relevant. An example of this is when we want to extract the dose for the standard name ctvp_breast, and the system finds two synonyms associated with ctvp_breast: CTV; breast sin and CTV; breast dxt in the same treatment. If these synonyms have been assigned a laterality, the system will prioritise the synonym with the same laterality as the treatment over the synonym with the highest priority count. 

If we want to analyse doses to structures that were not originally delineated and therefore cannot be found by structure name-mapping, we can create new augmented structure sets by adding delineations to the original structure set either with manual delineation or auto segmentation. Augmented structure sets are organised in structure collections, which can represent an auto segmentation model, a delineation workshop etc. When doing data analysis on treatments, the user can choose to use the original structure set or an augmented structure set from a structure collection. 

### Data extraction and analysis
When the user is satisfied with the curation and standardisation of the treatment collection, data can be batch extracted from all treatments. In principle, all the data available in the DICOM files (the study date of the treatment plan, the manufacture of the CT-scanner, the voxel size of the dose grid etc.), can be extracted along with any DVH parameter that is of interest. When extracting DVH parameters, the system will automatically utilise the structure name-mapping, dose scaling/summation and augmented structures if chosen. The actual dose extraction module is based on the Dicompyler-core Python package. When extracted, the data can be further analysed in the Python framework or saved as a file in the most common formats: csv, excel, stata etc. for analysis in another statistics program. The curated DICOM files can also be exported to any other systems which can act like a DICOM receiver. This could be a treatment planning system or a research storage solutions.

For more complex analyses, the system can be expanded by utilising the data organisation and classes to build advanced analysis modules. Currently these include a module for screening patients for Coronary artery calcifications and a collection of tools for analysing tube-shaped structures.


