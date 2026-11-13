"""Representative native face index for display; never aggregates physical discharge.

Every retained signed flux and row/column refers to one real 0.5 m face.
Selecting the strongest face in a display bin avoids point-sampling away canals.
"""
import numpy as np


def strongest(values,factor):
    """Maximum-absolute signed value and native indices per nonoverlapping block."""
    if values.ndim!=2 or factor<1:raise ValueError('Require 2D values and positive factor')
    rows,cols=values.shape;nr=(rows+factor-1)//factor;nc=(cols+factor-1)//factor
    padded=np.full((nr*factor,nc*factor),np.nan,np.float32);padded[:rows,:cols]=values
    patches=padded.reshape(nr,factor,nc,factor).transpose(0,2,1,3).reshape(nr,nc,-1)
    score=np.where(np.isfinite(patches),np.abs(patches),-1)
    k=score.argmax(axis=2);v=np.take_along_axis(patches,k[:,:,None],axis=2)[:,:,0]
    rr=np.arange(nr)[:,None]*factor+k//factor;cc=np.arange(nc)[None,:]*factor+k%factor
    valid=np.isfinite(v)
    return np.where(valid,v,0),np.where(valid,rr,-1),np.where(valid,cc,-1)


def reduce_records(records,factor):
    """Reduce [signed flux, native row, native col] without losing identity."""
    v,rr,cc=strongest(np.where(records[1]>=0,records[0],np.nan),factor)
    valid=rr>=0;ir=rr.clip(0);ic=cc.clip(0)
    return np.stack((v,np.where(valid,records[1,ir,ic],-1),np.where(valid,records[2,ir,ic],-1))).astype('float32')
