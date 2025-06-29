from typing import Any
import asyncio
import base64
import json
from curl_cffi.requests import AsyncSession
from curl_cffi import requests
import os
import traceback
import argparse
from dotenv import load_dotenv

load_dotenv()

AuthUserTokenV3_r = os.getenv("TOKEN_R")
AuthUserTokenV3_i = os.getenv("TOKEN_I")
api_base = os.getenv("API_BASE", "midjourney.com")
suffix = os.getenv("SUFFIX", "--v 7")


# The Discord channel ID is required by the Midjourney endpoint & must correspond
# to a channel you have access to. Grab it from the `channelId` field when you
# run Midjourney in your browser (F12 › Network).
CHANNEL_ID = os.getenv("CHANNEL_ID") or ""  # fallback to empty string

def init_cookies(r: str, i: str) -> dict:
    cookies = {
        "__Host-Midjourney.AuthUserTokenV3_r": r,
        "__Host-Midjourney.AuthUserTokenV3_i": i,
    }
    return cookies


def submit_job(
    prompt: str,
    cookies: dict,
    channelId: str,
    api_base: str = "www.midjourney.com",
):
    headers = {
        "cookie": "; ".join(f"{k}={v};" for k, v in cookies.items()),
        "Referer": f"https://{api_base}/",
        "Referrer-Policy": "origin-when-cross-origin",
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
        "content-type": "application/json",
        "priority": "u=1, i",
        "sec-ch-ua-mobile": "?0",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "x-csrf-protection": "1",
    }
    body = {
        "f": {"mode": "fast", "private": False},
        "channelId": channelId,
        "metadata": {
            "imagePrompts": 0,
            "imageReferences": 0,
            "characterReferences": 0,
            "depthReferences": 0,
            "lightboxOpen": "",
        },
        "t": "imagine",
        "prompt": prompt,
    }

    response = requests.post(
        f"https://{api_base}/api/app/submit-jobs",
        data=json.dumps(body),
        headers=headers,
        impersonate="safari",
    )

    print(f"➡️ [submit_job] Sent prompt to Midjourney (channel {channelId}). Status code: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        try:
            job_id: str = data["success"][0]["job_id"]
            print(f"✅ [submit_job] Job accepted. job_id={job_id}")
            return job_id
        except Exception as e:
            print(data)
            return None

    else:
        print(response.status_code)
        print(response.text)
        return None


def get_websocket_token(cookies: dict, api_base: str = "midjourney.com") -> str:
    url = f"https://www.{api_base}/api/auth/websocket-token"
    headers = {
        "cookie": "; ".join(f"{k}={v};" for k, v in cookies.items()),
        "Referer": f"https://{api_base}/",
        "Referrer-Policy": "origin-when-cross-origin",
        "dnt": "1",
        "accept": "*/*",
        "priority": "u=1, i",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "x-csrf-protection": "1",
        "Content-Type": "application/json",
        "mode": "cors",
        "credentials": "include",
    }

    response = requests.get(url, headers=headers, impersonate="safari")
    if response.status_code == 200:
        return response.json()
    else:
        print(response.status_code)
        print(response.text)
        return None


def final_image_response(id: str) -> list:
    def p(num: int) -> str:
        return f"https://cdn.midjourney.com/{id}/0_{num}_1024_N.webp"

    return [p(0), p(1), p(2), p(3)]


async def get_job_status(job_id: str, WSToken: str) -> dict:

    def url_encode(url: str):
        return url.encode("utf-8").decode("utf-8")

    url = url_encode(f"wss://ws.{api_base}/ws?token={WSToken}&v=4")

    headers = {
        "host": f"ws.{api_base}",
        "origin": f"https://{api_base}",
        "referer": f"https://{api_base}/",
        "sec-websocket-protocol": "graphql-ws",
        "sec-websocket-version": "13",
        "upgrade": "websocket",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
        "cache-control": "no-cache",
        "pragma": "no-cache",
        "sec-websocket-extensions": "permessage-deflate; client_max_window_bits",
        "sec-websocket-version": "13",
    }

    print(f"we connect to {url}")

    session = AsyncSession()
    ws = await session.ws_connect(url=url, impersonate="chrome", headers=headers)
    try:
        job_success = False
        job = ""
        percentage_complete = 0
        imgs = []

        user_id = None
        await ws.send(json.dumps({"type": "subscribe_to_user"}))
        await ws.send(
            json.dumps(
                {
                    "type": "subscribe_to_job",
                    "job_id": job_id,
                }
            )
        )
        while not ws.closed:
            data, _ = await ws.recv()
            message = json.loads(data.decode("utf-8"))

            if "type" in message and message["type"] == "user_success":
                user_id = message["user_id"]

            if "type" in message and message["type"] == "job_success":
                job_success = True
                job = job_id
                percentage_complete = 5

            if "current_status" in message and message["job_id"] == job_id:
                if message["current_status"] == "running":
                    if "percentage_complete" in message:
                        percentage_complete = message["percentage_complete"]

                    if "imgs" in message and len(message["imgs"]) > 0:
                        imgs = []
                        for item in message["imgs"]:
                            imgs.append(f"data:image/webp;base64,{item['data']}")

                    print(f"🔄 [job_status] {percentage_complete}% complete | imgs received: {len(imgs)}")

                if (
                    "current_status" in message
                    and message["current_status"] == "completed"
                ):
                    percentage_complete = 100
                    print("🎉 [job_status] Generation completed!")
                    break

        return {
            "job_success": job_success,
            "job": job,
            "percentage_complete": percentage_complete,
        }
    finally:
        await ws.close()


async def make_request(prompt: str, aspect_ratio: str):
    cookies = init_cookies(AuthUserTokenV3_r, AuthUserTokenV3_i)
    WSToken = get_websocket_token(cookies)
    if not WSToken:
        return {"error": "Failed to get websocket token"}
    if not CHANNEL_ID:
        return {"error": "CHANNEL_ID environment variable is not set"}

    job_id = submit_job(
        f"{prompt} --ar {aspect_ratio} {suffix}",
        cookies,
        CHANNEL_ID,
    )
    job_status = await get_job_status(job_id, WSToken)
    return job_status


# ------------------
# Public helper – can be imported elsewhere
# ------------------

async def generate_image(prompt: str, aspect_ratio: str = "1:1") -> list[str]:
    """Generate an image using Midjourney and return a list of CDN image URLs."""
    job_status = await make_request(prompt, aspect_ratio)
    if isinstance(job_status, dict) and job_status.get("error"):
        raise RuntimeError(job_status["error"])

    if job_status.get("job_success"):
        return final_image_response(job_status["job"])

    raise RuntimeError("Failed to generate image: No success status received")


# ------------------
# Command-line interface for quick testing
# ------------------

def _cli():
    parser = argparse.ArgumentParser(description="Midjourney image generator test")
    parser.add_argument("prompt", help="Text prompt (English)")
    parser.add_argument(
        "--aspect_ratio",
        "-ar",
        default="1:1",
        help="Aspect ratio, e.g. 1:1, 16:9, 3:4",
    )

    args = parser.parse_args()

    if not AuthUserTokenV3_r or not AuthUserTokenV3_i:
        parser.error("TOKEN_R and TOKEN_I environment variables must be set.")

    if not CHANNEL_ID:
        parser.error("CHANNEL_ID environment variable must be set.")

    print("▶ Generating image with Midjourney…")
    print(f"Prompt: {args.prompt}\nAspect ratio: {args.aspect_ratio}\n")

    try:
        urls = asyncio.run(generate_image(args.prompt, args.aspect_ratio))
        print("✅ Generation complete! URLs:")
        for u in urls:
            print(u)
    except Exception as e:
        traceback.print_exc()
        print(f"❌ {e}")


def main():
    _cli()


if __name__ == "__main__":
    main()