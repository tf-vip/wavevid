---
summary: wavevid biến podcast hoặc file audio thành video sóng âm cho người muốn đăng lên mạng xã hội.
audience: ["Người có podcast hoặc file audio muốn làm video cho YouTube, Facebook, Instagram, TikTok"]
needs: ["Claude Code", "Python 3.10 trở lên", "FFmpeg", "Khoá API Soniox (khi muốn tạo phụ đề tự động)"]
lessons: []
version: 0.1.1
---

## Nó làm gì

wavevid là CLI, tức tool bạn chạy bằng cách gõ lệnh trong terminal, cửa sổ để nhập lệnh vào máy. Nó nhận một file podcast hoặc audio rồi xuất thành video có sóng âm chạy theo giọng nói, ảnh đại diện, phụ đề và phần mở đầu hoặc kết thúc. Video làm xong có thể dùng cho YouTube, Facebook, Instagram hay TikTok.

Bạn chọn một trong năm kiểu sóng âm: `waveform`, `radial`, `bars`, `spectrum` hoặc `particles`. Phần nền có thể là một màu, màu chuyển, ảnh của bạn hoặc để tool chọn ngẫu nhiên. Khi dùng `--wave-color auto`, wavevid lấy màu sóng và màu phụ đề từ nền.

## Nó giúp bạn thế nào

Bạn không cần tự ghép từng lớp hình và âm thanh chỉ để biến một tập podcast thành video. wavevid có phần tiêu đề trên intro hoặc outro, nhận âm thanh riêng cho hai đoạn này, rồi chuyển cảnh bằng hiệu ứng mờ dần. Bạn cũng có thể thêm nhạc nền lặp lại, chỉnh âm lượng, và để tool tạo màn hình kết thúc có avatar cùng tiêu đề.

Nếu cần phụ đề, wavevid gửi audio cho Soniox để đổi giọng nói thành chữ. Cùng một audio sẽ không bị gửi lại vì bản chép lời được giữ trong `.transcribe_cache/`; bạn sửa chỗ chép sai bằng `--replace "old=new"` hoặc `--replace-file`.

Tool có sẵn tỷ lệ khung hình cho từng nơi đăng: `--aspect 16:9` cho YouTube 1920×1080, `1:1` cho Instagram feed, `9:16` cho Instagram/TikTok và `4:5` cho Facebook feed. Nếu chỉ cần bản âm thanh đã trộn intro, outro và nhạc nền, dùng `--audio-only` để không tạo video.

## Bạn cần gì

Bạn cần Python 3.10 trở lên và FFmpeg, phần mềm xử lý audio, video. Trên macOS, bạn cài FFmpeg bằng `brew install ffmpeg`. Sau đó cài wavevid bằng `pip install wavevid`; đây là bản 0.1.1 đã đăng trên PyPI, nơi đăng các gói Python.

Phụ đề tự động mới cần khoá API Soniox, tức mã để wavevid dùng dịch vụ Soniox. Bạn lấy khoá tại `https://console.soniox.com`, đặt `SONIOX_API_KEY=...` trong file `.env`, rồi chạy lệnh có `--subtitle`. Repo dùng giấy phép MIT.

Trong `examples/` có 10 script mẫu, tức các lệnh đã soạn sẵn, từ video cơ bản, avatar, phụ đề, Instagram Reels, YouTube ngang đến podcast đầy đủ, audio-only, chất lượng cao, màu riêng và thay chữ. Mọi tuỳ chọn nằm trong `README.md`; chi tiết phần trộn intro/outro và chọn màu tự động nằm trong `IMPROVEMENTS.md`.

## Bắt đầu

Trên tài nguyên “Source CLI tool để tạo video có sóng âm từ audio (Podcast)” trong Vibery, bấm “tải .zip”, giải nén rồi mở thư mục bằng Claude Code. Nói đúng: “Đọc WHAT.md và CLAUDE.md, rồi hướng dẫn mình chạy dự án này trên máy.” Claude Code sẽ kiểm tra Python và FFmpeg, cài wavevid, rồi làm video đầu tiên từ file audio của bạn.

Nếu dùng Git, repo public nên không cần đăng nhập GitHub. Chạy `git clone https://github.com/tf-vip/wavevid.git`, rồi `cd wavevid` và `pip install -e .`. Lệnh ngắn nhất để thử là `wavevid audio.m4a -o video.mp4`; muốn video vuông có avatar, dùng `wavevid audio.m4a -o video.mp4 --aspect 1:1 --avatar photo.jpg`.

## Có gì mới

Bản đầu tiên.
