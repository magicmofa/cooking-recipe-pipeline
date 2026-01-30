from videodl import videodl

video_client = videodl.VideoClient()
video_infos = video_client.parsefromurl("https://www.bilibili.com/video/BV1Wt411Z7td/?spm_id_from=333.337.search-card.all.click&vd_source=98f94d38e3ee009f159133339cd9b8d5")
video_client.download(video_infos=video_infos)
