import sys
import json
import asyncio
import argparse
import httpx
import websockets


def login_for_token(http_url: str, email: str, password: str) -> str:
    """Authenticates with the RecallOS API and returns a JWT access token."""
    print(f"[*] Authenticating with {http_url} as {email}...")
    with httpx.Client(base_url=http_url, timeout=90.0, follow_redirects=True) as client:
        # Try login
        res = client.post("/api/auth/login", json={"email": email, "password": password})
        if res.status_code != 200:
            # Try registering if account doesn't exist yet
            client.post(
                "/api/auth/register",
                json={"email": email, "password": password, "display_name": "WS Watcher"},
            )
            res = client.post("/api/auth/login", json={"email": email, "password": password})
            if res.status_code != 200:
                print(f"[!] Authentication failed: {res.status_code} - {res.text}")
                sys.exit(1)

        token = res.json().get("access_token")
        print("[+] Authentication successful.")
        return token


async def watch_job(ws_base: str, job_id: int, token: str) -> None:
    """Connects to /ws/generate/{job_id} and prints events in real-time."""
    ws_uri = f"{ws_base}/ws/generate/{job_id}?token={token}"
    # Mask token for terminal output security
    masked_uri = f"{ws_base}/ws/generate/{job_id}?token=***"
    print(f"[*] Connecting to WebSocket: {masked_uri} ...")

    try:
        async with websockets.connect(ws_uri) as ws:
            print(f"[+] Connected to live generation stream for Job #{job_id}!\n")

            async for raw_message in ws:
                try:
                    event = json.loads(raw_message)
                except json.JSONDecodeError:
                    print(f"  [RAW] {raw_message}")
                    continue

                event_type = event.get("type")
                data = event.get("data", {})

                if event_type == "snapshot":
                    print(f"[SNAPSHOT] Status: {data.get('status', '').upper()} | "
                          f"Chunks: {data.get('done_chunks')}/{data.get('total_chunks')} | "
                          f"Cards Created: {data.get('cards_created')}")

                elif event_type == "chunk_done":
                    new_cards = data.get("new_cards", [])
                    print(f"\n[CHUNK DONE] Chunk {data.get('chunk_index') + 1}/{data.get('total_chunks')} finished. "
                          f"Total Cards Created: {data.get('cards_created')}")
                    for card in new_cards:
                        print(f"  * [{card.get('topic')}] Q: {card.get('question')}")
                        print(f"    A: {card.get('answer')}")

                elif event_type == "chunk_failed":
                    print(f"\n[CHUNK FAILED] Chunk {data.get('chunk_index')} error: {data.get('reason')}")

                elif event_type == "ready":
                    print(f"\n[+] [READY] Generation finished! Deck ID: {data.get('deck_id')}, "
                          f"Total Cards Created: {data.get('cards_created')}")
                    print("[*] Stream complete. Exiting.")
                    break

                elif event_type == "failed":
                    print(f"\n[!] [FAILED] Generation job failed: {data.get('message')}")
                    print("[*] Stream complete. Exiting.")
                    break

                elif event_type == "ping":
                    print("  [PING] Server keepalive received")

                else:
                    print(f"  [{event_type.upper()}] {data}")

    except websockets.exceptions.ConnectionClosed as exc:
        if exc.rcvd and exc.rcvd.code == 4401:
            print(f"\n[!] Connection closed by server: 4401 Unauthorized (Invalid or expired token).")
        elif exc.rcvd and exc.rcvd.code == 4404:
            print(f"\n[!] Connection closed by server: 4404 Not Found (Job does not exist or belongs to another user).")
        else:
            print(f"\n[*] Connection closed: {exc}")
    except Exception as exc:
        print(f"\n[!] WebSocket error: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="RecallOS Live Generation WebSocket Watcher")
    parser.add_argument("job_id", type=int, help="ID of the card generation job to monitor")
    parser.add_argument("--token", default=None, help="JWT access token")
    parser.add_argument("--email", default="manual_test@example.com", help="Email for auto-login")
    parser.add_argument("--password", default="password123", help="Password for auto-login")
    parser.add_argument("--host", default="localhost:8000", help="Host and port or domain (e.g. localhost:8000 or recallos-backend.onrender.com)")
    parser.add_argument("--ssl", action="store_true", help="Force wss:// and https:// (auto-enabled if host is not localhost)")
    args = parser.parse_args()

    clean_host = args.host.replace("https://", "").replace("http://", "").replace("wss://", "").replace("ws://", "").rstrip("/")
    is_secure = args.ssl or ("localhost" not in clean_host and "127.0.0.1" not in clean_host)
    scheme_http = "https" if is_secure else "http"
    scheme_ws = "wss" if is_secure else "ws"

    http_url = f"{scheme_http}://{clean_host}"
    ws_base = f"{scheme_ws}://{clean_host}"

    token = args.token
    if not token:
        token = login_for_token(http_url, args.email, args.password)

    try:
        asyncio.run(watch_job(ws_base, args.job_id, token))
    except KeyboardInterrupt:
        print("\n[*] Exiting on user interrupt.")


if __name__ == "__main__":
    main()
