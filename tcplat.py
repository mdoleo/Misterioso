#!/usr/bin/env python3
"""
tcplat - Medidor de latencia TCP a IP:Puerto especifico
Util para pruebas de conectividad de aplicaciones y demostrar
el comportamiento de la red hacia un servicio especifico.

Uso:
    tcplat.py --host 200.1.2.3 --port 443
    tcplat.py --host 200.1.2.3 --port 443 --interval 1 --count 100
    tcplat.py --host 200.1.2.3 --port 443 --duration 300
"""

import argparse
import socket
import sys
import time
import csv
import statistics
from datetime import datetime

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    HAS_MPL = True
except ImportError:
    HAS_MPL = False


def measure_once(host, port, timeout):
    """Mide el tiempo de conexion TCP (handshake) a host:port en milisegundos.
    Retorna (latencia_ms, None) si tiene exito o (None, mensaje_error) si falla."""
    start = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
        elapsed_ms = (time.perf_counter() - start) * 1000
        return elapsed_ms, None
    except socket.timeout:
        return None, "Timeout"
    except ConnectionRefusedError:
        return None, "Conexion rechazada (puerto cerrado)"
    except OSError as e:
        return None, str(e)


def format_ts(ts):
    return datetime.fromtimestamp(ts).strftime("%H:%M:%S")


def print_summary(host, port, results):
    total = len(results)
    ok = [r for r in results if r["latency_ms"] is not None]
    lost = total - len(ok)
    loss_pct = (lost / total * 100) if total else 0

    print("\n" + "=" * 60)
    print(f"  Resumen de prueba: {host}:{port}")
    print("=" * 60)
    print(f"  Paquetes enviados : {total}")
    print(f"  Exitosos          : {len(ok)}")
    print(f"  Fallidos          : {lost}  ({loss_pct:.1f}% de perdida)")

    if ok:
        latencies = [r["latency_ms"] for r in ok]
        print(f"  Latencia minima   : {min(latencies):.2f} ms")
        print(f"  Latencia promedio : {statistics.mean(latencies):.2f} ms")
        print(f"  Latencia maxima   : {max(latencies):.2f} ms")
        if len(latencies) > 1:
            print(f"  Jitter (desv.std) : {statistics.stdev(latencies):.2f} ms")
    else:
        print("  No se obtuvieron respuestas exitosas.")
    print("=" * 60)


def save_csv(filename, host, port, results):
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "host", "port", "latency_ms", "error"])
        for r in results:
            writer.writerow([
                datetime.fromtimestamp(r["ts"]).strftime("%Y-%m-%d %H:%M:%S"),
                host,
                port,
                f"{r['latency_ms']:.2f}" if r["latency_ms"] is not None else "",
                r["error"] or "",
            ])
    print(f"[+] CSV guardado en: {filename}")


def save_graph(filename, host, port, results):
    if not HAS_MPL:
        print("[!] matplotlib no esta instalado, no se genera grafica.")
        print("    Instala con: pip install matplotlib")
        return

    times = [datetime.fromtimestamp(r["ts"]) for r in results]
    latencies = [r["latency_ms"] for r in results]

    fig, ax = plt.subplots(figsize=(12, 5))

    ok_times = [t for t, l in zip(times, latencies) if l is not None]
    ok_lat = [l for l in latencies if l is not None]
    fail_times = [t for t, l in zip(times, latencies) if l is None]

    ax.plot(ok_times, ok_lat, color="#2563eb", linewidth=1.2, marker="o",
            markersize=3, label="Latencia (ms)")

    if fail_times:
        ax.scatter(fail_times, [0] * len(fail_times), color="#dc2626",
                    marker="x", s=60, label="Fallido / sin respuesta", zorder=5)

    if ok_lat:
        avg = statistics.mean(ok_lat)
        ax.axhline(avg, color="#16a34a", linestyle="--", linewidth=1,
                    label=f"Promedio: {avg:.1f} ms")

    ax.set_title(f"Latencia TCP hacia {host}:{port}", fontsize=13, fontweight="bold")
    ax.set_xlabel("Hora")
    ax.set_ylabel("Latencia (ms)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    fig.autofmt_xdate()
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(filename, dpi=150)
    print(f"[+] Grafica guardada en: {filename}")


def main():
    parser = argparse.ArgumentParser(
        description="Mide latencia TCP hacia una IP y puerto especifico (como ping, pero por puerto/aplicacion)."
    )
    parser.add_argument("--host", required=True, help="IP o hostname destino")
    parser.add_argument("--port", required=True, type=int, help="Puerto TCP destino")
    parser.add_argument("--interval", type=float, default=1.0,
                         help="Segundos entre pruebas (default: 1)")
    parser.add_argument("--timeout", type=float, default=3.0,
                         help="Timeout de conexion en segundos (default: 3)")
    parser.add_argument("--count", type=int, default=0,
                         help="Numero de pruebas a realizar (default: infinito hasta Ctrl+C)")
    parser.add_argument("--duration", type=int, default=0,
                         help="Duracion total en segundos (alternativa a --count)")
    parser.add_argument("--output", default=None,
                         help="Prefijo de archivos de salida (default: host_puerto_fecha)")
    args = parser.parse_args()

    if args.output:
        prefix = args.output
    else:
        safe_host = args.host.replace(".", "-").replace(":", "-")
        prefix = f"{safe_host}_{args.port}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    print(f"Midiendo latencia TCP hacia {args.host}:{args.port}")
    print(f"Intervalo: {args.interval}s | Timeout: {args.timeout}s | "
          f"{'Continuo (Ctrl+C para detener)' if not args.count and not args.duration else ''}")
    print("-" * 60)

    results = []
    start_time = time.time()
    seq = 0

    try:
        while True:
            if args.count and seq >= args.count:
                break
            if args.duration and (time.time() - start_time) >= args.duration:
                break

            ts = time.time()
            latency_ms, error = measure_once(args.host, args.port, args.timeout)
            results.append({"ts": ts, "latency_ms": latency_ms, "error": error})

            if latency_ms is not None:
                print(f"[{format_ts(ts)}] seq={seq:<5} {args.host}:{args.port} -> {latency_ms:.2f} ms")
            else:
                print(f"[{format_ts(ts)}] seq={seq:<5} {args.host}:{args.port} -> FALLO ({error})")

            seq += 1
            time.sleep(max(0, args.interval))
    except KeyboardInterrupt:
        print("\n[!] Prueba detenida por el usuario.")

    if not results:
        print("No se registraron resultados.")
        sys.exit(0)

    print_summary(args.host, args.port, results)
    save_csv(f"{prefix}.csv", args.host, args.port, results)
    save_graph(f"{prefix}.png", args.host, args.port, results)


if __name__ == "__main__":
    main()
