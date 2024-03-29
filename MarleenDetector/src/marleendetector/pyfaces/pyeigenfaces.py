from math import sqrt
import pickle

from shutil import rmtree
from os import mkdir
from os.path import isdir, join, normpath
from os import listdir

import imageops
from numpy import asfarray, dot, argmin, zeros
from numpy import average, sort, trace
from numpy.linalg import svd, eigh

class DirectoryParser:
    """
        Finds all files in a directory with a given extension
    """
    
    def __init__(self, directoryName):
        self.directoryName = directoryName
        
    def parseDirectory(self, extension):
        """
            Returns all the files in directoryName hat have the extension
        """
        if not isdir(self.directoryName): return
        imagefilenameslist = sorted([
            normpath(join(self.directoryName, fname))
            for fname in listdir(self.directoryName)
            if fname.lower().endswith('.' + extension)            
            ])
        return imagefilenameslist
    
class ImageError(Exception):
    pass

class DirError(Exception):
    pass

class NoMatchError(Exception):
    pass
 
class FaceBundle:
    def __init__(self, imglist, wd, ht, adjfaces, fspace, avgvals, evals):
        """
            @param imglist: list of image filenames
            @param wd: the width of all the images in the bundle
            @param ht: the height of all the images in the bundle
            @param adjfaces: matrix where each row represents a flat normalized image-array with the average pixelvalue substracted
            @param fspace: fspace
            @param avgvals: array with average values for each pixel location (avgvals.length = wd*ht)
            @param evals: array of size image-list with sorted eigen values (max -> min)
        """
        self.imglist = imglist
        self.wd = wd
        self.ht = ht
        self.adjfaces = adjfaces
        self.eigenfaces = fspace
        self.avgvals = avgvals
        self.evals = evals

class egface:
    """
        EGFace class
    """
    def validateSelectedImage(self, imgname):
        """
            Check if the image conforms to the height/width of the images in the bundle
            Returns the XImage
        """
        print "validateSelectedImage()"               
        selectimg = imageops.XImage(imgname) # image (flat list)
        selectwdth = selectimg._width # width
        selectht = selectimg._height # height
        print "w:%d h:%d" % (self.bundle.wd, self.bundle.ht)  
        if((selectwdth != self.bundle.wd) or (selectht != self.bundle.ht)):            
            raise ImageError("select image of matching dimensions ! w:" + str(selectwdth) + " h:" + str(selectht))
        else:            
            return selectimg
        
    def findMatchingImage(self, imagename, selectedfacesnum, thresholdvalue):
        """
            Finds a matching image from the bundle
        """
        print "findMatchingImage()" 
        selectimg = self.validateSelectedImage(imagename) # returns the image
        inputfacepixels = selectimg._pixellist # image flat pixel list
        inputface = asfarray(inputfacepixels) # float[]
        pixlistmax = max(inputface) # max value
        inputfacen = inputface / pixlistmax   # norm-array: divide all values by max      
        inputface = inputfacen - self.bundle.avgvals
        usub = self.bundle.eigenfaces[:selectedfacesnum, :]
        input_wk = dot(usub, inputface.transpose()).transpose()        
        dist = ((self.weights - input_wk) ** 2).sum(axis=1)
        print dist # distance array
        idx = argmin(dist) # returns minimum value in the array
        print idx # the index in the array  
        mindist = sqrt(dist[idx])
        result = ''
        print "mindist:", mindist
        if mindist <= thresholdvalue:
            result = self.bundle.imglist[idx]
        print "try reconstruction"
        self.reconstructFaces(selectedfacesnum)            
        return mindist, result
    
    def doCalculations(self, dir, imglist, selectednumeigenfaces):
        """
            Create bundle, calculate weights
            @param dir: name of the directory
            @param imglist: list of image filenames
            @param selectedfacesnum: the number of eigen faces            
        """
        print "doCalculations()"        
        self.createFaceBundle(imglist);        
        egfaces = self.bundle.eigenfaces
        adjfaces = self.bundle.adjfaces # matrix where each row represents a flat normalized image-array with the average pixelvalue substracted
        self.weights = self.calculateWeights(egfaces, adjfaces, selectednumeigenfaces)
        
        #write to cache
        cachefile = join(dir, "saveddata.cache")
        f2 = open(cachefile, "w")
        pickle.dump(self.bundle, f2)
        f2.close()
        
    def validateDirectory(self, imgfilenameslist):
        """
            Validates the images in the list:
            The length of imgfilenameslist should be greater than zero.
            All the images should have the same dimension.
            Returns a list of XImage
        """
        print "validatedirectory()"        
        if (len(imgfilenameslist) == 0):
            print "folder empty!"
            raise DirError("folder empty!")
        imgfilelist = []
        for z in imgfilenameslist:
            img = imageops.XImage(z) # image (flat pixel list)
            imgfilelist.append(img)        
        sampleimg = imgfilelist[0]
        imgwdth = sampleimg._width
        imght = sampleimg._height        
        #check if all images have same dimensions
        for x in imgfilelist:
            newwdth = x._width
            newht = x._height
            if((newwdth != imgwdth) or (newht != imght)):
                raise DirError("select folder with all images of equal dimensions !")
        return imgfilelist
    
    def calculateWeights(self, eigenfaces, adjfaces, selectedfacesnum):
        """
            @param selectedfacesnum: number of eigen faces to use
        """
        print "calculateweights()"                
        usub = eigenfaces[:selectedfacesnum, :] # get the first selectedfacesnum rows   
        wts = dot(usub, adjfaces.transpose()).transpose()                         
        return wts           
            
    def createFaceBundle(self, imglist):
        """
            Creates a face bundle from the image list
            and saves the eigenface images to the eigenfaces-dir
            @param imglist: list of image filenames
        """
        print "createFaceBundle()"        
        imgfilelist = self.validateDirectory(imglist) # list of XImage
        
        img = imgfilelist[0]
        imgwdth = img._width
        imght = img._height
        numpixels = imgwdth * imght # number of pixels in each image
        numimgs = len(imgfilelist) # total number of images        
        #trying to create a 2d array ,each row holds pixvalues (flat array representation of the image matrix) of a single image
        facemat = zeros((numimgs, numpixels)) # face matrix         
        for i in range(numimgs):
            pixarray = asfarray(imgfilelist[i]._pixellist) # get pixel array of image
            pixarraymax = max(pixarray) # max value in the flat image array
            pixarrayn = pixarray / pixarraymax # normalize array                 
            facemat[i, :] = pixarrayn # set array to correct row in the matrix          
        
        #create average values, one for each column(ie pixel). 
        # each value stands for the average of the pixel in all images, thus we have an array of lenght numpixels  
        avgvals = average(facemat, axis=0)
        #make average faceimage in currentdir just for fun viewing..
        imageops.make_image(avgvals,"average.png",(imgwdth,imght))               
        #substract avg val from each orig val to get adjusted faces(phi of T&P)     
        adjfaces = facemat - avgvals
        adjfaces_tr = adjfaces.transpose()        
        L = dot(adjfaces , adjfaces_tr)
        evals1, evects1 = eigh(L)
        #svd also works..comment out the prev line and uncomment next line to see 
        #evects1,evals1,vt=svd(L,0)        
        reversedevalueorder = evals1.argsort()[::-1]
        evects = evects1[:, reversedevalueorder]               
        evals = sort(evals1)[::-1] # sort the eigen values
        #rows in u are eigenfaces        
        u = dot(adjfaces_tr, evects)
        u = u.transpose()               
        #NORMALISE rows of u
        for i in range(numimgs):
            ui = u[i]
            ui.shape = (imght, imgwdth)
            norm = trace(dot(ui.transpose(), ui))            
            u[i] = u[i] / norm        
        
        self.bundle = FaceBundle(imglist, imgwdth, imght, adjfaces, u, avgvals, evals)
        #print "in facebundle:imgwdth=",imgwdth,"imght=",imght
        self.createEigenimages(u)# eigenface images
        
    def reconstructFaces(self, selectedfacesnum):        
        #reconstruct                  
        recondir = '../reconfaces'
        newwt = zeros(self.weights.shape)
        eigenfaces = self.bundle.eigenfaces
        usub = eigenfaces[:selectedfacesnum, :]
        evals = self.bundle.evals # sorted eigen values
        evalssub = evals[:selectedfacesnum] # the first selectedfacesnum items
        for i in range(len(self.weights)):
            for j in range(len(evalssub)):        
                newwt[i][j] = self.weights[i][j] * evalssub[j]        
        phinew = dot(newwt, usub)    
        
        xnew = phinew + self.bundle.avgvals # array with average values for each pixel location (avgvals.length = wd*ht)
        try:
            if isdir(recondir):                             
                rmtree(recondir, True)                
        except Exception, inst:
            print "problem removing dir :", inst.message        
        mkdir(recondir)
        print "made:", recondir
        numimgs = len(self.bundle.imglist)
        for x in range(numimgs):
            imgname = recondir + "/reconphi" + str(x) + ".png" 
            imgdata = phinew[x]           
            imageops.make_image(imgdata, imgname, (self.bundle.wd, self.bundle.ht), True)
            
        for x in range(numimgs):
            filename = recondir + "/reconx" + str(x) + ".png"
            imgdata = xnew[x]
            imageops.make_image(imgdata, filename, (self.bundle.wd, self.bundle.ht), True)
    
    def createEigenimages(self, eigenspace):
        """
            Creates the eigenfaces and saves them,
            each row in the eigenspace matrix represents an image as flat-array
        """
        egndir = '../eigenfaces'        
        try:
            if isdir(egndir):                
                rmtree(egndir, True)                
        except Exception, inst:
            print "problem removing dir :", inst.message        
        mkdir(egndir)            
        numimgs = len(self.bundle.imglist)
        for x in range(numimgs):
            imgname = egndir + "/eigenface" + str(x) + ".png"            
            imageops.make_image(eigenspace[x], imgname, (self.bundle.wd, self.bundle.ht))
    
    def checkCache(self, dir, imglist, selectedfacesnum):
        """
            Check if the cache needs to be updated or created
            The Cache is updated when the number of images in the cache differs 
            from the number of images in the selected directory
            
            @param dir: name of the directory
            @param imglist: list of image filenames
            @param selectedfacesnum: the number of eigen faces
        """        
        cachefile = join(dir, "saveddata.cache")
        cache_changed = True
        try:
            f = open(cachefile)
        except IOError:
            print "no cache file found"            
            self.doCalculations(dir, imglist, selectedfacesnum)
        else:
            self.bundle = pickle.load(f)
            oldlist = self.bundle.imglist
            if(imglist == oldlist):
                print 'both sets same'
                cache_changed = False
                eigenfaces = self.bundle.eigenfaces
                adjfaces = self.bundle.adjfaces                             
                self.weights = self.calculateWeights(eigenfaces, adjfaces, selectedfacesnum);
            if(cache_changed):
                print "folder changed!!"                
                self.doCalculations(dir, imglist, selectedfacesnum)
            f.close()
    
    def isValid(self, selectedNumberOfEigenFaces, numberOfImageFiles):
        """
            Returns true if 0 < selectedNumberOfEigenFaces < numberOfImageFiles
        """     
        if selectedNumberOfEigenFaces < numberOfImageFiles and selectedNumberOfEigenFaces > 0:
            return True
        else:
            return False
        
        
            
        
