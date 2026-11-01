import http.server,os,sys
os.chdir(r'D:\workspace\fun\Weiqi\Weiqi_AI\josekiapp')
class H(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control','no-store, max-age=0');super().end_headers()
    def log_message(self,*a):pass
http.server.ThreadingHTTPServer(('127.0.0.1',8765),H).serve_forever()
