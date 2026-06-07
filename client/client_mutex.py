import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import grpc, random, time, logging, argparse

import scoreboard_pb2 as pb2_sb
import scoreboard_pb2_grpc as pb2_grpc_sb
import coordinator_pb2 as pb2_coord
import coordinator_pb2_grpc as pb2_grpc_coord

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s", datefmt="%H:%M:%S")


class MutexClient:
    def __init__(self, scoreboard_addr: str, coordinator_addr: str,
                 player_id: str, game_id: str):
        self.player_id = player_id
        self.game_id   = game_id
        self.log       = logging.getLogger(player_id)

        sb_channel = grpc.insecure_channel(scoreboard_addr)
        self.sb    = pb2_grpc_sb.ScoreboardServiceStub(sb_channel)

        coord_channel = grpc.insecure_channel(
            coordinator_addr,
            options=[("grpc.keepalive_time_ms", 10000),
                     ("grpc.keepalive_timeout_ms", 5000)])
        self.coord = pb2_grpc_coord.CoordinatorServiceStub(coord_channel)

        self.total_rounds  = 0
        self.total_success = 0

    def _acquire(self) -> str:
        self.log.info(">> Pedindo lock ao coordenador...")
        resp = self.coord.Acquire(
            pb2_coord.AcquireRequest(client_id=self.player_id),
            timeout=130)
        if not resp.granted:
            raise RuntimeError("Coordenador negou o lock (timeout)")
        self.log.info(">> Lock concedido (token=%s)", resp.token)
        return resp.token

    def _release(self, token: str):
        self.coord.Release(
            pb2_coord.ReleaseRequest(client_id=self.player_id, token=token))
        self.log.info("<< Lock liberado")

    def update_score(self, points_gained: int):
        self.total_rounds += 1

        # SEÇÃO CRÍTICA
        token = self._acquire()
        try:
            # 1. Consultar escore
            current   = self.sb.GetScore(pb2_sb.GetScoreRequest(game_id=self.game_id))
            new_score = current.score + points_gained

            # Simula tempo de processamento
            time.sleep(random.uniform(0.05, 0.15))

            # 2. Atualizar escore
            resp = self.sb.UpdateScore(pb2_sb.UpdateScoreRequest(
                game_id      = self.game_id,
                new_score    = new_score,
                base_version = current.version,
                player_id    = self.player_id))

            if resp.success:
                self.total_success += 1
                self.log.info("OK  +%d pts  score=%d  version=%d",
                              points_gained, resp.score, resp.version)
            else:
                # Com mutex correto isso NUNCA deve acontecer
                self.log.error("ERRO INESPERADO (mutex falhou?): %s", resp.message)
        finally:
            #  FIM DA SEÇÃO CRÍTICA
            self._release(token)

    def play(self, rounds: int, min_pts: int = 10, max_pts: int = 100,
             think_time: float = 0.3):
        self.log.info("Iniciando sessão: %d rodadas", rounds)
        start = time.time()
        for r in range(1, rounds + 1):
            pts = random.randint(min_pts, max_pts)
            self.log.info("Rodada %d/%d  pontos=%d", r, rounds, pts)
            self.update_score(pts)
            if r < rounds:
                time.sleep(random.uniform(0, think_time))
        elapsed = time.time() - start
        self.log.info("RESUMO: rodadas=%d sucessos=%d (%.2fs)",
                      self.total_rounds, self.total_success, elapsed)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scoreboard",   default="localhost:5678")
    parser.add_argument("--coordinator",  default="localhost:50052")
    parser.add_argument("--player",       default="Player1")
    parser.add_argument("--game",         default="game1")
    parser.add_argument("--rounds",       type=int,   default=10)
    parser.add_argument("--min-pts",      type=int,   default=10)
    parser.add_argument("--max-pts",      type=int,   default=100)
    parser.add_argument("--think",        type=float, default=0.3)
    args = parser.parse_args()

    client = MutexClient(args.scoreboard, args.coordinator, args.player, args.game)
    client.play(rounds=args.rounds, min_pts=args.min_pts,
                max_pts=args.max_pts, think_time=args.think)
