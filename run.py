import subprocess
import sys
import os

def main():
    print("=" * 60)
    print("🍕 Запуск Pizza GPT с MCP сервером...")
    print("=" * 60)
    
    # Запускаем MCP сервер как отдельный процесс
    print("📡 Запуск MCP сервера (mcp_server.py)...")
    mcp_process = subprocess.Popen(
        [sys.executable, "mcp_server.py"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    
    print("🖥️  Запуск интерфейса (main.py)...")
    # Запускаем основное приложение
    main_process = subprocess.Popen(
        [sys.executable, "main.py"],
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    
    try:
        main_process.wait()
    except KeyboardInterrupt:
        print("\n🛑 Завершение...")
    finally:
        mcp_process.terminate()
        try:
            mcp_process.wait(timeout=2)
        except:
            mcp_process.kill()

if __name__ == "__main__":
    main()