#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2006, 2008 Nedko Arnaudov <nedko@arnaudov.name>
# You can use this software for any purpose you want
# Use it at your own risk
# You are allowed to modify the code
# You are disallowed to remove author credits from header
#
# FUSE filesystem for wiki
#
# Uses XML-RPC for accessing wiki
# Documentation here: http://www.jspwiki.org/Wiki.jsp?page=WikiRPCInterface2
#
# Requires:
#  FUSE python bindings (0.2 or later), available from FUSE project http://fuse.sourceforge.net/
#  xmlrpclib, available since python 2.2
#
# Tested with:
#  Editors: xemacs, vi
#  FUSE lkm: one comming with 2.6.15, 2.6.23.1
#  FUSE usermode: 2.5.2, 2.7.3
#  Python: 2.4.2, 2.5.1
#  Wiki engines: MoinMoinWiki 1.5.0, 1.6.3
#
# Expected to work with:
#  Every editor (60%)
#  Python >= 2.2 (99%)
#  FUSE > 2.5.2 (70%)
#  MoinMoinWiki > 1.5.0 (90%)
#
# If you improve this code, send a modified version to author please
#
########################################################################################

example_config = """
# example configuration file for wikifuse
#
# wikis is array of dictionaries
# each dictionary represents one wiki server
#
# keys:
#  * name - REQUIRED name of the wiki server, will be used as directory name
#  * xmlrpc_url - REQUIRED xml-rpc url of the wiki server
#  * auth - OPTIONAL authentication method.
#
# authentication methods and related keys:
#  * 'moin_cookie' required keys:
#   * user_id - moin internal moin user id. Look at your data/users directory in wiki instance to get exact value
#  * 'moin_auth' required keys:
#   * username - your moin username
#   * password - your moin password

wikis = [
    {
    'name': 'example.com',
    'xmlrpc_url': 'http://wiki.example.com/moin.cgi?action=xmlrpc2',
    'auth': 'moin_cookie',
    'user_id': '1111111111.22.3333'
    },
    {
    'name': 'wiki_anon',
    'xmlrpc_url': 'http://wiki.example.com/moin.cgi/?action=xmlrpc2',
    },
    {
    'name': 'example.org',
    'xmlrpc_url': 'http://wiki.example.org/wiki/moin.cgi/?action=xmlrpc2',
    'auth': 'moin_auth',
    'username': 'foo',
    'password': 'bar'
    }
    ]
"""

# Verbosity
#
# 0 - silent
# 1 - errors
# 2 - basic
# 3 - debug
verbosity = 2

import xmlrpclib
import fuse
import os, sys
import xmlrpclib
import types
from errno import *
from stat import *
import locale
#import thread

fuse.fuse_python_api = (0, 2)

out_charset = locale.getpreferredencoding()
if out_charset == None:
    out_charset = "utf-8"

#print("Using charset %s for stdout" % out_charset)

def printex(str):
    if type(str) != types.StringType and type(str) != types.UnicodeType:
        raise "trying to print non-string type %s" % type(str)

    try:
        print str.encode(out_charset, "replace")
    except UnicodeDecodeError, e:
        print "---------------- cannot print: %s" % e
    except:
        print "---------------- cannot print: %s" % sys.exc_info()[0]

def log(str):
    printex(str)

def log_error(str):
    if verbosity >= 1:
        log(str)

def log_basic(str):
    if verbosity >= 2:
        log(str)

def log_debug(str):
    if verbosity >= 3:
        log(str)

class WikiServerProxy:
    def __init__(self, url, transport=None):
        self.url = url

        if verbosity >= 3:
            xmlrpc_verbose = 1
        else:
            xmlrpc_verbose = 0

        self.xmlrpc = xmlrpclib.ServerProxy(url, verbose=xmlrpc_verbose, transport=transport)

    def cleanup(self):
        pass

# xml rpc proxy without authentication
class WikiServerProxySimple(WikiServerProxy):
    def __init__(self, url):
        WikiServerProxy.__init__(self, url)

    def __getattr__(self, name):
        #log("__getattr__ " + name)
        return self.function(self.xmlrpc, name)

    class function:
        def __init__(self, xmlrpc, name):
            self.xmlrpc = xmlrpc
            self.name = name

        def __call__(self, *args):
            #log("proxy call %s%s" % (self.name, repr(args)))
            func = self.xmlrpc.__getattr__(self.name)
            return func(*args)

# moin_cookie authentication (MoinMoinWiki)
#
# For this to work change server check for self.request.user.trusted to check for self.request.user.valid
# The check is made in wikirpc.py, near line 362
#
# user_id is simply internal moin user id
# Look at your data/users directory in wiki instance to get exact value

class WikiServerProxyMoinCookie(WikiServerProxy):
    def __init__(self, url, user_id):
        transport = self.transport(user_id)
        WikiServerProxy.__init__(self, url, transport=transport)

    def __getattr__(self, name):
        #log("__getattr__ " + name)
        return self.function(self.xmlrpc, name)

    class function:
        def __init__(self, xmlrpc, name):
            self.xmlrpc = xmlrpc
            self.name = name

        def __call__(self, *args):
            #log("proxy call %s%s" % (self.name, repr(args)))
            func = self.xmlrpc.__getattr__(self.name)
            return func(*args)

    class transport(xmlrpclib.Transport):
        def __init__(self, user_id):
            xmlrpclib.Transport.__init__(self)
            self.user_id = user_id

        def get_host_info(self, host):
            host, extra_headers, x509 = xmlrpclib.Transport.get_host_info(self, host)

            if extra_headers == None:
                extra_headers = []
            extra_headers.append(("Cookie", "MOIN_ID=" + self.user_id))

            return host, extra_headers, x509

# MoinMoinWiki xmlrpc authentication
#
class WikiServerProxyMoinAuth(WikiServerProxy):
    def __init__(self, url, username, password):
        WikiServerProxy.__init__(self, url)

        self.username = username
        self.password = password
        self.token = None
        self.check_token()

    def __getattr__(self, name):
        #log("__getattr__ " + name)
        self.check_token()
        return self.function(self.xmlrpc, name, self.token)

    def cleanup(self):
        if self.token:
            log_basic("Deleting moin auth token for '%s'" % self.url)
            assert self.xmlrpc.deleteAuthToken(self.token) == 'SUCCESS'

    def check_token(self):
        # Verify that the token is valid by using it
        # and checking that the result is 'SUCCESS'.
        # The token should be valid for 15 minutes.

        if self.token:
            try:
                self.xmlrpc.applyAuthToken(self.token)
            except:
                self.token = None
        
        if not self.token:
            # refresh token
            log_basic("Getting new moin auth token for '%s'" % self.url)
            self.token = self.xmlrpc.getAuthToken(self.username, self.password)

            if self.xmlrpc.applyAuthToken(self.token) != 'SUCCESS':
                log_error("Invalid username/password when authenticating to '%s' (%s/%s)" % (url, username, password))

    class function:
        def __init__(self, xmlrpc, name, token):
            self.xmlrpc = xmlrpc
            self.name = name
            self.token = token

        def __call__(self, *args):
            #log("proxy call %s%s" % (self.name, repr(args)))

            # build a multicall object that
            mcall = xmlrpclib.MultiCall(self.xmlrpc)

            # first applies the token and
            mcall.applyAuthToken(self.token)

            # then call the real function
            mcall.__getattr__(self.name)(*args)

            # now execute the multicall
            results = mcall()

            #log_basic(results[0])

            try:
                ret = results[1]
            except xmlrpclib.Fault, f:
                ret = {'faultCode': f.faultCode, 'faultString': f.faultString}

            return ret

class WikiServer:
    def __init__(self, name, proxy):
        self.name = name

        self.wikiproxy = proxy

        info  = "name: %s\n" % name
        info += "url: %s\n" % proxy.url
        info += "proxy: %s\n" % proxy.__class__.__name__

        # test rpc
        #log("%10s: %s (%s)" % (name, self.wikiproxy.WhoAmI(), proxy.url))

        try:
            whoami = self.wikiproxy.WhoAmI()
        except xmlrpclib.Fault, e:
            whoami = e
        except:
            whoami = sys.exc_info()[0]

        info += "whoami: %s\n" % whoami

        try:
            version = self.wikiproxy.getRPCVersionSupported()
        except xmlrpclib.Fault, e:
            version = e
        except:
            version = sys.exc_info()[0]

        info += "wiki xml rpc version: %s\n" % version

        self.pages = {}
        self.virt_pages = {}

        self.virt_pages['_'] = info
        #self.virt_pages['cyr'] = u"ÐºÐ¸Ñ€Ð¸Ð»Ð¸Ñ Ð°"

    def cleanup(self):
        self.wikiproxy.cleanup()

    def readdir(self, offset):
        yield fuse.Direntry('.')
        yield fuse.Direntry('..')

        for page in self.virt_pages.iterkeys():
            yield fuse.Direntry(page)

        all = self.wikiproxy.getAllPages()
        for page in all:
            if page.find('/') == -1:
                yield fuse.Direntry(page)

    def getattr(self, path):
        log_basic("getattr \"%s\"" % path)

        st = fuse.Stat()
        st.st_nlink = 1

        st.st_mode = S_IFREG | 0666

        if self.virt_pages.has_key(path):
            st.st_size = len(self.virt_pages[path])
            return st

        if self.pages.has_key(path):
            st.st_size = self.pages[path]['size']
            return st

        info = self.wikiproxy.getPageInfo(path)
        if info.has_key('faultCode'):
            log_error("getPageInfo(%s) failed" % path + repr(info))
            return -ENOENT

        page = self.wikiproxy.getPage(path).encode('utf-8')
        st.st_size = len(page)

        return st

    def open(self, path, flags):
        log_basic("open \"%s\" flags %u" % (path, flags))

        if not self.pages.has_key(path):
            self.pages[path] = {}

        if self.virt_pages.has_key(path):
            data = self.virt_pages[path]
            self.pages[path]['data'] = data
            self.pages[path]['size'] = len(data)
            self.pages[path]['modified'] = False
            return 0

        data = self.wikiproxy.getPage(path).encode('utf-8')
        if self.pages[path].has_key('size'):
            size = self.pages[path]['size']
            if size != len(data):
                log_basic("Truncating to %u bytes" % size)
                if size == 0:
                    data = ""
                else:
                    data = data[size:]
                self.pages[path]['modified'] = True
                self.pages[path]['data'] = data
                log_debug("\"%s\"" % data)
        else:
            size = len(data)
            log_basic("Updating size of '%s' to %u bytes" % (path, size))
            self.pages[path]['modified'] = False
        self.pages[path]['data'] = data
        self.pages[path]['size'] = size
    	return 0

    def read(self, path, length, offset):
        log_basic("read \"%s\" %u bytes, from offset %u" % (path, length, offset))

        if offset + length > self.pages[path]['size']:
            length = self.pages[path]['size'] - offset

        if length == 0:
            data = ""
        else:
            data = self.pages[path]['data'][offset:offset+length]
        log_debug("\"%s\"" % data)
        log_basic("data length: %u bytes" % len(data))
        log_basic("type: %s" % type(data))
   	return data

    def write(self, path, buf, offset):
        log_basic("write \"%s\" %u bytes, to offset %u" % (path, len(buf), offset))
        size = len(buf)
        pre = self.pages[path]['data'][:offset]
        post =  self.pages[path]['data'][offset+size:]
        data = pre + buf + post
        self.pages[path]['size'] = len(data)
        log_debug("\"%s\"" % data)
        self.pages[path]['data'] = data
        self.pages[path]['modified'] = True
   	return size

    def truncate(self, path, size):
        log_basic("truncate \"%s\" %u bytes" % (path, size))

        if not self.pages.has_key(path):
            self.pages[path] = {}
        else:
            if size > self.pages[path]['size']:
                return -EINVAL
        self.pages[path]['modified'] = True
        self.pages[path]['size'] = size
        if self.pages[path].has_key('data'):
            self.pages[path]['data'] = self.pages[path]['data'][size:]
   	return 0

    def release(self, path, flags):
        log_basic("release \"%s\"" % path)

        ret = self.fsync_do(path)
        if ret == 0:
            del self.pages[path]['data']

   	return ret

    def fsync(self, path, isfsyncfile):
        log_basic("fsync: path=%s, isfsyncfile=%s" % (path, isfsyncfile))
        return self.fsync_do(path)

    def fsync_do(self, path):
        if self.pages.has_key(path):
            if self.pages[path]['modified']:
                log_basic("PUT PAGE")
                log_debug("\"%s\"" % self.pages[path]['data'])
                ret = self.wikiproxy.putPage(path, self.pages[path]['data'])
                if type(ret) == types.BooleanType and ret == True:
                    self.pages[path]['modified'] = False
                    return 0
                else:
                    log_error("putPage(%s) failed" % path + repr(ret))
                    return -EIO

class WikiFS(fuse.Fuse):

    def __init__(self, servers, *args, **kw):
        fuse.Fuse.__init__(self, *args, **kw)

        #log_basic("mountpoint: %s" % repr(self.mountpoint))
        #log_basic("unnamed mount options: %s" % self.optlist)
        #log_basic("named mount options: %s" % self.optdict)
    
        # do stuff to set up your filesystem here, if you want
        #thread.start_new_thread(self.mythread, ())

        self.servers = servers

    def mythread(self):
    
        """
        The beauty of the FUSE python implementation is that with the python interp
        running in foreground, you can have threads
        """
        log_basic("mythread: started")
        #while 1:
        #    time.sleep(120)
        #    log_basic("mythread: ticking")
    
    flags = 1
    
    def getattr(self, path):
        log_basic("getattr \"%s\"" % path)

        st = fuse.Stat()
        st.st_nlink = 2

        if path.count("/") == 1:
            st.st_mode = S_IFDIR | 0700
            return st

        server, subname = self.get_subname(path)
        if subname:
            return server.getattr(subname);
        
        return -EINVAL

    def readlink(self, path):
        log_basic("readlink")
   	return -ENOSYS

    def readdir_top(self, path, offset):
        yield fuse.Direntry('.')
        yield fuse.Direntry('..')

        for server in self.servers:
            yield fuse.Direntry(server.name)

    def readdir(self, path, offset):
        log_basic("readdir(path='%s', offset=%u)" % (path, offset))

        if path == '/':
            return self.readdir_top(path, offset)

        server_name = path[1:]
        for server in self.servers:
            if server.name == server_name:
                return server.readdir(offset)

        return -EINVAL

    def unlink(self, path):
        log_basic("unlink")
   	return -ENOSYS
    def rmdir(self, path):
        log_basic("rmdir")
   	return -ENOSYS
    def symlink(self, path, path1):
        log_basic("symlink")
   	return -ENOSYS
    def rename(self, path, path1):
        log_basic("rename")
   	return -ENOSYS
    def link(self, path, path1):
        log_basic("link")
   	return -ENOSYS
    def chmod(self, path, mode):
        log_basic("chmod")
   	return -ENOSYS
    def chown(self, path, user, group):
        log_basic("chown")
   	return -ENOSYS

    def truncate(self, path, size):
        log_basic("truncate \"%s\" %u bytes" % (path, size))

        server, subname = self.get_subname(path)
        if subname:
            return server.truncate(subname, size);
        
        return -EINVAL

    def mknod(self, path, mode, dev):
        log_basic("mknod")
   	return -ENOSYS
    def mkdir(self, path, mode):
        log_basic("mkdir")
   	return -ENOSYS
    def utime(self, path, times):
        log_basic("utime")
   	return -ENOSYS

    def get_subname(self, path):
        for server in self.servers:
            prefix = "/" + server.name + "/"
            if path.startswith(prefix):
                return (server, path[len(prefix):])

        return (None, None)

    def open(self, path, flags):
        log_basic("open \"%s\" flags %u" % (path, flags))

        server, subname = self.get_subname(path)
        if subname:
            return server.open(subname, flags);
        
        return -EINVAL

    #def opendir(self, path):
    #    log_basic("opendir \"%s\"" % path)
    #    return WikiDir()

    def read(self, path, length, offset):
        log_basic("read \"%s\" %u bytes, from offset %u" % (path, length, offset))

        server, subname = self.get_subname(path)
        if subname:
            return server.read(subname, length, offset);
        
        return -EINVAL

    def write(self, path, buf, offset):
        log_basic("write \"%s\" %u bytes, to offset %u" % (path, len(buf), offset))

        server, subname = self.get_subname(path)
        if subname:
            return server.write(subname, buf, offset);
        
        return -EINVAL
    
    def release(self, path, flags):
        log_basic("release \"%s\"" % path)

        server, subname = self.get_subname(path)
        if subname:
            return server.release(subname, flags);
        
        return -EINVAL

    def fsync(self, path, isfsyncfile):
        log_basic("fsync: path=%s, isfsyncfile=%s" % (path, isfsyncfile))

        server, subname = self.get_subname(path)
        if subname:
            return server.fsync(subname, isfsyncfile);
        
        return -EINVAL

    def main(self):
        fuse.Fuse.main(self)

# Read config file
old_path = sys.path
sys.path = [os.environ['HOME'] + "/.config/wikifuse"]
try:
    import config
except:
    log_error("No configuration file found in '%s'" % sys.path[0])
    #log_error(repr(sys.exc_info()[0]))
    log_error("Example configuration file (save it as %s/config.py):" % sys.path[0])
    log_error(example_config)
    sys.exit(1)

sys.path = old_path

def main():
    servers = []
    for wiki in config.wikis:
        proxy = None
        if wiki.has_key('auth'):
            if wiki['auth'] == 'moin_cookie':
                proxy = WikiServerProxyMoinCookie(wiki['xmlrpc_url'], wiki['user_id'])
            elif wiki['auth'] == 'moin_auth':
                proxy = WikiServerProxyMoinAuth(wiki['xmlrpc_url'], wiki['username'], wiki['password'])
            else:
                log_error("Unknown authentication method '%s'" % wiki['auth'])
                continue
        else:
            proxy = WikiServerProxySimple(wiki['xmlrpc_url'])
        servers.append(WikiServer(wiki['name'], proxy))

    fs = WikiFS(servers)
    #fs.multithreaded = 1
    fs.parse(errex=1)
    fs.main()

    for server in servers:
        server.cleanup()

if __name__ == '__main__':
    main()
