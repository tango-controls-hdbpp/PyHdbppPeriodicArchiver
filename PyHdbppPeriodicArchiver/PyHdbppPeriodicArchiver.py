#    "$Name:  $";
#    "$Header:  $";
#=============================================================================
#
# file :        PyPyHdbppPeriodicArchiver.py
#
# description : Python source for the Hdb++ peridic archiver device
#                The class has a thread responsible to insert attributes
#                in the HDB++ database when requested
#
# project :     TANGO Device Server
#
# $Author:  mbroseta@cells.es$
#
# $Revision:  1.0$
#
# $Log:  $
#
#
# copyleft :     ALBA Synchrotron - CELLS
#                Ctra. BP. 1413 km 3,308290
#                Cerdanyola del Valles
#                Barcelona (Spain)
#
#=============================================================================
#

import os
import PyTango
import sys
import threading
import time
import fandango as fn

from libhdbppinsert import *

RESULT_OK = 0
RESULT_NOT_OK = -1

#==================================================================
#   PeriodicArchiver Thread Description:
#
#
#==================================================================

class PeriodicArchiverThread(threading.Thread):
	def __init__(self, parent=None):
		threading.Thread.__init__(self)
		self._parent = parent

		self._thread_period = parent.ThreadPeriod / 1000.
		self._lock = threading.Lock()
		self._attDict = []
		self._async_insert = parent.AsynchronousInsert
		
		self._endProcess = False
		self._processEnded = False
		
	def end(self):
		self._endProcess = True
		
	def getProcessEnded(self):
		return self._processEnded
	
	def setAttributeDict(self, attDict = {}):
		self._attDict = attDict
		
	def insertAttribute(self, attribute):
		val = False
		try:
			attData = self._attDict[attribute]
			if attData['started']:
				
				if self._async_insert:
					res = self._parent._hdbppins.insert_Attr_Async(attribute)
				else:
					res = self._parent._hdbppins.insert_Attr(attribute)
					
				if res == RESULT_OK :
					attData['last_update'] =  time.time()
					attData['update'] = True
					attData['attempts'] = 0
					val = True
				else:
          				val = False
		except Exception, e:
			msg = "Error inserting attribute %s due to %s"%(attribute, str(e))
			self._parent.debug_stream(msg)
		return val
       
	def run(self): 
		while not (self._endProcess):
			with self._lock:
				#self._parent.debug_stream("in PeriodicArchiverThread()")
				any_attr_changes = False
				
				if self._attDict != {}:
					tnow = time.time() # Convert time to milliseconds
					
					for attribute in self._attDict.keys():
						attData = self._attDict[attribute]
						try:
							if attData['started']:
								period = attData['period']
								last_update = attData["last_update"]
								
								# calculated period in seconds
								calculated_period = (tnow - last_update) * 1000.
								if calculated_period >= period:
									any_attr_changes = True
									ret = self.insertAttribute(attribute)
									if ret:
										self._parent.addPeriodData(attribute, calculated_period)
										attData['attempts'] = 0
										msg = "Save Inserted attribute %s"%attribute.split("/",3)[3]
										msg += " with period: %s"%str(attData['period'])
										msg +=" >> real_period: %s"%str(attData['average_period'])
										#self._parent.debug_stream(msg)
									else:
										if attData['attempts'] >= self._parent.InsertAttempts:
											attData['update'] = False
											attData['attempts'] = 0
											msg = "Error inserting %s "%attribute
											self._parent.error_stream(msg)
											# Reset pending operatins flag and try again
											self._parent._hdbppins.reset_Attr_Pending_Ops(attribute)
										else:
											attData['attempts'] = attData['attempts'] + 1
						except Exception, e:
							msg = "Error updating attribute %s definition! %s"%(attribute, str(e))
							attData['update'] = False
							self._parent.debug_stream(msg)
				if any_attr_changes:
					# Only update AttrLists if any attribute has changed
					self._parent.updateDataLists()
			time.sleep(self._thread_period)
			
		self._processEnded = True


#==================================================================
#   PyHdbppPeriodicArchiver Class Description:
#
#
#==================================================================

class PyHdbppPeriodicArchiver(PyTango.Device_4Impl):
    
#------------------------------------------------------------------
#    Device constructor
#------------------------------------------------------------------
	def __init__(self,cl, name):
		PyTango.Device_4Impl.__init__(self,cl,name)
		#get device properties
		self.get_device_properties(self.get_device_class())
		PyHdbppPeriodicArchiver.init_device(self)

#------------------------------------------------------------------
#    Device destructor
#------------------------------------------------------------------
	def delete_device(self):
		self.debug_stream("In delete_device()")

		if self.get_state() == PyTango.DevState.ON or self._periodicArch_thread is not None:
			self.Stop()
			
		self.debug_stream("delete_device() Done!")            


#------------------------------------------------------------------
#    Device initialization
#------------------------------------------------------------------
	def init_device(self):
		self.debug_stream("In init_device()")

		self.get_device_properties(self.get_device_class())
		
		# Initialize variables
		self._periodicArch_thread = None
		
		self._hdbppins = None
		self._user = None
		self._passw = None
		self._dbname = None
		self._dbhost = None
		self._libname = None
		self._lightschema = None
		self._port = None
		
		self.ThreadPeriod = 100
		
		try:
			db = PyTango.Database()
			schemas = db.get_device_property(self.ConfigurationManagerDS,'LibConfiguration')['LibConfiguration']          
			for el in schemas:
				try:
					item = el.split("=")[0].lower()
					val = el.split("=")[1]
					if 'dbname' in item:
						self._dbname = val
					elif 'host' in item:
						self._dbhost = val
					elif 'user' in item:
						self._user = val
					elif 'password' in item:
						self._passw = val
					elif 'libname' in item:
						self._libname = val
						#self._libname = "/homelocal/sicilia/local/libhdbpp-mysql/lib/libhdb++mysql.so"
					elif 'lightschema' in item:
						self._lightschema = val
					elif 'port' in item:
						self._port = val
				except:
					continue
		except:
			self.set_state(PyTango.DevState.FAULT)
			msg = "Incorrect schema value defined in Schema property!"
			self.set_status(msg)
			self.debug_stream(msg)
			return
		
		# Create Attribute dictionary
		self.updateAttrDict()

		try:
			self._hdbppins = HdbppInsert(self._user, self._passw, self._dbhost, self._dbname,
								self._libname, self._lightschema, self._port)   
			if not self._hdbppins.is_Connected():
				self.set_state(PyTango.DevState.FAULT)
				msg = "Not possible to connect to selected Database in schema!"
				self.set_status(msg)
				self.debug_stream(msg)
				self._hdbppins = None
		except:
			self.set_state(PyTango.DevState.FAULT)
			msg = "Not possible to connect to selected Database in schema!"
			self.set_status(msg)
			self.debug_stream(msg)
			self._hdbppins = None
			return
		
		self.set_state(PyTango.DevState.ON)
		self.status_string = "Device Initialized!"
		self.set_status(self.status_string)
		
		if self.AutoStart:
			self.Start()
			

#------------------------------------------------------------------
#    Always excuted hook method
#------------------------------------------------------------------
	def always_executed_hook(self):
		#print "In ", self.get_name(), "::always_excuted_hook()"
		pass

#==================================================================
#
#    Conditioning read/write attribute methods
#
#==================================================================
#------------------------------------------------------------------
#    Read Attribute Hardware
#------------------------------------------------------------------
	def read_attr_hardware(self,data):
		pass
		
	def read_AttributesList(self, attr):
		msg = '[%s]' % ', '.join(map(str, self._attributesList))
		self.debug_stream("in read_AttributesList(): %s"%msg)
		attr.set_value(self._attributesList)

	def read_AttributesPeriodList(self, attr):
		msg = '[%s]' % ', '.join(map(str, self._periodList))
		self.debug_stream("in read_AttributesPeriodList(): %s"%msg)
		attr.set_value(self._periodList)

	def read_AttributesErrorList(self, attr):
		msg = '[%s]' % ', '.join(map(str, self._errorList))
		self.debug_stream("in read_AttributesErrorList(): %s"%msg)
		attr.set_value(self._errorList)

	def read_AttributesErrorNumber(self, attr):
		self.debug_stream("in read_AttributesErrorNumber(): Number of fail attributes %s"%str(self._errorNumber))
		attr.set_value(self._errorNumber)

	def read_AttributesAveragePeriodList(self, attr):
		msg = '[%s]' % ', '.join(map(str, self._avgPeriodList))
		self.debug_stream("in read_AttributesAveragePeriodList(): %s"%msg)
		attr.set_value(self._avgPeriodList)

	def read_AttributesOKList(self, attr):
		msg = '[%s]' % ', '.join(map(str, self._OKList))
		self.debug_stream("in read_AttributesOKList(): %s"%msg)
		attr.set_value(self._OKList)

	def read_AttributesOKNumber(self, attr):
		self.debug_stream("in read_AttributesOKNumber(): Number of fail attributes %s"%str(self._OKNumber))
		attr.set_value(self._OKNumber)
		
	def read_LoadAverage(self, attr):
		val = 1
		
		calculated = 0.0
		default = 0.0
		for att, item in self._attrDict.iteritems():
			default = default + item['period']
			calculated = calculated + item['average_period']
			
		val = float(calculated/default)
		
		self.debug_stream("in read_LoadAverage(): Load average to insert attributes: %s"%str(val))
		attr.set_value(val)
		

#==================================================================
#
#    Conditioning command methods
#
#==================================================================

#------------------------------------------------------------------
#    Command:
#
#    Description: 
#------------------------------------------------------------------
	def Start(self):
		self.debug_stream("In Start()")
		
		self._periodicArch_thread = None
		try:
			self._periodicArch_thread = PeriodicArchiverThread(self)
			self._periodicArch_thread.setAttributeDict(self._attrDict)
			self._periodicArch_thread.setDaemon(True)                
			self._periodicArch_thread.start()            
		except Exception, e:
			self.error_stream("Error while starting, due to %s"%(str(e)))
			self.set_state(PyTango.DevState.FAULT)
			self.set_status("Failed to Start Thread!!")
			return False
	
		self.set_state(PyTango.DevState.RUNNING)
		msg = "HDB Periodic Archiver Thread Started and running"
		self.set_status(msg)
		self.debug_stream(msg)
		return True
		
	def is_Start_allowed(self):
		self.debug_stream("in is_Start_allowed")
		return (self.get_state() == PyTango.DevState.ON)
	
	def Stop(self):
		self.debug_stream("In Stop()")
		
		try:
			if self._periodicArch_thread is not None:
				self._periodicArch_thread.end()
			
			while not self._periodicArch_thread.getProcessEnded():
				self.debug_stream("stop(): Waiting process to die")
				time.sleep(0.5)
		except Exception, e:
			self.error_stream("Error while stopping, due to %s"%(str(e)))
			self.set_state(PyTango.DevState.FAULT)
			self.set_status("Failed to Stop Thread!!!")
			return False
	
		self.set_state(PyTango.DevState.ON)
		self.status_string = "Thread Stopped"
		self.set_status(self.status_string)
		return True
        
	def is_Stop_allowed(self):
		self.debug_stream("in is_Stop_allowed")
		return (self.get_state() == PyTango.DevState.RUNNING or self.get_state() == PyTango.DevState.FAULT)
	
	def Reset(self):
		self.debug_stream("In Reset()")
		
		if self.get_state() == PyTango.DevState.RUNNING or self._periodicArch_thread is not None:
			self.Stop()
		
		self.set_state(PyTango.DevState.INIT)
		self.set_status("Device Reset")      
		
	def AttributeAveragePeriod(self, argin):
		val = 0
		try:
			attr = str(argin)
			attr = fn.tango.get_full_name(attr, fqdn=True)
			self.debug_stream("AttributeAveragePeriod() attribute % s"%attr)

			val = self._attrDict[attr]['average_period']
		except Exception, e:
			msg = "AttributeAveragePeriod attribute %s not found in Periodic archiver"%attr
			PyTango.Except.throw_exception('AttributeAveragePeriod',msg,'PyHdbppPeriodicArchiver')
			return
		
		return val
	
	def AttributeData(self, argin):
		try:
			attr = str(argin)
			attr = fn.tango.get_full_name(attr, fqdn=True)
			self.debug_stream("AttributeData() attribute % s"%attr)
			
			msg = attr
			aux = self._attrDict[attr]
			#msg += ": " + str(self._attrDict[attr])
			
			ret_value = {}
			ret_value = aux
			ret_value['name'] = attr
			
			msg = str(ret_value)

		except Exception, e:
			msg = "AttributeData attribute %s not found in Periodic archiver"%attr
			PyTango.Except.throw_exception('AttributeData',msg,'PyHdbppPeriodicArchiver')
			return
		
		return msg
	
	def AttributeLastUpdate(self, argin):
		try:
			attr = str(argin)
			attr = fn.tango.get_full_name(attr, fqdn=True)
			self.debug_stream("AttributeLastUpdate() attribute % s"%attr)

			msg = attr
			aux = self._attrDict[attr]['last_update']
			#msg += ": " + time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(int(aux)))+str(aux-int(aux))[1:]
			msg = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(int(aux)))+str(aux-int(aux))[1:]
		except Exception, e:
			msg = "AttributeLastUpdate attribute %s not found in Periodic archiver"%attr
			PyTango.Except.throw_exception('AttributeLastUpdate',msg,'PyHdbppPeriodicArchiver')
			return
		
		return msg
	
	def AttributeAdd(self, argin):
		self.debug_stream("AttributeAdd()")

		try:
			attr = str(argin[0])
			period = int(argin[1])
			attr = fn.tango.get_full_name(attr, fqdn=True)
		except Exception, e:
			msg = "AttributeAdd incorrect argument types. "
			msg += "Expected 2 arguments (string: attribute name, integer: period in miliseconds)"
			PyTango.Except.throw_exception('AttributeAdd',msg,'PyHdbppPeriodicArchiver')
			return False
			
		cadena = attr+";period="+str(period)
		
		db = PyTango.Database()
		props = db.get_device_property(self.get_name(), 'AttributeList')		
		found = False
		for idx, item in enumerate(props['AttributeList']):
			aux = item.split(";")[0]
			if attr.lower() == aux.lower():
				del props['AttributeList'][idx]
				props['AttributeList'].append(cadena)
				found = True

		if not found:
			if fn.tango.read_attribute(attr) is not None:
				props['AttributeList'].append(cadena)
			else:
				msg = "AttributeAdd. Incorrect attribute name %s or not responidng!!"%attr
				PyTango.Except.throw_exception('AttributeAdd',msg,'PyHdbppPeriodicArchiver')
				self.error_stream(msg)
				return False

		db.put_device_property(self.get_name(),props)
		msg = "AttributeAdd(): AttributeList property updated: " + str(props)
		self.debug_stream(msg)
		self.updateAttrDict()
		return True
	
	def AttributeInsert(self, argin):
		self.debug_stream("AttributeInsert()")

		try:
			attr = str(argin)
			attr = fn.tango.get_full_name(attr, fqdn=True)
		except Exception, e:
			msg = "AttributeInsert incorrect argument name" 
			PyTango.Except.throw_exception('AttributeInsert',msg,'PyHdbppPeriodicArchiver')
			return False
		
		if self._periodicArch_thread is not None:
			try:
				if self._attrDict[attr]['started']:
					return self._periodicArch_thread.insertAttribute(attr)
			except:
				msg = "Attribute %s not started"%attr
				PyTango.Except.throw_exception('AttributeInsert',msg,'PyHdbppPeriodicArchiver')
		else:
			return False
	
	def AttributeRemove(self, argin):
		self.debug_stream("AttributeRemove()")

		try:
			attr = str(argin)
			attr = fn.tango.get_full_name(attr, fqdn=True)
		except Exception, e:
			msg = "AttributeRemove incorrect argument types. Expected 2 arguments" 
			msg += "(string: attribute name, integer: period in miliseconds)"
			PyTango.Except.throw_exception('AttributeRemove',msg,'PyHdbppPeriodicArchiver')
			return False
		
		db = PyTango.Database()
		props = db.get_device_property(self.get_name(), 'AttributeList')
		
		found = False
		for idx, item in enumerate(props['AttributeList']):
			aux = item.split(";")[0]
			if attr.lower() == aux.lower():
				del props['AttributeList'][idx]
				found = True

		if found:
			db.put_device_property(self.get_name(),props)
			self.updateAttrDict()
		else:
			msg = "AttributeRemove. incorrect argument. Attribute %s not in Attribute List"%attr
			PyTango.Except.throw_exception('AttributeRemove',msg,'PyHdbppPeriodicArchiver')
			self.error_stream(msg)
			return False
		
		return True

	def AttributeStart(self, argin):
		self.debug_stream("AttributeStart()")
		
		if (self.get_state() == PyTango.DevState.RUNNING):
			msg = "AttributeStart Insert HDB++ thread not running. Start the DS." 
			PyTango.Except.throw_exception('AttributeInsert',msg,'PyHdbppPeriodicArchiver')
			return msg
		
		try:
			attr = str(argin)
			attr = fn.tango.get_full_name(attr, fqdn=True)
		except Exception, e:
			msg = "AttributeInsert incorrect argument name" 
			PyTango.Except.throw_exception('AttributeInsert',msg,'PyHdbppPeriodicArchiver')
			return False
		
		if attr in self._attrDict():
			self._attrDict[attr]['started']=True
			self.updateAttrDict()
			msg ="%s Started"%attr
		else:
			msg = "%s NOT in AtributeList"%attr
		
		return msg

	def AttributeStop(self, argin):
		self.debug_stream("AttributeStop()")
		
		if (self.get_state() == PyTango.DevState.RUNNING):
			msg = "AttributeStop Insert HDB++ thread not running. Start the DS." 
			PyTango.Except.throw_exception('AttributeStop',msg,'PyHdbppPeriodicArchiver')
			return msg
		
		try:
			attr = str(argin)
			attr = fn.tango.get_full_name(attr, fqdn=True)
		except Exception, e:
			msg = "AttributeStop incorrect argument name" 
			PyTango.Except.throw_exception('AttributeStop',msg,'PyHdbppPeriodicArchiver')
			return False
		
		if attr in self._attrDict():
			self._attrDict[attr]['started']=False
			self.updateAttrDict()
			msg ="%s Started"%attr
		else:
			msg = "%s NOT in AtributeList"%attr
		
		return msg

	def UpdateAttributeList(self):
		self.debug_stream("UpdateAttributeList()")
		self.updateAttrDict()

		
#==================================================================
#
#    Hdb Periodic Archiver extra command methods
#
#==================================================================
	def updateAttrDict(self):		
		self.debug_stream("in updateAttrDict()")
		
		self._attrDict = {}
		self._attributesList = []
		self._periodList = []
		self._errorList = []
		self._avgPeriodList = []
		self._OKList = []
		self._OKNumber = 0
		self._errorNumber = 0
		
		self.get_device_properties(self.get_device_class())
		
		for item in self.AttributeList:
			if item[0] == "#":
				continue
			period = self.DefaultAttPeriod
			
			try:
				els = item.split(";")
				attribute = els[0].lower()
				for el in els:
					if 'period=' in el:
						try:
							period = int(el.split("=")[1])
						except:
							continue
			except:
				attribute = item.lower()  
				
			aux = {}                        
			if attribute in self._attrDict.keys():
				aux = self._attrDict[attribute]
				aux['period'] = period
			else:
				aux['last_update'] = 0
				aux['average_period'] = 0
				aux['update'] = False
				aux['period'] = period
				aux['attempts'] = 0
				aux['started'] = True
				aux['avg_per_buffer'] = []
			self._attrDict[attribute.lower()] = aux
			
		# Update attributes List
		self._attributesList = []
		self._periodList = []
		
		if self._attrDict != {}:
			for att, item in self._attrDict.iteritems():
				self._attributesList.append(att)
				self._periodList.append(item['period'])
				
		# Update periodic Thread if enabled
		if self._periodicArch_thread is not None:
			self._periodicArch_thread.setAttributeDict(self._attrDict)
			
	def updateDataLists(self):
		#self.debug_stream("in updateDataLists()")
		try:
			self._errorList = []
			self._avgPeriodList = []
			self._OKList = []
			
			if self._attrDict != {}:
				for att in self._attributesList:
					self._avgPeriodList.append(self._attrDict[att]['average_period'])
					if self._attrDict[att]['update'] == False or self._hdbppins.get_Attr_Update_Status(att) == RESULT_NOT_OK:
						self._errorList.append(att)
					else:
						self._OKList.append(att)
					
				self._OKNumber = len(self._OKList)
				self._errorNumber = len(self._errorList)
				
			if self.get_state() == PyTango.DevState.RUNNING:
				msg = "RUNNING: Updated %s attributes Ok, %s Fail!"%(str(self._OKNumber), str(self._errorNumber))
				self.debug_stream(msg)
				self.set_status(msg)
		except Exception, e:
			self.error_stream("in updateDataLists(): Error lists not updated due to %s"%(str(e)))
			
	def addPeriodData(self, attribute, period):
		if attribute in self._attrDict.keys():
			vals = self._attrDict[attribute]['avg_per_buffer']
			if len(vals) >= self.AverageBufferSize:
				vals.pop(0)
			vals.append(period)
			
			avg_value = 0
			for el in vals:
				avg_value = avg_value + el
			avg_value = avg_value / len(vals)
			
			self._attrDict[attribute]['avg_per_buffer'] = vals
			self._attrDict[attribute]['average_period'] = avg_value
			
			
#==================================================================
#
#    PyHdbppPeriodicArchiverClass class definition
#
#==================================================================
class PyHdbppPeriodicArchiverClass(PyTango.DeviceClass):

	#    Class Properties
	class_property_list = {
		}


	#    Device Properties
	device_property_list = {
		'AsynchronousInsert':
			[PyTango.DevBoolean,
			"This property defines if the DS inserts attributes in HD B using an asynchronous thread or not",
			[True] ],
		'AttributeList':
			[PyTango.DevVarStringArray,
			"List that contains the attributes and their refresh period to be inserted in HDB++.\
			The format of this list is: long_attrbiute_name;period=value_in_miliseconds",
			[] ],
		'AutoStart':
			[PyTango.DevBoolean,
			"This property if set, forces the device serve to automatically launch the insert thread at init",
			[True] ],
		'AverageBufferSize':
			[PyTango.DevShort,
			"Number of values to store in the temporal buffer that calculates de average period",
			[3] ],
		'DefaultAttPeriod':
			[PyTango.DevDouble,
			"Default period in ms to archive attributes",
			[1000] ],            
		'ConfigurationManagerDS':
			[PyTango.DevString,
			"HDB++ configuration manager device with the corresponding HDB++ configuration to access",
			[""]],   
		'InsertAttempts':
			[PyTango.DevShort,
			"Number of attempts before reporting error to insert an attribute in HDB++ in case of failure",
			[2] ],
		'ThreadPeriod':
			[PyTango.DevDouble,
			"time in which the Periodic Archiver thread is executed in miliseconds",
			[500] ],
		}


	#    Command definitions
	cmd_list = {
		'Start':
			[[PyTango.DevVoid, "none"],
			[PyTango.DevBoolean, "none"]],
		'Stop':
			[[PyTango.DevVoid, "none"],
			[PyTango.DevBoolean, "none"]],
		'Reset':
			[[PyTango.DevVoid, "none"],
			[PyTango.DevBoolean, "none"]],
		'AttributeAveragePeriod':
			[[PyTango.DevString, "none"],
			[PyTango.DevDouble, "none"]],
		'AttributeData':
			[[PyTango.DevString, "none"],
			[PyTango.DevString, "none"]],
		'AttributeLastUpdate':
			[[PyTango.DevString, "none"],
			[PyTango.DevString, "none"]],			
		'AttributeAdd':
			[[PyTango.DevVarStringArray, "none"],
			[PyTango.DevBoolean, "none"]],
		'AttributeInsert':
			[[PyTango.DevVarStringArray, "none"],
			[PyTango.DevBoolean, "none"]],
		'AttributeRemove':
			[[PyTango.DevString, "none"],
			[PyTango.DevBoolean, "none"]],
		'AttributeStart':
			[[PyTango.DevVarStringArray, "none"],
			[PyTango.DevString, "none"]],			
		'AttributeStop':
			[[PyTango.DevVarStringArray, "none"],
			[PyTango.DevString, "none"]],			
		'UpdateAttributeList':
			[[PyTango.DevVoid, "none"],
			[PyTango.DevVoid, "none"]],
		}


	#    Attribute definitions
	attr_list = {
		'AttributesList':
			[[PyTango.DevString,
			PyTango.SPECTRUM,
			PyTango.READ, 1024],
			{
				'description': "List of attributes to insert in HDB++",
			} ],
		'AttributesPeriodList':
			[[PyTango.DevDouble,
			PyTango.SPECTRUM,
			PyTango.READ, 1024],
			{
				'description': "List of selected period for each attribute in the list",
			} ],
			
		'AttributesErrorList':
			[[PyTango.DevString,
			PyTango.SPECTRUM,
			PyTango.READ, 1024],
			{
				'description': "List of attributes the have failed to insert in HDB++",
			} ],
		'AttributesErrorNumber':
			[[PyTango.DevShort,
			PyTango.SCALAR,
			PyTango.READ],
			{
				'description': "Number of attributes that have failed to insert in HDB++",
			} ],
		'AttributesAveragePeriodList':
			[[PyTango.DevDouble,
			PyTango.SPECTRUM,
			PyTango.READ, 1024],
			{
				'description': "List of average insert time period for each attribute in the list",
			} ],
		'AttributesOKList':
			[[PyTango.DevString,
			PyTango.SPECTRUM,
			PyTango.READ, 1024],
			{
				'description': "List of attributes succesfully inserted in HDB++",
			} ],
		'AttributesOKNumber':
			[[PyTango.DevShort,
			PyTango.SCALAR,
			PyTango.READ],
			{
				'description': "Number of attributes that have been succesfully inserted in HDB++",
			} ],
		'LoadAverage':
			[[PyTango.DevDouble,
			PyTango.SCALAR,
			PyTango.READ],
			{
				'description': "Returns the load average of the DS. The mean value to insert and attribute in HDB++",
			} ],
		}

#------------------------------------------------------------------
#    PyHdbppPeriodicArchiverClass Constructor
#------------------------------------------------------------------
	def __init__(self, name):
		PyTango.DeviceClass.__init__(self, name)
		self.set_type(name);
		print "In PyHdbppPeriodicArchiverClass  constructor"

#==================================================================
#
#    Conditioning class main method
#
#==================================================================
def main():
	try:
		py = PyTango.Util(sys.argv)
		py.add_TgClass(PyHdbppPeriodicArchiverClass,PyHdbppPeriodicArchiver,'PyHdbppPeriodicArchiver')

		U = PyTango.Util.instance()
		U.server_init()
		U.server_run()

	except PyTango.DevFailed,e:
		print '-------> Received a DevFailed exception:',e
	except Exception,e:
		print '-------> An unforeseen exception occured....',e

if __name__ == '__main__':
	main()
