#include "image.h"

#include <algorithm>

namespace so {

GrayImage fromRGBA(const uint8_t* rgba, int width, int height) {
  GrayImage img(width, height);
  for (size_t i = 0, p = 0; i < img.data.size(); i++, p += 4)
    img.data[i] = (0.299f * rgba[p] + 0.587f * rgba[p + 1] + 0.114f * rgba[p + 2]) / 255.f;
  return img;
}

GrayImage fromYUYV(const uint8_t* yuyv, int width, int height) {
  // Luma is every other byte.
  GrayImage img(width, height);
  for (size_t i = 0; i < img.data.size(); i++) img.data[i] = yuyv[2 * i] / 255.f;
  return img;
}

GrayImage downsample(const GrayImage& src, int factor) {
  const int w = src.width / factor, h = src.height / factor;
  GrayImage out(w, h);
  const float norm = 1.f / (factor * factor);
  for (int y = 0; y < h; y++)
    for (int x = 0; x < w; x++) {
      float s = 0;
      for (int dy = 0; dy < factor; dy++)
        for (int dx = 0; dx < factor; dx++) s += src.at(x * factor + dx, y * factor + dy);
      out.at(x, y) = s * norm;
    }
  return out;
}

GrayImage resizeArea(const GrayImage& src, int width, int height) {
  GrayImage out(width, height);
  const float sx = static_cast<float>(src.width) / width;
  const float sy = static_cast<float>(src.height) / height;
  for (int y = 0; y < height; y++) {
    const int y0 = static_cast<int>(y * sy), y1 = std::max(y0 + 1, static_cast<int>((y + 1) * sy));
    for (int x = 0; x < width; x++) {
      const int x0 = static_cast<int>(x * sx), x1 = std::max(x0 + 1, static_cast<int>((x + 1) * sx));
      float s = 0;
      for (int yy = y0; yy < y1; yy++)
        for (int xx = x0; xx < x1; xx++) s += src.at(xx, yy);
      out.at(x, y) = s / ((x1 - x0) * (y1 - y0));
    }
  }
  return out;
}

GrayImage blur(const GrayImage& src) {
  const int w = src.width, h = src.height;
  static const float k[5] = {1 / 16.f, 4 / 16.f, 6 / 16.f, 4 / 16.f, 1 / 16.f};
  GrayImage tmp(w, h), out(w, h);
  for (int y = 0; y < h; y++)
    for (int x = 0; x < w; x++) {
      float s = 0;
      for (int i = -2; i <= 2; i++) s += k[i + 2] * src.at(std::clamp(x + i, 0, w - 1), y);
      tmp.at(x, y) = s;
    }
  for (int y = 0; y < h; y++)
    for (int x = 0; x < w; x++) {
      float s = 0;
      for (int i = -2; i <= 2; i++) s += k[i + 2] * tmp.at(x, std::clamp(y + i, 0, h - 1));
      out.at(x, y) = s;
    }
  return out;
}

float sample(const GrayImage& img, float x, float y) {
  const int w = img.width, h = img.height;
  x = std::clamp(x, 0.f, w - 1.001f);
  y = std::clamp(y, 0.f, h - 1.001f);
  const int x0 = static_cast<int>(x), y0 = static_cast<int>(y);
  const float fx = x - x0, fy = y - y0;
  const float* d = img.data.data() + static_cast<size_t>(y0) * w + x0;
  const float a = d[0] + (d[1] - d[0]) * fx;
  const float b = d[w] + (d[w + 1] - d[w]) * fx;
  return a + (b - a) * fy;
}

}  // namespace so
