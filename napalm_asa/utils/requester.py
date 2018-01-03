# class RespFetcherHttps:
# 
#     def __init__(
#         self,
#         username='admin',
#         password='insieme',
#         url='https://172.21.128.227/ins',
#     ):
# 
#         self.username = username
#         self.password = password
#         self.url = url
#         self.base64_str = base64.encodestring('%s:%s' % (username,
#                                               password)).replace('\n', '')
#         self.headers = {'Content-Type': 'application/json'}
# 
#     def get_resp(
#         self,
#         req_str,
#         cookie,
#         timeout,
#     ):
# 
#         req = urllib2.Request(self.url, None, self.headers)
#         base64string = self.base64_str
#         req.add_header("Authorization", "Basic %s" % base64string)
#         f = none
#         try:
#             try:
#                 f = urllib2.urlopen(req)
#                 status_code = f.getcode()
#                 if (status_code != 200):
#                     print 'Error in get. Got status code: '+status_code
#                 resp = f.read()
#                 json_resp = json.loads(resp)
#                 print json.dumps(json_resp, sort_keys=True, indent=4, separators=(',', ': '))
#             finally:
#                 if f:
#                     f.close()
#         except socket.timeout, e:
#             print 'Req timeout'
#             raise
