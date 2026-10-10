#include "webcam.h"

#include <cerrno>
#include <cstring>
#include <fcntl.h>
#include <linux/videodev2.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>

namespace so::live {

static int xioctl(int fd, unsigned long req, void* arg) {
  int r;
  do r = ioctl(fd, req, arg);
  while (r == -1 && errno == EINTR);
  return r;
}

bool Webcam::open(const std::string& device, int width, int height) {
  close();
  fd_ = ::open(device.c_str(), O_RDWR | O_NONBLOCK);
  if (fd_ < 0) {
    error_ = device + ": " + std::strerror(errno);
    return false;
  }
  auto fail = [&](const char* what) {
    error_ = std::string(what) + ": " + std::strerror(errno);
    close();
    return false;
  };
  v4l2_format fmt{};
  fmt.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
  fmt.fmt.pix.width = width;
  fmt.fmt.pix.height = height;
  fmt.fmt.pix.pixelformat = V4L2_PIX_FMT_YUYV;
  fmt.fmt.pix.field = V4L2_FIELD_ANY;
  if (xioctl(fd_, VIDIOC_S_FMT, &fmt) < 0) return fail("VIDIOC_S_FMT");
  if (fmt.fmt.pix.pixelformat != V4L2_PIX_FMT_YUYV) {
    errno = ENOTSUP;
    return fail("camera does not offer YUYV");
  }
  width_ = static_cast<int>(fmt.fmt.pix.width);
  height_ = static_cast<int>(fmt.fmt.pix.height);

  v4l2_requestbuffers req{};
  req.count = 4;
  req.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
  req.memory = V4L2_MEMORY_MMAP;
  if (xioctl(fd_, VIDIOC_REQBUFS, &req) < 0) return fail("VIDIOC_REQBUFS");
  for (unsigned i = 0; i < req.count; i++) {
    v4l2_buffer buf{};
    buf.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    buf.memory = V4L2_MEMORY_MMAP;
    buf.index = i;
    if (xioctl(fd_, VIDIOC_QUERYBUF, &buf) < 0) return fail("VIDIOC_QUERYBUF");
    void* p = mmap(nullptr, buf.length, PROT_READ | PROT_WRITE, MAP_SHARED, fd_, buf.m.offset);
    if (p == MAP_FAILED) return fail("mmap");
    buffers_.push_back({p, buf.length});
    if (xioctl(fd_, VIDIOC_QBUF, &buf) < 0) return fail("VIDIOC_QBUF");
  }
  v4l2_buf_type type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
  if (xioctl(fd_, VIDIOC_STREAMON, &type) < 0) return fail("VIDIOC_STREAMON");
  error_.clear();
  return true;
}

void Webcam::close() {
  if (fd_ >= 0) {
    v4l2_buf_type type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    xioctl(fd_, VIDIOC_STREAMOFF, &type);
    for (auto& b : buffers_) munmap(b.start, b.length);
    ::close(fd_);
  }
  buffers_.clear();
  fd_ = -1;
}

std::optional<GrayImage> Webcam::grab() {
  if (fd_ < 0) return std::nullopt;
  std::optional<GrayImage> out;
  // Drain the queue so we always process the newest frame.
  for (;;) {
    v4l2_buffer buf{};
    buf.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    buf.memory = V4L2_MEMORY_MMAP;
    if (xioctl(fd_, VIDIOC_DQBUF, &buf) < 0) break;
    out = fromYUYV(static_cast<const uint8_t*>(buffers_[buf.index].start), width_, height_);
    xioctl(fd_, VIDIOC_QBUF, &buf);
  }
  return out;
}

}  // namespace so::live
