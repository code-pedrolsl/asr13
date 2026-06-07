import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import grpc, threading, logging, argparse, time, uuid
from concurrent import futures

import coordinator_pb2 as pb2
import coordinator_pb2_grpc as pb2_grpc

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [COORD] %(levelname)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)


class CoordinatorServicer(pb2_grpc.CoordinatorServiceServicer):
    def __init__(self):
        self._lock         = threading.Lock()
        self._owner        = None
        self._owner_token  = None
        self._queue        = []
        self._total_grants = 0

    def Acquire(self, request, context):
        client_id = request.client_id
        token     = str(uuid.uuid4())[:8]
        event     = threading.Event()

        with self._lock:
            if self._owner is None:
                self._owner       = client_id
                self._owner_token = token
                self._total_grants += 1
                log.info("GRANT imediato -> %-12s (token=%s)", client_id, token)
                return pb2.AcquireResponse(granted=True, token=token, queue_pos=0)
            else:
                pos = len(self._queue) + 1
                self._queue.append((client_id, event, token))
                log.info("FILA  posição=%-2d  cliente=%-12s  (dono atual: %s)",
                         pos, client_id, self._owner)

        event.wait(timeout=120)

        if not event.is_set():
            log.warning("TIMEOUT cliente=%s", client_id)
            with self._lock:
                self._queue = [(c, e, t) for c, e, t in self._queue
                               if c != client_id]
            return pb2.AcquireResponse(granted=False, token="", queue_pos=-1)

        log.info("GRANT após fila -> %-12s (token=%s)", client_id, token)
        return pb2.AcquireResponse(granted=True, token=token, queue_pos=0)

    def Release(self, request, context):
        client_id = request.client_id
        token     = request.token

        with self._lock:
            if self._owner != client_id or self._owner_token != token:
                msg = f"Release inválido: {client_id} não é o dono atual"
                log.warning(msg)
                return pb2.ReleaseResponse(success=False, message=msg)

            log.info("RELEASE <- %-12s", client_id)
            self._owner       = None
            self._owner_token = None

            if self._queue:
                next_client, next_event, next_token = self._queue.pop(0)
                self._owner       = next_client
                self._owner_token = next_token
                self._total_grants += 1
                log.info("GRANT próximo -> %-12s (token=%s)  fila restante=%d",
                         next_client, next_token, len(self._queue))
                next_event.set()

        return pb2.ReleaseResponse(success=True, message="OK")

    def Status(self, request, context):
        with self._lock:
            return pb2.StatusResponse(
                owner        = self._owner or "",
                queue_size   = len(self._queue),
                queue        = [c for c, _, _ in self._queue],
                total_grants = self._total_grants,
            )


def serve(host: str, port: int):
    servicer = CoordinatorServicer()
    server   = grpc.server(futures.ThreadPoolExecutor(max_workers=32))
    pb2_grpc.add_CoordinatorServiceServicer_to_server(servicer, server)
    addr = f"{host}:{port}"
    server.add_insecure_port(addr)
    server.start()
    log.info("Coordenador iniciado em %s", addr)
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        server.stop(grace=5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=50052)
    args = parser.parse_args()
    serve(args.host, args.port)
