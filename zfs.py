#!/usr/bin/env python

from __future__ import with_statement
from grpc.beta import implementations

import zfs_pb2
import os
import sys
import errno
import random
import time

from functools import partial

from fuse import FUSE, FuseOSError, Operations

BLOCK_SIZE = 4096

class ZFS(Operations):

    def __init__(self, root, remote_host):
        self.root = root
        if not os.listdir(root).__contains__('tmp'):
            os.mkdir(root + "/tmp")
        channel = implementations.insecure_channel(remote_host, 50051)
        self.stub = zfs_pb2.beta_create_ZfsRpc_stub(channel)

    # Helpers
    # =======

    def _full_path(self, partial):
        if partial.startswith("/"):
            partial = partial[1:]
        path = os.path.join(self.root, partial)
        return path

    def rmdir(self, path):
        full_path = self._full_path(path)
        print "sending rmdir req for:", full_path
        os.rmdir(full_path)
        self.stub.RemoveDir(zfs_pb2.FilePath(path=full_path, mode=0), 10)
        #print "Response: " + response.message
        #return response.message

    def mkdir(self, path, mode):
        #print path, " : Hi"
        full_path = self._full_path(path)
        print "sending mkdir req for: ", full_path
        os.mkdir(full_path, mode)
        self.stub.MakeDir(zfs_pb2.FilePath(path=full_path, mode=mode), 10)
        #print "Response: " + response.message
        #return response.message

    def create(self, path, mode, fi=None):
        # rpc call stub.create()

        '''full_path = self._full_path(path)
        print "sending create req for file:", full_path #TODO
        return os.open(full_path, os.O_WRONLY | os.O_CREAT, mode)'''

        self.open(path, 1234)

        #return self.stub.create(zfs_pb2.Create(path=full_path, mode=mode), 10)
        #print "Response: " + response.message
        #return response.message

    def unlink(self, path):
        full_path = self._full_path(path)
        print "sending unlink req for file:", full_path #TODO :
        os.unlink(full_path)
        self.stub.RemoveFile(zfs_pb2.FilePath(path=full_path, mode=0), 10)
        #print "Response: " + response.message
        #return response.message

    def getattr(self, path, fh=None):
        # print "GETATTR: ", path
        full_path = self._full_path(path)
        #print "sending getattr req for: " + full_path
        st = os.lstat(full_path)
        return dict((key, getattr(st, key)) for key in ('st_atime', 'st_ctime', 'st_gid', 'st_mode', 'st_mtime', 'st_nlink', 'st_size', 'st_uid'))
        '''fileStat = self.stub.GetFileStat(zfs_pb2.FilePath(path=full_path, mode=0), 10)
        statMap = {'st_atime': fileStat.st_atime,
                   'st_ctime': fileStat.st_ctime,
                   'st_mtime': fileStat.st_mtime,
                   'st_dev': fileStat.st_dev,
                   'st_ino': fileStat.st_ino,
                   'st_size': fileStat.st_size,
                   'st_uid': fileStat.st_uid,
                   'st_gid': fileStat.st_gid,
                   'st_mode': fileStat.st_mode,
                   'st_nlink': fileStat.st_nlink}
        return statMap'''

    def readdir(self, path, fh):
        full_path = self._full_path(path)
        print "sending readdir req"
        files = self.stub.FetchDir(zfs_pb2.FilePath(path=full_path, mode=0), 10)
        for f in files:
            yield f.dir_list_block

    def open(self, path, flags):
        full_path = self._full_path(path)
        print "sending open req for file: ", full_path
        # check server mod time
        flag = 0
        reply = zfs_pb2.TestAuthReply()
        if os.path.isfile(full_path):
            print "file exists:", full_path
            mtime = os.lstat(full_path).st_mtime
            reply = self.stub.TestAuth(zfs_pb2.TestAuthRequest(path=full_path, st_mtime=mtime), 10)
        else:
            print "file doesn't exist:", full_path
            files = self.stub.FetchDir(zfs_pb2.FilePath(path=os.getcwd(), mode=0), 10)
            strSplit = full_path.split("/")[-1]
            print "file name: ", strSplit
            isFound=False
            for f in files:
                print "file from server:", f.dir_list_block
                if f is strSplit:
                    isFound=True
            if not isFound:
                return os.open(full_path, os.O_WRONLY | os.O_CREAT, 0777)
            else:
                flag = 1
        print "reply", reply.flag
        if reply.flag == 1 or flag == 1:
            print "File modified on server, fetching it again"
            rand = random.randint(10000000, 99999999)
            tmpFileName = self.root + "/tmp/" + str(rand)
            fd = open(tmpFileName, 'w')
            data_blocks = self.stub.Fetch(zfs_pb2.FilePath(path=full_path, mode=0), 10)
            actlen = 0
            count = 0
            for block in data_blocks:
                print block.data_block
                if count == 0:
                    count += 1
                    actlen = block.data_block
                else:
                    fd.write(block.data_block)
            fd.close()
            tmplen = os.stat(tmpFileName).st_size
            print "tmplen:", tmplen, "actual len:", actlen
            if not tmplen < actlen:
                os.rename(tmpFileName, full_path)

        return os.open(full_path, flags)

    def write(self, path, buf, offset, fh):
        full_path = self._full_path(path)
        print "sending write req for file: ", full_path
        os.lseek(fh, offset, os.SEEK_SET)
        return os.write(fh, buf)

    def release(self, path, fh):
        full_path = self._full_path(path)
        print "sending release req for file: ", full_path
        os.lseek(fh, 0, 0)
        chunk = self.generate_chunk_iter(full_path)
        self.stub.Store(chunk, 10)
        return os.close(fh)

    def generate_chunk_iter(self, full_path):
         yield zfs_pb2.FileDataBlock(data_block=full_path)
         fd = open(full_path)
         with fd as reader:
            for chunk in iter(partial(reader.read, BLOCK_SIZE), ''):
                yield zfs_pb2.FileDataBlock(data_block=chunk)

    def read(self, path, length, offset, fh):
        full_path = self._full_path(path)
        print "reading file: ", full_path
        os.lseek(fh, offset, os.SEEK_SET)
        return os.read(fh, length)

    def flush(self, path, fh):
        full_path = self._full_path(path)
        print "sending flush req for file: ", full_path
        return os.fsync(fh)

    def fsync(self, path, fdatasync, fh):
        full_path = self._full_path(path)
        print "sending fsync req for file: ", full_path
        return self.flush(path, fh)

    def rename(self, old, new):
        print "sending rename req"
        return self.stub.Rename(zfs_pb2.FilePath(old=self._full_path(old), new=self._full_path(new)), 10)

    '''def release(self, path, fh):
        full_path = self._full_path(path)
        print "sending release req for file: ", full_path
        return os.close(fh)

    def access(self, path, mode):
        print "sending access req"
        full_path = self._full_path(path)
        if not os.access(full_path, mode):
            raise FuseOSError(errno.EACCES)

    def chmod(self, path, mode):
        print "sending chmod req"
        full_path = self._full_path(path)
        return os.chmod(full_path, mode)

    def chown(self, path, uid, gid):
        print "sending chown req"
        full_path = self._full_path(path)
        return os.chown(full_path, uid, gid)

    def readlink(self, path):
        print "sending readlink req"
        pathname = os.readlink(self._full_path(path))
        if pathname.startswith("/"):
            # Path name is absolute, sanitize it.
            return os.path.relpath(pathname, self.root)
        else:
            return pathname

    def mknod(self, path, mode, dev):
        print "sending mknod req"
        return os.mknod(self._full_path(path), mode, dev)

    def statfs(self, path):
        print "sending statfs req"
        full_path = self._full_path(path)
        stv = os.statvfs(full_path)
        return dict((key, getattr(stv, key)) for key in ('f_bavail', 'f_bfree',
                                                         'f_blocks', 'f_bsize', 'f_favail', 'f_ffree', 'f_files',
                                                         'f_flag',
                                                         'f_frsize', 'f_namemax'))

    def symlink(self, name, target):
        print "sending symlink req"
        return os.symlink(name, self._full_path(target))


    def link(self, target, name):
        print "sending link req"
        return os.link(self._full_path(target), self._full_path(name))

    def utimens(self, path, times=None):
        print "sending utimes req"
        return os.utime(self._full_path(path), times)'''


def main(mntPoint, mountee, remote):
    FUSE(ZFS(mountee, remote), mntPoint, nothreads=True, foreground=True)


if __name__ == '__main__':
    mntPoint = "/users/vvaidhy/mnt"
    mountee = "/users/vvaidhy/mountee"
    remote = "128.104.222.43"
    if (len(sys.argv) == 4):
        mntPoint = sys.argv[1]
        mountee = sys.argv[2]
        remote = sys.argv[3]
    main(mntPoint, mountee, remote)
