#!/usr/bin/env python
"""
:platform: Unix, Windows, Mac
:synopsis: Gets a ISR sensor constants and calculates theoretical beam patterns.

.. moduleauthor:: John Swoboda <swoboj@bu.edu>
"""
from . import Path
import tables
import numpy as np
from scipy.interpolate import griddata
import scipy as sp
#
from .mathutils import diric, angles2xy, jinc, rotcoords
from .physConstants import v_C_0
## Parameters for Sensor
#AMISR = {'Name':'AMISR','Pt':2e6,'k':9.4,'G':10**4.3,'lamb':0.6677,'fc':449e6,'fs':50e3,\
#    'taurg':14,'Tsys':120,'BeamWidth':(2,2)}
#AMISR['t_s'] = 1/AMISR['fs']


def getConst(typestr,angles = None):
    """Get the constants associated with a specific radar system. This will fill
    out a dictionary with all of the parameters.

    Args:
        type (str): Name of the radar system.
        angles (:obj:`numpy array`): Nx2 array where each row is an az, el pair in degrees.

    Returns:
        sensdict (dict[str, obj]): Holds the different sensor constants.::

            {
                    'Name': radar name,
                    'Pt': Transmit power in W,
                    'k': wave number in rad/m,
                    'lamb': Wave length in m,
                    'fc': Carrier Frequency in Hz,
                    'fs': Sampling frequency in Hz,
                    'taurg': Pulse length number of samples,
                    'Tsys': System Temperature in K,
                    'BeamWidth': Tuple of beamwidths in degrees,
                    'Ksys': ,
                    'BandWidth': Filter bandwidth in Hz,
                    'Angleoffset': Tuple of angle offset,
                    'ArrayFunc': Function to calculate antenna pattern,
                    't_s': Sampling time in s
            }
    """
    dirname = Path(__file__).expanduser().parent.parent
    if typestr.lower() == 'risr' or typestr.lower() == 'risr-n':
        arrayfunc = AMISR_Patternadj
        h5filename = dirname/'RISR_PARAMS.h5'
    elif typestr.lower() == 'pfisr':
        arrayfunc = AMISR_Patternadj
        h5filename = dirname/'PFISR_PARAMS.h5'
    elif typestr.lower() == 'millstone':
        arrayfunc = Millstone_Pattern_M
        h5filename = dirname/'Millstone_PARAMS.h5'
    elif typestr.lower() == 'millstonez':
        arrayfunc = Millstone_Pattern_Z
        h5filename = dirname/'Millstone_PARAMS.h5'
    elif typestr.lower() == 'sondrestrom':
        arrayfunc = Sond_Pattern
        h5filename = dirname/'Sondrestrom_PARAMS.h5'

    with tables.open_file(str(h5filename)) as f:
        kmat = f.root.Params.Kmat.read()
        freq = float(f.root.Params.Frequency.read())
        P_r = float(f.root.Params.Power.read())
        bandwidth = f.get_node('/Params/Bandwidth').read()
        ts = f.get_node('/Params/Sampletime').read()
        systemp = f.get_node('/Params/Systemp').read()
        Ang_off = f.root.Params.Angleoffset.read()

    Ksens = freq*2*np.pi/v_C_0
    lamb = Ksens/2.0/np.pi
    az = kmat[:, 1]
    el = kmat[:, 2]
    ksys = kmat[:, 3]

    (xin, yin) = angles2xy(az, el)
    points = sp.column_stack((xin, yin))
    if angles is not None:
        (xvec,yvec) = angles2xy(angles[:,0],angles[:,1])
        ksysout = griddata(points, ksys, (xvec, yvec), method='nearest')
    else:
        ksysout = None

    #'G':10**4.3, This doesn't get used anymore it seems
    sensdict = {'Name':typestr,'Pt':P_r,'k':Ksens,'lamb':lamb,'fc':freq,'fs':1/ts,\
    'taurg':14,'Tsys':systemp,'BeamWidth':(2,2),'Ksys':ksysout,'BandWidth':bandwidth,\
    'Angleoffset':Ang_off,'ArrayFunc':arrayfunc}
    sensdict['t_s'] = ts
    return sensdict

def AMISR_Patternadj(Az,El,Az0,El0,Angleoffset):
    """This function will call AMISR beam patern function after it rotates the coordinates
    given the offset of the phased array.

    Args:
        Az (:obj:`numpy array`): Azimuth angles in degrees.
        El (:obj:`numpy array`): Elevation angles in degrees.
        Az_0 (float): The azimuth pointing angle in degrees.
        El_0 (float): The elevation pointing angle in degrees.
        Angleoffset (list): A 2 element list holding the offset of the face of the array
            from north.
    Returns:
        Beam_Pattern (:obj:`numpy array`): The relative beam pattern from the azimuth points.
    """
    d2r = np.pi/180.0

    Azs, Els = rotcoords(Az, El, -Angleoffset[0], -Angleoffset[1])
    eps = np.finfo(Az. dtype).eps
    Azs[np.abs(Azs) < 15*eps] = 0.
    Azs = np.mod(Azs, 360.)

    Az0s, El0s = rotcoords(Az0, El0, -Angleoffset[0], -Angleoffset[1])
    Elr = (90.-Els)*d2r
    El0r = (90.-El0s)*d2r
    Azr = Azs*d2r
    Az0r = Az0s*d2r
    return AMISR_Pattern(Azr, Elr, Az0r, El0r)

def Sond_Pattern(Az,El,Az0,El0,Angleoffset):
    """Gives the ideal antenna pattern for the Sondestrom radar.

    This function will call circular antenna beam patern function after it
    rotates the coordinates given the pointing direction.

    Args:
        Az (:obj:`numpy array`): Azimuth angles in degrees.
        El (:obj:`numpy array`): Elevation angles in degrees.
        Az_0 (float): The azimuth pointing angle in degrees.
        El_0 (float): The elevation pointing angle in degrees.
        Angleoffset (list): A 2 element list holding the offset of the face of the array
            from north.

    Returns:
        Beam_Pattern (:obj:`numpy array`): The relative beam pattern from the azimuth points.
    """


    d2r= np.pi/180.0
    radius = 30.
    lamb = v_C_0/1.2e9

    __, Eladj = rotcoords(Az,El,-Az0,El0-90.)
    Elr = (90.0-Eladj)*d2r
    return Circ_Ant_Pattern(Elr,radius,lamb)

def Millstone_Pattern_Z(Az, El, Az0, El0, Angleoffset):
    """Gives the ideal antenna pattern for the Zenith dish at Milstone hill.

    This function will call circular antenna beam patern function after it
    rotates the coordinates given the pointing direction.


    Args:
        Az (:obj:`numpy array`): Azimuth angles in degrees.
        El (:obj:`numpy array`): Elevation angles in degrees.
        Az_0 (float): The azimuth pointing angle in degrees.
        El_0 (float): The elevation pointing angle in degrees.
        Angleoffset (list): A 2 element list holding the offset of the face of the array
            from north.

    Returns:
        Beam_Pattern (:obj:`numpy array`): The relative beam pattern from the azimuth points.
    """
    d2r = np.pi/180.0
    radius = 33.5
    lamb = v_C_0/4.4e8
    __, Eladj = rotcoords(Az, El, 0.0, 0.)
    Elr = (90.0-Eladj)*d2r
    return Circ_Ant_Pattern(Elr,radius,lamb)

def Millstone_Pattern_M(Az,El,Az0,El0,Angleoffset):
    """Gives the ideal antenna pattern for the MISA dish at Milstone hill.

    This function will call circular antenna beam patern function after it
    rotates the coordinates given the pointing direction.


    Args:
        Az (:obj:`numpy array`): Azimuth angles in degrees.
        El (:obj:`numpy array`): Elevation angles in degrees.
        Az_0 (float): The azimuth pointing angle in degrees.
        El_0 (float): The elevation pointing angle in degrees.
        Angleoffset (list): A 2 element list holding the offset of the face of the array
            from north.

    Returns:
        Beam_Pattern (:obj:`numpy array`): The relative beam pattern from the azimuth points.
    """
    d2r= np.pi/180.0
    r = 23.
    lamb = v_C_0/4.4e8
    Azadj,Eladj = rotcoords(Az,El,-Az0,El0-90.)
    Elr = (90.0-Eladj)*d2r
    return Circ_Ant_Pattern(Elr,r,lamb)
def Circ_Ant_Pattern(EL,r,lamb):
    """Returns the pattern for a circular dish antenna.

    This function will create an idealized antenna pattern for a circular antenna
    array. The pattern is not normalized.
    The antenna is assumed to made of a grid of ideal cross dipole
    elements. In the array every other column is shifted by 1/2 dy. The
    parameters are taken from the AMISR spec and the method for calculating
    the field is derived from a report by Adam R. Wichman.
    The inputs for the az and el coordinates can be either an array or
    scalar. If both are arrays they must be the same shape.

    Args:

        EL (:obj:`numpy array`): The elevation coordinates in radians. Vertical is at zero radians.
        r (float): Radius of the antenna in meters.
        lamb (float): wavelength of radiation in meters.

    Returns:
        Patout (:obj:`numpy array`): The normalized radiation density.
    """

    Patout = (2.*r/lamb)**2* np.abs(jinc((2.*r/lamb)*np.sin(EL)))
    Patout[EL<0]=0
    normfactor = (2.*r/lamb)**2* jinc(0.)
    return Patout/normfactor

def get_files(fname):
    """ Gets the hdf5 files associated with the radar.

    Args:
        fname (str): Name for the radar.

    Returns:
        newpath (str): String holding the location for the file.
    """
    curpath = Path(__file__).parent.parent
    newpath=curpath.joinpath(fname)
    if not newpath.is_file():
        return False
    return str(newpath)

def AMISR_Pattern(AZ,EL,Az0,El0):
    """
        Returns the AMISR pattern in the direction of the array face.

        This function will create an idealized antenna pattern for the AMISR array. The pattern is not normalized. The antenna is assumed to made of a grid of ideal cross dipole
        elements. In the array every other column is shifted by 1/2 dy. The
        parameters are taken from the AMISR spec and the method for calculating
        the field is derived from a report by Adam R. Wichman.
        The inputs for the az and el coordinates can be either an array or
        scalar. If both are arrays they must be the same shape.

        Args:
            Az (:obj:`numpy array`): Azimuth angles in degrees.
            El (:obj:`numpy array`): Elevation angles in degrees.
            Az_0 (float): The azimuth pointing angle in degrees.
            El_0 (float): The elevation pointing angle in degrees.

        Returns:
            Patout (:obj:`numpy array`): The normalized radiation density.
    """
    f0=440e6 # frequency of AMISR in Hz
    lam0=v_C_0/f0 # wavelength in m
    k0=2*np.pi/lam0 # wavenumber in rad/m

    dx=0.4343 # x spacing[m]
    dy=0.4958 # y spacing[m]
    # element pattern from an ideal cross dipole array.
    elementpower=(1.0/2.0)*(1.0+(np.cos(EL))**2)
    # Use this to kill back lobes.
    elementpower[EL<0] = 0.
#    pdb.set_trace()
    m=8.0;# number of pannels in the x direction
    mtot = 8.0*m;# number of elements times panels in x direction

    n = 16.0;# number of pannels in the y direction
    ntot = n*4.0;# number of elements times panels in y direction
    # relative phase between the x elements
    phix = k0*dx*(np.sin(EL)*np.cos(AZ)-np.sin(El0)*np.cos(Az0))
    # relative phase between the y elements
    phiy = k0*dy*(np.sin(EL)*np.sin(AZ)-np.sin(El0)*np.sin(Az0))

    AF = (1.0+np.exp(1j*(phiy/2.+phix)))*diric(2.0*phix,mtot/2.0)*diric(phiy,ntot)
    arrayfac = abs(AF)**2
    Patout = elementpower*arrayfac
    return Patout
