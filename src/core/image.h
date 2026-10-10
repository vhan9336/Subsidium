#pragma once
#include <cstdint>
#include <vector>

namespace so {

// Grayscale float image, row-major, values roughly in [0, 1].
struct GrayImage {
  int width = 0;
  int height = 0;
  std::vector<float> data;

  GrayImage() = default;
  GrayImage(int w, int h) : width(w), height(h), data(static_cast<size_t>(w) * h, 0.f) {}
  float& at(int x, int y) { return data[static_cast<size_t>(y) * width + x]; }
  float at(int x, int y) const { return data[static_cast<size_t>(y) * width + x]; }
  bool empty() const { return data.empty(); }
};

GrayImage fromRGBA(const uint8_t* rgba, int width, int height);
GrayImage fromYUYV(const uint8_t* yuyv, int width, int height);
// Box-filter downsample by an integer factor.
GrayImage downsample(const GrayImage& src, int factor);
// Resize to an exact size with box averaging (for webcam frames of any size).
GrayImage resizeArea(const GrayImage& src, int width, int height);
// Separable 5-tap binomial blur (sigma ~ 1).
GrayImage blur(const GrayImage& src);
// Bilinear sample with edge clamping.
float sample(const GrayImage& img, float x, float y);

}  // namespace so
