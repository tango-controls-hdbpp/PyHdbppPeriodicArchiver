PyHdbppPeriodicArchiver
=======================

PyHdbppPeriodicArchiver DS to periodically insert attribute values in HDB++

Requires Tango, PyTango, LibHdb++ and LibHdbppInsert

How it works?
=============

The PyHdbppPeriodicArchiver DS uses the "LibConfiguration" property defined in the 'ConfigurationManagerDS' to create an instance to the selected HDB++ library. The instance is created using the libhdbppinsert library.

Once the instance is created, a thread is created that periodically insert the attributes defined in the 'AttributeList' property according to the period defined for each attribute. It uses the insert_Attr_Asycn function of the library to insert attributes in HDB++. This function creates an independent for each attribute that, reads the attribute value and inserts it in HDB++. If there is another thread pending to finish for the same attribute, a new thread is not created and this function returns NOT_OK.

Properties
==========

- AsynchronousInsert:
	This property defines if the DS inserts attributes in HDB++ using an asynchronous thread or not.

- AttributeList:
	List that contains the attributes and their refresh period to be inserted in HDB++. The format of this list is long_attrbiute_name;period=value_in_miliseconds

- AutoStart:
	This property if set, forces the device serve to automatically launch the insert thread at init

- DefaultAttPeriod:
	Default period in ms to archive attributes

- ConfigurationManagerDS:
	HDB++ configuration manager device with the corresponding HDB++ configuration to access

- Attemps:
	Number of attemps before reporting error to insert an attribute in HDB++ in case of failure

- ThreadPeriod:
	"Time in which the Periodic Archiver thread is executed in miliseconds",


Commands
========

- Init():
	Creates a new instance of the HDB++ through the libhdbppinsert library

- Start():
	Starts the PeriodicArchiver thread in the DS, responsible to check the defined period for each attribute in the 'AttributeList' and call the insert_Attr_Async command if corresponds. Sets the device state to RUNNING
	
- Stop():
	Stops the Periodic Archiver thread if it is RUNNING and sets the device state to ON
	
- Reset():
	Executes an Stop and sets the state INIT.
	
- AttributeAveragePeriod(attribute):
	This command returns the average insert period calculated for an attribute
	
- AttributeData(attribute):
	Returns dictionary converted to string with the configuration for the selected attribute

- AttributeLastUpdate(attribute):
	Returns the last updated time for the selected attribute

- AttributeAdd(attribute, period)':
	Inserts an attrbiute to the AttributeList with the corresponding selected period. The attribute is then controlled by the PeriodicArchiver thread.

- AttributeInsert(attribute):
	Forces an insert in HDB++ of the attribute selected if it is in the AttributeList.
	
- AttributeRemove(attribute):
	Stops the automatic insert of the selected attribute and removes it from the AtributeList

- AttributeStart(attribute):
	The automatic insert of an attrbute can be temporally stop. This command is used to restart the automatic insert of the atribute. By the defult the automatic insert of an attribute is enabled when the DS is initialized

- AttributeStop(attribute):
	Stops the automatic insert of an attribute in the AtributeList, without removing it form the AttributeList

- UpdateAttributeList():
	Forces an update of the Attributes List managed by the Periodic insert thread that has been created from the AttributeList property of this device

Attributes
==========

- AttributesAveragePeriodList:
	READ_ONLY: List of real insert time period for each attribute in the list

- AttributesErrorList:
	READ_ONLY: List of attributes the have failed to insert in HDB++
	
- AttributesErrorNumber:
	READ_ONLY: Number of attributes that have failed to insert in HDB++
	
- AttributesList:
	READ_ONLY: List with the atributes to be controlled by the PeriodicArchiver thread

- AttributesOKList:
	READ_ONLY: List of attributes succesfully inserted in HDB++
	
- AttributesOKNumber:
	READ_ONLY: Number of attributes that have been succesfully inserted in HDB++

- AttributesPeriodList:
	READ_ONLY: List of selected period for each attribute in the list
	
º- LoadAverage:
	READ_ONLY: Returns the load average of the DS. The mean value to insert and attribute in HDB++
	
- State:
	Returns the status of the device:
		INIT: Instance to libhdbppinsert NOT created
		ON: Instance to libhdppinsert created succesfully
		RUNNING: Periodic Archiver thread running
		FAULT: Error in DS. Check Status for more details
		
- Status:
	Returns detailed information for each of the DS States
