# File name: a2fuse2.py
# Author: Hannah Soria
# User ID: 778838340
# Date: 24/9/2023
# Class: CS340

#!/usr/bin/env python

from __future__ import print_function, absolute_import, division

import logging

import os
import sys
import errno
from time import time
from stat import S_IFDIR, S_IFLNK, S_IFREG
from collections import defaultdict
from errno import ENOENT


from fuse import FUSE, FuseOSError, Operations, LoggingMixIn
from passthrough import Passthrough

class A2Fuse2(LoggingMixIn, Passthrough):

    #take in both sources
    def __init__(self, primary, fallback):
        self.primary = primary
        self.fallback = fallback
        
        #empty dictionary that will hold new files
        self.files = {}
        
        #necessary variable for memory files
        now = time()                
        self.fd = 0
        self.data = defaultdict(bytes)
        self.files['/'] = dict(st_mode=(S_IFDIR | 0o755), st_ctime=now, st_mtime=now, st_atime=now, st_nlink=2)
        

    #override from passthrough to return multiple directories
    def _full_path(self, partial, flag = False):
    	if partial.startswith("/"):
        	partial = partial[1:]
        	
        #the path for the primary
    	path = os.path.join(self.fallback if flag else self.primary, partial)
    	
    	#if the path does not exists then the path is the fallback
    	#if the path does not exist at all the path is also set to fallback as a placeholder, even though
    	#it does not exists there. This does not put it in the fallback it only makes the path usable
    	if not os.path.exists(path) and (flag == False):
    		path = os.path.join(self.fallback, partial)
    		
    	return path
        
    #override from passthrough to list contents of both directories and the contents of the memory dictionary
    def readdir(self, path, fh):
    	full_path = self._full_path(path, flag = True)
    	full_path2 = self._full_path(path)
    	dirents = ['.', '..']
    	if os.path.isdir(full_path):
    		dirents.extend(os.listdir(full_path))
    	if os.path.isdir(full_path2):
    		dirents.extend(os.listdir(full_path2))
    	dirents.extend([x[8:] for x in self.files if x != '/'])
    	for r in dirents:
    		yield r
        
     #if a new file is created in memory it is added to a dictionary       
     #create only happens if the the file is new to mount
    def create(self, path, mode):
    	full_path = self._full_path(path, flag = True)
    	self.files[full_path] = dict(st_mode=(S_IFREG | mode), st_nlink=1,st_size=0, st_ctime=time(), st_mtime=time(),st_atime=time())
    	self.fd += 1
    	return self.fd
    	
     #following methods check if dict is empty if yes that means that the file exists in a directory
     #if file existed make super call to passthough
     #otherwise handle for a file in memory
     
    def getattr(self, path, fh=None):
    	full_path = self._full_path(path)
    	if (self.files.get(full_path) == None):
    		return super(A2Fuse2, self).getattr(path, fh)
    	else:
    		return self.files[full_path]
        	
    def open(self, path, flags):
    	full_path = self._full_path(path)
    	if full_path not in self.files:
    		return super(A2Fuse2, self).open(path, flags)
    	if full_path in self.files:
    		self.fd += 1
    		return self.fd
        	
    def read(self, path, length, offset, fh):
    	full_path = self._full_path(path)
    	if full_path not in self.files:
    		return super(A2Fuse2, self).read(path, length, offset, fh)
    	if full_path in self.files:
    		return self.data[path][offset:offset + length]
        
    def write(self, path, data, offset, fh):
    	full_path = self._full_path(path)
    	if full_path not in self.files:
    		return super(A2Fuse2, self).write(path, data, offset, fh)
    	if full_path in self.files:
    		self.data[full_path] = self.data[full_path][:offset] + data
    		self.files[full_path]['st_size'] = len(self.data[full_path])
    		return len(data)
        	
    def readlink(self, path):
    	full_path = self._full_path(path)
    	if full_path not in self.files:
    		return super(A2Fuse2, self).readlink(path)
    	if full_path in self.files:
    		return self.data[path]
    		
    def rmdir(self, path):
    	full_path = self._full_path(path)
    	if full_path not in self.files:
    		return super(A2Fuse2, self).rmdir(path)
    	if full_path in self.files:
    		self.files.pop(path)
    		self.files['/']['st_nlink'] -= 1
    		
    def statfs(self, path):
    	full_path = self._full_path(path)
    	if full_path not in self.files:
    		return super(A2Fuse2, self).statfs(path)
    	if full_path in self.files:
    		return dict(f_bsize=512, f_blocks=4096, f_bavail=2048)
    		
    def unlink(self, path):
    	full_path = self._full_path(path)
    	if full_path not in self.files:
    		return super(A2Fuse2, self).unlink(path)
    	if full_path in self.files:
    		self.files.pop(full_path)
    		
    def access(self, path, mode):
        full_path = self._full_path(path)
        if full_path not in self.files:
        	return super(A2Fuse2, self).access(path, mode)
        if full_path in self.files:
        	return 0
            
    def flush(self, path, fh):
    	full_path = self._full_path(path)
    	if full_path not in self.files:
    		return super(A2Fuse2, self).flush(path, fh)
    	if full_path in self.files:
    		return 0
    		
    def release(self, path, fh):
    	full_path = self._full_path(path)
    	if full_path not in self.files:
    		return super(A2Fuse2, self).release(path, fh)
    	if full_path in self.files:
    		return 0
    		
    def getxattr(self, path, name, position=0):
        attrs = self.files[path].get('attrs', {})

        try:
            return attrs[name]
        except KeyError:
            return ''       # Should return ENOATTR
            
    def chmod(self, path, mode):
    	full_path = self._full_path(path)
    	if full_path not in self.files:
    		return super(A2Fuse2, self).chmod(path, mode)
    	if full_path in self.files:
	    	self.files[path]['st_mode'] &= 0o770000
	    	self.files[path]['st_mode'] |= mode
	    	return 0

    def chown(self, path, uid, gid):
    	full_path = self._full_path(path)
    	if full_path not in self.files:
    		return super(A2Fuse2, self).chown(path, uid, gid)
    	if full_path in self.files:
    		self.files[path]['st_uid'] = uid
    		self.files[path]['st_gid'] = gid
    

def main(primary, fallback, mountpoint):
    FUSE(A2Fuse2(primary, fallback), mountpoint, nothreads=True, foreground=True)

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main(sys.argv[1], sys.argv[2], sys.argv[3])
