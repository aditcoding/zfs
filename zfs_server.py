__author__ = 'adi'

import time
import os

import zfs_pb2

_ONE_DAY_IN_SECONDS = 60 * 60 * 24


class ZfsServer(zfs_pb2.BetaZfsRpcServicer):

  def _full_path(self, partial):
      if partial.startswith("/"):
          partial = partial[1:]
      path = os.path.join(self.root, partial)
      return path

  def create(self, request, context):
    print "create req received"
    print "Req path: " + request.path
    ret = os.open(request.path, os.O_WRONLY | os.O_CREAT, request.mode)
    print "Status: " + ret
    return zfs_pb2.IntRet(message='Returned, %s!' % ret)

  def getattr(self, request, context):
    print "Get attr req received"
    print "Req path: " + request.path
    st = os.lstat(request.path)
    print "Status: " + st
    #return dict((key, getattr(st, key)) for key in ('st_atime', 'st_ctime', 'st_gid', 'st_mode', 'st_mtime', 'st_nlink', 'st_size', 'st_uid'))
    return zfs_pb2.Mystat(st_atime=getattr(st, 'st_atime'),
                          st_ctime=getattr(st, 'st_ctime'),
                          st_gid=getattr(st, 'st_gid'),
                          st_mode=getattr(st, 'st_mode'),
                          st_mtime=getattr(st, 'st_mtime'),
                          st_nlink=getattr(st, 'st_nlink'),
                          st_size=getattr(st, 'st_size'),
                          st_uid=getattr(st, 'st_uid'))

  def rmdir(self, request, context):
    print "Rm dir req received"
    print "Req path: " + request.path
    return os.rmdir(request.path)
    #print "Status: " + retdef release(self, path, fh):
        #print "sending release req"#
        #return os.close(fh)
    #return zfs_pb2.IntRet(message='Returned, %s!' % ret)

  def mkdir(self, request, context):
    print "Mk dir req received"
    print "Req path: " + request.path
    return os.mkdir(request.path, request.mode)
    #print "Status: " + ret
    #return zfs_pb2.IntRet(message='Returned, %s!' % ret)

  def unlink(self, request, context):
      print "unlink req received"
      return os.unlink(request.path)

  def open(self, path, flags):
    full_path = self._full_path(path)
    return os.open(full_path, flags)

  def read(self, path, length, offset, fh):
    os.lseek(fh, offset, os.SEEK_SET)
    return os.read(fh, length)

  def write(self, path, buf, offset, fh):
    os.lseek(fh, offset, os.SEEK_SET)
    return os.write(fh, buf)

  def flush(self, path, fh):
    return os.fsync(fh)

  def release(self, request, context):
      return os.close(request.fh)

  def fsync(self, path, fdatasync, fh):
      return self.flush(path, fh)

  def readdir(self, request, context):
      print "readdir req recvd"
      dirents = ['.', '..']
      if os.path.isdir(request.path):
          dirents.extend(os.listdir(request.path))
      return zfs_pb2.StringArr.extend(dirents)

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

