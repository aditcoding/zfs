__author__ = 'adi'

import time
import os
import traceback

import zfs_pb2
from functools import partial

_ONE_DAY_IN_SECONDS = 60 * 60 * 24
BLOCK_SIZE = 4096


class ZfsServer(zfs_pb2.BetaZfsRpcServicer):
    def _full_path(self, partial):
        if partial.startswith("/"):
            partial = partial[1:]
        path = os.path.join(self.root, partial)
        return path

    def CreateFile(self, request, context):
        print "create req received"
        print "Req path: " + request.path
        ret = os.open(request.path, os.O_WRONLY | os.O_CREAT, request.mode)
        print "Status: ", ret
        return zfs_pb2.StdReply(error_message='Returned, %s!' % ret, status=0)

    def GetFileStat(self, request, context):
        print "Get attr req received"
        print "Req path: " + request.path
        st = os.lstat(request.path)
        #print "atime", getattr(st, 'st_atime'), "ctime", getattr(st, 'st_ctime')
        #statMap = dict((key, getattr(st, key)) for key in ('st_ino', 'st_dev', 'st_atime', 'st_ctime', 'st_gid', 'st_mode', 'st_mtime', 'st_nlink', 'st_size', 'st_uid'))
        #print "from map", statMap['st_atime'], statMap['st_ctime']
        return zfs_pb2.FileStat(st_atime=getattr(st, 'st_atime'),
                              st_ctime=getattr(st, 'st_ctime'),
                              st_gid=getattr(st, 'st_gid'),
                              st_mode=getattr(st, 'st_mode'),
                              st_mtime=getattr(st, 'st_mtime'),
                              st_nlink=getattr(st, 'st_nlink'),
                              st_size=getattr(st, 'st_size'),
                              st_uid=getattr(st, 'st_uid'),
                              st_ino=getattr(st, 'st_ino'),
                              st_dev=getattr(st, 'st_dev'))
        #for key in ['st_ino', 'st_dev', 'st_atime', 'st_ctime', 'st_gid', 'st_mode', 'st_mtime', 'st_nlink', 'st_size', 'st_uid']:
            #fileStat.mapfield[key] = st.key

    def RemoveDir(self, request, context):
        print "Rm dir req received"
        print "Req path: " + request.path
        os.rmdir(request.path)
        return zfs_pb2.StdReply(status=1, error_message='')
        # print "Status: " + retdef release(self, path, fh):
        # print "sending release req"#
        # return os.close(fh)
        # return zfs_pb2.IntRet(message='Returned, %s!' % ret)

    def MakeDir(self, request, context):
        print "Mk dir req received"
        print "Req path: " + request.path
        os.mkdir(request.path, request.mode)
        return zfs_pb2.StdReply(status=1, error_message='')
        # print "Status: " + ret
        # return zfs_pb2.IntRet(message='Returned, %s!' % ret)

    def RemoveFile(self, request, context):
        print "unlink req received"
        os.unlink(request.path)
        return zfs_pb2.StdReply(status=1, error_message='')

    def Fetch(self, request, context):
        print "read file req recvd for file: ", request.path
        try:
            fd = open(request.path, 'r+')
            with fd as reader:
                for chunk in iter(partial(reader.read, BLOCK_SIZE), ''):
                    #print "read block", chunk
                    yield zfs_pb2.FileDataBlock(data_block=chunk)
        except (OSError, ValueError, IOError):
            print "error", traceback.print_exc()

    def read(self, path, length, offset, fh):
        return os.lsos.read(fh, length)

    def Store(self, request_iterator, context):
        print "store req received"
        is_read = False
        fd = 0
        for chunk in request_iterator:
            if not is_read:
                print "Not read, opening file: ", chunk.data_block
                is_read = True
                fd = open(chunk.data_block, 'w')
            else:
                #print "writing chunk: ", chunk.data_block
                fd.write(chunk.data_block)
        fd.close()
        return zfs_pb2.StdReply(status=1, error_message='')

    def FetchDir(self, request, context):
        print "readdir req recvd for:", request.path
        dirents = ['.', '..']
        if os.path.isdir(request.path):
            dirents.extend(os.listdir(request.path))
        for r in dirents:
            yield zfs_pb2.DirListBlock(dir_list_block=r)

    def TestAuth(self, request, context):
        print "test auth req received for file: ", request.path
        mtime = os.lstat(request.path).st_mtime
        caller_mtime = request.st_mtime
        print "mtime on server: ", mtime, "; mtime received from client: ", caller_mtime, "; server-client= ", mtime-caller_mtime
        if mtime > caller_mtime:
            print "file modified on server"
            return zfs_pb2.TestAuthReply(flag=1)
        else:
            return zfs_pb2.TestAuthReply(flag=0)

    def SetFileStat(self, request, context):
        print "set file stat"

    def write(self, path, buf, offset, fh):
        os.lseek(fh, offset, os.SEEK_SET)
        return os.write(fh, buf)

    def flush(self, path, fh):
        print "flushing at server file:", path
        return os.fsync(fh)

    def release(self, path, fh):
        print "releasing at server file: ", path
        return os.close(fh)

    def fsync(self, path, fdatasync, fh):
        print "fsyncing at server for file: ", path
        return self.flush(path, fh)

    def access(self, path, mode):
        full_path = self._full_path(path)
        os.access(full_path, mode)

    def chmod(self, path, mode):
        full_path = self._full_path(path)
        return os.chmod(full_path, mode)

    def chown(self, path, uid, gid):
        full_path = self._full_path(path)
        return os.chown(full_path, uid, gid)

    def readlink(self, path):
        pathname = os.readlink(self._full_path(path))
        if pathname.startswith("/"):
            # Path name is absolute, sanitize it.
            return os.path.relpath(pathname, self.root)
        else:
            return pathname

    def mknod(self, path, mode, dev):
        return os.mknod(self._full_path(path), mode, dev)

    def statfs(self, path):
        full_path = self._full_path(path)
        stv = os.statvfs(full_path)
        return dict((key, getattr(stv, key)) for key in ('f_bavail', 'f_bfree',
                                                         'f_blocks', 'f_bsize', 'f_favail', 'f_ffree', 'f_files',
                                                         'f_flag',
                                                         'f_frsize', 'f_namemax'))

    def symlink(self, name, target):
        return os.symlink(name, self._full_path(target))

    def rename(self, old, new):
        return os.rename(self._full_path(old), self._full_path(new))

    def link(self, target, name):
        return os.link(self._full_path(target), self._full_path(name))

    def utimens(self, path, times=None):
        return os.utime(self._full_path(path), times)

    def truncate(self, path, length, fh=None):
        full_path = self._full_path(path)
        with open(full_path, 'r+') as f:
            f.truncate(length)


def serve():
    print "running server"
    server = zfs_pb2.beta_create_ZfsRpc_server(ZfsServer())
    server.add_insecure_port('[::]:50051')
    server.start()
    try:
        while True:
            time.sleep(_ONE_DAY_IN_SECONDS)
    except KeyboardInterrupt:
        server.stop()


if __name__ == '__main__':
    serve()
