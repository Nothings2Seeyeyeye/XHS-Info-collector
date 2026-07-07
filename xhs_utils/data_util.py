import json
import os
import re
import shutil
import subprocess
import time
from io import BytesIO
from typing import Optional
import openpyxl
import requests
from loguru import logger
from retry import retry
from PIL import Image
from xhs_utils.browser_profile import apply_browser_headers
from xhs_utils.rate_limit_util import sleep_before_media


def norm_str(str):
    new_str = re.sub(r"|[\\/:*?\"<>| ]+", "", str).replace('\n', '').replace('\r', '')
    return new_str

def norm_text(text):
    ILLEGAL_CHARACTERS_RE = re.compile(r'[\000-\010]|[\013-\014]|[\016-\037]')
    text = ILLEGAL_CHARACTERS_RE.sub(r'', text)
    return text


def timestamp_to_str(timestamp):
    time_local = time.localtime(timestamp / 1000)
    dt = time.strftime("%Y-%m-%d %H:%M:%S", time_local)
    return dt

def handle_user_info(data, user_id):
    home_url = f'https://www.xiaohongshu.com/user/profile/{user_id}'
    nickname = data['basic_info']['nickname']
    avatar = data['basic_info']['imageb']
    red_id = data['basic_info']['red_id']
    gender = data['basic_info']['gender']
    if gender == 0:
        gender = '男'
    elif gender == 1:
        gender = '女'
    else:
        gender = '未知'
    ip_location = data['basic_info']['ip_location']
    desc = data['basic_info']['desc']
    follows = data['interactions'][0]['count']
    fans = data['interactions'][1]['count']
    interaction = data['interactions'][2]['count']
    tags_temp = data['tags']
    tags = []
    for tag in tags_temp:
        try:
            tags.append(tag['name'])
        except:
            pass
    return {
        'user_id': user_id,
        'home_url': home_url,
        'nickname': nickname,
        'avatar': avatar,
        'red_id': red_id,
        'gender': gender,
        'ip_location': ip_location,
        'desc': desc,
        'follows': follows,
        'fans': fans,
        'interaction': interaction,
        'tags': tags,
    }

def handle_note_info(data):
    note_id = data['id']
    note_url = data['url']
    note_type = data['note_card']['type']
    if note_type == 'normal':
        note_type = '图集'
    else:
        note_type = '视频'
    user_id = data['note_card']['user']['user_id']
    home_url = f'https://www.xiaohongshu.com/user/profile/{user_id}'
    nickname = data['note_card']['user']['nickname']
    avatar = data['note_card']['user']['avatar']
    title = data['note_card']['title']
    if title.strip() == '':
        title = f'无标题'
    desc = data['note_card']['desc']
    liked_count = data['note_card']['interact_info']['liked_count']
    collected_count = data['note_card']['interact_info']['collected_count']
    comment_count = data['note_card']['interact_info']['comment_count']
    share_count = data['note_card']['interact_info']['share_count']
    image_list_temp = data['note_card']['image_list']
    image_list = []
    for image in image_list_temp:
        try:
            image_list.append(image['info_list'][1]['url'])
            # success, msg, img_url = XHS_Apis.get_note_no_water_img(image['info_list'][1]['url'])
            # image_list.append(img_url)
        except:
            pass
    if note_type == '视频':
        video_cover = image_list[0] if image_list else None
        video_addr = None
        video_info = data.get('note_card', {}).get('video', {})
        streams = video_info.get('media', {}).get('stream', {}).get('h264', [])
        if streams:
            video_addr = streams[0].get('master_url') or streams[0].get('url')
        if not video_addr and 'consumer' in video_info:
            origin_key = video_info['consumer'].get('origin_video_key')
            if origin_key:
                video_addr = f"https://sns-video-bd.xhscdn.com/{origin_key}"
    else:
        video_cover = None
        video_addr = None
    tags_temp = data['note_card']['tag_list']
    tags = []
    for tag in tags_temp:
        try:
            tags.append(tag['name'])
        except:
            pass
    upload_time = timestamp_to_str(data['note_card']['time'])
    if 'ip_location' in data['note_card']:
        ip_location = data['note_card']['ip_location']
    else:
        ip_location = '未知'
    return {
        'note_id': note_id,
        'note_url': note_url,
        'note_type': note_type,
        'user_id': user_id,
        'home_url': home_url,
        'nickname': nickname,
        'avatar': avatar,
        'title': title,
        'desc': desc,
        'liked_count': liked_count,
        'collected_count': collected_count,
        'comment_count': comment_count,
        'share_count': share_count,
        'video_cover': video_cover,
        'video_addr': video_addr,
        'image_list': image_list,
        'tags': tags,
        'upload_time': upload_time,
        'ip_location': ip_location,
    }

def handle_comment_info(data):
    note_id = data['note_id']
    note_url = data['note_url']
    comment_id = data['id']
    user_id = data['user_info']['user_id']
    home_url = f'https://www.xiaohongshu.com/user/profile/{user_id}'
    nickname = data['user_info']['nickname']
    avatar = data['user_info']['image']
    content = data['content']
    show_tags = data['show_tags']
    like_count = data['like_count']
    upload_time = timestamp_to_str(data['create_time'])
    try:
        ip_location = data['ip_location']
    except:
        ip_location = '未知'
    pictures = []
    try:
        pictures_temp = data['pictures']
        for picture in pictures_temp:
            try:
                pictures.append(picture['info_list'][1]['url'])
                # success, msg, img_url = XHS_Apis.get_note_no_water_img(picture['info_list'][1]['url'])
                # pictures.append(img_url)
            except:
                pass
    except:
        pass
    return {
        'note_id': note_id,
        'note_url': note_url,
        'comment_id': comment_id,
        'user_id': user_id,
        'home_url': home_url,
        'nickname': nickname,
        'avatar': avatar,
        'content': content,
        'show_tags': show_tags,
        'like_count': like_count,
        'upload_time': upload_time,
        'ip_location': ip_location,
        'pictures': pictures,
    }
def save_to_xlsx(datas, file_path, type='note'):
    wb = openpyxl.Workbook()
    ws = wb.active
    if type == 'note':
        headers = ['笔记id', '笔记url', '笔记类型', '用户id', '用户主页url', '昵称', '头像url', '标题', '描述', '点赞数量', '收藏数量', '评论数量', '分享数量', '视频封面url', '视频地址url', '图片地址url列表', '标签', '上传时间', 'ip归属地']
    elif type == 'user':
        headers = ['用户id', '用户主页url', '用户名', '头像url', '小红书号', '性别', 'ip地址', '介绍', '关注数量', '粉丝数量', '作品被赞和收藏数量', '标签']
    else:
        headers = ['笔记id', '笔记url', '评论id', '用户id', '用户主页url', '昵称', '头像url', '评论内容', '评论标签', '点赞数量', '上传时间', 'ip归属地', '图片地址url列表']
    ws.append(headers)
    for data in datas:
        data = {k: norm_text(str(v)) for k, v in data.items()}
        ws.append(list(data.values()))
    wb.save(file_path)
    logger.info(f'数据保存至 {file_path}')

def get_download_headers():
    return apply_browser_headers({
        "referer": "https://www.xiaohongshu.com/",
    })

def infer_image_ext(url, content_type, content):
    content_type = (content_type or "").lower()
    if "image/jpeg" in content_type or "image/jpg" in content_type:
        return ".jpg"
    if "image/png" in content_type:
        return ".png"
    if "image/webp" in content_type:
        return ".webp"
    if "image/avif" in content_type:
        return ".avif"
    if content.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if content.startswith(b"RIFF") and b"WEBP" in content[:16]:
        return ".webp"
    url = (url or "").lower()
    if ".png" in url:
        return ".png"
    if ".webp" in url:
        return ".webp"
    if ".avif" in url:
        return ".avif"
    return ".jpg"

def download_media(path, name, url, type):
    if not url:
        raise ValueError(f'{name} 下载地址为空')
    sleep_before_media(type)
    if type == 'image':
        res = requests.get(url, headers=get_download_headers(), timeout=20)
        res.raise_for_status()
        content = res.content
        content_type = res.headers.get("content-type", "")
        if "image" not in content_type.lower():
            if content[:16].lstrip().lower().startswith(b"<!doctype html") or content[:16].lstrip().lower().startswith(b"<html"):
                raise ValueError(f'{name} 下载失败，返回了HTML页面')
        ext = infer_image_ext(url, content_type, content)
        file_path = path + '/' + name + ext
        with open(file_path, mode="wb") as f:
            f.write(content)
        return file_path
    elif type == 'video':
        res = requests.get(url, headers=get_download_headers(), stream=True, timeout=30)
        res.raise_for_status()
        chunk_size = 1024 * 1024
        file_path = path + '/' + name + '.mp4'
        with open(file_path, mode="wb") as f:
            for data in res.iter_content(chunk_size=chunk_size):
                f.write(data)
        return file_path


def download_image_as_png(path, name, url):
    if not url:
        raise ValueError(f'{name} 下载地址为空')
    res = requests.get(url, headers=get_download_headers(), timeout=20)
    res.raise_for_status()
    content = res.content
    content_type = res.headers.get("content-type", "")
    if "image" not in content_type.lower():
        if content[:16].lstrip().lower().startswith(b"<!doctype html") or content[:16].lstrip().lower().startswith(b"<html"):
            raise ValueError(f'{name} 下载失败，返回了HTML页面')
    image = Image.open(BytesIO(content)).convert("RGBA")
    file_path = path + '/' + name + '.png'
    image.save(file_path, format='PNG')
    return file_path


def extract_audio_from_video(video_path: str) -> Optional[str]:
    """
    使用 ffmpeg 从已下载的 mp4 中抽取音轨：
    1) 优先输出 audio.mp3（libmp3lame）
    2) 若 MP3 编码不可用则输出 audio.wav（PCM 16-bit）
    未安装 ffmpeg 时返回 None，不阻断主流程。
    返回成功时写入的文件名（不含路径），如 audio.mp3 / audio.wav。
    """
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        logger.warning('未找到 ffmpeg，无法从视频提取音频。请安装 ffmpeg 并加入 PATH（https://ffmpeg.org）')
        return None
    if not os.path.isfile(video_path) or os.path.getsize(video_path) == 0:
        logger.warning(f'视频文件不存在或为空，跳过音频提取: {video_path}')
        return None
    out_dir = os.path.dirname(video_path)
    mp3_path = os.path.join(out_dir, 'audio.mp3')
    wav_path = os.path.join(out_dir, 'audio.wav')
    for p in (mp3_path, wav_path):
        if os.path.isfile(p):
            try:
                os.remove(p)
            except OSError:
                pass
    cmd_mp3 = [
        ffmpeg, '-hide_banner', '-loglevel', 'error', '-y',
        '-i', video_path, '-vn', '-c:a', 'libmp3lame', '-q:a', '2', mp3_path,
    ]
    try:
        r = subprocess.run(cmd_mp3, capture_output=True, timeout=600)
    except subprocess.TimeoutExpired:
        logger.warning(f'ffmpeg 导出 MP3 超时: {video_path}')
        return None
    if r.returncode == 0 and os.path.isfile(mp3_path) and os.path.getsize(mp3_path) > 0:
        logger.info(f'音频已提取为 MP3: {mp3_path}')
        return 'audio.mp3'
    if os.path.isfile(mp3_path):
        try:
            os.remove(mp3_path)
        except OSError:
            pass
    cmd_wav = [
        ffmpeg, '-hide_banner', '-loglevel', 'error', '-y',
        '-i', video_path, '-vn', '-c:a', 'pcm_s16le', wav_path,
    ]
    try:
        r2 = subprocess.run(cmd_wav, capture_output=True, timeout=600)
    except subprocess.TimeoutExpired:
        logger.warning(f'ffmpeg 导出 WAV 超时: {video_path}')
        return None
    if r2.returncode == 0 and os.path.isfile(wav_path) and os.path.getsize(wav_path) > 0:
        logger.info(f'音频已提取为 WAV（MP3 编码不可用时回退）: {wav_path}')
        return 'audio.wav'
    err = (r.stderr or b'') + (r2.stderr or b'')
    logger.warning(f'ffmpeg 提取音频失败: {err.decode(errors="replace")[:800]}')
    return None


def save_user_detail(user, path):
    with open(f'{path}/detail.txt', mode="w", encoding="utf-8") as f:
        # 逐行输出到txt里
        f.write(f"用户id: {user['user_id']}\n")
        f.write(f"用户主页url: {user['home_url']}\n")
        f.write(f"用户名: {user['nickname']}\n")
        f.write(f"头像url: {user['avatar']}\n")
        f.write(f"小红书号: {user['red_id']}\n")
        f.write(f"性别: {user['gender']}\n")
        f.write(f"ip地址: {user['ip_location']}\n")
        f.write(f"介绍: {user['desc']}\n")
        f.write(f"关注数量: {user['follows']}\n")
        f.write(f"粉丝数量: {user['fans']}\n")
        f.write(f"作品被赞和收藏数量: {user['interaction']}\n")
        f.write(f"标签: {user['tags']}\n")

def save_note_detail(note, path):
    with open(f'{path}/detail.txt', mode="w", encoding="utf-8") as f:
        # 逐行输出到txt里
        f.write(f"笔记id: {note['note_id']}\n")
        f.write(f"笔记url: {note['note_url']}\n")
        f.write(f"笔记类型: {note['note_type']}\n")
        f.write(f"用户id: {note['user_id']}\n")
        f.write(f"用户主页url: {note['home_url']}\n")
        f.write(f"昵称: {note['nickname']}\n")
        f.write(f"头像url: {note['avatar']}\n")
        f.write(f"标题: {note['title']}\n")
        f.write(f"描述: {note['desc']}\n")
        f.write(f"点赞数量: {note['liked_count']}\n")
        f.write(f"收藏数量: {note['collected_count']}\n")
        f.write(f"评论数量: {note['comment_count']}\n")
        f.write(f"分享数量: {note['share_count']}\n")
        f.write(f"视频封面url: {note['video_cover']}\n")
        f.write(f"视频地址url: {note['video_addr']}\n")
        f.write(f"图片地址url列表: {note['image_list']}\n")
        f.write(f"标签: {note['tags']}\n")
        f.write(f"上传时间: {note['upload_time']}\n")
        f.write(f"ip归属地: {note['ip_location']}\n")


def clean_ocr_text(raw_text: str) -> str:
    if not raw_text:
        return ""
    text = raw_text
    # 去掉 markdown 代码块（包括```...```）
    text = re.sub(r"```[\s\S]*?```", "", text)
    # 去掉 html 标签
    text = re.sub(r"<[^>]+>", "", text)
    # 去掉 markdown 图片语法 ![...](...)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    # 去掉可能的本地路径引用
    text = re.sub(r"/Users/[^\s]+", "", text)
    # 去掉单独的 @ 符号行
    text = re.sub(r"^\s*@\s*$", "", text, flags=re.MULTILINE)
    # 规整空行
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines).strip()


def save_ai_context(note_info, save_path):
    """
    生成给 AI 使用的上下文文件：
    - 标题（title）
    - 描述（desc）
    - 是否已有 OCR 结果（has_ocr）
    - OCR 图片文本（image_ocr_text）
    文件保存到同一笔记目录下的 ai_context 子目录。
    """
    ocr_dir = os.path.join(save_path, 'ocr')
    has_ocr = False
    image_ocr_text_parts = []
    if os.path.isdir(ocr_dir):
        md_files = sorted([name for name in os.listdir(ocr_dir) if name.endswith('.md')])
        has_ocr = len(md_files) > 0
        for md_name in md_files:
            md_path = os.path.join(ocr_dir, md_name)
            try:
                with open(md_path, mode='r', encoding='utf-8') as f:
                    text = f.read().strip()
                text = clean_ocr_text(text)
                if text:
                    image_ocr_text_parts.append(f'[{md_name}]\n{text}')
            except Exception as e:
                logger.warning(f'读取 OCR 文件失败: {md_path}, err: {e}')
    image_ocr_text = '\n\n'.join(image_ocr_text_parts).strip()

    ai_dir = os.path.join(save_path, 'ai_context')
    check_and_create_path(ai_dir)
    tags = note_info.get('tags', [])
    if not isinstance(tags, list):
        tags = [str(tags)]

    ai_obj = {
        "title": note_info.get('title', ''),
        "desc": note_info.get('desc', ''),
        "tags": tags,
        "has_ocr": has_ocr,
        "image_ocr_text": image_ocr_text if image_ocr_text else "",
    }

    ai_file = os.path.join(ai_dir, 'note_ai_context.txt')
    with open(ai_file, mode='w', encoding='utf-8') as f:
        f.write(f"title: {ai_obj['title']}\n")
        f.write(f"desc: {ai_obj['desc']}\n")
        f.write(f"tags: {ai_obj['tags']}\n")
        f.write(f"has_ocr: {str(ai_obj['has_ocr']).lower()}\n")
        f.write("image_ocr_text:\n")
        if ai_obj['image_ocr_text']:
            f.write(ai_obj['image_ocr_text'] + "\n")
        else:
            f.write("(empty)\n")

    ai_json_file = os.path.join(ai_dir, 'note_ai_context.json')
    with open(ai_json_file, mode='w', encoding='utf-8') as f:
        json.dump(ai_obj, f, ensure_ascii=False, indent=2)


def load_note_info(save_path):
    info_path = os.path.join(save_path, 'info.json')
    if not os.path.isfile(info_path):
        return None
    with open(info_path, mode='r', encoding='utf-8') as f:
        return json.load(f)


def collect_note_image_files(save_path):
    image_exts = {'.jpg', '.jpeg', '.png', '.webp', '.avif'}
    image_files = []
    if not os.path.isdir(save_path):
        return image_files
    for name in sorted(os.listdir(save_path)):
        file_path = os.path.join(save_path, name)
        if not os.path.isfile(file_path):
            continue
        _, ext = os.path.splitext(name)
        if ext.lower() in image_exts:
            image_files.append(file_path)
    return image_files


def ocr_note_images(save_path, ocr_client, overwrite=False):
    if not ocr_client:
        raise ValueError('OCR 客户端不能为空')
    save_path = os.path.abspath(save_path)
    if not os.path.isdir(save_path):
        raise FileNotFoundError(f'笔记目录不存在: {save_path}')
    image_files = collect_note_image_files(save_path)
    if not image_files:
        logger.warning(f'笔记目录中未找到可 OCR 的图片: {save_path}')
        return 0, 0

    ocr_save_path = os.path.join(save_path, 'ocr')
    check_and_create_path(ocr_save_path)
    success_count = 0
    skip_count = 0
    for image_file in image_files:
        image_name = os.path.splitext(os.path.basename(image_file))[0]
        ocr_file = os.path.join(ocr_save_path, f'{image_name}.md')
        if os.path.isfile(ocr_file) and not overwrite:
            logger.info(f'OCR 已存在，跳过: {ocr_file}')
            skip_count += 1
            continue
        success, msg, ocr_text = ocr_client.parse_image_file(image_file)
        if success and ocr_text:
            with open(ocr_file, mode='w', encoding='utf-8') as f:
                f.write(ocr_text)
            logger.info(f'OCR 完成: {image_file} -> {ocr_file}')
            success_count += 1
        else:
            logger.warning(f'OCR 失败 {image_file}: {msg}')

    note_info = load_note_info(save_path)
    if note_info:
        save_ai_context(note_info, save_path)
    else:
        logger.warning(f'未找到 info.json，已跳过 ai_context 刷新: {save_path}')
    return success_count, skip_count



@retry(tries=3, delay=1)
def download_note(note_info, path, save_choice, png_path=None):
    note_id = note_info['note_id']
    user_id = note_info['user_id']
    title = note_info['title']
    title = norm_str(title)[:40]
    nickname = note_info['nickname']
    nickname = norm_str(nickname)[:20]
    if title.strip() == '':
        title = f'无标题'
    save_path = f'{path}/{nickname}_{user_id}/{title}_{note_id}'
    check_and_create_path(save_path)
    png_save_path = None
    # PNG 文件固定放在“同一条笔记目录”下的独立子文件夹中，避免散落到其他位置。
    if png_path is not None:
        png_save_path = f'{save_path}/png'
        check_and_create_path(png_save_path)
    with open(f'{save_path}/info.json', mode='w', encoding='utf-8') as f:
        f.write(json.dumps(note_info) + '\n')
    note_type = note_info['note_type']
    save_note_detail(note_info, save_path)
    if note_type == '图集' and save_choice in ['media', 'media-image', 'all']:
        for img_index, img_url in enumerate(note_info['image_list']):
            download_media(save_path, f'image_{img_index}', img_url, 'image')
            if png_save_path:
                download_image_as_png(png_save_path, f'image_{img_index}', img_url)
    elif note_type == '视频' and save_choice in ['media', 'media-video', 'all']:
        download_media(save_path, 'cover', note_info['video_cover'], 'image')
        if png_save_path:
            download_image_as_png(png_save_path, 'cover', note_info['video_cover'])
        video_save_path = os.path.join(save_path, 'video_files')
        check_and_create_path(video_save_path)
        download_media(video_save_path, 'video', note_info['video_addr'], 'video')
        video_file = os.path.join(video_save_path, 'video.mp4')
        with open(f'{save_path}/detail.txt', mode='a', encoding='utf-8') as f:
            f.write('本地视频文件: video_files/video.mp4\n')
        audio_name = extract_audio_from_video(video_file)
        if audio_name:
            with open(f'{save_path}/detail.txt', mode='a', encoding='utf-8') as f:
                f.write(f'本地音频文件: video_files/{audio_name}\n')
    save_ai_context(note_info, save_path)
    return save_path


def check_and_create_path(path):
    if not os.path.exists(path):
        os.makedirs(path)
