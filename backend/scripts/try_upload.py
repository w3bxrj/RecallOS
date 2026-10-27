import os
import sys
import time
import argparse
import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description="RecallOS Manual End-to-End Upload Tester")
    parser.add_argument("file_path", nargs="?", default=None, help="Path to PDF or TXT file to upload")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Base URL of running RecallOS API server")
    parser.add_argument("--email", default="manual_test@example.com", help="Test user email")
    parser.add_argument("--password", default="password123", help="Test user password")
    args = parser.parse_args()

    client = httpx.Client(base_url=args.base_url, timeout=90.0, follow_redirects=True)

    # 1. Prepare file to upload
    target_path = args.file_path
    temp_file_created = False
    if not target_path:
        target_path = "sample_test_notes.txt"
        print(f"[*] No file specified. Creating a sample study notes file at {target_path}...")
        sample_notes = (
            "Operating Systems Concepts:\n\n"
            "Virtual memory is a memory management capability of an operating system that uses hardware and software to allow a computer to compensate for physical memory shortages by temporarily transferring data from random access memory (RAM) to disk storage.\n\n"
            "Process scheduling is an essential part of a multiprogramming operating system. Such operating systems allow more than one process to be loaded into the executable memory at a time and the loaded process shares the CPU using time multiplexing.\n\n"
            "A semaphore is a variable or abstract data type used to control access to a common resource by multiple processes in a concurrent system such as a multitasking operating system.\n\n"
            "Thrashing occurs when a computer's virtual memory resources are overused, leading to a constant state of paging and page faults, inhibiting most application-level execution."
        )
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(sample_notes)
        temp_file_created = True

    if not os.path.exists(target_path):
        print(f"[!] Error: File '{target_path}' not found.")
        sys.exit(1)

    print(f"[*] Target file: {target_path} ({os.path.getsize(target_path)} bytes)")

    # 2. Authenticate / Register user
    print(f"[*] Authenticating as {args.email}...")
    reg_res = client.post(
        "/api/auth/register",
        json={"email": args.email, "password": args.password, "display_name": "E2E Tester"},
    )
    # Registration might return 409 if user exists; login either way
    login_res = client.post(
        "/api/auth/login",
        json={"email": args.email, "password": args.password},
    )
    if login_res.status_code != 200:
        print(f"[!] Login failed: {login_res.status_code} - {login_res.text}")
        sys.exit(1)

    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("[+] Successfully authenticated.")

    # 3. Upload file
    filename = os.path.basename(target_path)
    print(f"[*] Uploading '{filename}' to {args.base_url}/api/uploads...")
    with open(target_path, "rb") as f:
        file_bytes = f.read()

    upload_res = client.post(
        "/api/uploads",
        headers=headers,
        data={"title": f"Manual Test - {filename}"},
        files={"file": (filename, file_bytes, "application/octet-stream")},
    )

    if upload_res.status_code == 409:
        err = upload_res.json().get("error", {})
        print(f"[!] Upload returned 409: {err.get('code')} - {err.get('message')}")
        if "deck_id" in err:
            print(f"[*] Existing Deck ID: {err['deck_id']}")
        sys.exit(0)

    if upload_res.status_code != 200:
        print(f"[!] Upload failed with HTTP {upload_res.status_code}: {upload_res.text}")
        sys.exit(1)

    upload_data = upload_res.json()
    deck_id = upload_data["deck_id"]
    job_id = upload_data["job_id"]
    print(f"[+] Upload accepted! Deck ID: {deck_id}, Job ID: {job_id}")

    # 4. Poll job status
    print(f"[*] Polling generation job {job_id}...")
    start_time = time.time()
    while True:
        poll_res = client.get(f"/api/jobs/{job_id}", headers=headers)
        if poll_res.status_code != 200:
            print(f"[!] Failed to poll job: {poll_res.status_code} - {poll_res.text}")
            break

        job = poll_res.json()
        status = job["status"]
        done_chunks = job["done_chunks"]
        total_chunks = job["total_chunks"]
        cards_created = job["cards_created"]
        is_vision = job.get("is_vision", False)
        notice = job.get("notice")
        elapsed = int(time.time() - start_time)

        mode_label = "[VISION]" if is_vision else "[TEXT]"
        print(f"  [{elapsed}s] {mode_label} Status: {status.upper()} | Chunks: {done_chunks}/{total_chunks} | Cards Created: {cards_created}")
        if notice:
            print(f"       Notice: {notice}")

        if status == "ready":
            print(f"\n[+] Generation completed successfully! {cards_created} cards created.")
            # Fetch generated cards
            cards_res = client.get(f"/api/decks/{deck_id}/cards", headers=headers)
            if cards_res.status_code == 200:
                cards = cards_res.json()
                print(f"\n[*] Sample generated cards (Total: {len(cards)}):")
                for i, c in enumerate(cards[:5], 1):
                    print(f"\n--- Card {i} [{c['topic']}] ---")
                    print(f"Q: {c['question']}")
                    print(f"A: {c['answer']}")
                    print(f"Distractors: {c['distractors']}")
            break

        elif status == "failed":
            print(f"\n[!] Job failed with error: {job.get('error_message')}")
            break

        time.sleep(1.0)

    if temp_file_created and os.path.exists(target_path):
        os.remove(target_path)


if __name__ == "__main__":
    main()
