import http.server,os,sys
def _root():   # project folder to serve: env WEIQI_PROJ, else the folder above this script if it has index.html, else the original path
    if os.environ.get('WEIQI_PROJ'):return os.environ['WEIQI_PROJ']
    up=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return up if os.path.exists(os.path.join(up,'index.html')) else r'D:\workspace\fun\Weiqi\Weiqi_AI\josekiapp'
os.chdir(_root())
class H(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control','no-store, max-age=0');super().end_headers()   # never let the browser show an old page or old library.js
    def log_message(self,*a):pass
if __name__=='__main__':
    http.server.ThreadingHTTPServer(('127.0.0.1',int(os.environ.get('WEIQI_PORT','8765'))),H).serve_forever()
