#pragma once
#include <optional>
#include <string>
#include <vector>

#include "core/image.h"

namespace so::live {

// Video4Linux2 capture (YUYV), luma only.
class Webcam {
 public:
  ~Webcam() { close(); }
  bool open(const std::string& device, int width = 320, int height = 240);
  void close();
  bool isOpen() const { return fd_ >= 0; }
  // Newest frame since the last call, converted to grayscale.
  std::optional<GrayImage> grab();
  const std::string& error() const { return error_; }
  int width() const { return width_; }
  int height() const { return height_; }

 private:
  int fd_ = -1;
  int width_ = 0, height_ = 0;
  struct Buffer {
    void* start;
    size_t length;
  };
  std::vector<Buffer> buffers_;
  std::string error_;
};

}  // namespace so::live
