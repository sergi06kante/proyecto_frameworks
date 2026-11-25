# sin_framework/servidor.py
from http.server import BaseHTTPRequestHandler, HTTPServer

class Manejador(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/hola":
            codigo, cuerpo = 200, "Hola"
        else:
            codigo, cuerpo = 404, "No encontrado"

        datos = cuerpo.encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)
        
if __name__ == "__main__":
    servidor = HTTPServer(("127.0.0.1", 8000), Manejador)
    print("Servidor en http://127.0.0.1:8000 (Ctrl+C para parar)")
    print("TODO OK")
    servidor.serve_forever()