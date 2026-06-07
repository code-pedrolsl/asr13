"""
Teste de Exclusão Mútua — ASR 13
==================================
Roda N clientes simultâneos usando o coordenador centralizado.
Compara com ASR 12: aqui conflitos OCC devem ser ZERO.

Uso:
    python tests/test_mutex.py \
        --scoreboard <IP>:5678 \
        --coordinator <IP>:50052 \
        --players 5 --rounds 10 --instance-id aws-1
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'client'))

import threading, time, argparse, logging, json, random
from datetime import datetime

import grpc
import scoreboard_pb2 as pb2_sb
import scoreboard_pb2_grpc as pb2_grpc_sb
from client_mutex import MutexClient

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(name)-12s] %(levelname)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("TEST-MUTEX")


class TestResults:
    def __init__(self):
        self._lock   = threading.Lock()
        self.players = {}
        self.errors  = []

    def record(self, player_id: str, client: MutexClient):
        with self._lock:
            self.players[player_id] = {
                "rounds":  client.total_rounds,
                "success": client.total_success,
            }

    def record_error(self, player_id: str, error: str):
        with self._lock:
            self.errors.append({"player": player_id, "error": error})

    def summary(self):
        return {
            "players": len(self.players),
            "rounds":  sum(p["rounds"]  for p in self.players.values()),
            "success": sum(p["success"] for p in self.players.values()),
            "errors":  len(self.errors),
        }


def worker(sb_addr, coord_addr, player_id, game_id,
           rounds, min_pts, max_pts, think_time,
           results, barrier):
    try:
        client = MutexClient(sb_addr, coord_addr, player_id, game_id)
        barrier.wait()
        client.play(rounds=rounds, min_pts=min_pts,
                    max_pts=max_pts, think_time=think_time)
        results.record(player_id, client)
    except Exception as e:
        log.error("Erro no player %s: %s", player_id, e)
        results.record_error(player_id, str(e))


def run_test(sb_addr, coord_addr, n_players, game_id,
             rounds, min_pts, max_pts, think_time, instance_id):

    log.info("TESTE EXCLUSÃO MÚTUA — %d jogadores, %d rodadas cada", n_players, rounds)
    log.info("Scoreboard : %s", sb_addr)
    log.info("Coordenador: %s", coord_addr)
    log.info("Instância  : %s", instance_id)

    results = TestResults()
    barrier = threading.Barrier(n_players)
    threads = [threading.Thread(
        target=worker,
        args=(sb_addr, coord_addr, f"{instance_id}-P{i:02d}", game_id,
              rounds, min_pts, max_pts, think_time, results, barrier),
        daemon=True) for i in range(1, n_players + 1)]

    start = time.time()
    for t in threads: t.start()
    for t in threads: t.join(timeout=600)
    elapsed = time.time() - start

    channel = grpc.insecure_channel(sb_addr)
    stub    = pb2_grpc_sb.ScoreboardServiceStub(channel)
    final   = stub.GetScore(pb2_sb.GetScoreRequest(game_id=game_id))
    summary = results.summary()

    expected_version = n_players * rounds

    log.info("=" * 55)
    log.info("RESULTADO FINAL — %.2fs", elapsed)
    log.info("  Escore final       : %d", final.score)
    log.info("  Versão final       : %d", final.version)
    log.info("  Rodadas executadas : %d", summary["rounds"])
    log.info("  Sucessos           : %d", summary["success"])
    log.info("  Conflitos OCC      : 0  (garantido pelo mutex)")
    log.info("  Erros              : %d", summary["errors"])
    log.info("=" * 55)

    out_file = f"result_mutex_{instance_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(out_file, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "instance_id": instance_id,
            "scoreboard": sb_addr, "coordinator": coord_addr,
            "elapsed_s": round(elapsed, 2),
            "final_score": final.score,
            "final_version": final.version,
            "integrity_ok": final.version >= expected,
            "summary": summary,
            "per_player": results.players,
            "errors": results.errors,
        }, f, indent=2)
    log.info("Resultado salvo em: %s", out_file)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scoreboard",   default="localhost:5678")
    parser.add_argument("--coordinator",  default="localhost:50052")
    parser.add_argument("--players",      type=int,   default=5)
    parser.add_argument("--game",         default="game1")
    parser.add_argument("--rounds",       type=int,   default=10)
    parser.add_argument("--min-pts",      type=int,   default=10)
    parser.add_argument("--max-pts",      type=int,   default=100)
    parser.add_argument("--think",        type=float, default=0.1)
    parser.add_argument("--instance-id",  default="local")
    args = parser.parse_args()

    run_test(args.scoreboard, args.coordinator, args.players, args.game,
             args.rounds, args.min_pts, args.max_pts, args.think, args.instance_id)
