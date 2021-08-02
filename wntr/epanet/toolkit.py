"""
The wntr.epanet.toolkit module is a Python extensions for the EPANET 
Programmers Toolkit DLLs.

.. rubric:: Contents

.. autosummary::

    runepanet
    ENepanet
    EpanetException
    ENgetwarning

"""
import ctypes, os, sys
from ctypes import byref
import os.path
from pkg_resources import resource_filename
import platform
import time # ADDED
from random import randrange  # ADDED
epanet_toolkit = 'wntr.epanet.toolkit'

if os.name in ['nt','dos']:
    libepanet = resource_filename(__name__,'Windows/epanet2.dll')
elif sys.platform in ['darwin']:
    libepanet = resource_filename(__name__,'Darwin/libepanet.dylib')
else:
    libepanet = resource_filename(__name__,'Linux/libepanet2.so')

import logging
logger = logging.getLogger(__name__)

# import warnings

class EpanetException(Exception):
    pass


def ENgetwarning(code, sec=-1):
    if sec >= 0:
        hours = int(sec/3600.)
        sec -= hours*3600
        mm = int(sec/60.)
        sec -= mm*60
        header = 'At %3d:%.2d:%.2d, '%(hours,mm,sec)
    else:
        header = ''
    if code == 1:
        return header+'System hydraulically unbalanced - convergence to a hydraulic solution was not achieved in the allowed number of trials'
    elif code == 2:
        return header+'System may be hydraulically unstable - hydraulic convergence was only achieved after the status of all links was held fixed'
    elif code == 3:
        return header+'System disconnected - one or more nodes with positive demands were disconnected for all supply sources'
    elif code == 4:
        return header+'Pumps cannot deliver enough flow or head - one or more pumps were forced to either shut down (due to insufficient head) or operate beyond the maximum rated flow'
    elif code == 5:
        return header+'Vavles cannot deliver enough flow - one or more flow control valves could not deliver the required flow even when fully open'
    elif code == 6:
        return header+'System has negative pressures - negative pressures occurred at one or more junctions with positive demand'
    else:
        return header+'Unknown warning: %d'%code

def runepanet(inpfile):
    """Run an EPANET command-line simulation
    
    Parameters
    ----------
    inpfile : str
        The input file name

    """
    file_prefix, file_ext = os.path.splitext(inpfile)
    enData = ENepanet()
    rptfile = 'temp/' + file_prefix + '.rpt'
    outfile = 'temp/' + file_prefix + '.bin'
    enData.ENopen(inpfile, rptfile, outfile)
    enData.ENsolveH()
    #enData.ENsaveH()
    enData.ENsolveQ()
    #enData.ENcloseQ()
    try:
        enData.ENreport()
    except:
        pass
    enData.ENclose()


class ENepanet():
    """Wrapper class to load the EPANET DLL object, then perform operations on
    the EPANET object that is created when a file is loaded.

    Parameters
    ----------
    inpfile : str
        Input file to use
    rptfile : str
        Output file to report to
    binfile : str
        Results file to generate
    version : float
        EPANET version to use (either 2.0 or 2.2)
    
    """
    
    ENlib = None
    """The variable that holds the ctypes Library object"""

    errcode = 0
    """Return code from the EPANET library functions"""

    errcodelist = []
    cur_time = 0

    Warnflag = False
    """A warning occurred at some point during EPANET execution"""

    Errflag = False
    """A fatal error occurred at some point during EPANET execution"""

    inpfile = 'temp.inp'
    """The name of the EPANET input file"""

    rptfile = 'temp.rpt'
    """The report file to generate"""

    binfile = 'temp.bin'
    """The optional binary output file"""

    fileLoaded = False
    
    # ADDED
    ph_idx = int(time.time())+randrange(10000)
    ph = ctypes.c_void_p(ph_idx)


    def __init__(self, ph = ph, inpfile='', rptfile='', binfile='', version=2.2):

        self.inpfile = inpfile
        self.rptfile = rptfile
        self.binfile = binfile


        if float(version) == 2.0:
            libnames = ['epanet2_x86','epanet2','epanet']
            if '64' in platform.machine():
                libnames.insert(0, 'epanet2_amd64')
        elif float(version) == 2.2:
            libnames = []#['epanet22', 'epanet22_win32']
            if '64' in platform.machine():
                libnames.insert(0, 'epanet22_amd64')
        for lib in libnames:
            try:
                if os.name in ['nt','dos']:
                    libepanet = resource_filename(epanet_toolkit,'Windows/%s.dll' % lib)
                    #self.ENlib = ctypes.cdll.LoadLibrary(libepanet)
                    self.ENlib = ctypes.windll.LoadLibrary(libepanet)
                elif sys.platform in ['darwin']:
                    libepanet = resource_filename(epanet_toolkit,'Darwin/lib%s.dylib' % lib)
                    self.ENlib = ctypes.cdll.LoadLibrary(libepanet)
                else:
                    libepanet = resource_filename(epanet_toolkit,'Linux/lib%s.so' % lib)
                    self.ENlib = ctypes.cdll.LoadLibrary(libepanet)
                return # OK!
            except Exception as E1:
                if lib == libnames[-1]:
                    raise E1
                pass
        
        # ADDED
        self.ph = ph
        #print(self.ph)
        
        return

    def isOpen(self):
        """Checks to see if the file is open"""
        return self.fileLoaded

    def _error(self):
        """Print the error text the corresponds to the error code returned"""
        if not self.errcode: return
        #errtxt = self.ENlib.ENgeterror(self.errcode)
        logger.error("EPANET error: %d",self.errcode)
        if self.errcode >= 100:
            self.Errflag = True
            self.errcodelist.append(self.errcode)
            raise EpanetException('EPANET Error {}'.format(self.errcode))
        else:
            self.Warnflag = True
            # warnings.warn(ENgetwarning(self.errcode))
            self.errcodelist.append(ENgetwarning(self.errcode,self.cur_time))
        return

    def ENopen(self, inpfile=None, rptfile=None, binfile=None):
        """
        Opens an EPANET input file and reads in network data

        Parameters
        ----------
        inpfile : str
            EPANET INP file (default to constructor value)
        rptfile : str
            Output file to create (default to constructor value)
        binfile : str
            Binary output file to create (default to constructor value)
            
        """
        if self.fileLoaded: self.EN_close(self.ph)
        if self.fileLoaded:
            raise RuntimeError("File is loaded and cannot be closed")
        if inpfile is None: inpfile = self.inpfile
        if rptfile is None: rptfile = self.rptfile
        if binfile is None: binfile = self.binfile
        inpfile = inpfile.encode('ascii')
        rptfile = rptfile.encode('ascii')
        binfile = binfile.encode('ascii')
        self.ENlib.EN_createproject.argtypes = [ctypes.c_void_p]
        self.ENlib.EN_createproject(ctypes.byref(self.ph))
        self.errcode = self.ENlib.EN_open(self.ph, inpfile, rptfile, binfile)
        self._error()
        if self.errcode < 100:
            self.fileLoaded = True
        #print(self.ph)
        return

    def ENclose(self):
        """Frees all memory and files used by EPANET"""
        self.errcode = self.ENlib.EN_deleteproject(self.ph)
        self._error()
        if self.errcode < 100:
            self.fileLoaded = False
        return

    def ENsolveH(self):
        """Solves for network hydraulics in all time periods"""
        self.errcode = self.ENlib.EN_solveH(self.ph)
        self._error()
        return

    def ENsaveH(self):
        """Solves for network hydraulics in all time periods

        Must be called before ENreport() if no water quality simulation made.
        Should not be called if ENsolveQ() will be used.

        """
        self.errcode = self.ENlib.EN_saveH(self.ph)
        self._error()
        return

    def ENopenH(self):
        """Sets up data structures for hydraulic analysis"""
        self.errcode = self.ENlib.EN_openH(self.ph)
        self._error()
        return

    def ENinitH(self, iFlag):
        """Initializes hydraulic analysis

        Parameters
        -----------
        iFlag : 2-digit flag
            2-digit flag where 1st (left) digit indicates
            if link flows should be re-initialized (1) or
            not (0) and 2nd digit indicates if hydraulic
            results should be saved to file (1) or not (0)
            
        """
        self.errcode = self.ENlib.EN_initH(self.ph, iFlag)
        self._error()
        return

    def ENrunH(self):
        """Solves hydraulics for conditions at time t
        
        This function is used in a loop with ENnextH() to run
        an extended period hydraulic simulation.
        See ENsolveH() for an example.
        
        Returns
        --------
        Current simulation time (seconds)
        
        """
        lT = ctypes.c_long()
        self.errcode = self.ENlib.EN_runH(self.ph, byref(lT))
        self._error()
        self.cur_time = lT.value
        return lT.value

    def ENnextH(self):
        """Determines time until next hydraulic event
        
        This function is used in a loop with ENrunH() to run
        an extended period hydraulic simulation.
        See ENsolveH() for an example.
        
        Returns
        ---------
         Time (seconds) until next hydraulic event (0 marks end of simulation period)
         
        """
        lTstep = ctypes.c_long()
        self.errcode = self.ENlib.EN_nextH(byref(self.ph, lTstep))
        self._error()
        return lTstep.value

    def ENcloseH(self):
        """Frees data allocated by hydraulics solver"""
        self.errcode = self.ENlib.EN_closeH()
        self._error()
        return

    def ENsavehydfile(self, filename):
        """Copies binary hydraulics file to disk

        Parameters
        -------------
        filename : str
            Name of file
            
        """
        self.errcode = self.ENlib.EN_savehydfile(self.ph, filename.encode('ascii'))
        self._error()
        return

    def ENusehydfile(self, filename):
        """Opens previously saved binary hydraulics file

        Parameters
        -------------
        filename : str
            Name of file
            
        """
        self.errcode = self.ENlib.EN_usehydfile(self.ph, filename.encode('ascii'))
        self._error()
        return

    def ENsolveQ(self):
        """Solves for network water quality in all time periods"""
        self.errcode = self.ENlib.EN_solveQ(self.ph)
        self._error()
        return

    def ENopenQ(self):
        """Sets up data structures for water quality analysis"""
        self.errcode = self.ENlib.EN_openQ(self.ph)
        self._error()
        return

    def ENinitQ(self, iSaveflag):
        """Initializes water quality analysis

        Parameters
        -------------
         iSaveflag : int
             EN_SAVE (1) if results saved to file, EN_NOSAVE (0) if not
             
        """
        self.errcode = self.ENlib.EN_initQ(self.ph, iSaveflag)
        self._error()
        return

    def ENrunQ(self):
        """Retrieves hydraulic and water quality results at time t
        
        This function is used in a loop with ENnextQ() to run
        an extended period water quality simulation. See ENsolveQ() for
        an example.
        
        Returns
        -------
        Current simulation time (seconds)
         
        """
        lT = ctypes.c_long()
        self.errcode = self.ENlib.EN_runQ(self.ph, byref(lT))
        self._error()
        return lT.value

    def ENnextQ(self):
        """Advances water quality simulation to next hydraulic event

        This function is used in a loop with ENrunQ() to run
        an extended period water quality simulation. See ENsolveQ() for
        an example.
        
        Returns
        --------
        Time (seconds) until next hydraulic event (0 marks end of simulation period)
         
        """
        lTstep = ctypes.c_long()
        self.errcode = self.ENlib.EN_nextQ(self.ph, byref(lTstep))
        self._error()
        return lTstep.value

    def ENcloseQ(self):
        """Frees data allocated by water quality solver"""
        self.errcode = self.ENlib.EN_closeQ(self.ph)
        self._error()
        return

    def ENreport(self):
        """Writes report to report file"""
        self.errcode = self.ENlib.EN_report(self.ph)
        self._error()
        return

    def ENgetcount(self, iCode):
        """Retrieves the number of components of a given type in the network

        Parameters
        -------------
        iCode : int
            Component code (see toolkit.optComponentCounts)

        Returns
        ---------
        Number of components in network
        
        """
        iCount = ctypes.c_int()
        self.errcode = self.ENlib.EN_getcount(self.ph, iCode, byref(iCount))
        self._error()
        return iCount.value

    def ENgetflowunits(self):
        """Retrieves flow units code

        Returns
        -----------
        Code of flow units in use (see toolkit.optFlowUnits)
        
        """
        iCode = ctypes.c_int()
        self.errcode = self.ENlib.EN_getflowunits(self.ph, byref(iCode))
        self._error()
        return iCode.value

    def ENgetnodeindex(self, sId):
        """Retrieves index of a node with specific ID

        Parameters
        -------------
        sId : int
            Node ID

        Returns
        ---------
        Index of node in list of nodes
        
        """
        iIndex = ctypes.c_int()
        self.errcode = self.ENlib.EN_getnodeindex(self.ph, sId.encode('ascii'), byref(iIndex))
        self._error()
        return iIndex.value

    def ENgetnodevalue(self, iIndex, iCode):
        """Retrieves parameter value for a node

        Parameters
        -------------
        iIndex: int
            Node index
        iCode : int
            Node parameter code (see toolkit.optNodeParams)

        Returns
        ---------
        Value of node's parameter

        """
        fValue = ctypes.c_float()
        self.errcode = self.ENlib.EN_getnodevalue(self.ph, iIndex, iCode, byref(fValue))
        self._error()
        return fValue.value

    def ENgetlinkindex(self, sId):
        """Retrieves index of a link with specific ID

        Parameters
        -------------
        sId : int
            Link ID

        Returns
        ---------
        Index of link in list of links

        """
        iIndex = ctypes.c_int()
        self.errcode = self.ENlib.EN_getlinkindex(self.ph, sId.encode('ascii'), byref(iIndex))
        self._error()
        return iIndex.value

    def ENgetlinkvalue(self, iIndex, iCode):
        """Retrieves parameter value for a link

        Parameters
        -------------
        iIndex : int
            Link index
        iCode : int
            Link parameter code (see toolkit.optLinkParams)

        Returns
        ---------
        Value of link's parameter

        """
        fValue = ctypes.c_float()
        self.errcode = self.ENlib.EN_getlinkvalue(self.ph, iIndex, iCode, byref(fValue))
        self._error()
        return fValue.value


    def ENsaveinpfile(self, inpfile):
        """Saves EPANET input file

        Parameters
        -------------
        inpfile : str
		    EPANET INP output file

        """

        inpfile = inpfile.encode('ascii')
        self.errcode = self.ENlib.EN_saveinpfile(self.ph, inpfile)
        self._error()

        return


    
