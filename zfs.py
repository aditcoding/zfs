#!/usr/bin/env python

from __future__ import with_statement
from grpc.beta import implementations

import zfs_pb2
import os
import sys
import errno

from fuse import FUSE, FuseOSError, Operations


class ZFS(Operations):

    def __init__(self, root, remote_host):
        self.root = root
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
        print "sending rmdir req"
        return self.stub.rmdir(zfs_pb2.Create(path=full_path, mode=0), 10)
        #print "Response: " + response.message
        #return response.message

    def mkdir(self, path, mode):
        #print path, " : Hi"
        full_path = self._full_path(path)
        print "sending mkdir req"
        return self.stub.mkdir(zfs_pb2.Create(path=full_path, mode=mode), 10)
        #print "Response: " + response.message
        #return response.message

    def create(self, path, mode, fi=None):
        # rpc call stub.create()
        full_path = self._full_path(path)
        print "sending create req"
        return self.stub.create(zfs_pb2.Create(path=full_path, mode=mode), 10)
        #print "Response: " + response.message
        #return response.message

    def unlink(self, path):
        full_path = self._full_path(path)
        print "sending unlink req"
        return self.stub.unlink(zfs_pb2.Create(path=full_path, mode=0), 10)
        #print "Response: " + response.message
        #return response.message

    def getattr(self, path, fh=None):
        # print "GETATTR: ", path
        full_path = self._full_path(path)
        print "sending getattr req"
        st = os.lstat(full_path)
        return dict((key, getattr(st, key)) for key in ('st_atime', 'st_ctime', 'st_gid', 'st_mode', 'st_mtime', 'st_nlink', 'st_size', 'st_uid'))
        #return self.stub.getattr(zfs_pb2.Create(path=full_path, mode=0), 10)

    def open(self, path, flags):
        print "sending open req"
        full_path = self._full_path(path)
        return os.open(full_path, flags)

    def read(self, path, length, offset, fh):
        print "sending read req"
        os.lseek(fh, offset, os.SEEK_SET)
        return os.read(fh, length)

    def write(self, path, buf, offset, fh):
        print "sending write req"
        os.lseek(fh, offset, os.SEEK_SET)
        return os.write(fh, buf)

    def truncate(self, path, length, fh=None):
        print "sending truncate req"
        full_path = self._full_path(path)
        with open(full_path, 'r+') as f:
            f.truncate(length)

    def flush(self, path, fh):
        print "sending flush req"
        return os.fsync(fh)

    def release(self, path, fh):
        print "sending release req"
        return os.close(fh)

    def fsync(self, path, fdatasync, fh):
        print "sending fsync req"
        return self.flush(path, fh)

    # Filesystem methods
    # ==================

    def readdir(self, path, fh):
        full_path = self._full_path(path)
        print "sending readdir req"
        dirents = ['.', '..']
        if os.path.isdir(full_path):
            dirents.extend(os.listdir(full_path))
        for r in dirents:
            yield r
        #return self.stub.readdir(zfs_pb2.Create(path=full_path, mode=0), 10)

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

    def rename(self, old, new):
        print "sending rename req"
        return os.rename(self._full_path(old), self._full_path(new))

    def link(self, target, name):
        print "sending link req"
        return os.link(self._full_path(target), self._full_path(name))

    def utimens(self, path, times=None):
        print "sending utimes req"
        return os.utime(self._full_path(path), times)


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
