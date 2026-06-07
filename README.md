# Exclusão Mútua Distribuída — ASR 13

**Disciplina:** INF0344A-BCC — Sistemas Distribuídos  
**Middleware:** gRPC  
**Algoritmo:** Exclusão mútua com coordenador centralizado

---

## Estrutura de arquivos

```
├── proto/
│   ├── scoreboard.proto       # Contrato do scoreboard (ASR 12)
│   └── coordinator.proto      # Contrato do coordenador (ASR 13)
├── server/
│   └── server.py              # Servidor de scoreboard
├── coordinator/
│   └── coordinator.py         # Coordenador de exclusão mútua
├── client/
│   ├── client.py              # Cliente simples (ASR 12, sem mutex)
│   └── client_mutex.py        # Cliente com exclusão mútua (ASR 13)
├── tests/
│   ├── test_concurrent.py     # Teste automatizado sem mutex (ASR 12)
│   └── test_mutex.py          # Teste automatizado com mutex (ASR 13)
├── setup.sh                   # Gera os arquivos gRPC (rodar uma vez)
└── requirements.txt
```

---

## Setup (rodar uma vez em cada máquina)

```bash
bash setup.sh
```

---

## Máquinas necessárias

```
instância-servidor  → roda server.py
instância-peer1     → roda coordinator.py + cliente (coordenador + jogador)
instância-peer2     → roda cliente (jogador)
instância-peer3     → roda cliente (jogador)
```

Liberar no Security Group:
- porta **5678** na instância-servidor
- porta **50052** na instância-peer1

O IP só é passado na hora de rodar, nos argumentos `--scoreboard` e `--coordinator`.

---

## Forma 1 — Teste automatizado

**instância-servidor:**
```bash
python3 server/server.py --host 0.0.0.0 --port 5678
```

**instância-peer1** (dois terminais):
```bash
# Terminal 1
python3 coordinator/coordinator.py --host 0.0.0.0 --port 50052

# Terminal 2
python3 tests/test_mutex.py \
    --scoreboard IP_SERVIDOR:5678 \
    --coordinator localhost:50052 \
    --players 3 --rounds 10 --instance-id peer1
```

**instância-peer2:**
```bash
python3 tests/test_mutex.py \
    --scoreboard IP_SERVIDOR:5678 \
    --coordinator IP_PEER1:50052 \
    --players 3 --rounds 10 --instance-id peer2
```

**instância-peer3:**
```bash
python3 tests/test_mutex.py \
    --scoreboard IP_SERVIDOR:5678 \
    --coordinator IP_PEER1:50052 \
    --players 3 --rounds 10 --instance-id peer3
```

> Rode peer1, peer2 e peer3 ao mesmo tempo.  
> O resultado é salvo em `result_mutex_<instance-id>_<timestamp>.json`.  
> `--instance-id` é só um nome para identificar a máquina no resultado — pode colocar qualquer coisa.

---

## Forma 2 — Teste manual (um cliente por máquina)

**instância-servidor:**
```bash
python3 server/server.py --host 0.0.0.0 --port 5678
```

**instância-peer1** (dois terminais):
```bash
# Terminal 1
python3 coordinator/coordinator.py --host 0.0.0.0 --port 50052

# Terminal 2
python3 client/client_mutex.py \
    --scoreboard IP_SERVIDOR:5678 \
    --coordinator localhost:50052 \
    --player P1 --rounds 10
```

**instância-peer2:**
```bash
python3 client/client_mutex.py \
    --scoreboard IP_SERVIDOR:5678 \
    --coordinator IP_PEER1:50052 \
    --player P2 --rounds 10
```

**instância-peer3:**
```bash
python3 client/client_mutex.py \
    --scoreboard IP_SERVIDOR:5678 \
    --coordinator IP_PEER1:50052 \
    --player P3 --rounds 10
```

> Rode peer1, peer2 e peer3 ao mesmo tempo.

---

## O que observar nos logs

**Log do coordenador (peer1):**
```
GRANT imediato → P1
FILA  posição=1  cliente=P2  (dono atual: P1)
FILA  posição=2  cliente=P3  (dono atual: P1)
RELEASE ← P1
GRANT próximo → P2   fila restante=1
RELEASE ← P2
GRANT próximo → P3   fila restante=0
```

**Log dos clientes:**
```
>> Pedindo lock ao coordenador...
>> Lock concedido (token=abc12345)
OK  +73 pts  score=850  version=12
<< Lock liberado
```

**Log do servidor — sem nenhum CONFLITO** (diferente da ASR 12).
